"""Recurring scheduler helpers for maintenance-style runs."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ScheduleSpec:
    """One recurring schedule for maintenance runs."""

    raw: str
    interval_sec: int
    max_runs: int | None = None
    start_immediately: bool = True


_SCHEDULE_RE = re.compile(
    r"^\s*(?P<count>\d+)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)\s*$",
    re.IGNORECASE,
)
_UNIT_SECONDS = {
    "s": 1,
    "sec": 1,
    "secs": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "mins": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hrs": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}
_ALIASES = {
    "hourly": 3600,
    "daily": 86400,
}


def format_interval(interval_sec: int) -> str:
    """Render a compact human-readable interval."""
    if interval_sec % 86400 == 0:
        days = interval_sec // 86400
        return f"{days}d"
    if interval_sec % 3600 == 0:
        hours = interval_sec // 3600
        return f"{hours}h"
    if interval_sec % 60 == 0:
        minutes = interval_sec // 60
        return f"{minutes}m"
    return f"{interval_sec}s"


def parse_schedule_spec(
    raw: str,
    *,
    max_runs: int | None = None,
    start_immediately: bool = True,
) -> ScheduleSpec:
    """Parse a CLI schedule like `30m`, `6h`, `hourly`, or `daily`."""
    normalized = str(raw or "").strip().lower()
    if not normalized:
        raise ValueError("schedule must not be empty")
    if max_runs is not None and int(max_runs) < 1:
        raise ValueError("max_runs must be at least 1")

    if normalized in _ALIASES:
        interval_sec = _ALIASES[normalized]
    else:
        match = _SCHEDULE_RE.match(normalized)
        if match is None:
            raise ValueError("schedule must look like `30m`, `6h`, `1d`, `45s`, `hourly`, or `daily`")
        interval_sec = int(match.group("count")) * _UNIT_SECONDS[match.group("unit").lower()]

    if interval_sec < 1:
        raise ValueError("schedule interval must be at least 1 second")
    return ScheduleSpec(
        raw=normalized,
        interval_sec=interval_sec,
        max_runs=int(max_runs) if max_runs is not None else None,
        start_immediately=bool(start_immediately),
    )


def _scheduled_exit_code(run_summaries: list[dict[str, Any]]) -> int:
    exit_codes = [int(summary.get("exit_code", 0)) for summary in run_summaries]
    if any(code not in {0, 3} for code in exit_codes):
        return 1
    if any(code == 3 for code in exit_codes):
        return 3
    return 0


def build_scheduled_summary(
    job_name: str,
    schedule: ScheduleSpec,
    run_summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured summary for one scheduled maintenance loop."""
    return {
        "kind": "scheduled_run_summary",
        "timestamp": _utcnow_iso(),
        "job_name": job_name,
        "schedule": {
            "raw": schedule.raw,
            "interval_sec": schedule.interval_sec,
            "interval_label": format_interval(schedule.interval_sec),
            "max_runs": schedule.max_runs,
            "start_immediately": schedule.start_immediately,
        },
        "run_count": len(run_summaries),
        "exit_code": _scheduled_exit_code(run_summaries),
        "failed_runs": [
            summary.get("scheduled_run_index")
            for summary in run_summaries
            if int(summary.get("exit_code", 0)) not in {0, 3}
        ],
        "paused_runs": [
            summary.get("scheduled_run_index")
            for summary in run_summaries
            if int(summary.get("exit_code", 0)) == 3
        ],
        "last_run_at": run_summaries[-1].get("timestamp") if run_summaries else None,
        "runs": run_summaries,
    }


def run_scheduled_job(
    *,
    job_name: str,
    schedule: ScheduleSpec,
    runner: Callable[[int], dict[str, Any]],
    emit: Callable[[str, str, str], None] | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Run a recurring job on an in-process schedule."""
    next_run_at = monotonic() if schedule.start_immediately else monotonic() + schedule.interval_sec
    run_summaries: list[dict[str, Any]] = []

    while True:
        delay = max(0.0, next_run_at - monotonic())
        if delay > 0:
            if emit is not None:
                emit(
                    "maintenance_sleeping",
                    f"{job_name} sleeping for {format_interval(int(round(delay)))} before the next scheduled run.",
                    "info",
                )
            sleep(delay)

        run_index = len(run_summaries) + 1
        if emit is not None:
            emit(
                "maintenance_run_started",
                f"{job_name} scheduled run {run_index} started.",
                "info",
            )
        summary = dict(runner(run_index) or {})
        summary.setdefault("scheduled_run_index", run_index)
        run_summaries.append(summary)
        if emit is not None:
            emit(
                "maintenance_run_completed",
                f"{job_name} scheduled run {run_index} finished with exit {summary.get('exit_code', 0)}.",
                "info",
            )
        if schedule.max_runs is not None and run_index >= schedule.max_runs:
            break
        next_run_at += schedule.interval_sec

    return build_scheduled_summary(job_name, schedule, run_summaries)
