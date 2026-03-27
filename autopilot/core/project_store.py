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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.loop_runner import apply_autopilot_ralph_overrides, check_ralph_installed, init_ralph_project

TIMELINE_LIMIT = 300
TERMINAL_STORY_STATUSES = {"done", "skipped", "stuck"}
PLACEHOLDER_ISSUE_PATTERN = re.compile(r"^-\s*Issue\s+\d+:\s*specific description\s*$", re.IGNORECASE)


def utcnow_iso() -> str:
    """Return the current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


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
        normalized_stories.append(
            {
                "id": story_id,
                "title": str(story.get("title") or f"Story {index}").strip(),
                "description": str(story.get("description") or "").strip(),
                "position": index - 1,
                "status": status,
            }
        )

    return {
        "title": title,
        "description": description,
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
        "started_at": None,
        "completed_at": None,
        "updated_at": utcnow_iso(),
        "iteration": 0,
        "agent": None,
        "critic": None,
        "last_error": None,
        "requeue_count": 0,
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
        "story_state": {
            str(story["id"]): _story_state_from_definition(story) for story in prd.get("stories", [])
        },
        "timeline": timeline,
    }


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
    state.setdefault("timeline", [])
    state.setdefault("story_state", {})

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
        current.setdefault("started_at", None)
        current.setdefault("completed_at", None)
        current.setdefault("updated_at", utcnow_iso())
        current.setdefault("iteration", 0)
        current.setdefault("agent", None)
        current.setdefault("critic", None)
        current.setdefault("last_error", None)
        current.setdefault("requeue_count", 0)
        synchronized_story_state[key] = current
    if synchronized_story_state != state["story_state"]:
        state["story_state"] = synchronized_story_state
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
    if event in {"worker_failed", "critic_rejected", "story_stuck", "run_failed"}:
        state["last_error"] = message
    if story_id is not None:
        story_state = state.setdefault("story_state", {}).get(str(story_id))
        if story_state is not None:
            story_state["updated_at"] = event_record["timestamp"]
            if event in {"worker_failed", "critic_rejected", "story_stuck"}:
                story_state["last_error"] = message
    save_project_state(config, project_id, state)
    _append_event_log(config, event_record)
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


def merge_project_stories(project: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    prd = load_project_prd(project, seed_mode="migrate")
    merged: list[dict[str, Any]] = []
    for story in prd.get("stories", []):
        runtime = state.get("story_state", {}).get(str(story["id"]), {})
        merged.append(
            {
                "id": story["id"],
                "title": story["title"],
                "description": story["description"],
                "position": story["position"],
                "status": runtime.get("status", "open"),
                "started_at": runtime.get("started_at"),
                "completed_at": runtime.get("completed_at"),
                "updated_at": runtime.get("updated_at"),
                "iteration": runtime.get("iteration"),
                "agent": runtime.get("agent"),
                "critic": runtime.get("critic"),
                "last_error": _sanitize_message(runtime.get("last_error") or ""),
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


def build_project_summary(config: AutopilotConfig, project: dict[str, Any]) -> dict[str, Any]:
    state = ensure_project_state(config, project, seed_mode="migrate")
    stories = merge_project_stories(project, state)
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
    prd = load_project_prd(project, seed_mode="migrate")
    stories = merge_project_stories(project, state)
    summary = build_project_summary(config, project)

    return {
        **summary,
        "description": prd.get("description", ""),
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
    }


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
            f"--prd {shlex.quote(project.get('prd', '.agents/tasks/prd.json'))}"
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


def resume_project_run(config: AutopilotConfig, project_id: str) -> tuple[bool, Path | None, str]:
    return launch_project_run(
        config,
        project_id,
        event_name="resumed",
        event_message="Project resumed.",
    )
