"""Context visibility helpers for operator-facing CLI inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autopilot.core.bootstrap_visibility import build_bootstrap_status
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import build_project_detail, resolve_runtime_project_entry
from autopilot.core.repo_registry import (
    build_repo_registry_key,
    find_canonical_git_root,
    get_github_repo,
    get_known_paths_for_repo,
)


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _truncate_message(message: str, *, max_len: int = 240) -> str:
    cleaned = str(message or "").strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[: max_len - 1].rstrip() + "…"


def _instruction_layers(detail: dict[str, Any]) -> dict[str, Any]:
    delivery_loop = dict(detail.get("delivery_loop") or {})
    brief = dict(delivery_loop.get("brief") or {})
    discoveries = list(detail.get("discoveries") or [])
    guardrails = str(detail.get("guardrails") or "")
    active_tools = dict(detail.get("active_tools") or {})
    active_connectors = dict(detail.get("active_connectors") or {})
    activation_errors = dict(detail.get("activation_errors") or {})

    discovery_kinds = sorted({str(marker.get("kind") or "").strip() for marker in discoveries if str(marker.get("kind") or "").strip()})
    return {
        "brief": {
            "title": str(brief.get("title") or ""),
            "relpath": str(brief.get("relpath") or ""),
            "path": str(brief.get("path") or ""),
            "present": bool(brief.get("present")),
        },
        "task_source": dict(detail.get("task_source") or {}),
        "guardrails": {
            "present": bool(guardrails.strip()),
            "char_count": len(guardrails),
            "line_count": len([line for line in guardrails.splitlines() if line.strip()]),
        },
        "discoveries": {
            "count": len(discoveries),
            "kinds": discovery_kinds,
        },
        "active_tools": {
            "story_count": len(active_tools),
            "stories": active_tools,
        },
        "active_connectors": {
            "story_count": len(active_connectors),
            "stories": active_connectors,
        },
        "activation_errors": {
            "story_count": len(activation_errors),
            "stories": activation_errors,
        },
    }


def _build_microcompact(detail: dict[str, Any], *, repo_key: str, github_repo: str) -> str:
    current_story = str(detail.get("current_story_title") or "idle").strip() or "idle"
    status = str(detail.get("status") or "idle").strip() or "idle"
    delivery = dict(detail.get("delivery_status") or {})
    delivery_label = str(delivery.get("status") or "unknown").strip() or "unknown"
    runtime_session_id = str(detail.get("runtime_session_id") or "").strip()
    runtime_hint = f"runtime={runtime_session_id}" if runtime_session_id else "runtime=offline"
    repo_hint = github_repo or repo_key or "repo=untracked"
    return f"status={status} story={current_story} delivery={delivery_label} {runtime_hint} repo={repo_hint}"


def build_context_snapshot(
    config: AutopilotConfig,
    *,
    project_path: Path | str = ".",
    project_id: str | None = None,
    event_limit: int = 12,
) -> dict[str, Any]:
    """Build a repo-aware operator snapshot of current project context."""

    normalized_path = _normalize_path(project_path)
    project = resolve_runtime_project_entry(
        config,
        project_path=normalized_path,
        project_id=project_id,
        include_archived=True,
    )
    if project is None:
        raise KeyError(str(project_id or normalized_path))

    detail = build_project_detail(config, str(project["id"]))
    repo_root = find_canonical_git_root(normalized_path) or find_canonical_git_root(project["path"])
    repo_key = build_repo_registry_key(repo_root) if repo_root is not None else ""
    github_repo = get_github_repo(repo_root) if repo_root is not None else ""
    recent_events = list(detail.get("timeline") or [])[-max(event_limit, 0) :] if event_limit > 0 else []
    recent_events_payload = [
        {
            "timestamp": event.get("timestamp"),
            "event": str(event.get("event") or ""),
            "status": str(event.get("status") or ""),
            "story_id": event.get("story_id"),
            "message": _truncate_message(str(event.get("message") or "")),
        }
        for event in recent_events
    ]

    return {
        "project_id": str(project["id"]),
        "project_name": str(project.get("name") or ""),
        "project_path": str(detail.get("path") or project["path"]),
        "repo": {
            "repo_root": str(repo_root) if repo_root is not None else "",
            "repo_key": repo_key,
            "github_repo": github_repo,
            "known_paths": get_known_paths_for_repo(config, repo_key=repo_key) if repo_key else [],
        },
        "status": {
            "status": str(detail.get("status") or "idle"),
            "paused": bool(detail.get("paused")),
            "current_story_id": detail.get("current_story_id"),
            "current_story_title": str(detail.get("current_story_title") or ""),
            "runtime_session_id": str(detail.get("runtime_session_id") or ""),
            "pid": detail.get("pid"),
            "started_at": detail.get("started_at"),
            "finished_at": detail.get("finished_at"),
            "last_error": str(detail.get("last_error") or ""),
        },
        "delivery": {
            "status": dict(detail.get("delivery_status") or {}),
            "latest_handoff": dict(detail.get("latest_handoff") or {}),
            "loop": dict(detail.get("delivery_loop") or {}),
        },
        "bootstrap": build_bootstrap_status(
            project_path=str(detail.get("path") or project["path"]),
            project=project,
        ),
        "instruction_layers": _instruction_layers(detail),
        "recent_events": recent_events_payload,
        "trace": {
            "summary": dict(detail.get("trace_summary") or {}),
            "path": str(detail.get("trace_path") or ""),
        },
        "microcompact": _build_microcompact(detail, repo_key=repo_key, github_repo=github_repo),
    }
