"""Knowledge distillation from working-log events into durable memory and skills."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.memory_graph import build_memory_graph_snapshot, rebuild_memory_graph
from autopilot.core.session_memory import (
    ExtractedSkillRecord,
    SessionMemoryRecord,
    append_working_log,
    load_session_memory,
    load_working_log,
    save_session_memory,
    upsert_memories,
    upsert_skills,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class KnowledgeDistillationResult(BaseModel):
    processed_entry_count: int = 0
    memory_count: int = 0
    skill_count: int = 0
    graph_snapshot: dict[str, Any] = Field(default_factory=dict)


def _memory_type_for_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    if normalized in {"critic_feedback", "guardrail", "failure", "verification_failed"}:
        return "feedback"
    if normalized in {"user_note", "user_request"}:
        return "user"
    if normalized in {"reference_note", "tool_reference"}:
        return "reference"
    return "project"


def _title_for_entry(kind: str, summary: str, story_id: int | None) -> str:
    normalized = str(kind or "").strip().replace("_", " ")
    if story_id is not None:
        return f"Story #{story_id}: {normalized}"
    return normalized.title() or summary[:80]


def _tags_for_entry(kind: str, summary: str) -> list[str]:
    normalized = str(kind or "").strip().lower()
    tags: list[str] = []
    if normalized in {"failure", "verification_failed", "critic_feedback"}:
        tags.append("failure")
    if normalized in {"verification_passed", "story_completed", "verified_fix"}:
        tags.append("verified_fix")
    if "decision" in normalized:
        tags.append("decision")
    if re.search(r"\bverified\b", summary, re.IGNORECASE):
        tags.append("verified_fix")
    return sorted(set(tags))


def distill_session_memory(project_path: Path) -> KnowledgeDistillationResult:
    """Process new working-log entries into durable memory and graph state."""

    state = load_session_memory(project_path)
    entries = load_working_log(project_path)
    new_entries: list[Any] = []
    if state.last_distilled_entry_id:
        seen = False
        for entry in entries:
            if seen:
                new_entries.append(entry)
            elif entry.entry_id == state.last_distilled_entry_id:
                seen = True
        if not seen:
            new_entries = entries
    else:
        new_entries = entries

    now = _utcnow_iso()
    memories: list[SessionMemoryRecord] = []
    skills: list[ExtractedSkillRecord] = []
    for entry in new_entries:
        memories.append(
            SessionMemoryRecord(
                memory_id=f"mem-{entry.entry_id}",
                memory_type=_memory_type_for_kind(entry.kind),
                title=_title_for_entry(entry.kind, entry.summary, entry.story_id),
                summary=entry.summary,
                source=entry.source,
                story_id=entry.story_id,
                tags=_tags_for_entry(entry.kind, entry.summary),
                created_at=entry.created_at,
                updated_at=now,
                evidence_entry_ids=[entry.entry_id],
                metadata=dict(entry.metadata),
            )
        )
        if str(entry.kind).strip().lower() in {"story_completed", "verified_fix"}:
            label = str(entry.metadata.get("story_title") or f"Story #{entry.story_id or '?'}").strip()
            skills.append(
                ExtractedSkillRecord(
                    skill_id=f"skill-{entry.story_id or 'general'}-{re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-') or 'completion'}",
                    label=label,
                    summary=entry.summary,
                    story_id=entry.story_id,
                    created_at=entry.created_at,
                    updated_at=now,
                    evidence_entry_ids=[entry.entry_id],
                    metadata=dict(entry.metadata),
                )
            )

    if memories:
        upsert_memories(project_path, memories)
    if skills:
        upsert_skills(project_path, skills)
    latest_state = load_session_memory(project_path).model_copy(
        update={
            "last_distilled_entry_id": entries[-1].entry_id if entries else "",
            "working_log_count": len(entries),
        }
    )
    save_session_memory(project_path, latest_state)
    rebuild_memory_graph(project_path)
    return KnowledgeDistillationResult(
        processed_entry_count=len(new_entries),
        memory_count=len(load_session_memory(project_path).memories),
        skill_count=len(load_session_memory(project_path).skills),
        graph_snapshot=build_memory_graph_snapshot(project_path),
    )


def ensure_completed_story_skills(project_path: Path, stories: list[dict[str, Any]]) -> KnowledgeDistillationResult:
    """Ensure completed stories are represented in skill memory, even across sessions."""

    state = load_session_memory(project_path)
    known_skills = {
        (skill.story_id, skill.label.strip().lower())
        for skill in state.skills
    }
    for story in stories:
        status = str(story.get("status") or "").strip().lower()
        if status not in {"done", "skipped"}:
            continue
        label = str(story.get("title") or f"Story #{story.get('id') or '?'}").strip()
        key = (int(story.get("id")) if story.get("id") is not None else None, label.lower())
        if key in known_skills:
            continue
        append_working_log(
            project_path,
            kind="story_completed",
            summary=f"Completed story #{story.get('id')}: {story.get('title') or ''}. {story.get('description') or ''}".strip(),
            source="project_store",
            story_id=int(story.get("id")) if story.get("id") is not None else None,
            metadata={
                "story_title": label,
                "story_status": status,
                "story_tags": list(story.get("tags") or []),
            },
        )
        known_skills.add(key)
    return distill_session_memory(project_path)


__all__ = [
    "KnowledgeDistillationResult",
    "distill_session_memory",
    "ensure_completed_story_skills",
]
