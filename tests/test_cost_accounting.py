"""Tests for cost and token accounting helpers."""

from __future__ import annotations

from autopilot.core.cost_accounting import (
    record_iteration_cost,
    start_run_cost_bucket,
    summarize_invocation_usage,
)
from autopilot.core.models import IterationRecord


def test_summarize_invocation_usage_parses_tokens_and_estimates_cost(monkeypatch) -> None:
    monkeypatch.setenv(
        "AUTOPILOT_PRICING_JSON",
        '{"codex":{"input_per_million_usd":10,"output_per_million_usd":20}}',
    )

    usage = summarize_invocation_usage(
        "Input tokens: 100\nOutput tokens: 50\nCached tokens: 20\n",
        provider="codex",
        role="worker",
    )

    assert usage["tracked_invocations"] == 1
    assert usage["priced_invocations"] == 1
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50
    assert usage["cached_tokens"] == 20
    assert usage["estimated_cost_usd"] == 0.002


def test_record_iteration_cost_accumulates_run_story_project_and_agent_usage() -> None:
    state: dict = {}
    start_run_cost_bucket(state, started_at="2026-03-31T00:00:00+00:00")
    iteration = IterationRecord(
        story_id=7,
        iteration=1,
        profile_used="acc1",
        provider="codex",
        gates_passed=True,
        worker_usage={
            "invocations": 1,
            "tracked_invocations": 1,
            "priced_invocations": 0,
            "input_tokens": 120,
            "output_tokens": 30,
            "cached_tokens": 0,
            "total_tokens": 150,
            "estimated_cost_usd": 0.0,
        },
        critic_usage={
            "invocations": 1,
            "tracked_invocations": 1,
            "priced_invocations": 0,
            "input_tokens": 40,
            "output_tokens": 10,
            "cached_tokens": 0,
            "total_tokens": 50,
            "estimated_cost_usd": 0.0,
        },
    )

    usage = record_iteration_cost(
        state,
        story_id=7,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
        iteration_record=iteration,
    )

    assert usage["project"]["invocations"] == 2
    assert usage["project"]["total_tokens"] == 200
    assert usage["run"]["tracked_invocations"] == 2
    assert usage["stories"]["7"]["input_tokens"] == 160
    assert usage["agents"]["codex/acc1"]["total_tokens"] == 150
    assert usage["agents"]["codex/acc2"]["total_tokens"] == 50
