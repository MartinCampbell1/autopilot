"""Tests for machine-friendly headless runtime helpers."""

import io
import json

from autopilot.core.headless import (
    RUN_EXIT_FAILED,
    RUN_EXIT_PAUSED,
    RUN_EXIT_PRECHECK_FAILED,
    RUN_EXIT_SUCCESS,
    activate_structured_io,
    build_preflight_summary,
    build_run_all_summary,
    emit_headless_event,
    emit_headless_summary,
    build_run_summary,
    exit_code_for_state,
)
from autopilot.core.structured_io import StructuredIO


def test_exit_code_for_state_only_marks_completed_runs_as_success() -> None:
    assert exit_code_for_state({"status": "completed", "paused": False}) == RUN_EXIT_SUCCESS
    assert exit_code_for_state({"status": "failed", "paused": False}) == RUN_EXIT_FAILED
    assert exit_code_for_state({"status": "idle", "paused": False}) == RUN_EXIT_FAILED
    assert exit_code_for_state({"status": "running", "paused": True}) == RUN_EXIT_PAUSED


def test_build_preflight_summary_marks_precheck_failures() -> None:
    summary = build_preflight_summary(
        "/tmp/project",
        project_id="demo-123",
        project_name="Demo",
        message="Project not found.",
    )

    assert summary["project_id"] == "demo-123"
    assert summary["project_name"] == "Demo"
    assert summary["exit_code"] == RUN_EXIT_PRECHECK_FAILED
    assert summary["status"] == "failed"


def test_build_run_summary_tracks_blocked_stories() -> None:
    summary = build_run_summary(
        {"id": "demo-123", "name": "Demo", "path": "/tmp/project"},
        {
            "status": "failed",
            "paused": False,
            "current_story_id": 2,
            "parallel_story_ids": [2],
            "started_at": "2026-03-31T12:00:00+00:00",
            "finished_at": "2026-03-31T12:05:00+00:00",
            "last_error": "Blocked by upstream story.",
            "log_path": "/tmp/autopilot.log",
            "story_state": {
                "1": {"story_id": 1, "status": "done", "blocked_on": []},
                "2": {"story_id": 2, "status": "open", "blocked_on": [1]},
                "3": {"story_id": 3, "status": "merge_blocked", "blocked_on": []},
            },
        },
        exit_code=RUN_EXIT_FAILED,
    )

    assert summary["stories_done"] == 1
    assert summary["stories_total"] == 3
    assert summary["blocked_story_ids"] == [2]
    assert summary["story_status_counts"]["merge_blocked"] == 1
    assert summary["cost"]["run"] == {}


def test_build_run_all_summary_prioritizes_failures_over_pauses() -> None:
    summary = build_run_all_summary(
        [
            {"project_id": "ok", "exit_code": RUN_EXIT_SUCCESS},
            {"project_id": "paused", "exit_code": RUN_EXIT_PAUSED},
            {"project_id": "failed", "exit_code": RUN_EXIT_FAILED},
        ]
    )

    assert summary["exit_code"] == RUN_EXIT_FAILED
    assert summary["failed_projects"] == ["failed"]
    assert summary["paused_projects"] == ["paused"]


def test_headless_emitters_use_structured_io_when_active() -> None:
    output = io.StringIO()
    runtime = StructuredIO(session_id="sess_headless", input_stream=io.StringIO(""), output_stream=output)
    activate_structured_io(runtime)
    try:
        emit_headless_event("run_started", message="Started", project_id="proj_1")
        emit_headless_summary({"kind": "run_summary", "project_id": "proj_1", "exit_code": 0})
    finally:
        activate_structured_io(None)
        runtime.close()

    payloads = [json.loads(line) for line in output.getvalue().splitlines()]
    assert payloads[0]["type"] == "event"
    assert payloads[0]["event"] == "run_started"
    assert payloads[1]["type"] == "result"
    assert payloads[1]["summary"]["kind"] == "run_summary"
