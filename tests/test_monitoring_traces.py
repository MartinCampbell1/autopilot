"""Tests for trace monitoring and forensic replay helpers."""

from __future__ import annotations

from autopilot.core.monitoring.traces import annotate_trace_entries, build_trace_monitor, build_trace_replay


def test_annotate_trace_entries_derives_run_ids_and_sequences() -> None:
    entries = [
        {"timestamp": "2026-04-02T00:00:00+00:00", "kind": "project_event", "event": "run_started"},
        {"timestamp": "2026-04-02T00:01:00+00:00", "kind": "iteration_record", "story_id": 1, "status": "approved"},
        {"timestamp": "2026-04-02T00:02:00+00:00", "kind": "project_event", "event": "run_finished"},
        {"timestamp": "2026-04-02T00:03:00+00:00", "kind": "project_event", "event": "run_started"},
    ]

    annotated = annotate_trace_entries(entries)

    assert annotated[0]["run_id"] == "run-1"
    assert annotated[1]["run_id"] == "run-1"
    assert annotated[3]["run_id"] == "run-2"
    assert annotated[3]["run_sequence"] == 2


def test_build_trace_monitor_compares_latest_two_runs() -> None:
    entries = [
        {"timestamp": "2026-04-02T00:00:00+00:00", "kind": "project_event", "event": "run_started", "run_id": "sess-1"},
        {
            "timestamp": "2026-04-02T00:01:00+00:00",
            "kind": "iteration_record",
            "run_id": "sess-1",
            "story_id": 1,
            "status": "approved",
            "iteration_usage": {"total_tokens": 100, "estimated_cost_usd": 0.01},
            "critic_approved": True,
        },
        {"timestamp": "2026-04-02T00:02:00+00:00", "kind": "project_event", "event": "run_completed", "run_id": "sess-1"},
        {"timestamp": "2026-04-02T00:03:00+00:00", "kind": "project_event", "event": "run_started", "run_id": "sess-2"},
        {
            "timestamp": "2026-04-02T00:04:00+00:00",
            "kind": "iteration_record",
            "run_id": "sess-2",
            "story_id": 1,
            "status": "critic_rejected",
            "iteration_usage": {"total_tokens": 180, "estimated_cost_usd": 0.03},
            "critic_approved": False,
            "quality_regression": True,
        },
        {"timestamp": "2026-04-02T00:05:00+00:00", "kind": "project_event", "event": "critic_rejected", "run_id": "sess-2"},
        {"timestamp": "2026-04-02T00:06:00+00:00", "kind": "project_event", "event": "run_failed", "run_id": "sess-2"},
    ]

    monitor = build_trace_monitor(entries)

    assert len(monitor["runs"]) == 2
    assert monitor["runs"][-1]["failure_count"] == 2
    assert monitor["comparison"]["cost_regression"] is True
    assert monitor["comparison"]["reliability_regression"] is True
    assert monitor["recent_failures"][-1]["event"] == "run_failed"


def test_build_trace_replay_filters_by_story_and_run() -> None:
    entries = [
        {"timestamp": "2026-04-02T00:00:00+00:00", "kind": "project_event", "event": "run_started", "run_id": "sess-1"},
        {"timestamp": "2026-04-02T00:01:00+00:00", "kind": "iteration_record", "run_id": "sess-1", "story_id": 1, "status": "approved"},
        {"timestamp": "2026-04-02T00:02:00+00:00", "kind": "iteration_record", "run_id": "sess-1", "story_id": 2, "status": "approved"},
    ]

    replay = build_trace_replay(entries, story_id=2, run_id="sess-1")

    assert replay["entry_count"] == 1
    assert replay["entries"][0]["story_id"] == 2
    assert replay["entries"][0]["run_id"] == "sess-1"
