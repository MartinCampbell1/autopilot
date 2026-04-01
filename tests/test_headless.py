"""Tests for machine-friendly headless runtime helpers."""

from autopilot.core.headless import (
    RUN_EXIT_FAILED,
    RUN_EXIT_PAUSED,
    RUN_EXIT_PRECHECK_FAILED,
    RUN_EXIT_SUCCESS,
    build_preflight_summary,
    build_run_all_summary,
    build_run_summary,
    exit_code_for_state,
)


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
