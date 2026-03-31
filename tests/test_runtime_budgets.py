"""Tests for runtime budget primitives."""

from autopilot.core.runtime_budgets import consume_iteration_budget, default_budget_policy, ensure_budget_state, update_budget_policy


def test_consume_iteration_budget_updates_project_and_agent_usage() -> None:
    state: dict = {}
    ensure_budget_state(state)

    allowed, reason = consume_iteration_budget(
        state,
        worker_label="codex/acc1",
        critic_label="codex/acc2",
    )

    assert allowed is True
    assert reason is None
    assert state["budget_usage"]["project"]["worker_iterations"] == 1
    assert state["budget_usage"]["agents"]["codex/acc1"]["worker_iterations"] == 1
    assert state["budget_usage"]["agents"]["codex/acc2"]["critic_reviews"] == 1


def test_consume_iteration_budget_reports_exhaustion() -> None:
    state = {
        "budget_policy": {
            **default_budget_policy(),
            "project_max_worker_iterations": 1,
            "project_max_critic_reviews": 1,
            "agent_max_worker_iterations": 1,
            "agent_max_critic_reviews": 1,
        },
        "budget_usage": {
            "project": {"worker_iterations": 1, "critic_reviews": 1},
            "agents": {
                "codex/acc1": {"worker_iterations": 1, "critic_reviews": 0},
                "codex/acc2": {"worker_iterations": 0, "critic_reviews": 1},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    }

    allowed, reason = consume_iteration_budget(
        state,
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
