"""Tests for working-log distillation into memory and skills."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.knowledge_distiller import distill_session_memory, ensure_completed_story_skills
from autopilot.core.session_memory import build_memory_snapshot, load_session_memory, append_working_log


def test_distill_session_memory_creates_structured_memory_and_skill(tmp_path: Path) -> None:
    append_working_log(
        tmp_path,
        kind="critic_feedback",
        summary="Verifier found callback regression in redirect validation.",
        source="critic",
        story_id=3,
    )
    append_working_log(
        tmp_path,
        kind="verified_fix",
        summary="Verified callback allowlist fix and pytest coverage.",
        source="runtime",
        story_id=3,
        metadata={"story_title": "Tighten callback validation"},
    )

    result = distill_session_memory(tmp_path)
    snapshot = build_memory_snapshot(tmp_path)
    state = load_session_memory(tmp_path)

    assert result.processed_entry_count == 2
    assert snapshot["memory_count"] == 2
    assert snapshot["skill_count"] == 1
    assert state.memories[-1].memory_type == "project"
    assert "verified_fix" in state.memories[-1].tags


def test_ensure_completed_story_skills_is_idempotent(tmp_path: Path) -> None:
    stories = [
        {"id": 7, "title": "Ship OAuth callback hardening", "description": "Add allowlist validation", "status": "done"}
    ]

    ensure_completed_story_skills(tmp_path, stories)
    ensure_completed_story_skills(tmp_path, stories)
    snapshot = build_memory_snapshot(tmp_path)

    assert snapshot["skill_count"] == 1
