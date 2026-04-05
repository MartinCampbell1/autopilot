"""Tests for durable session memory helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.session_memory import (
    SessionMemoryRecord,
    append_working_log,
    build_memory_snapshot,
    load_working_log,
    render_session_memory_context,
    upsert_memories,
)


def test_session_memory_working_log_and_snapshot(tmp_path: Path) -> None:
    append_working_log(tmp_path, kind="user_note", summary="Remember tenant callback constraints.", source="user")
    append_working_log(tmp_path, kind="reference_note", summary="OAuth callback URLs must be allowlisted.", source="docs")

    entries = load_working_log(tmp_path)
    snapshot = build_memory_snapshot(tmp_path)

    assert len(entries) == 2
    assert snapshot["working_log_count"] == 2
    assert snapshot["memory_count"] == 0


def test_session_memory_context_renders_recent_memories(tmp_path: Path) -> None:
    upsert_memories(
        tmp_path,
        [
            SessionMemoryRecord(
                memory_id="mem-1",
                memory_type="project",
                title="Story #4: Callback fix",
                summary="Verified callback validation and tests.",
                story_id=4,
                created_at="2026-04-02T00:00:00+00:00",
                updated_at="2026-04-02T00:00:00+00:00",
            )
        ],
    )

    rendered = render_session_memory_context(tmp_path)

    assert "[project]" in rendered
    assert "Story #4: Callback fix" in rendered
