"""Registry, runtime state, and event helpers for dashboard projects."""

from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from autopilot.core.capability_store import (
    DEFAULT_CONNECTORS,
    DEFAULT_SKILL_PACKS,
    enrich_story_plan,
    load_connectors_registry,
    load_routing_policies_registry,
    load_skill_packs_registry,
    normalize_launch_profile,
    normalize_phase_plan,
    normalize_review_phases,
    normalize_story_pipeline,
    resolve_story_runtime_plan,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.cost_accounting import default_cost_usage, ensure_cost_state
from autopilot.core.github_prs import normalize_story_github_pr
from autopilot.core.loop_runner import apply_autopilot_ralph_overrides, check_ralph_installed, init_ralph_project
from autopilot.core.models import normalize_story_blocked_by, resolve_story_blocked_on, validate_story_dependencies
from autopilot.core.runtime_agents import build_story_pipeline_state
from autopilot.core.runtime_budgets import default_budget_policy, default_budget_usage, ensure_budget_state, update_budget_policy

TIMELINE_LIMIT = 300
DISCOVERY_BOARD_LIMIT = 200
TERMINAL_STORY_STATUSES = {"done", "skipped", "stuck", "merge_blocked"}
PLACEHOLDER_ISSUE_PATTERN = re.compile(
    r"^-\s*(?:Issue\s+\d+:\s*specific description|<[^>]+>|concrete issue\b.*|second concrete issue\b.*)\s*$",
    re.IGNORECASE,
)
DISCOVERY_SECTION_PATTERN = re.compile(r"^#{1,3}\s*(warnings?|constraints?|intents?|notes?)\s*:?\s*$", re.IGNORECASE)
DISCOVERY_PREFIX_PATTERN = re.compile(r"^(warning|constraint|intent|note)s?\s*:\s*(.+)$", re.IGNORECASE)
DISCOVERY_KIND_ALIASES = {
    "warning": "warning",
    "warnings": "warning",
    "constraint": "constraint",
    "constraints": "constraint",
    "intent": "intent",
    "intents": "intent",
    "note": "note",
    "notes": "note",
}


def utcnow_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def default_quality_policy() -> dict[str, Any]:
    """Return the default quality-ratcheting policy for one project."""

    return {
        "regression_mode": "retry",
        "auto_revert": False,
    }


def slugify_project_name(name: str) -> str:
    """Convert a project name into a safe filesystem slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _atomic_write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(contents)
    temp_path.replace(path)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    _atomic_write_text(path, yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"projects": []}
    return yaml.safe_load(path.read_text()) or {"projects": []}


def _read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text())


def _ps_output(*args: str) -> str:
    result = subprocess.run(
        ["ps", *args],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _is_temp_project_path(project_path: str) -> bool:
    return project_path.startswith("/tmp/") or project_path.startswith("/private/tmp/")


def _sanitize_message(message: str, *, max_len: int = 1200) -> str:
    if not message:
        return ""

    lines = [line.strip() for line in message.splitlines() if line.strip()]
    needs_work_indexes = [index for index, line in enumerate(lines) if "NEEDS_WORK" in line.upper()]
    search_space = lines[needs_work_indexes[-1] + 1 :] if needs_work_indexes else lines
    issue_lines: list[str] = []
    for line in search_space:
        if re.match(r"^-\s*Issue\b", line, flags=re.IGNORECASE):
            if PLACEHOLDER_ISSUE_PATTERN.match(line):
                continue
            issue_lines.append(line)
            continue
        if issue_lines:
            break
    if issue_lines:
        deduped: list[str] = []
        for issue in issue_lines:
            if issue not in deduped:
                deduped.append(issue)
        return "\n".join(deduped[:6])

    if needs_work_indexes:
        cleaned_lines = [
            line
            for line in search_space
            if line
            and line.upper() != "NEEDS_WORK"
            and not PLACEHOLDER_ISSUE_PATTERN.match(line)
        ]
        if cleaned_lines:
            cleaned = "\n".join(cleaned_lines[:6])
            if len(cleaned) <= max_len:
                return cleaned
            return cleaned[: max_len - 1].rstrip() + "…"
        return "Critic returned NEEDS_WORK without actionable issues."

    cleaned = message.strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _normalize_story_id(value: Any, fallback: int, seen_ids: set[int]) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = fallback

    if candidate in seen_ids:
        candidate = fallback
    seen_ids.add(candidate)
    return candidate


def normalize_discovery_kind(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    return DISCOVERY_KIND_ALIASES.get(normalized, "note")


def build_discovery_marker(
    *,
    story_id: int | None,
    source: str,
    kind: str,
    detail: str,
    title: str | None = None,
    created_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cleaned_detail = str(detail or "").strip()
    if not cleaned_detail:
        return None
    cleaned_title = str(title or "").strip() or cleaned_detail.splitlines()[0]
    return {
        "id": f"discovery-{uuid.uuid4().hex[:10]}",
        "story_id": story_id,
        "source": str(source or "runtime").strip() or "runtime",
        "kind": normalize_discovery_kind(kind),
        "title": cleaned_title[:120],
        "detail": cleaned_detail[:2000],
        "status": "active",
        "created_at": created_at or utcnow_iso(),
        "updated_at": created_at or utcnow_iso(),
        "metadata": dict(metadata or {}),
    }


def extract_structured_discoveries(
    text: str,
    *,
    story_id: int | None,
    source: str,
    created_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Extract structured discovery markers from markdown-like notes."""

    markers: list[dict[str, Any]] = []
    seen: set[tuple[int | None, str, str, str]] = set()
    current_kind: str | None = None
    timestamp = created_at or utcnow_iso()

    def append_marker(kind: str, detail: str) -> None:
        marker = build_discovery_marker(
            story_id=story_id,
            source=source,
            kind=kind,
            detail=detail,
            created_at=timestamp,
            metadata=metadata,
        )
        if marker is None:
            return
        fingerprint = (
            marker.get("story_id"),
            str(marker.get("source") or ""),
            str(marker.get("kind") or ""),
            str(marker.get("detail") or "").lower(),
        )
        if fingerprint in seen:
            return
        seen.add(fingerprint)
        markers.append(marker)

    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        section_match = DISCOVERY_SECTION_PATTERN.match(line)
        if section_match:
            current_kind = normalize_discovery_kind(section_match.group(1))
            continue
        prefixed_match = DISCOVERY_PREFIX_PATTERN.match(line)
        if prefixed_match:
            current_kind = normalize_discovery_kind(prefixed_match.group(1))
            append_marker(current_kind, prefixed_match.group(2).strip())
            continue
        if line.startswith(("-", "*")) and current_kind:
            append_marker(current_kind, line[1:].strip())

    return markers


def _discovery_fingerprint(marker: dict[str, Any]) -> tuple[int | None, str, str, str]:
    return (
        marker.get("story_id"),
        str(marker.get("source") or ""),
        str(marker.get("kind") or ""),
        str(marker.get("detail") or "").strip().lower(),
    )


def record_discovery_markers(
    config: AutopilotConfig,
    project_id: str,
    markers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist structured discovery markers and deduplicate stable repeats."""

    if not markers:
        return []

    state = load_project_state(config, project_id)
    if not state:
        return []

    discoveries = list(state.setdefault("discoveries", []))
    existing_index = {_discovery_fingerprint(marker): index for index, marker in enumerate(discoveries)}
    recorded: list[dict[str, Any]] = []

    for marker in markers:
        fingerprint = _discovery_fingerprint(marker)
        existing_index_for_marker = existing_index.get(fingerprint)
        if existing_index_for_marker is not None:
            current = dict(discoveries[existing_index_for_marker])
            current["updated_at"] = marker.get("updated_at") or marker.get("created_at") or utcnow_iso()
            current["metadata"] = {
                **dict(current.get("metadata") or {}),
                **dict(marker.get("metadata") or {}),
            }
            discoveries[existing_index_for_marker] = current
            recorded.append(current)
            continue

        discoveries.append(marker)
        existing_index[fingerprint] = len(discoveries) - 1
        recorded.append(marker)

    state["discoveries"] = discoveries[-DISCOVERY_BOARD_LIMIT:]
    state["updated_at"] = utcnow_iso()
    save_project_state(config, project_id, state)
    return recorded


def build_story_discovery_context(
    state: dict[str, Any],
    *,
    story_id: int | None = None,
    limit: int = 24,
) -> list[dict[str, Any]]:
    """Return active discoveries relevant to one story."""

    discoveries = [
        dict(marker)
        for marker in state.get("discoveries", [])
        if str(marker.get("status") or "active") == "active"
    ]
    discoveries.sort(
        key=lambda marker: (
            str(marker.get("story_id") or ""),
            str(marker.get("updated_at") or marker.get("created_at") or ""),
            str(marker.get("kind") or ""),
        )
    )
    if story_id is not None:
        same_story = [marker for marker in discoveries if marker.get("story_id") == story_id]
        shared = [marker for marker in discoveries if marker.get("story_id") != story_id]
        discoveries = shared + same_story
    return discoveries[-limit:]


def normalize_prd(prd: dict[str, Any], *, seed_mode: str = "new") -> dict[str, Any]:
    """Normalize PRD stories while keeping runtime state out of the document."""
    title = str(prd.get("title") or "Untitled Project").strip()
    description = str(prd.get("description") or "").strip()
    stories = prd.get("stories") or []

    normalized_stories: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for index, story in enumerate(stories, start=1):
        story_id = _normalize_story_id(story.get("id"), index, seen_ids)
        incoming_status = str(story.get("status") or "open")
        if seed_mode == "migrate" and incoming_status in {"done", "skipped"}:
            status = incoming_status
        else:
            status = "open"

        phase_id = str(story.get("phase_id") or "").strip() or None
        phase_title = str(story.get("phase_title") or "").strip() or None
        phase_goal = str(story.get("phase_goal") or "").strip() or ""
        raw_pipeline = story.get("pipeline") if "pipeline" in story else story.get("story_pipeline") if "story_pipeline" in story else None
        normalized_pipeline = (
            []
            if raw_pipeline in (None, "") or (isinstance(raw_pipeline, list) and len(raw_pipeline) == 0)
            else normalize_story_pipeline(raw_pipeline)
        )
        raw_review_phases = story.get("review_phases")
        normalized_review_phases = (
            []
            if raw_review_phases in (None, "") or (isinstance(raw_review_phases, list) and len(raw_review_phases) == 0)
            else normalize_review_phases(raw_review_phases)
        )
        normalized_story = enrich_story_plan(
            {
                "id": story_id,
                "title": str(story.get("title") or f"Story {index}").strip(),
                "description": str(story.get("description") or "").strip(),
                "position": index - 1,
                "status": status,
                "phase_id": phase_id,
                "phase_title": phase_title,
                "phase_goal": phase_goal,
                "acceptance_criteria": story.get("acceptance_criteria") or [],
                "blocked_by": normalize_story_blocked_by(story.get("blocked_by"), story_id=story_id),
                "pipeline": normalized_pipeline,
                "review_phases": normalized_review_phases,
                "tags": story.get("tags") or [],
                "role": story.get("role"),
                "skill_packs": story.get("skill_packs") or [],
                "connectors": story.get("connectors") or [],
            },
            skill_packs=list(DEFAULT_SKILL_PACKS),
            connectors=list(DEFAULT_CONNECTORS),
        )
        normalized_stories.append(normalized_story)

    phases = normalize_phase_plan(prd, normalized_stories)
    phases_by_id = {phase["id"]: phase for phase in phases}
    if phases:
        fallback_phase = phases[0]
        for story in normalized_stories:
            phase_id = str(story.get("phase_id") or "").strip() or fallback_phase["id"]
            phase = phases_by_id.get(phase_id, fallback_phase)
            story["phase_id"] = phase["id"]
            story["phase_title"] = phase["title"]
            story["phase_goal"] = story.get("phase_goal") or phase.get("goal") or ""

    dependency_graph = validate_story_dependencies(normalized_stories)
    for story in normalized_stories:
        story["blocked_by"] = dependency_graph[story["id"]]

    return {
        "title": title,
        "description": description,
        "phases": phases,
        "stories": normalized_stories,
    }


def _generate_project_id(existing_ids: set[str], project_name: str) -> str:
    base = slugify_project_name(project_name)[:32]
    while True:
        candidate = f"{base}-{uuid.uuid4().hex[:8]}"
        if candidate not in existing_ids:
            return candidate


def migrate_projects_registry(config: AutopilotConfig) -> list[dict[str, Any]]:
    """Migrate projects.yaml into the new id-based registry shape."""
    data = _read_yaml(config.projects_yaml_path)
    projects = data.setdefault("projects", [])

    changed = False
    now = utcnow_iso()
    existing_ids = {str(project.get("id")) for project in projects if project.get("id")}

    for project in projects:
        if not project.get("id"):
            project["id"] = _generate_project_id(existing_ids, str(project.get("name") or "project"))
            existing_ids.add(project["id"])
            changed = True

        if "priority" not in project:
            project["priority"] = "normal"
            changed = True
        if "prd" not in project:
            project["prd"] = ".agents/tasks/prd.json"
            changed = True
        if "archived" not in project:
            project["archived"] = _is_temp_project_path(str(project.get("path") or ""))
            changed = True
        if "tracker_refs" not in project:
            project["tracker_refs"] = []
            changed = True
        if "created_at" not in project:
            project["created_at"] = now
            changed = True
        if "last_opened_at" not in project:
            project["last_opened_at"] = None
            changed = True

    if changed:
        _atomic_write_yaml(config.projects_yaml_path, data)

    return projects


def load_projects_registry(
    config: AutopilotConfig,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    projects = migrate_projects_registry(config)
    if include_archived:
        return projects
    return [project for project in projects if not project.get("archived", False)]


def save_projects_registry(config: AutopilotConfig, projects: list[dict[str, Any]]) -> None:
    _atomic_write_yaml(config.projects_yaml_path, {"projects": projects})


def get_project_entry(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    project_path: Path | None = None,
    include_archived: bool = True,
) -> dict[str, Any] | None:
    projects = load_projects_registry(config, include_archived=include_archived)
    for project in projects:
        if project_id and project.get("id") == project_id:
            return project
        if project_path and Path(project["path"]).expanduser().resolve() == project_path.expanduser().resolve():
            return project
    return None


def update_project_entry(config: AutopilotConfig, updated_project: dict[str, Any]) -> dict[str, Any]:
    projects = migrate_projects_registry(config)
    for index, project in enumerate(projects):
        if project["id"] == updated_project["id"]:
            projects[index] = updated_project
            save_projects_registry(config, projects)
            return updated_project
    raise KeyError(updated_project["id"])


def normalize_tracker_reference(
    *,
    provider: str,
    kind: str,
    external_id: str,
    title: str = "",
    url: str = "",
    event: str = "",
    repository: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = dict(repository or {})
    repo_name = str(repo.get("full_name") or repo.get("name") or "").strip()
    return {
        "provider": str(provider or "").strip().lower(),
        "kind": str(kind or "").strip().lower(),
        "external_id": str(external_id or "").strip(),
        "title": str(title or "").strip(),
        "url": str(url or "").strip(),
        "event": str(event or "").strip().lower(),
        "repository": {
            "id": repo.get("id"),
            "name": repo.get("name"),
            "full_name": repo_name,
            "url": repo.get("html_url") or repo.get("url") or "",
        },
        "metadata": dict(metadata or {}),
        "linked_at": utcnow_iso(),
    }


def _tracker_reference_key(reference: dict[str, Any]) -> tuple[str, str, str, str]:
    repository = reference.get("repository") or {}
    return (
        str(reference.get("provider") or "").strip().lower(),
        str(reference.get("kind") or "").strip().lower(),
        str(repository.get("full_name") or "").strip().lower(),
        str(reference.get("external_id") or "").strip(),
    )


def find_project_by_tracker_reference(config: AutopilotConfig, reference: dict[str, Any]) -> dict[str, Any] | None:
    for project in load_projects_registry(config, include_archived=True):
        for tracker_ref in project.get("tracker_refs", []):
            if _tracker_reference_key(tracker_ref) == _tracker_reference_key(reference):
                return project
    return None


def attach_tracker_reference(config: AutopilotConfig, project_id: str, reference: dict[str, Any]) -> dict[str, Any]:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    tracker_refs = list(project.get("tracker_refs") or [])
    reference_key = _tracker_reference_key(reference)
    updated = False
    for index, tracker_ref in enumerate(tracker_refs):
        if _tracker_reference_key(tracker_ref) != reference_key:
            continue
        tracker_refs[index] = {
            **dict(tracker_ref),
            **dict(reference),
            "linked_at": tracker_ref.get("linked_at") or reference.get("linked_at") or utcnow_iso(),
        }
        updated = True
        break
    if not updated:
        tracker_refs.append(reference)

    project["tracker_refs"] = tracker_refs
    update_project_entry(config, project)
    return project


def register_project(
    config: AutopilotConfig,
    *,
    name: str,
    project_path: Path,
    prd_relpath: str = ".agents/tasks/prd.json",
    priority: str = "normal",
) -> dict[str, Any]:
    projects = migrate_projects_registry(config)
    existing_names = {str(project["name"]) for project in projects}
    existing_ids = {str(project["id"]) for project in projects}
    created_at = utcnow_iso()

    final_name = name
    if final_name in existing_names:
        index = 2
        while f"{name} {index}" in existing_names:
            index += 1
        final_name = f"{name} {index}"

    existing = get_project_entry(config, project_path=project_path, include_archived=True)
    if existing is not None:
        existing.update(
            {
                "name": final_name,
                "path": str(project_path),
                "priority": priority,
                "prd": prd_relpath,
                "archived": False,
                "last_opened_at": existing.get("last_opened_at"),
            }
        )
        update_project_entry(config, existing)
        return existing

    project = {
        "id": _generate_project_id(existing_ids, final_name),
        "name": final_name,
        "path": str(project_path),
        "priority": priority,
        "prd": prd_relpath,
        "archived": False,
        "tracker_refs": [],
        "created_at": created_at,
        "last_opened_at": None,
    }
    projects.append(project)
    save_projects_registry(config, projects)
    return project


def project_state_path(config: AutopilotConfig, project_id: str) -> Path:
    return config.runtime_state_dir / f"{project_id}.json"


def _story_state_from_definition(story: dict[str, Any]) -> dict[str, Any]:
    return {
        "story_id": story["id"],
        "position": story["position"],
        "status": story["status"],
        "blocked_by": list(story.get("blocked_by") or []),
        "blocked_on": [],
        "started_at": None,
        "completed_at": None,
        "updated_at": utcnow_iso(),
        "iteration": 0,
        "agent": None,
        "critic": None,
        "last_error": None,
        "requeue_count": 0,
        "team_mode": "solo",
        "team_members": [],
        "story_pipeline": list(story.get("pipeline") or []),
        "review_phases": list(story.get("review_phases") or []),
        "pipeline_state": [],
        "connector_activation": [],
        "activation_errors": [],
        "worktree_path": None,
        "branch_name": None,
        "ownership": None,
        "checkout": None,
        "github_pr": {},
    }


def _requeue_interrupted_stories(state: dict[str, Any], fallback_error: str) -> bool:
    changed = False
    for story_state in state.get("story_state", {}).values():
        if story_state.get("status") != "in_progress":
            continue
        story_state["status"] = "open"
        story_state["started_at"] = None
        story_state["completed_at"] = None
        story_state["updated_at"] = utcnow_iso()
        story_state["agent"] = None
        story_state["critic"] = None
        story_state["last_error"] = _sanitize_message(story_state.get("last_error") or fallback_error)
        story_state["team_mode"] = state.get("launch_profile", {}).get("story_execution_mode", "solo")
        story_state["team_members"] = []
        story_state["pipeline_state"] = []
        story_state["connector_activation"] = []
        story_state["activation_errors"] = []
        story_state["worktree_path"] = None
        story_state["branch_name"] = None
        story_state["ownership"] = None
        story_state["checkout"] = None
        changed = True

    if changed:
        state["current_story_id"] = None
        state["current_iteration"] = 0
        state["active_worker"] = None
        state["active_critic"] = None
        state["finished_at"] = state.get("finished_at") or utcnow_iso()
    return changed


def _default_runtime_state(project_id: str, prd: dict[str, Any]) -> dict[str, Any]:
    timeline: list[dict[str, Any]] = []
    return {
        "project_id": project_id,
        "pid": None,
        "status": "idle",
        "paused": False,
        "current_story_id": None,
        "current_iteration": 0,
        "active_worker": None,
        "active_critic": None,
        "started_at": None,
        "updated_at": utcnow_iso(),
        "finished_at": None,
        "last_error": None,
        "log_path": "",
        "launch_profile": normalize_launch_profile().model_dump(),
        "activation_errors": [],
        "parallel_story_ids": [],
        "budget_policy": default_budget_policy(),
        "budget_usage": default_budget_usage(),
        "cost_usage": default_cost_usage(),
        "discoveries": [],
        "story_state": {
            str(story["id"]): _story_state_from_definition(story) for story in prd.get("stories", [])
        },
        "timeline": timeline,
    }


def _sync_story_dependencies(prd: dict[str, Any], state: dict[str, Any]) -> bool:
    changed = False
    story_state = state.get("story_state", {})
    for story in prd.get("stories", []):
        runtime = story_state.get(str(story["id"]))
        if runtime is None:
            continue
        blocked_by = list(story.get("blocked_by") or [])
        if runtime.get("blocked_by") != blocked_by:
            runtime["blocked_by"] = blocked_by
            changed = True
        blocked_on = [] if runtime.get("status") in {"done", "skipped"} else resolve_story_blocked_on(blocked_by, story_state)
        if runtime.get("blocked_on") != blocked_on:
            runtime["blocked_on"] = blocked_on
            changed = True
    return changed


def load_project_prd(project: dict[str, Any], *, seed_mode: str = "migrate") -> dict[str, Any]:
    prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
    if not prd_path.exists():
        return {"title": project["name"], "description": "", "stories": []}

    try:
        data = json.loads(prd_path.read_text())
    except Exception:
        return {"title": project["name"], "description": "", "stories": []}
    return normalize_prd(data, seed_mode=seed_mode)


def save_project_prd(project: dict[str, Any], prd: dict[str, Any]) -> Path:
    prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
    _atomic_write_json(prd_path, prd)
    return prd_path


def ensure_project_state(
    config: AutopilotConfig,
    project: dict[str, Any],
    *,
    seed_mode: str = "migrate",
) -> dict[str, Any]:
    prd = load_project_prd(project, seed_mode=seed_mode)
    state_path = project_state_path(config, project["id"])
    changed = False

    if state_path.exists():
        state = _read_json(state_path, {})
    else:
        state = _default_runtime_state(project["id"], prd)
        changed = True

    state.setdefault("project_id", project["id"])
    state.setdefault("pid", None)
    state.setdefault("status", "idle")
    state.setdefault("paused", False)
    state.setdefault("current_story_id", None)
    state.setdefault("current_iteration", 0)
    state.setdefault("active_worker", None)
    state.setdefault("active_critic", None)
    state.setdefault("started_at", None)
    state.setdefault("updated_at", utcnow_iso())
    state.setdefault("finished_at", None)
    state.setdefault("last_error", None)
    state.setdefault("log_path", "")
    state.setdefault("launch_profile", normalize_launch_profile().model_dump())
    state.setdefault("activation_errors", [])
    state.setdefault("parallel_story_ids", [])
    state.setdefault("budget_policy", default_budget_policy())
    state.setdefault("budget_usage", default_budget_usage())
    state.setdefault("quality_policy", default_quality_policy())
    state.setdefault("cost_usage", default_cost_usage())
    state.setdefault("discoveries", [])
    state.setdefault("timeline", [])
    state.setdefault("story_state", {})
    ensure_budget_state(state)
    ensure_cost_state(state)

    synchronized_story_state: dict[str, Any] = {}
    for story in prd.get("stories", []):
        key = str(story["id"])
        current = state["story_state"].get(key)
        if current is None:
            current = _story_state_from_definition(story)
            changed = True
        current.setdefault("story_id", story["id"])
        current["position"] = story["position"]
        current.setdefault("status", story["status"])
        current.setdefault("blocked_by", list(story.get("blocked_by") or []))
        current.setdefault("blocked_on", [])
        current.setdefault("started_at", None)
        current.setdefault("completed_at", None)
        current.setdefault("updated_at", utcnow_iso())
        current.setdefault("iteration", 0)
        current.setdefault("agent", None)
        current.setdefault("critic", None)
        current.setdefault("last_error", None)
        current.setdefault("requeue_count", 0)
        current.setdefault("team_mode", "solo")
        current.setdefault("team_members", [])
        current.setdefault("story_pipeline", list(story.get("pipeline") or []))
        current.setdefault("review_phases", list(story.get("review_phases") or []))
        current.setdefault("pipeline_state", [])
        current.setdefault("connector_activation", [])
        current.setdefault("activation_errors", [])
        current.setdefault("worktree_path", None)
        current.setdefault("branch_name", None)
        current.setdefault("ownership", None)
        current.setdefault("checkout", None)
        if not current.get("story_pipeline"):
            current["story_pipeline"] = list(story.get("pipeline") or [])
        if not current.get("review_phases"):
            current["review_phases"] = list(story.get("review_phases") or [])
        if not current.get("pipeline_state") and current.get("story_pipeline"):
            current["pipeline_state"] = build_story_pipeline_state(
                current.get("story_pipeline"),
                current.get("team_members") or [],
            )
        current["github_pr"] = normalize_story_github_pr(
            project["name"],
            story,
            existing=current.get("github_pr") or {},
        )
        synchronized_story_state[key] = current
    if synchronized_story_state != state["story_state"]:
        state["story_state"] = synchronized_story_state
        changed = True
    if _sync_story_dependencies(prd, state):
        changed = True

    if state.get("pid") and not _is_pid_running(state["pid"]):
        state["pid"] = None
        state["active_worker"] = None
        state["active_critic"] = None
        if state.get("status") == "running" and not state.get("paused"):
            interruption_error = _sanitize_message(
                state.get("last_error") or "Background run stopped unexpectedly."
            )
            has_active_story = state.get("current_story_id") is not None or any(
                story_state.get("status") == "in_progress" for story_state in state["story_state"].values()
            )
            if has_active_story:
                state["status"] = "failed"
                state["last_error"] = interruption_error
                if _requeue_interrupted_stories(state, interruption_error):
                    changed = True
        changed = True

    if (
        state.get("pid") is None
        and not state.get("paused")
        and state.get("status") == "failed"
    ):
        failure_error = _sanitize_message(state.get("last_error") or "Background run stopped unexpectedly.")
        if _requeue_interrupted_stories(state, failure_error):
            state["last_error"] = failure_error
            changed = True

    if all(story["status"] in {"done", "skipped"} for story in state["story_state"].values()) and state["story_state"]:
        state["status"] = "completed"
        state["finished_at"] = state["finished_at"] or utcnow_iso()
        changed = True

    if changed:
        save_project_state(config, project["id"], state)

    return state


def load_project_state(config: AutopilotConfig, project_id: str) -> dict[str, Any]:
    return _read_json(project_state_path(config, project_id), {})


def save_project_state(config: AutopilotConfig, project_id: str, state: dict[str, Any]) -> None:
    state["updated_at"] = utcnow_iso()
    _atomic_write_json(project_state_path(config, project_id), state)


def _append_event_log(config: AutopilotConfig, event_record: dict[str, Any]) -> None:
    path = config.events_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event_record, ensure_ascii=False) + "\n")


def emit_project_event(
    config: AutopilotConfig,
    project_id: str,
    *,
    event: str,
    status: str,
    message: str,
    story_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_project_state(config, project_id)
    if not state:
        return {}

    event_record = {
        "event": event,
        "project_id": project_id,
        "story_id": story_id,
        "status": status,
        "message": _sanitize_message(message),
        "timestamp": utcnow_iso(),
    }
    if extra:
        event_record.update(extra)

    timeline = state.setdefault("timeline", [])
    timeline.append(event_record)
    state["timeline"] = timeline[-TIMELINE_LIMIT:]
    state["updated_at"] = event_record["timestamp"]
    if event in {"worker_failed", "story_gate_failed", "critic_rejected", "story_stuck", "run_failed"}:
        state["last_error"] = message
    if story_id is not None:
        story_state = state.setdefault("story_state", {}).get(str(story_id))
        if story_state is not None:
            story_state["updated_at"] = event_record["timestamp"]
            if event in {"worker_failed", "story_gate_failed", "critic_rejected", "story_stuck"}:
                story_state["last_error"] = message
    save_project_state(config, project_id, state)
    _append_event_log(config, event_record)
    try:
        from autopilot.core.run_trace import append_trace_entry

        append_trace_entry(
            config,
            project_id,
            {
                "kind": "project_event",
                **event_record,
            },
        )
    except Exception:
        pass
    # Runtime issue synchronization is best-effort: execution must not fail because control-plane issue
    # bookkeeping could not be updated.
    try:
        from autopilot.core.control_plane_issues import sync_runtime_issue_from_event

        sync_runtime_issue_from_event(config, event_record)
    except Exception:
        pass
    try:
        from autopilot.core.notifiers import dispatch_project_event_notification

        project_entry = get_project_entry(config, project_id=project_id, include_archived=True)
        if project_entry is not None:
            prd = load_project_prd(project_entry, seed_mode="migrate")
            story_title = None
            if story_id is not None:
                story_title = next(
                    (
                        str(story.get("title") or f"Story {story_id}")
                        for story in prd.get("stories", [])
                        if story.get("id") == story_id
                    ),
                    f"Story {story_id}",
                )
            dispatch_project_event_notification(
                config,
                project_entry=project_entry,
                state=state,
                event_record=event_record,
                story_title=story_title,
            )
    except Exception:
        pass
    return event_record


def update_project_runtime(
    config: AutopilotConfig,
    project_id: str,
    **fields: Any,
) -> dict[str, Any]:
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)
    state.update(fields)
    save_project_state(config, project_id, state)
    return state


def update_story_runtime(
    config: AutopilotConfig,
    project_id: str,
    story_id: int,
    **fields: Any,
) -> dict[str, Any]:
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)

    story_state = state.setdefault("story_state", {}).get(str(story_id))
    if story_state is None:
        raise KeyError(story_id)

    story_state.update(fields)
    story_state["updated_at"] = utcnow_iso()
    save_project_state(config, project_id, state)
    return story_state


def requeue_recoverable_stuck_stories(config: AutopilotConfig, project_id: str) -> list[int]:
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)

    story_state = state.get("story_state", {})
    done_timestamps = [
        datetime.fromisoformat(str(entry["updated_at"]).replace("Z", "+00:00"))
        for entry in story_state.values()
        if entry.get("status") == "done" and entry.get("updated_at")
    ]
    if not done_timestamps:
        return []

    latest_done = max(done_timestamps)
    reopened: list[int] = []
    for entry in story_state.values():
        if entry.get("status") != "stuck":
            continue
        if int(entry.get("requeue_count", 0)) >= 1:
            continue
        updated_at = entry.get("updated_at")
        if not updated_at:
            continue
        stuck_updated = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
        if stuck_updated >= latest_done:
            continue
        entry["status"] = "open"
        entry["started_at"] = None
        entry["completed_at"] = None
        entry["updated_at"] = utcnow_iso()
        entry["iteration"] = 0
        entry["agent"] = None
        entry["critic"] = None
        entry["last_error"] = None
        entry["requeue_count"] = int(entry.get("requeue_count", 0)) + 1
        entry["team_mode"] = state.get("launch_profile", {}).get("story_execution_mode", "solo")
        entry["team_members"] = []
        entry["connector_activation"] = []
        entry["activation_errors"] = []
        entry["worktree_path"] = None
        entry["branch_name"] = None
        entry["ownership"] = None
        entry["checkout"] = None
        reopened.append(int(entry["story_id"]))

    if not reopened:
        return []

    state["status"] = "running"
    state["finished_at"] = None
    state["last_error"] = None
    state["current_story_id"] = None
    state["current_iteration"] = 0
    state["active_worker"] = None
    state["active_critic"] = None
    save_project_state(config, project_id, state)
    return reopened


def _resolve_story_runtime_metadata(
    config: AutopilotConfig,
    state: dict[str, Any],
    story: dict[str, Any],
    runtime: dict[str, Any],
) -> dict[str, Any]:
    launch_profile = normalize_launch_profile(state.get("launch_profile"))
    team_mode = runtime.get("team_mode")
    team_members = runtime.get("team_members") or []
    story_pipeline = runtime.get("story_pipeline") or []
    review_phases = runtime.get("review_phases") or []
    pipeline_state = runtime.get("pipeline_state") or []
    connector_activation = runtime.get("connector_activation") or []
    activation_errors = runtime.get("activation_errors") or []
    has_runtime_plan = bool(
        team_members
        or connector_activation
        or activation_errors
        or runtime.get("worktree_path")
        or runtime.get("branch_name")
        or (team_mode not in {None, "", "solo"})
    )
    if has_runtime_plan:
        return {
            "team_mode": team_mode or launch_profile.story_execution_mode,
            "team_members": team_members,
            "story_pipeline": story_pipeline,
            "review_phases": review_phases or list(story.get("review_phases") or []),
            "pipeline_state": pipeline_state,
            "connector_activation": connector_activation,
            "activation_errors": activation_errors,
        }

    resolved = resolve_story_runtime_plan(
        story,
        launch_profile=launch_profile,
        provider=launch_profile.provider,
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        routing_policies=load_routing_policies_registry(config),
    )
    return {
        "team_mode": resolved["team_mode"],
        "team_members": runtime.get("team_members") or resolved["team_members"],
        "story_pipeline": resolved["story_pipeline"],
        "review_phases": runtime.get("review_phases") or resolved.get("review_phases") or [],
        "pipeline_state": runtime.get("pipeline_state")
        or build_story_pipeline_state(
            resolved["story_pipeline"],
            runtime.get("team_members") or resolved["team_members"],
        ),
        "connector_activation": runtime.get("connector_activation") or resolved["active_connectors"],
        "activation_errors": runtime.get("activation_errors") or resolved["activation_errors"],
    }


def merge_project_stories(
    config: AutopilotConfig,
    project: dict[str, Any],
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    prd = load_project_prd(project, seed_mode="migrate")
    merged: list[dict[str, Any]] = []
    for story in prd.get("stories", []):
        runtime = state.get("story_state", {}).get(str(story["id"]), {})
        runtime_metadata = _resolve_story_runtime_metadata(config, state, story, runtime)
        merged.append(
            {
                "id": story["id"],
                "title": story["title"],
                "description": story["description"],
                "position": story["position"],
                "phase_id": story.get("phase_id"),
                "phase_title": story.get("phase_title"),
                "phase_goal": story.get("phase_goal"),
                "tags": story.get("tags", []),
                "role": story.get("role"),
                "skill_packs": story.get("skill_packs", []),
                "connectors": story.get("connectors", []),
                "required_connectors": story.get("required_connectors", []),
                "preferred_connectors": story.get("preferred_connectors", []),
                "forbidden_connectors": story.get("forbidden_connectors", []),
                "acceptance_criteria": story.get("acceptance_criteria", []),
                "blocked_by": runtime.get("blocked_by", story.get("blocked_by", [])),
                "blocked_on": runtime.get("blocked_on", []),
                "status": runtime.get("status", "open"),
                "started_at": runtime.get("started_at"),
                "completed_at": runtime.get("completed_at"),
                "updated_at": runtime.get("updated_at"),
                "iteration": runtime.get("iteration"),
                "agent": runtime.get("agent"),
                "critic": runtime.get("critic"),
                "last_error": _sanitize_message(runtime.get("last_error") or ""),
                "team_mode": runtime_metadata["team_mode"],
                "team_members": runtime_metadata["team_members"],
                "story_pipeline": runtime_metadata["story_pipeline"],
                "review_phases": runtime_metadata["review_phases"] or story.get("review_phases", []),
                "discoveries": build_story_discovery_context(state, story_id=int(story["id"])),
                "pipeline_state": runtime_metadata["pipeline_state"],
                "connector_activation": runtime_metadata["connector_activation"],
                "activation_errors": runtime_metadata["activation_errors"],
                "worktree_path": runtime.get("worktree_path"),
                "branch_name": runtime.get("branch_name"),
                "ownership": runtime.get("ownership"),
                "checkout": runtime.get("checkout"),
                "github_pr": runtime.get("github_pr") or normalize_story_github_pr(project["name"], story),
                "cost": dict(
                    (state.get("cost_usage", {}).get("stories") or {}).get(
                        str(story["id"]),
                        default_cost_usage()["project"],
                    )
                ),
            }
        )
    return merged


def _read_guardrails(project: dict[str, Any]) -> str:
    guardrails_path = Path(project["path"]) / ".ralph" / "guardrails.md"
    if not guardrails_path.exists():
        return ""
    return guardrails_path.read_text()


def _read_log_tail(log_path: str, lines: int = 80) -> str:
    if not log_path:
        return ""
    path = Path(log_path)
    if not path.exists():
        return ""
    content = path.read_text().splitlines()
    return "\n".join(content[-lines:])


def _project_progress_counts(stories: list[dict[str, Any]]) -> tuple[int, int]:
    done = sum(1 for story in stories if story["status"] == "done")
    total = len(stories)
    return done, total


def _resolve_launch_contract(
    config: AutopilotConfig,
    launch_profile: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    normalized = normalize_launch_profile(launch_profile)
    provider_config = asdict(
        config.resolve_provider_config(normalized.provider, normalized.provider_config_id)
    )
    runtime_profile = asdict(config.resolve_runtime_profile(normalized.runtime_profile_id))
    return normalized.model_dump(), provider_config, runtime_profile


def build_project_summary(config: AutopilotConfig, project: dict[str, Any]) -> dict[str, Any]:
    state = ensure_project_state(config, project, seed_mode="migrate")
    launch_profile, provider_config, runtime_profile = _resolve_launch_contract(config, state.get("launch_profile"))
    stories = merge_project_stories(config, project, state)
    stories_done, stories_total = _project_progress_counts(stories)
    current_story = next((story for story in stories if story["id"] == state.get("current_story_id")), None)
    last_event = state.get("timeline", [])[-1] if state.get("timeline") else None
    return {
        "id": project["id"],
        "name": project["name"],
        "path": project["path"],
        "priority": project.get("priority", "normal"),
        "archived": project.get("archived", False),
        "status": state.get("status", "idle"),
        "paused": state.get("paused", False),
        "stories_done": stories_done,
        "stories_total": stories_total,
        "current_story_id": state.get("current_story_id"),
        "current_story_title": current_story["title"] if current_story else None,
        "last_activity_at": state.get("updated_at"),
        "last_message": _sanitize_message(last_event["message"]) if last_event else "",
        "pid": state.get("pid"),
        "launch_profile": launch_profile,
        "provider_config": provider_config,
        "runtime_profile": runtime_profile,
        "budget_policy": state.get("budget_policy", default_budget_policy()),
        "budget_usage": state.get("budget_usage", default_budget_usage()),
        "quality_policy": state.get("quality_policy", default_quality_policy()),
        "cost_usage": state.get("cost_usage", default_cost_usage()),
    }


def touch_project_last_opened(config: AutopilotConfig, project_id: str) -> None:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)
    project["last_opened_at"] = utcnow_iso()
    update_project_entry(config, project)


def build_project_detail(config: AutopilotConfig, project_id: str) -> dict[str, Any]:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    touch_project_last_opened(config, project_id)
    state = ensure_project_state(config, project, seed_mode="migrate")
    launch_profile, provider_config, runtime_profile = _resolve_launch_contract(config, state.get("launch_profile"))
    prd = load_project_prd(project, seed_mode="migrate")
    stories = merge_project_stories(config, project, state)
    summary = build_project_summary(config, project)
    running_story_ids = {
        story["id"] for story in stories if story["status"] in {"in_progress", "merge_blocked", "stuck"}
    }
    team_assignments = {
        str(story["id"]): story.get("team_members", [])
        for story in stories
        if story["id"] in running_story_ids or story.get("team_members")
    }
    active_connectors = {
        str(story["id"]): story.get("connector_activation", [])
        for story in stories
        if story["id"] in running_story_ids or story.get("connector_activation")
    }
    activation_errors = {
        str(story["id"]): story.get("activation_errors", [])
        for story in stories
        if story.get("activation_errors")
    }
    trace_summary: dict[str, Any] = {}
    trace_file = ""
    try:
        from autopilot.core.run_trace import build_trace_summary, read_trace_entries, trace_path

        trace_summary = build_trace_summary(read_trace_entries(config, project_id, limit=400))
        trace_file = str(trace_path(config, project_id))
    except Exception:
        pass

    return {
        **summary,
        "description": prd.get("description", ""),
        "phases": prd.get("phases", []),
        "stories": stories,
        "timeline": [{**event, "message": _sanitize_message(str(event.get("message") or ""))} for event in state.get("timeline", [])],
        "guardrails": _read_guardrails(project),
        "log_tail": _read_log_tail(state.get("log_path", "")),
        "log_path": state.get("log_path", ""),
        "last_error": _sanitize_message(state.get("last_error") or ""),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "active_worker": state.get("active_worker"),
        "active_critic": state.get("active_critic"),
        "current_iteration": state.get("current_iteration", 0),
        "launch_profile": launch_profile,
        "provider_config": provider_config,
        "runtime_profile": runtime_profile,
        "budget_policy": state.get("budget_policy", default_budget_policy()),
        "budget_usage": state.get("budget_usage", default_budget_usage()),
        "quality_policy": state.get("quality_policy", default_quality_policy()),
        "cost_usage": state.get("cost_usage", default_cost_usage()),
        "discoveries": build_story_discovery_context(state, story_id=None),
        "team_assignments": team_assignments,
        "active_connectors": active_connectors,
        "activation_errors": activation_errors,
        "trace_summary": trace_summary,
        "trace_path": trace_file,
    }


def update_project_budget_policy(
    config: AutopilotConfig,
    project_id: str,
    **fields: Any,
) -> dict[str, Any]:
    """Update a project's runtime budget policy."""
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)
    policy = update_budget_policy(state, updates=fields)
    save_project_state(config, project_id, state)
    return policy


def append_guidance(config: AutopilotConfig, project_id: str, payload: str, story_id: int | None = None) -> None:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    ralph_dir = Path(project["path"]) / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    guardrails = ralph_dir / "guardrails.md"
    existing = guardrails.read_text() if guardrails.exists() else "# Guardrails\n\nDo not repeat these mistakes:\n\n"
    guardrails.write_text(f"{existing}\n- [HUMAN]: {payload}\n")
    emit_project_event(
        config,
        project_id,
        event="guidance_added",
        status="ok",
        message=payload,
        story_id=story_id,
    )


def mark_story_skipped(config: AutopilotConfig, project_id: str, story_id: int) -> None:
    update_story_runtime(
        config,
        project_id,
        story_id,
        status="skipped",
        completed_at=utcnow_iso(),
    )
    state = load_project_state(config, project_id)
    if state.get("current_story_id") == story_id:
        state["current_story_id"] = None
        state["current_iteration"] = 0
        state["active_worker"] = None
        state["active_critic"] = None
        save_project_state(config, project_id, state)
    emit_project_event(
        config,
        project_id,
        event="story_skipped",
        status="skipped",
        message=f"Story #{story_id} skipped by user.",
        story_id=story_id,
    )


def archive_project(config: AutopilotConfig, project_id: str) -> dict[str, Any]:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    state = load_project_state(config, project_id)
    if state.get("pid"):
        pause_project_run(config, project_id)

    project["archived"] = True
    update_project_entry(config, project)
    emit_project_event(
        config,
        project_id,
        event="project_archived",
        status="archived",
        message="Project archived from dashboard.",
    )
    return project


def _is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    stat = _ps_output("-o", "stat=", "-p", str(pid))
    if not stat:
        return False
    return "Z" not in stat.upper()


def _child_pids(pid: int) -> list[int]:
    output = _ps_output("-axo", "pid=,ppid=")
    children: dict[int, list[int]] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        child_pid = int(parts[0])
        parent_pid = int(parts[1])
        children.setdefault(parent_pid, []).append(child_pid)

    result: list[int] = []
    queue = [pid]
    seen: set[int] = set()
    while queue:
        current = queue.pop()
        for child in children.get(current, []):
            if child in seen:
                continue
            seen.add(child)
            result.append(child)
            queue.append(child)
    return result


def launch_project_run(
    config: AutopilotConfig,
    project_id: str,
    *,
    launch_profile: dict[str, Any] | None = None,
    event_name: str = "run_started",
    event_message: str = "Background run started.",
) -> tuple[bool, Path | None, str]:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        return False, None, "Project not found."

    state = ensure_project_state(config, project, seed_mode="migrate")
    existing_pid = state.get("pid")
    if _is_pid_running(existing_pid):
        return True, Path(state["log_path"]) if state.get("log_path") else None, "Project is already running."

    state["launch_profile"] = normalize_launch_profile(launch_profile or state.get("launch_profile")).model_dump()

    if not check_ralph_installed():
        return False, None, "Project created, but Ralph is not installed. Install Ralph before launching."

    project_path = Path(project["path"])
    if not (project_path / ".agents" / "ralph" / "loop.sh").exists():
        if not init_ralph_project(project_path):
            return False, None, "Ralph project initialization failed."
    else:
        apply_autopilot_ralph_overrides(project_path)

    logs_dir = config.autopilot_home / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{project['id']}.log"

    with log_path.open("a", encoding="utf-8") as log_file:
        run_cmd = (
            f"{shlex.quote(sys.executable)} -m autopilot run "
            f"{shlex.quote(str(project['path']))} "
            f"--project-id {shlex.quote(project_id)} "
            f"--prd {shlex.quote(project.get('prd', '.agents/tasks/prd.json'))} "
            "--headless"
        )
        process = subprocess.Popen(
            ["/bin/sh", "-lc", run_cmd],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    started_at = utcnow_iso()
    state.update(
        {
            "pid": process.pid,
            "status": "running",
            "paused": False,
            "started_at": state.get("started_at") or started_at,
            "finished_at": None,
            "log_path": str(log_path),
            "last_error": None,
            "parallel_story_ids": [],
            "activation_errors": [],
        }
    )
    save_project_state(config, project_id, state)
    emit_project_event(
        config,
        project_id,
        event=event_name,
        status="running",
        message=event_message,
    )
    return True, log_path, event_message


def pause_project_run(config: AutopilotConfig, project_id: str) -> str:
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)

    pid = state.get("pid")
    if pid and _is_pid_running(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            for child_pid in reversed(_child_pids(pid)):
                try:
                    os.kill(child_pid, signal.SIGTERM)
                except OSError:
                    continue
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass

        deadline = time.time() + 5
        while time.time() < deadline and _is_pid_running(pid):
            time.sleep(0.1)

        if _is_pid_running(pid):
            try:
                os.killpg(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                for child_pid in reversed(_child_pids(pid)):
                    try:
                        os.kill(child_pid, signal.SIGKILL)
                    except OSError:
                        continue
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass

    state.update(
        {
            "pid": None,
            "status": "paused",
            "paused": True,
            "active_worker": None,
            "active_critic": None,
            "parallel_story_ids": [],
        }
    )
    save_project_state(config, project_id, state)
    emit_project_event(
        config,
        project_id,
        event="paused",
        status="paused",
        message="Project paused by user.",
        story_id=state.get("current_story_id"),
    )
    return "Project paused."


def auto_pause_project_run(
    config: AutopilotConfig,
    project_id: str,
    *,
    message: str,
    story_id: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Pause a project from inside the runtime without sending signals to the current process."""
    state = load_project_state(config, project_id)
    if not state:
        raise KeyError(project_id)

    state.update(
        {
            "pid": None,
            "status": "paused",
            "paused": True,
            "active_worker": None,
            "active_critic": None,
            "parallel_story_ids": [],
            "last_error": message,
        }
    )
    save_project_state(config, project_id, state)
    emit_project_event(
        config,
        project_id,
        event="budget_paused",
        status="paused",
        message=message,
        story_id=story_id,
        extra=extra,
    )
    return message


def resume_project_run(config: AutopilotConfig, project_id: str) -> tuple[bool, Path | None, str]:
    return launch_project_run(
        config,
        project_id,
        event_name="resumed",
        event_message="Project resumed.",
    )
