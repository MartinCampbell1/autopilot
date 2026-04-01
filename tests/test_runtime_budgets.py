"""Tests for runtime budget primitives."""

from autopilot.core.runtime_budgets import (
    consume_iteration_budget,
    default_budget_policy,
    ensure_budget_state,
    start_run_budget_bucket,
    update_budget_policy,
)


def test_consume_iteration_budget_updates_project_and_agent_usage() -> None:
    state: dict = {}
    ensure_budget_state(state)

    allowed, reason = consume_iteration_budget(
        state,
        story_id=1,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert allowed is True
    assert reason is None
    assert state["budget_usage"]["project"]["worker_iterations"] == 1
    assert state["budget_usage"]["run"]["worker_iterations"] == 1
    assert state["budget_usage"]["stories"]["1"]["worker_iterations"] == 1
    assert state["budget_usage"]["agents"]["codex/acc1"]["worker_iterations"] == 1
    assert state["budget_usage"]["agents"]["codex/acc2"]["critic_reviews"] == 1


def test_consume_iteration_budget_reports_exhaustion() -> None:
    state = {
        "budget_policy": {
            **default_budget_policy(),
            "project_max_worker_iterations": 1,
            "project_max_critic_reviews": 1,
            "run_max_worker_iterations": 1,
            "run_max_critic_reviews": 1,
            "story_max_worker_iterations": 1,
            "story_max_critic_reviews": 1,
            "agent_max_worker_iterations": 1,
            "agent_max_critic_reviews": 1,
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

    allowed, reason = consume_iteration_budget(
        state,
        story_id=7,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert allowed is False
    assert "budget exhausted" in str(reason)
    assert state["budget_usage"]["auto_paused_at"] is not None


def test_update_budget_policy_applies_partial_changes() -> None:
    state: dict = {}
    policy = update_budget_policy(
        state,
        updates={
            "project_max_worker_iterations": 12,
            "auto_pause_on_exhaustion": False,
        },
    )

    assert policy["project_max_worker_iterations"] == 12
    assert policy["auto_pause_on_exhaustion"] is False


def test_start_run_budget_bucket_resets_run_counters() -> None:
    state = {
        "budget_usage": {
            "project": {"worker_iterations": 4, "critic_reviews": 4},
            "run": {"started_at": "2026-04-01T00:00:00+00:00", "worker_iterations": 3, "critic_reviews": 2},
            "stories": {},
            "agents": {},
            "last_exhaustion_reason": "old",
            "last_watchdog_reason": "old-watchdog",
            "auto_paused_at": "2026-04-01T01:00:00+00:00",
        }
    }

    bucket = start_run_budget_bucket(state, started_at="2026-04-01T02:00:00+00:00")

    assert bucket["started_at"] == "2026-04-01T02:00:00+00:00"
    assert bucket["worker_iterations"] == 0
    assert bucket["critic_reviews"] == 0
    assert state["budget_usage"]["last_exhaustion_reason"] is None
    assert state["budget_usage"]["last_watchdog_reason"] is None
    assert state["budget_usage"]["auto_paused_at"] is None


def test_consume_iteration_budget_reports_story_budget_exhaustion() -> None:
    state = {
        "budget_policy": {
            **default_budget_policy(),
            "story_max_worker_iterations": 1,
            "story_max_critic_reviews": 1,
        },
        "budget_usage": {
            "project": {"worker_iterations": 1, "critic_reviews": 1},
            "run": {"started_at": "2026-04-01T00:00:00+00:00", "worker_iterations": 1, "critic_reviews": 1},
            "stories": {"2": {"worker_iterations": 1, "critic_reviews": 1}},
            "agents": {
                "codex/acc1": {"worker_iterations": 1, "critic_reviews": 0},
                "codex/acc2": {"worker_iterations": 0, "critic_reviews": 1},
            },
            "last_exhaustion_reason": None,
            "last_watchdog_reason": None,
            "auto_paused_at": None,
        },
    }

    allowed, reason = consume_iteration_budget(
        state,
        story_id=2,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert allowed is False
    assert "story worker iteration budget exhausted" in str(reason)
