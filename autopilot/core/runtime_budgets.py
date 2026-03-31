"""Runtime budget primitives for project and per-agent execution limits."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_budget_policy() -> dict[str, Any]:
    """Return the default runtime budget policy for one project."""
    return {
        "project_max_worker_iterations": 200,
        "project_max_critic_reviews": 200,
        "agent_max_worker_iterations": 60,
        "agent_max_critic_reviews": 60,
        "auto_pause_on_exhaustion": True,
    }


def default_budget_usage() -> dict[str, Any]:
    """Return the default runtime budget counters for one project."""
    return {
        "project": {
            "worker_iterations": 0,
            "critic_reviews": 0,
        },
        "agents": {},
        "last_exhaustion_reason": None,
        "auto_paused_at": None,
    }


def ensure_budget_state(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Ensure budget policy and usage fields exist in project runtime state."""
    policy = state.setdefault("budget_policy", default_budget_policy())
    usage = state.setdefault("budget_usage", default_budget_usage())

    policy.setdefault("project_max_worker_iterations", 200)
    policy.setdefault("project_max_critic_reviews", 200)
    policy.setdefault("agent_max_worker_iterations", 60)
    policy.setdefault("agent_max_critic_reviews", 60)
    policy.setdefault("auto_pause_on_exhaustion", True)

    project_usage = usage.setdefault("project", {})
    project_usage.setdefault("worker_iterations", 0)
    project_usage.setdefault("critic_reviews", 0)

    usage.setdefault("agents", {})
    usage.setdefault("last_exhaustion_reason", None)
    usage.setdefault("auto_paused_at", None)
    return policy, usage


def _ensure_agent_usage(usage: dict[str, Any], agent_label: str) -> dict[str, int]:
    agent_usage = usage.setdefault("agents", {}).setdefault(
        agent_label,
        {
            "worker_iterations": 0,
            "critic_reviews": 0,
        },
    )
    agent_usage.setdefault("worker_iterations", 0)
    agent_usage.setdefault("critic_reviews", 0)
    return agent_usage


def consume_iteration_budget(
    state: dict[str, Any],
    *,
    worker_label: str,
    critic_label: str,
) -> tuple[bool, str | None]:
    """Consume one worker+critic iteration budget or return the exhaustion reason."""
    policy, usage = ensure_budget_state(state)
    project_usage = usage["project"]
    worker_usage = _ensure_agent_usage(usage, worker_label)
    critic_usage = _ensure_agent_usage(usage, critic_label)

    violations: list[str] = []
    if int(project_usage["worker_iterations"]) + 1 > int(policy["project_max_worker_iterations"]):
        violations.append("project worker iteration budget exhausted")
    if int(project_usage["critic_reviews"]) + 1 > int(policy["project_max_critic_reviews"]):
        violations.append("project critic review budget exhausted")
    if int(worker_usage["worker_iterations"]) + 1 > int(policy["agent_max_worker_iterations"]):
        violations.append(f"worker budget exhausted for {worker_label}")
    if int(critic_usage["critic_reviews"]) + 1 > int(policy["agent_max_critic_reviews"]):
        violations.append(f"critic budget exhausted for {critic_label}")

    if violations:
        reason = "Runtime budget exhausted: " + "; ".join(violations) + "."
        usage["last_exhaustion_reason"] = reason
        if policy.get("auto_pause_on_exhaustion", True):
            usage["auto_paused_at"] = _utcnow_iso()
        return False, reason

    project_usage["worker_iterations"] = int(project_usage["worker_iterations"]) + 1
    project_usage["critic_reviews"] = int(project_usage["critic_reviews"]) + 1
    worker_usage["worker_iterations"] = int(worker_usage["worker_iterations"]) + 1
    critic_usage["critic_reviews"] = int(critic_usage["critic_reviews"]) + 1
    return True, None


def update_budget_policy(
    state: dict[str, Any],
    *,
    updates: dict[str, Any],
) -> dict[str, Any]:
    """Apply partial updates to the project's budget policy."""
    policy, _ = ensure_budget_state(state)
    for key, value in updates.items():
        if value is None:
            continue
        policy[key] = value
    return policy
