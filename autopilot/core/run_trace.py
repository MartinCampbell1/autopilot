"""Structured runtime trace helpers for forensic replay."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trace_path(config: AutopilotConfig, project_id: str) -> Path:
    """Return the JSONL trace path for one project."""
    return config.autopilot_home / "traces" / f"{project_id}.jsonl"


def append_trace_entry(
    config: AutopilotConfig,
    project_id: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    """Append one structured trace entry."""
    record = {
        "timestamp": entry.get("timestamp") or _utcnow_iso(),
        "project_id": project_id,
        **entry,
    }
    path = trace_path(config, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_trace_entries(
    config: AutopilotConfig,
    project_id: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read structured trace entries for one project."""
    path = trace_path(config, project_id)
    if not path.exists():
        return []
    entries = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None and limit > 0:
        return entries[-limit:]
    return entries


def build_trace_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a replay-friendly summary from trace entries."""
    kinds = Counter(str(entry.get("kind") or "unknown") for entry in entries)
    by_story: dict[str, dict[str, Any]] = {}
    for entry in entries:
        story_id = entry.get("story_id")
        if story_id in (None, ""):
            continue
        story_key = str(story_id)
        story_summary = by_story.setdefault(
            story_key,
            {
                "story_id": story_id,
                "entry_count": 0,
                "iteration_count": 0,
                "latest_kind": None,
                "latest_status": None,
                "last_timestamp": None,
            },
        )
        story_summary["entry_count"] += 1
        if entry.get("kind") == "iteration_record":
            story_summary["iteration_count"] += 1
        story_summary["latest_kind"] = entry.get("kind")
        story_summary["latest_status"] = entry.get("status") or entry.get("event")
        story_summary["last_timestamp"] = entry.get("timestamp")

    return {
        "entry_count": len(entries),
        "by_kind": dict(kinds),
        "stories": list(by_story.values()),
        "first_timestamp": entries[0]["timestamp"] if entries else None,
        "last_timestamp": entries[-1]["timestamp"] if entries else None,
    }
