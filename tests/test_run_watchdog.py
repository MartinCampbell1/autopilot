"""Tests for runtime run/story watchdog checks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autopilot.core.run_watchdog import check_runtime_watchdog


def test_check_runtime_watchdog_detects_story_timeout() -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=3700)
    state = {
        "budget_policy": {
            "story_max_runtime_seconds": 3600,
            "run_max_runtime_seconds": 28800,
        },
        "budget_usage": {
            "project": {"worker_iterations": 0, "critic_reviews": 0},
            "run": {"started_at": datetime.now(timezone.utc).isoformat(), "worker_iterations": 0, "critic_reviews": 0},
            "stories": {},
            "agents": {},
            "last_exhaustion_reason": None,
            "last_watchdog_reason": None,
            "auto_paused_at": None,
        },
        "story_state": {
            "4": {
                "status": "in_progress",
                "started_at": started_at.isoformat(),
            }
        },
    }

    decision = check_runtime_watchdog(state, story_id=4, now=datetime.now(timezone.utc))

    assert decision.triggered is True
    assert decision.scope == "story"
    assert decision.story_id == 4
    assert "Story watchdog triggered for story 4" in decision.reason


def test_check_runtime_watchdog_detects_run_timeout() -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=301)
    state = {
        "budget_policy": {
            "story_max_runtime_seconds": 3600,
            "run_max_runtime_seconds": 300,
        },
        "budget_usage": {
            "project": {"worker_iterations": 0, "critic_reviews": 0},
            "run": {"started_at": started_at.isoformat(), "worker_iterations": 0, "critic_reviews": 0},
            "stories": {},
            "agents": {},
            "last_exhaustion_reason": None,
            "last_watchdog_reason": None,
            "auto_paused_at": None,
        },
        "story_state": {},
    }

    decision = check_runtime_watchdog(state, now=datetime.now(timezone.utc))

    assert decision.triggered is True
    assert decision.scope == "run"
    assert "Run watchdog triggered" in decision.reason


def test_check_runtime_watchdog_ignores_non_running_story() -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=3700)
    state = {
        "budget_policy": {
            "story_max_runtime_seconds": 3600,
            "run_max_runtime_seconds": 28800,
        },
        "budget_usage": {
            "project": {"worker_iterations": 0, "critic_reviews": 0},
            "run": {"started_at": datetime.now(timezone.utc).isoformat(), "worker_iterations": 0, "critic_reviews": 0},
            "stories": {},
            "agents": {},
            "last_exhaustion_reason": None,
            "last_watchdog_reason": None,
            "auto_paused_at": None,
        },
        "story_state": {
            "4": {
                "status": "done",
                "started_at": started_at.isoformat(),
            }
        },
    }

    decision = check_runtime_watchdog(state, story_id=4, now=datetime.now(timezone.utc))

    assert decision.triggered is False
