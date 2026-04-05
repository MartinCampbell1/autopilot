"""Tests for unified runtime budget enforcement helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from autopilot.core.budget_enforcer import (
    check_budget_enforcement,
    reserve_iteration_with_budget_enforcement,
)
from autopilot.core.runtime_budgets import ensure_budget_state


def test_check_budget_enforcement_returns_watchdog_metadata() -> None:
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

    decision = check_budget_enforcement(state, story_id=4, now=datetime.now(timezone.utc))

    assert decision.allowed is False
    assert decision.kind == "watchdog"
    assert decision.scope == "story"
    assert decision.story_id == 4
    assert decision.elapsed_seconds > decision.limit_seconds
    assert decision.as_event_extra()["scope"] == "story"


def test_reserve_iteration_with_budget_enforcement_updates_usage_when_allowed() -> None:
    state: dict = {}
    ensure_budget_state(state)

    decision = reserve_iteration_with_budget_enforcement(
        state,
        story_id=1,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert decision.allowed is True
    assert state["budget_usage"]["project"]["worker_iterations"] == 1
    assert state["budget_usage"]["run"]["worker_iterations"] == 1
    assert state["budget_usage"]["stories"]["1"]["worker_iterations"] == 1


def test_reserve_iteration_with_budget_enforcement_reports_budget_exhaustion() -> None:
    state = {
        "budget_policy": {
            "project_max_worker_iterations": 1,
            "project_max_critic_reviews": 1,
            "run_max_worker_iterations": 1,
            "run_max_critic_reviews": 1,
            "story_max_worker_iterations": 1,
            "story_max_critic_reviews": 1,
            "agent_max_worker_iterations": 1,
            "agent_max_critic_reviews": 1,
            "run_max_runtime_seconds": 28800,
            "story_max_runtime_seconds": 7200,
            "auto_pause_on_exhaustion": True,
        },
        "budget_usage": {
            "project": {"worker_iterations": 1, "critic_reviews": 1},
            "run": {"started_at": None, "worker_iterations": 1, "critic_reviews": 1},
            "stories": {"7": {"worker_iterations": 1, "critic_reviews": 1}},
            "agents": {
                "codex/acc1": {"worker_iterations": 1, "critic_reviews": 0},
                "codex/acc2": {"worker_iterations": 0, "critic_reviews": 1},
            },
            "last_exhaustion_reason": None,
            "last_watchdog_reason": None,
            "auto_paused_at": None,
        },
    }

    decision = reserve_iteration_with_budget_enforcement(
        state,
        story_id=7,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert decision.allowed is False
    assert decision.kind == "budget"
    assert "budget exhausted" in decision.reason


def test_reserve_iteration_with_budget_enforcement_does_not_consume_budget_after_watchdog() -> None:
    started_at = datetime.now(timezone.utc) - timedelta(seconds=3700)
    state = {
        "budget_policy": {
            "story_max_runtime_seconds": 3600,
            "run_max_runtime_seconds": 28800,
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "run_max_worker_iterations": 120,
            "run_max_critic_reviews": 120,
            "story_max_worker_iterations": 12,
            "story_max_critic_reviews": 12,
            "agent_max_worker_iterations": 60,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
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
            "9": {
                "status": "in_progress",
                "started_at": started_at.isoformat(),
            }
        },
    }

    decision = reserve_iteration_with_budget_enforcement(
        state,
        story_id=9,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
        now=datetime.now(timezone.utc),
    )

    assert decision.allowed is False
    assert decision.kind == "watchdog"
    assert state["budget_usage"]["project"]["worker_iterations"] == 0
    assert state["budget_usage"]["run"]["worker_iterations"] == 0
