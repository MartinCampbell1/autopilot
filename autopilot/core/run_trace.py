"""Structured runtime trace helpers for forensic replay."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.audit_chain import append_jsonl_audit_record, build_audit_bundle
from autopilot.core.config import AutopilotConfig
from autopilot.core.monitoring.traces import annotate_trace_entries, build_trace_replay


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
    return append_jsonl_audit_record(path, record, chain_kind="trace", config=config)


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


def _filter_trace_entries(
    entries: list[dict[str, Any]],
    *,
    story_id: int | None = None,
    run_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    annotated = annotate_trace_entries(entries)
    filtered = [
        dict(entry)
        for entry, annotated_entry in zip(entries, annotated, strict=False)
        if (story_id is None or int(annotated_entry.get("story_id") or 0) == int(story_id))
        and (run_id is None or str(annotated_entry.get("run_id") or "") == str(run_id))
    ]
    if limit is not None and limit > 0:
        filtered = filtered[-limit:]
    return filtered


def build_trace_summary(
    entries: list[dict[str, Any]],
    *,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        "verified": bool((verification or verify_trace_chain(entries))["verified"]) if entries else True,
        "latest_hash": (
            str((verification or verify_trace_chain(entries)).get("latest_hash") or "")
            if entries
            else ""
        ),
    }


def verify_trace_chain(entries: list[dict[str, Any]], *, config: AutopilotConfig | None = None) -> dict[str, Any]:
    from autopilot.core.audit_chain import verify_audit_chain

    return verify_audit_chain(entries, chain_kind="trace", config=config)


def build_trace_audit_bundle(
    config: AutopilotConfig,
    project_id: str,
    *,
    story_id: int | None = None,
    run_id: str | None = None,
    limit: int | None = None,
    include_entries: bool = True,
) -> dict[str, Any]:
    entries = read_trace_entries(config, project_id)
    source_verification = verify_trace_chain(entries, config=config)
    selected_entries = _filter_trace_entries(entries, story_id=story_id, run_id=run_id, limit=limit)
    replay = build_trace_replay(entries, story_id=story_id, run_id=run_id, limit=limit)
    bundle = build_audit_bundle(
        selected_entries,
        chain_kind="trace",
        project_id=project_id,
        run_id=str(run_id or ""),
        story_id=story_id,
        config=config,
        include_entries=include_entries,
        source_verification=source_verification,
        source_entry_count=len(entries),
    )
    bundle["summary"] = build_trace_summary(
        selected_entries,
        verification=dict((bundle.get("audit_chain") or {}).get("verification") or {}),
    )
    bundle["source_summary"] = build_trace_summary(entries, verification=source_verification)
    bundle["replay"] = replay
    return bundle
