"""Resume discovery and repo-aware session history helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import get_project_entry, load_project_state, load_projects_registry
from autopilot.core.repo_registry import (
    build_repo_registry_key,
    find_canonical_git_root,
    get_github_repo,
    get_known_paths_for_repo,
    update_repo_path_mapping,
)
from autopilot.core.worktree import resolve_story_worktree_owner


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _best_effort_update_repo_registry(config: AutopilotConfig, project_path: Path) -> None:
    try:
        update_repo_path_mapping(config, project_path)
    except Exception:
        return


def _resolve_current_project(projects: list[dict[str, Any]], current_path: Path) -> dict[str, Any] | None:
    best_match: dict[str, Any] | None = None
    best_depth = -1
    for project in projects:
        project_root = _normalize_path(project["path"])
        if current_path != project_root and project_root not in current_path.parents:
            continue
        depth = len(project_root.parts)
        if depth > best_depth:
            best_match = project
            best_depth = depth
    return best_match


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


def _resume_relation(
    *,
    project: dict[str, Any],
    current_project: dict[str, Any] | None,
    project_repo_key: str,
    current_repo_key: str,
) -> str:
    if current_project is not None and str(project.get("id") or "") == str(current_project.get("id") or ""):
        return "current_project"
    if current_repo_key and project_repo_key and current_repo_key == project_repo_key:
        return "same_repo"
    return "cross_project"


def _resume_sort_key(candidate: dict[str, Any]) -> tuple[int, int, str, str]:
    relation_rank = {
        "current_project": 0,
        "same_repo": 1,
        "cross_project": 2,
    }.get(str(candidate.get("relation") or ""), 3)
    resumable_rank = 0 if bool(candidate.get("can_resume")) else 1
    last_seen = str(candidate.get("last_opened_at") or candidate.get("created_at") or "")
    return (relation_rank, resumable_rank, last_seen, str(candidate.get("name") or ""))


def _canonicalize_same_repo_paths(paths: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_path in paths:
        try:
            candidate = _normalize_path(raw_path)
        except Exception:
            continue
        canonical = find_canonical_git_root(candidate) or candidate
        serialized = str(canonical)
        if serialized in seen:
            continue
        seen.add(serialized)
        normalized.append(serialized)
    return sorted(normalized)


def build_resume_discovery(config: AutopilotConfig, project_path: Path | str = ".") -> dict[str, Any]:
    """Build a repo-aware resume candidate list for one current path."""

    current_path = _normalize_path(project_path)
    _best_effort_update_repo_registry(config, current_path)
    projects = load_projects_registry(config, include_archived=True)
    worktree_owner = resolve_story_worktree_owner(current_path)
    current_checkout_root = worktree_owner[1] if worktree_owner is not None else (find_canonical_git_root(current_path) or current_path)
    current_repo_key = build_repo_registry_key(current_checkout_root)

    current_project: dict[str, Any] | None = None
    if worktree_owner is not None:
        current_project = get_project_entry(config, project_path=worktree_owner[0], include_archived=True)
    if current_project is None:
        current_project = _resolve_current_project(projects, current_path)

    candidates: list[dict[str, Any]] = []
    registered_paths = {str(_normalize_path(project["path"])) for project in projects}
    for project in projects:
        project_root = _normalize_path(project["path"])
        state = load_project_state(config, str(project["id"]))
        project_repo_key = build_repo_registry_key(project_root)
        pid = state.get("pid")
        is_running = _is_pid_running(pid if isinstance(pid, int) else None)
        candidates.append(
            {
                "project_id": str(project["id"]),
                "name": str(project.get("name") or ""),
                "path": str(project_root),
                "relation": _resume_relation(
                    project=project,
                    current_project=current_project,
                    project_repo_key=project_repo_key,
                    current_repo_key=current_repo_key,
                ),
                "repo_key": project_repo_key,
                "github_repo": get_github_repo(project_root),
                "status": str(state.get("status") or "idle"),
                "paused": bool(state.get("paused", False)),
                "runtime_session_id": str(state.get("runtime_session_id") or ""),
                "is_running": is_running,
                "can_resume": not is_running,
                "last_opened_at": str(project.get("last_opened_at") or ""),
                "created_at": str(project.get("created_at") or ""),
                "archived": bool(project.get("archived", False)),
            }
        )

    known_paths = _canonicalize_same_repo_paths(get_known_paths_for_repo(config, repo_key=current_repo_key)) if current_repo_key else []
    unregistered_same_repo_paths = [
        path
        for path in known_paths
        if path not in registered_paths and path != str(current_checkout_root)
    ]

    return {
        "current_path": str(current_path),
        "current_checkout_root": str(current_checkout_root),
        "current_project_id": str(current_project.get("id") or "") if current_project is not None else "",
        "current_project_name": str(current_project.get("name") or "") if current_project is not None else "",
        "current_repo_key": current_repo_key,
        "current_github_repo": get_github_repo(current_checkout_root),
        "same_repo_known_paths": known_paths,
        "unregistered_same_repo_paths": unregistered_same_repo_paths,
        "projects": sorted(candidates, key=_resume_sort_key),
    }
