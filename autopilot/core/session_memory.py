"""Durable session memory and append-only working log helpers."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json

MEMORY_VERSION = 1
DEFAULT_MEMORY_LIMIT = 96
DEFAULT_SKILL_LIMIT = 48
DEFAULT_RECENT_LOG_LIMIT = 12


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized or "memory"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_atomic_write_json(path, payload)


class WorkingLogEntry(BaseModel):
    """Append-only event in the per-project working log."""

    entry_id: str
    created_at: str
    kind: str
    summary: str
    source: str = "runtime"
    story_id: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionMemoryRecord(BaseModel):
    """Distilled structured memory record."""

    memory_id: str
    memory_type: str
    title: str
    summary: str
    source: str = "distilled"
    story_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    evidence_entry_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedSkillRecord(BaseModel):
    """Learned skill extracted from a completed story."""

    skill_id: str
    label: str
    summary: str
    story_id: int | None = None
    created_at: str
    updated_at: str
    evidence_entry_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionMemoryState(BaseModel):
    """Persisted durable memory state for one project."""

    version: int = MEMORY_VERSION
    updated_at: str = Field(default_factory=_utcnow_iso)
    last_distilled_entry_id: str = ""
    working_log_count: int = 0
    memories: list[SessionMemoryRecord] = Field(default_factory=list)
    skills: list[ExtractedSkillRecord] = Field(default_factory=list)


def memory_root(project_path: Path) -> Path:
    return project_path / ".ralph" / "memory"


def working_log_path(project_path: Path) -> Path:
    return memory_root(project_path) / "working-log.jsonl"


def session_memory_path(project_path: Path) -> Path:
    return memory_root(project_path) / "session-memory.json"


def _normalize_summary(text: str, *, max_chars: int = 800) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def append_working_log(
    project_path: Path,
    *,
    kind: str,
    summary: str,
    source: str = "runtime",
    story_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkingLogEntry:
    """Append one normalized working-log entry to disk."""

    entry = WorkingLogEntry(
        entry_id=f"log-{uuid.uuid4().hex[:12]}",
        created_at=_utcnow_iso(),
        kind=str(kind or "").strip().lower() or "event",
        summary=_normalize_summary(summary),
        source=str(source or "runtime").strip() or "runtime",
        story_id=story_id,
        metadata=dict(metadata or {}),
    )
    path = working_log_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry.model_dump(), ensure_ascii=False) + "\n")
    return entry


def load_working_log(project_path: Path, *, limit: int | None = None) -> list[WorkingLogEntry]:
    """Load persisted working-log entries from disk."""

    path = working_log_path(project_path)
    if not path.exists():
        return []
    entries: list[WorkingLogEntry] = []
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            entries.append(WorkingLogEntry.model_validate_json(line))
        except Exception:
            continue
    if limit is not None and limit >= 0:
        return entries[-limit:]
    return entries


def load_session_memory(project_path: Path) -> SessionMemoryState:
    """Load session memory state from disk, or return an empty state."""

    path = session_memory_path(project_path)
    if not path.exists():
        return SessionMemoryState()
    try:
        return SessionMemoryState.model_validate_json(path.read_text())
    except Exception:
        return SessionMemoryState()


def save_session_memory(project_path: Path, state: SessionMemoryState) -> SessionMemoryState:
    """Persist one session memory state snapshot."""

    updated = state.model_copy(update={"updated_at": _utcnow_iso()})
    _atomic_write_json(session_memory_path(project_path), updated.model_dump())
    return updated


def _memory_key(record: SessionMemoryRecord) -> tuple[str, int | None, str]:
    return (record.memory_type, record.story_id, record.title.strip().lower())


def _skill_key(record: ExtractedSkillRecord) -> tuple[int | None, str]:
    return (record.story_id, record.label.strip().lower())


def upsert_memories(
    project_path: Path,
    records: list[SessionMemoryRecord],
    *,
    max_memories: int = DEFAULT_MEMORY_LIMIT,
) -> SessionMemoryState:
    """Merge distilled memory records into persisted state."""

    state = load_session_memory(project_path)
    by_key = {_memory_key(record): record for record in state.memories}
    for record in records:
        existing = by_key.get(_memory_key(record))
        if existing is None:
            by_key[_memory_key(record)] = record
            continue
        by_key[_memory_key(record)] = existing.model_copy(
            update={
                "summary": record.summary,
                "updated_at": record.updated_at,
                "tags": sorted(set(existing.tags + record.tags)),
                "evidence_entry_ids": list(dict.fromkeys(existing.evidence_entry_ids + record.evidence_entry_ids)),
                "metadata": {**existing.metadata, **record.metadata},
            }
        )
    memories = sorted(by_key.values(), key=lambda item: (item.updated_at, item.created_at, item.memory_id))
    trimmed = memories[-max_memories:]
    updated = state.model_copy(
        update={
            "memories": trimmed,
            "working_log_count": len(load_working_log(project_path)),
        }
    )
    return save_session_memory(project_path, updated)


def upsert_skills(
    project_path: Path,
    records: list[ExtractedSkillRecord],
    *,
    max_skills: int = DEFAULT_SKILL_LIMIT,
) -> SessionMemoryState:
    """Merge extracted skills into persisted state."""

    state = load_session_memory(project_path)
    by_key = {_skill_key(record): record for record in state.skills}
    for record in records:
        existing = by_key.get(_skill_key(record))
        if existing is None:
            by_key[_skill_key(record)] = record
            continue
        by_key[_skill_key(record)] = existing.model_copy(
            update={
                "summary": record.summary,
                "updated_at": record.updated_at,
                "evidence_entry_ids": list(dict.fromkeys(existing.evidence_entry_ids + record.evidence_entry_ids)),
                "metadata": {**existing.metadata, **record.metadata},
            }
        )
    skills = sorted(by_key.values(), key=lambda item: (item.updated_at, item.created_at, item.skill_id))
    trimmed = skills[-max_skills:]
    updated = state.model_copy(update={"skills": trimmed})
    return save_session_memory(project_path, updated)


def build_memory_snapshot(project_path: Path) -> dict[str, Any]:
    """Return a compact summary of persisted session memory."""

    state = load_session_memory(project_path)
    recent_log = load_working_log(project_path, limit=DEFAULT_RECENT_LOG_LIMIT)
    type_counts: dict[str, int] = {}
    for memory in state.memories:
        type_counts[memory.memory_type] = type_counts.get(memory.memory_type, 0) + 1
    return {
        "version": state.version,
        "working_log_count": len(load_working_log(project_path)),
        "memory_count": len(state.memories),
        "skill_count": len(state.skills),
        "memory_type_counts": type_counts,
        "last_distilled_entry_id": state.last_distilled_entry_id,
        "updated_at": state.updated_at,
        "recent_memories": [record.model_dump() for record in state.memories[-6:]],
        "skills": [record.model_dump() for record in state.skills[-6:]],
        "recent_working_log": [entry.model_dump() for entry in recent_log],
    }


def render_session_memory_context(project_path: Path, *, max_chars: int = 1200) -> str:
    """Render a compact textual memory summary for prompt inclusion."""

    snapshot = build_memory_snapshot(project_path)
    lines: list[str] = []
    for record in snapshot["recent_memories"][-4:]:
        prefix = f"[{record['memory_type']}]"
        story = f" story #{record['story_id']}" if record.get("story_id") is not None else ""
        lines.append(f"- {prefix}{story} {record['title']}: {record['summary']}")
    if snapshot["skills"]:
        labels = ", ".join(record["label"] for record in snapshot["skills"][-3:])
        lines.append(f"- [skills] {labels}")
    if not lines:
        return ""
    rendered = "\n".join(lines)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max_chars - 3].rstrip() + "..."


__all__ = [
    "DEFAULT_MEMORY_LIMIT",
    "DEFAULT_RECENT_LOG_LIMIT",
    "ExtractedSkillRecord",
    "SessionMemoryRecord",
    "SessionMemoryState",
    "WorkingLogEntry",
    "append_working_log",
    "build_memory_snapshot",
    "load_session_memory",
    "load_working_log",
    "memory_root",
    "render_session_memory_context",
    "save_session_memory",
    "session_memory_path",
    "upsert_memories",
    "upsert_skills",
    "working_log_path",
]
