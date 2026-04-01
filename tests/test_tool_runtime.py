"""Tests for the runtime tool contract, permissions, hooks, and runner."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.tool_contracts import ToolResult, ToolUseContext, build_tool, get_empty_tool_permission_context
from autopilot.core.tool_hooks import ToolHookDefinition
from autopilot.core.tool_permissions import (
    PermissionRuleValue,
    PermissionUpdate,
    apply_permission_update,
    load_tool_permission_context,
    persist_permission_update,
    resolve_tool_permission_decision,
)
from autopilot.core.tool_runner import run_tool_use


def test_permission_updates_persist_user_and_project_rules(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    persist_permission_update(
        config,
        PermissionUpdate(
            type="add_rules",
            destination="user",
            behavior="ask",
            rules=[PermissionRuleValue(tool_name="execution.pause")],
        ),
    )
    persist_permission_update(
        config,
        PermissionUpdate(
            type="add_rules",
            destination="project",
            behavior="deny",
            project_id="proj_123",
            rules=[PermissionRuleValue(tool_name="execution.archive")],
        ),
    )

    context = load_tool_permission_context(config, project_id="proj_123")

    assert config.tool_permissions_json_path.exists()
    assert context.always_ask_rules["user"] == ["execution.pause"]
    assert context.always_deny_rules["project"] == ["execution.archive"]


def test_tool_runner_permission_hook_can_auto_allow_and_pre_hook_can_mutate_input() -> None:
    tool = build_tool(
        name="demo.write",
        description="Write demo payload.",
        approval_policy="policy",
        execute=lambda tool_input, _: ToolResult(
            status="ok",
            message="ran",
            payload={"value": tool_input["value"]},
        ),
    )
    permission_context = apply_permission_update(
        get_empty_tool_permission_context(),
        PermissionUpdate(
            type="add_rules",
            destination="session",
            behavior="ask",
            rules=[PermissionRuleValue(tool_name="demo.write")],
        ),
    )
    hooks = [
        ToolHookDefinition(
            name="auto-approve",
            event="permission_request",
            handler=lambda _: {"permission_behavior": "allow"},
        ),
        ToolHookDefinition(
            name="rewrite-input",
            event="pre_tool_use",
            handler=lambda _: {"updated_input": {"value": "mutated"}},
        ),
        ToolHookDefinition(
            name="annotate-result",
            event="post_tool_use",
            handler=lambda _: {"result_updates": {"post_hook": True}},
        ),
    ]

    result = run_tool_use(
        tool,
        {"value": "original"},
        ToolUseContext(actor="tester"),
        permission_context=permission_context,
        hooks=hooks,
    )

    assert result.status == "ok"
    assert result.input["value"] == "mutated"
    assert result.tool_result is not None
    assert result.tool_result.payload["value"] == "mutated"
    assert result.tool_result.payload["post_hook"] is True


def test_tool_runner_returns_denied_for_explicit_rule() -> None:
    tool = build_tool(
        name="demo.delete",
        description="Delete demo payload.",
        approval_policy="policy",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )
    permission_context = apply_permission_update(
        get_empty_tool_permission_context(),
        PermissionUpdate(
            type="add_rules",
            destination="session",
            behavior="deny",
            rules=[PermissionRuleValue(tool_name="demo.delete")],
        ),
    )

    result = run_tool_use(
        tool,
        {"value": "ignored"},
        ToolUseContext(actor="tester"),
        permission_context=permission_context,
    )

    assert result.status == "denied"
    assert "demo.delete" in result.message


def test_repeated_denials_escalate_to_explicit_approval(tmp_path: Path) -> None:
    tool = build_tool(
        name="demo.pause",
        description="Pause execution.",
        approval_policy="ask",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )
    permission_context = apply_permission_update(
        get_empty_tool_permission_context().model_copy(update={"mode": "dont_ask"}),
        PermissionUpdate(
            type="add_rules",
            destination="session",
            behavior="ask",
            rules=[PermissionRuleValue(tool_name="demo.pause")],
        ),
    )
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    first = resolve_tool_permission_decision(
        tool,
        {},
        permission_context,
        config=config,
        project_id="proj_demo",
        record_denial=True,
    )
    second = resolve_tool_permission_decision(
        tool,
        {},
        permission_context,
        config=config,
        project_id="proj_demo",
        record_denial=True,
    )
    third = resolve_tool_permission_decision(
        tool,
        {},
        permission_context,
        config=config,
        project_id="proj_demo",
        record_denial=True,
    )

    assert first.behavior == "deny"
    assert first.denial_count == 1
    assert second.behavior == "deny"
    assert second.denial_count == 2
    assert third.behavior == "ask"
    assert third.denial_count == 3
    assert third.escalation_required is True


def test_tool_runner_denial_breaker_escalates_to_approval(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    tool = build_tool(
        name="execution.pause",
        description="Pause one execution project.",
        approval_policy="policy",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )
    permission_context = apply_permission_update(
        get_empty_tool_permission_context(),
        PermissionUpdate(
            type="add_rules",
            destination="session",
            behavior="deny",
            rules=[PermissionRuleValue(tool_name="execution.pause")],
        ),
    )
    use_context = ToolUseContext(config=config, actor="tester", project_id="proj_123")

    first = run_tool_use(tool, {}, use_context, permission_context=permission_context)
    second = run_tool_use(tool, {}, use_context, permission_context=permission_context)
    third = run_tool_use(tool, {}, use_context, permission_context=permission_context)

    assert first.status == "denied"
    assert second.status == "denied"
    assert third.status == "approval_required"
    assert "explicit approval" in third.message
