"""Runtime and context diagnostics for doctor flows."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_project_state, load_projects_registry
from autopilot.core.repo_registry import build_repo_registry_key, get_git_remote_url, get_known_paths_for_repo
from autopilot.core.worktree import resolve_story_worktree_owner

EVENT_LOG_WARN_BYTES = 10 * 1024 * 1024


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _ps_output(*args: str) -> str:
    try:
        result = subprocess.run(
            ["ps", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def _is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    stat = _ps_output("-o", "stat=", "-p", str(pid))
    if not stat:
        return False
    return "Z" not in stat.upper()


def _diagnostic(
    *,
    code: str,
    severity: str,
    scope: str,
    message: str,
    fix: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "scope": scope,
        "message": message,
        "fix": fix,
        "metadata": dict(metadata or {}),
    }


def build_runtime_diagnostics(
    *,
    config: AutopilotConfig,
    config_path: Path,
    project_path: Path,
) -> dict[str, Any]:
    """Build concrete runtime/context diagnostics for one doctor invocation."""

    normalized_project_path = _normalize_path(project_path)
    diagnostics: list[dict[str, Any]] = []
    if not config_path.exists():
        diagnostics.append(
            _diagnostic(
                code="config_missing",
                severity="warning",
                scope="config",
                message="Autopilot config file does not exist yet.",
                fix="Create ~/.autopilot/config.yaml or run an Autopilot command that writes initial config.",
            )
        )

    worktree_owner = resolve_story_worktree_owner(normalized_project_path)
    effective_project_root = worktree_owner[0] if worktree_owner is not None else normalized_project_path
    current_repo_key = build_repo_registry_key(effective_project_root)
    same_repo_paths = sorted(get_known_paths_for_repo(config, repo_key=current_repo_key)) if current_repo_key else []
    related_projects: list[dict[str, Any]] = []
    for project in load_projects_registry(config, include_archived=True):
        project_repo_key = build_repo_registry_key(Path(project["path"]))
        if current_repo_key and current_repo_key == project_repo_key:
            related_projects.append(project)

    if (
        effective_project_root.exists()
        and (effective_project_root / ".git").exists()
        and not str(get_git_remote_url(effective_project_root) or "").strip()
    ):
        diagnostics.append(
            _diagnostic(
                code="repo_identity_missing",
                severity="warning",
                scope="project",
                message="Git repository has no stable repo identity yet.",
                fix="Add an origin remote so resume and ship flows can map this repo across clones and worktrees.",
                metadata={"path": str(effective_project_root)},
            )
        )

    if len(same_repo_paths) > 1:
        diagnostics.append(
            _diagnostic(
                code="same_repo_multiple_paths",
                severity="info",
                scope="resume",
                message=f"Same repo has been observed in {len(same_repo_paths)} local paths.",
                fix="Use `autopilot resume` or `autopilot run --project-id ...` to disambiguate the intended clone/worktree.",
                metadata={"paths": same_repo_paths},
            )
        )

    if worktree_owner is not None:
        diagnostics.append(
            _diagnostic(
                code="story_worktree_detected",
                severity="info",
                scope="resume",
                message="Current path is inside an Autopilot story worktree.",
                fix="Run resume or run commands from this checkout safely; Autopilot can map it back to the owning project.",
                metadata={
                    "owner_project_path": str(worktree_owner[0]),
                    "worktree_root": str(worktree_owner[1]),
                },
            )
        )

    for project in related_projects:
        state = load_project_state(config, str(project["id"]))
        pid = state.get("pid")
        if str(state.get("status") or "") != "running":
            continue
        if _is_pid_running(pid if isinstance(pid, int) else None):
            continue
        diagnostics.append(
            _diagnostic(
                code="stale_runtime_pid",
                severity="warning",
                scope="runtime",
                message=f"Registered project '{project['name']}' still says running, but its PID is no longer alive.",
                fix="Resume or pause this project to reconcile state before relying on its runtime status.",
                metadata={
                    "project_id": str(project["id"]),
                    "project_path": str(project["path"]),
                    "pid": pid,
                    "runtime_session_id": str(state.get("runtime_session_id") or ""),
                },
            )
        )

    if config.events_log_path.exists():
        try:
            events_log_size = config.events_log_path.stat().st_size
        except OSError:
            events_log_size = 0
        if events_log_size >= EVENT_LOG_WARN_BYTES:
            diagnostics.append(
                _diagnostic(
                    code="events_log_large",
                    severity="info",
                    scope="context",
                    message="Structured event log has grown large enough to be worth pruning.",
                    fix="Archive or rotate ~/.autopilot/events/events.jsonl if live diagnostics or local disk usage start to degrade.",
                    metadata={"bytes": events_log_size},
                )
            )

    return {
        "project_path": str(normalized_project_path),
        "effective_project_root": str(effective_project_root),
        "current_repo_key": current_repo_key,
        "same_repo_known_paths": same_repo_paths,
        "related_project_ids": [str(project["id"]) for project in related_projects],
        "diagnostics": diagnostics,
        "summary": {
            "error_count": sum(1 for item in diagnostics if item["severity"] == "error"),
            "warning_count": sum(1 for item in diagnostics if item["severity"] == "warning"),
            "info_count": sum(1 for item in diagnostics if item["severity"] == "info"),
        },
    }
