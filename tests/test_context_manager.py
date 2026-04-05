"""Tests for context pressure helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from autopilot.core.adapters import AdapterExecutionRequest
from autopilot.core.context_manager import (
    build_compacted_prompt,
    build_compaction_pipeline,
    build_compact_recovery_prompt,
    execute_with_context_recovery,
    is_prompt_too_long_error,
    render_bounded_feedback,
)
from autopilot.core.session_memory import append_working_log, upsert_memories, SessionMemoryRecord
from autopilot.core.models import Profile


def test_is_prompt_too_long_error_detects_common_provider_signals() -> None:
    assert is_prompt_too_long_error("Prompt is too long for this model.")
    assert is_prompt_too_long_error("maximum context length exceeded")
    assert is_prompt_too_long_error("context_window_exceeded")
    assert not is_prompt_too_long_error("normal worker failure")


def test_build_compact_recovery_prompt_preserves_story_identity() -> None:
    prompt = (
        "You are an autonomous coding agent.\n\n"
        "Selected story #7: Tighten OAuth callback validation\n"
        "Story description: Add explicit allowlist validation for callback URLs and tests. "
        "Read AGENTS.md, read critic feedback, verify thoroughly, update progress, and be careful about the existing repo context.\n"
        "PRD snapshot: .agents/tasks/prd.json\n"
    )

    compact = build_compact_recovery_prompt(prompt)

    assert "Selected story #7" in compact
    assert "PRD snapshot:" in compact
    assert len(compact) < len(prompt)


def test_render_bounded_feedback_spills_full_text_to_artifact(tmp_path: Path) -> None:
    large_feedback = ("failure details\n" * 600).strip()

    rendered = render_bounded_feedback(tmp_path, large_feedback)

    assert "full context stored at" in rendered
    artifact_dir = tmp_path / ".ralph" / "context"
    artifacts = list(artifact_dir.glob("critic-feedback-*.txt"))
    assert len(artifacts) == 1
    assert artifacts[0].read_text() == large_feedback


def test_execute_with_context_recovery_retries_with_compact_prompt(tmp_path: Path) -> None:
    adapter = MagicMock()
    adapter.execute.side_effect = [
        SimpleNamespace(success=False, output="Prompt is too long for this model.", stderr=""),
        SimpleNamespace(success=True, output="fixed", stderr=""),
    ]
    adapter.parse_output.side_effect = [
        SimpleNamespace(text="Prompt is too long for this model.", rate_limited=False),
        SimpleNamespace(text="fixed", rate_limited=False),
    ]
    request = AdapterExecutionRequest(
        profile=Profile(name="acc1", provider="codex", path=str(tmp_path)),
        prompt=(
            "You are an autonomous coding agent.\n"
            "Selected story #3: Fix callback\n"
            "Story description: Tighten OAuth callback validation. Read AGENTS.md, read critic feedback, update progress, and verify the result.\n"
            "PRD snapshot: .agents/tasks/prd.json\n"
        ),
        workdir=tmp_path,
        env={"PATH": "/usr/bin"},
    )

    result, parsed = execute_with_context_recovery(adapter, request)

    assert result.success is True
    assert parsed.text == "fixed"
    assert adapter.execute.call_count == 2
    retry_request = adapter.execute.call_args_list[1].args[0]
    assert "Selected story #3" in retry_request.prompt
    assert len(retry_request.prompt) < len(request.prompt)


def test_build_compaction_pipeline_uses_memory_and_working_log(tmp_path: Path) -> None:
    upsert_memories(
        tmp_path,
        [
            SessionMemoryRecord(
                memory_id="mem-1",
                memory_type="project",
                title="Story #8: Callback repair",
                summary="Verified fix for callback allowlist.",
                story_id=8,
                created_at="2026-04-02T00:00:00+00:00",
                updated_at="2026-04-02T00:00:00+00:00",
            )
        ],
    )
    append_working_log(tmp_path, kind="failure", summary="Previous callback smoke test failed.", story_id=8)
    prompt = (
        "You are an autonomous coding agent.\n"
        "Selected story #8: Callback repair\n"
        "Story description: Tighten callback validation and tests.\n"
        "PRD snapshot: .agents/tasks/prd.json\n"
    )

    bundle = build_compaction_pipeline(tmp_path, prompt)
    compacted = build_compacted_prompt(tmp_path, prompt)

    assert any(item["stage"] == "memory" and item["content"] for item in bundle["stages"])
    assert any(item["stage"] == "working_log" and item["content"] for item in bundle["stages"])
    assert "Memory:" in compacted
    assert "Working Log:" in compacted
