"""Helpers for unattended/headless runtime execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import typer

RUN_EXIT_SUCCESS = 0
RUN_EXIT_FAILED = 1
RUN_EXIT_PRECHECK_FAILED = 2
RUN_EXIT_PAUSED = 3


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_headless_event(
    event: str,
    *,
    message: str,
    level: str = "info",
    **extra: Any,
) -> None:
    """Emit one structured runtime event line."""
    payload = {
        "kind": "run_event",
        "timestamp": _utcnow_iso(),
        "event": event,
        "level": level,
        "message": message,
    }
    for key, value in extra.items():
        if value is not None:
            payload[key] = value
    typer.echo(json.dumps(payload, ensure_ascii=False))


def emit_headless_summary(summary: dict[str, Any]) -> None:
    """Emit one structured summary line."""
    typer.echo(json.dumps({"timestamp": _utcnow_iso(), **summary}, ensure_ascii=False))


def exit_code_for_state(state: dict[str, Any]) -> int:
    """Map persisted runtime state to a process exit code."""
    if state.get("paused"):
        return RUN_EXIT_PAUSED
    if state.get("status") == "completed":
        return RUN_EXIT_SUCCESS
    return RUN_EXIT_FAILED


def build_preflight_summary(
    project_path: str,
    *,
    project_id: str | None = None,
    project_name: str | None = None,
    message: str,
    exit_code: int = RUN_EXIT_PRECHECK_FAILED,
) -> dict[str, Any]:
    """Build a failure summary before runtime state exists."""
    resolved_name = project_name or Path(project_path).name or "project"
    if exit_code == RUN_EXIT_SUCCESS:
        status = "completed"
    elif exit_code == RUN_EXIT_PAUSED:
        status = "paused"
    else:
        status = "failed"
    return {
        "kind": "run_summary",
        "timestamp": _utcnow_iso(),
        "project_id": project_id,
        "project_name": resolved_name,
        "project_path": project_path,
        "status": status,
        "paused": exit_code == RUN_EXIT_PAUSED,
        "exit_code": exit_code,
        "stories_done": 0,
        "stories_total": 0,
        "story_status_counts": {},
        "blocked_story_ids": [],
        "current_story_id": None,
        "parallel_story_ids": [],
        "started_at": None,
        "finished_at": None,
        "last_error": message,
        "log_path": "",
    }


def build_run_summary(
    project: dict[str, Any],
    state: dict[str, Any],
    *,
    exit_code: int,
    exception: BaseException | None = None,
) -> dict[str, Any]:
    """Build a structured summary for one project run."""
    story_state = state.get("story_state", {})
    story_status_counts: dict[str, int] = {}
    blocked_story_ids: list[int] = []
    stories_done = 0

    for key, entry in story_state.items():
        status = str(entry.get("status") or "open")
        story_status_counts[status] = story_status_counts.get(status, 0) + 1
        if status in {"done", "skipped"}:
            stories_done += 1
        if status == "open" and entry.get("blocked_on"):
            blocked_story_ids.append(int(entry.get("story_id") or key))

    summary = {
        "kind": "run_summary",
        "timestamp": _utcnow_iso(),
        "project_id": project.get("id"),
        "project_name": project.get("name"),
        "project_path": project.get("path"),
        "status": state.get("status", "idle"),
        "paused": bool(state.get("paused")),
        "exit_code": exit_code,
        "stories_done": stories_done,
        "stories_total": len(story_state),
        "story_status_counts": story_status_counts,
        "blocked_story_ids": sorted(blocked_story_ids),
        "current_story_id": state.get("current_story_id"),
        "parallel_story_ids": list(state.get("parallel_story_ids") or []),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "last_error": state.get("last_error"),
        "log_path": state.get("log_path") or "",
        "cost": {
            "run": (state.get("cost_usage") or {}).get("run") or {},
            "project": (state.get("cost_usage") or {}).get("project") or {},
        },
    }
    if exception is not None:
        summary["exception_type"] = type(exception).__name__
        if not summary.get("last_error"):
            summary["last_error"] = str(exception)
    return summary


def build_run_all_summary(project_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a structured summary for `run-all`."""
    failed_projects = [
        summary.get("project_id") or summary.get("project_name")
        for summary in project_summaries
        if int(summary.get("exit_code", RUN_EXIT_SUCCESS)) in {RUN_EXIT_FAILED, RUN_EXIT_PRECHECK_FAILED}
    ]
    paused_projects = [
        summary.get("project_id") or summary.get("project_name")
        for summary in project_summaries
        if int(summary.get("exit_code", RUN_EXIT_SUCCESS)) == RUN_EXIT_PAUSED
    ]
    if failed_projects:
        exit_code = RUN_EXIT_FAILED
    elif paused_projects:
        exit_code = RUN_EXIT_PAUSED
    else:
        exit_code = RUN_EXIT_SUCCESS

    return {
        "kind": "run_all_summary",
        "timestamp": _utcnow_iso(),
        "exit_code": exit_code,
        "project_count": len(project_summaries),
        "failed_projects": failed_projects,
        "paused_projects": paused_projects,
        "completed_projects": [
            summary.get("project_id") or summary.get("project_name")
            for summary in project_summaries
            if int(summary.get("exit_code", RUN_EXIT_SUCCESS)) == RUN_EXIT_SUCCESS
        ],
        "cost": {
            "run": {
                "estimated_cost_usd": round(
                    sum(float(((summary.get("cost") or {}).get("run") or {}).get("estimated_cost_usd") or 0.0) for summary in project_summaries),
                    8,
                ),
                "input_tokens": sum(int(((summary.get("cost") or {}).get("run") or {}).get("input_tokens") or 0) for summary in project_summaries),
                "output_tokens": sum(int(((summary.get("cost") or {}).get("run") or {}).get("output_tokens") or 0) for summary in project_summaries),
                "total_tokens": sum(int(((summary.get("cost") or {}).get("run") or {}).get("total_tokens") or 0) for summary in project_summaries),
                "tracked_invocations": sum(
                    int(((summary.get("cost") or {}).get("run") or {}).get("tracked_invocations") or 0)
                    for summary in project_summaries
                ),
                "priced_invocations": sum(
                    int(((summary.get("cost") or {}).get("run") or {}).get("priced_invocations") or 0)
                    for summary in project_summaries
                ),
            }
        },
        "projects": project_summaries,
    }
