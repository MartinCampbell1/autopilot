"""Workspace and worktree policy inspection helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import os
import re
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_project_state
from autopilot.core.runtime_control import WorkItemLease, list_project_work_item_leases, release_work_item_lease
from autopilot.core.worktree import remove_worktree

WORKTREE_SUFFIX_PATTERN = re.compile(r"^(?P<name>.+)-story-(?P<story_id>\d+)$")
DEFAULT_STALE_LEASE_AFTER_SEC = 900


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _pid_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _lease_health(lease: WorkItemLease | None, *, stale_after_sec: int) -> tuple[str, list[str]]:
    if lease is None:
        return "missing", []

    issues: list[str] = []
    status = "healthy"
    heartbeat_at = _parse_iso_timestamp(lease.updated_at)
    if heartbeat_at is not None:
        age_sec = max(0, int((datetime.now(timezone.utc) - heartbeat_at).total_seconds()))
        if age_sec > stale_after_sec and not _pid_is_running(lease.runtime_pid):
            status = "stale"
            issues.append(
                f"Lease heartbeat is stale ({age_sec}s old) and runtime pid {lease.runtime_pid or 'unknown'} is not running."
            )
    elif not _pid_is_running(lease.runtime_pid):
        status = "stale"
        issues.append("Lease has no valid heartbeat timestamp and its runtime pid is not running.")

    return status, issues


def _checkout_health(
    *,
    project_path: Path,
    status: str,
    checkout: dict[str, Any] | None,
    ownership: dict[str, Any] | None,
    lease: WorkItemLease | None,
    stale_after_sec: int,
) -> dict[str, Any]:
    if not checkout:
        return {
            "status": "missing",
            "mode": "unknown",
            "path": None,
            "branch_name": None,
            "issues": ["No checkout metadata recorded."],
        }

    checkout_path = Path(str(checkout.get("path") or project_path))
    mode = str(checkout.get("mode") or "shared_main")
    branch_name = checkout.get("branch_name")
    issues: list[str] = []

    if mode == "worktree":
        if not checkout_path.exists():
            issues.append("Reserved worktree path does not exist on disk.")
        if not branch_name:
            issues.append("Worktree checkout is missing branch metadata.")
    elif checkout_path != project_path:
        issues.append("Shared-main checkout should point to the primary project path.")

    if ownership is None and status in {"in_progress", "merge_blocked", "stuck"}:
        issues.append("Active story state has no ownership metadata.")

    health = "healthy"
    lease_status, lease_issues = _lease_health(lease, stale_after_sec=stale_after_sec)
    issues.extend(lease_issues)
    if lease_status == "stale":
        health = "stale"
    if issues:
        if health != "stale":
            health = "blocked" if status == "merge_blocked" else "degraded"

    return {
        "status": health,
        "mode": mode,
        "path": str(checkout_path),
        "branch_name": branch_name,
        "lease_status": lease_status,
        "issues": issues,
    }


def _discover_orphaned_worktrees(project_path: Path, active_checkout_paths: set[str]) -> list[dict[str, Any]]:
    orphaned: list[dict[str, Any]] = []
    parent = project_path.parent
    prefix = f"{project_path.name}-story-"
    for candidate in sorted(parent.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith(prefix):
            continue
        if str(candidate) in active_checkout_paths:
            continue
        match = WORKTREE_SUFFIX_PATTERN.match(candidate.name)
        story_id = int(match.group("story_id")) if match else None
        orphaned.append(
            {
                "story_id": story_id,
                "path": str(candidate),
                "status": "orphaned",
                "issues": ["Worktree exists on disk without an active checkout reservation."],
            }
        )
    return orphaned


def inspect_project_workspace_policy(
    config: AutopilotConfig,
    project_id: str,
    *,
    stale_after_sec: int = DEFAULT_STALE_LEASE_AFTER_SEC,
) -> dict[str, Any]:
    """Inspect runtime-control health for leases and checkout paths."""
    from autopilot.core.project_store import get_project_entry

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    project_path = Path(project["path"]).expanduser().resolve()
    state = load_project_state(config, project_id)
    leases = list_project_work_item_leases(config, project_id)
    leases_by_story = {lease.story_id: lease for lease in leases}

    story_checkouts: list[dict[str, Any]] = []
    active_checkout_paths: set[str] = set()
    for story_id_raw, runtime in sorted(state.get("story_state", {}).items(), key=lambda item: int(item[0])):
        story_id = int(story_id_raw)
        checkout = runtime.get("checkout")
        ownership = runtime.get("ownership")
        lease = leases_by_story.get(story_id)
        health = _checkout_health(
            project_path=project_path,
            status=str(runtime.get("status") or "open"),
            checkout=checkout,
            ownership=ownership,
            lease=lease,
            stale_after_sec=stale_after_sec,
        )
        if checkout and checkout.get("path"):
            active_checkout_paths.add(str(checkout["path"]))
        if lease is not None and checkout and checkout.get("path") and lease.checkout_path != checkout.get("path"):
            health["issues"].append("Lease checkout path does not match story runtime checkout metadata.")
            health["status"] = "degraded"
        story_checkouts.append(
            {
                "story_id": story_id,
                "story_status": runtime.get("status", "open"),
                "ownership": ownership,
                "lease": {
                    "role": lease.role,
                    "owner": lease.owner,
                    "runtime_pid": lease.runtime_pid,
                    "checkout_path": lease.checkout_path,
                    "branch_name": lease.branch_name,
                    "acquired_at": lease.acquired_at,
                    "updated_at": lease.updated_at,
                } if lease is not None else None,
                "checkout": checkout,
                "health": health,
            }
        )

    orphaned_worktrees = _discover_orphaned_worktrees(project_path, active_checkout_paths)
    return {
        "project_id": project_id,
        "leases": [
            {
                "story_id": lease.story_id,
                "role": lease.role,
                "owner": lease.owner,
                "runtime_pid": lease.runtime_pid,
                "status": lease.status,
                "checkout_path": lease.checkout_path,
                "branch_name": lease.branch_name,
                "acquired_at": lease.acquired_at,
                "updated_at": lease.updated_at,
            }
            for lease in leases
        ],
        "stories": story_checkouts,
        "orphaned_worktrees": orphaned_worktrees,
        "stale_after_sec": stale_after_sec,
    }


def recover_story_checkout(
    config: AutopilotConfig,
    project_id: str,
    story_id: int,
    *,
    cleanup_worktree: bool = True,
    reopen_story: bool = False,
) -> dict[str, Any]:
    """Release stale checkout metadata for a story when no run is active."""
    from autopilot.core.project_store import _is_pid_running, get_project_entry, load_project_state, save_project_state

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    state = load_project_state(config, project_id)
    if _is_pid_running(state.get("pid")):
        raise RuntimeError("Cannot recover checkout while the project is running.")

    story_state = state.get("story_state", {}).get(str(story_id))
    if story_state is None:
        raise KeyError(story_id)

    checkout = story_state.get("checkout") or {}
    checkout_path_raw = checkout.get("path")
    project_path = Path(project["path"]).expanduser().resolve()
    checkout_path = Path(str(checkout_path_raw)).expanduser().resolve() if checkout_path_raw else None

    cleanup_performed = False
    if cleanup_worktree and checkout_path is not None and checkout_path != project_path and checkout_path.exists():
        remove_worktree(project_path, checkout_path)
        cleanup_performed = True

    release_work_item_lease(config, project_id=project_id, story_id=story_id)

    story_state["ownership"] = None
    story_state["checkout"] = None
    story_state["worktree_path"] = None
    story_state["branch_name"] = None
    if reopen_story and story_state.get("status") in {"in_progress", "stuck", "merge_blocked"}:
        story_state["status"] = "open"
        story_state["started_at"] = None
        story_state["completed_at"] = None
        story_state["agent"] = None
        story_state["critic"] = None
        story_state["iteration"] = 0
        story_state["last_error"] = None

    save_project_state(config, project_id, state)
    return {
        "story_id": story_id,
        "cleanup_performed": cleanup_performed,
        "reopened": reopen_story and story_state.get("status") == "open",
    }


def sweep_stale_project_checkouts(
    config: AutopilotConfig,
    project_id: str,
    *,
    stale_after_sec: int = DEFAULT_STALE_LEASE_AFTER_SEC,
    cleanup_worktrees: bool = True,
    reopen_stories: bool = True,
) -> dict[str, Any]:
    """Recover all stale checkouts for a non-running project."""
    inspection = inspect_project_workspace_policy(config, project_id, stale_after_sec=stale_after_sec)
    recovered: list[dict[str, Any]] = []
    for story in inspection["stories"]:
        if story.get("health", {}).get("lease_status") != "stale":
            continue
        result = recover_story_checkout(
            config,
            project_id,
            int(story["story_id"]),
            cleanup_worktree=cleanup_worktrees,
            reopen_story=reopen_stories,
        )
        recovered.append(result)

    return {
        "project_id": project_id,
        "recovered": recovered,
        "stale_after_sec": stale_after_sec,
    }
