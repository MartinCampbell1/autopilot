"""Unit tests for execution-blueprint planning and caching."""

from __future__ import annotations

from autopilot.core.config import AutopilotConfig
from autopilot.core.execution_blueprint import plan_execution_blueprint


def test_plan_execution_blueprint_caches_by_family(tmp_path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    actions = [
        {
            "action_key": "agent:1:update_budget_policy",
            "action_type": "suggested_command",
            "command": "update_budget_policy",
            "project_id": "proj_1",
        }
    ]

    plan = plan_execution_blueprint(
        config,
        actions=actions,
        requested_mode="auto",
        policy_profile="",
    )
    replay = plan_execution_blueprint(
        config,
        actions=actions,
        requested_mode="auto",
        policy_profile="",
    )

    assert plan.strategy == "bounded_blueprint"
    assert plan.cache_hit is False
    assert plan.blueprint is not None
    assert replay.strategy == "bounded_blueprint"
    assert replay.cache_hit is True
    assert replay.blueprint is not None
    assert replay.blueprint.id == plan.blueprint.id
    assert replay.blueprint.cache_key == plan.blueprint.cache_key
    assert replay.blueprint.task_family == plan.blueprint.task_family
