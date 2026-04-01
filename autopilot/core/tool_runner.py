"""Runtime tool execution lifecycle."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.tool_contracts import (
    ToolDef,
    ToolPermissionContext,
    ToolResult,
    ToolUseContext,
    get_empty_tool_permission_context,
)
from autopilot.core.tool_hooks import (
    HookExecutionRecord,
    ToolHookDefinition,
    execute_hooks,
    execute_permission_request_hooks,
    run_pre_tool_use_hooks,
)
from autopilot.core.tool_permissions import PermissionDecision, resolve_tool_permission_decision
from autopilot.core.tool_result_storage import store_large_tool_result


class ToolRunResult(BaseModel):
    """Full result envelope for one tool execution."""

    status: str
    tool_name: str
    message: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    permission: PermissionDecision | None = None
    tool_result: ToolResult | None = None
    hooks: list[HookExecutionRecord] = Field(default_factory=list)


def run_tool_use(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    use_context: ToolUseContext,
    *,
    permission_context: ToolPermissionContext | None = None,
    hooks: list[ToolHookDefinition] | None = None,
) -> ToolRunResult:
    """Run one tool through permission checks, hooks, and execution."""

    normalized_input = dict(tool_input or {})
    resolved_permission_context = permission_context or get_empty_tool_permission_context()
    hook_records: list[HookExecutionRecord] = []

    permission_decision = resolve_tool_permission_decision(
        tool,
        normalized_input,
        resolved_permission_context,
        config=use_context.config,
        project_id=use_context.project_id,
        record_denial=True,
    )
    if permission_decision.behavior == "ask":
        permission_hook_result = execute_permission_request_hooks(
            tool,
            normalized_input,
            use_context,
            permission_decision,
            hooks=hooks,
        )
        hook_records.extend(permission_hook_result.records)
        normalized_input = dict(permission_hook_result.tool_input)
        if permission_hook_result.blocked:
            return ToolRunResult(
                status="blocked",
                tool_name=tool.name,
                message=permission_hook_result.message,
                input=normalized_input,
                permission=permission_hook_result.permission_decision or permission_decision,
                hooks=hook_records,
            )
        permission_decision = permission_hook_result.permission_decision or permission_decision

    if permission_decision.behavior == "ask":
        return ToolRunResult(
            status="approval_required",
            tool_name=tool.name,
            message=permission_decision.message,
            input=normalized_input,
            permission=permission_decision,
            hooks=hook_records,
        )

    if permission_decision.behavior == "deny":
        return ToolRunResult(
            status="denied",
            tool_name=tool.name,
            message=permission_decision.message,
            input=normalized_input,
            permission=permission_decision,
            hooks=hook_records,
        )

    pre_hook_result = run_pre_tool_use_hooks(tool, normalized_input, use_context, hooks=hooks)
    hook_records.extend(pre_hook_result.records)
    normalized_input = dict(pre_hook_result.tool_input)
    if pre_hook_result.blocked:
        return ToolRunResult(
            status="blocked",
            tool_name=tool.name,
            message=pre_hook_result.message,
            input=normalized_input,
            permission=permission_decision,
            hooks=hook_records,
        )

    try:
        tool_result = tool.execute(normalized_input, use_context)
    except Exception as exc:
        failure_records, failure_outputs = execute_hooks(
            event="post_tool_use_failure",
            tool=tool,
            tool_input=normalized_input,
            use_context=use_context,
            hooks=hooks,
            permission_decision=permission_decision,
            error=exc,
        )
        hook_records.extend(failure_records)
        message = str(exc)
        for output in failure_outputs:
            if output.message:
                message = output.message
                break
        return ToolRunResult(
            status="error",
            tool_name=tool.name,
            message=message,
            input=normalized_input,
            permission=permission_decision,
            hooks=hook_records,
        )

    post_records, post_outputs = execute_hooks(
        event="post_tool_use",
        tool=tool,
        tool_input=normalized_input,
        use_context=use_context,
        hooks=hooks,
        permission_decision=permission_decision,
        tool_result=tool_result,
    )
    hook_records.extend(post_records)
    for output in post_outputs:
        if output.result_updates:
            tool_result.payload.update(output.result_updates)
        if output.message:
            tool_result.message = output.message
    tool_result = store_large_tool_result(tool.name, tool_result, use_context)

    return ToolRunResult(
        status=str(tool_result.status or "ok"),
        tool_name=tool.name,
        message=tool_result.message,
        input=normalized_input,
        permission=permission_decision,
        tool_result=tool_result,
        hooks=hook_records,
    )
