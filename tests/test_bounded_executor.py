"""Unit tests for bounded execution-blueprint follow-through."""

from __future__ import annotations

from autopilot.core.bounded_executor import execute_bounded_execution_blueprint
from autopilot.core.config import AutopilotConfig
from autopilot.core.execution_blueprint import plan_execution_blueprint


def test_bounded_executor_routes_preview_blueprint_to_preview_terminal(tmp_path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    plan = plan_execution_blueprint(
        config,
        actions=[
            {
                "action_key": "agent:1:update_budget_policy",
                "action_type": "suggested_command",
                "command": "update_budget_policy",
                "project_id": "proj_1",
            }
        ],
        requested_mode="auto",
        policy_profile="",
    )
    assert plan.blueprint is not None

    result = execute_bounded_execution_blueprint(
        plan.blueprint,
        actions=[
            {
                "action_key": "agent:1:update_budget_policy",
                "action_type": "suggested_command",
                "command": "update_budget_policy",
                "project_id": "proj_1",
            }
        ],
        step_executor=lambda step, action: {"status": "planned_execute", "command_result": {"command": action["command"]}},
        continue_on_error=True,
    )

    assert result.visited_node_ids == ["step_1"]
    assert result.terminal_verdict.state == "completed"
    assert result.step_results[0].result["command_result"]["command"] == "update_budget_policy"
