"""Runtime tool execution lifecycle."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.approval_runtime import create_or_reuse_approval_runtime
from autopilot.core.structured_runtime import get_active_structured_io
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
    approval_runtime_id: str = ""
    tool_result: ToolResult | None = None
    hooks: list[HookExecutionRecord] = Field(default_factory=list)


def _bridge_permission_decision(
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
) -> tuple[PermissionDecision | None, str]:
    """Try resolving tool permissions through the active structured bridge first."""

    runtime = get_active_structured_io()
    if runtime is None:
        return None, "tool_runner"

    bridge_mode = str(runtime.metadata.get("permission_bridge_mode") or "").strip().lower()
    if bridge_mode != "bridge_first":
        return None, "tool_runner"

    timeout_raw = use_context.metadata.get("permission_bridge_timeout_sec", runtime.metadata.get("permission_bridge_timeout_sec", 0.5))
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError):
        timeout = 0.5
    if timeout <= 0:
        timeout = 0.5

    tool_use_id = str(
        use_context.metadata.get("tool_use_id")
        or tool_input.get("tool_use_id")
        or f"toolu_{uuid.uuid4().hex[:12]}"
    ).strip()
    request_id = f"perm_{tool_use_id}"
    try:
        response = runtime.send_request(
            {
                "subtype": "can_use_tool",
                "tool_name": tool.name,
                "input": dict(tool_input),
                "tool_use_id": tool_use_id,
                "description": tool.description,
                "display_name": tool.name,
                "decision_reason": str(use_context.metadata.get("permission_decision_reason") or "").strip() or None,
                "agent_id": use_context.runtime_agent_ids[0] if use_context.runtime_agent_ids else None,
            },
            timeout=timeout,
            request_id=request_id,
        )
    except (TimeoutError, RuntimeError, ValueError):
        return None, "tool_runner.bridge_fallback"

    behavior = str(response.get("behavior") or "").strip().lower()
    if behavior not in {"allow", "ask", "deny"}:
        return None, "tool_runner.bridge_fallback"

    try:
        decision = PermissionDecision(
            behavior=behavior,
            message=str(response.get("message") or ""),
            reasons=[str(reason) for reason in response.get("reasons") or [] if str(reason).strip()],
            rule_source=response.get("rule_source"),
            matched_rule=response.get("matched_rule"),
            denial_count=int(response.get("denial_count") or 0),
            escalation_required=bool(response.get("escalation_required")),
        )
    except Exception:
        return None, "tool_runner.bridge_fallback"

    return decision, "tool_runner.bridge"


def _resolve_tool_use_id(
    use_context: ToolUseContext,
    tool_input: dict[str, Any],
) -> str:
    """Return one stable tool-use id for runtime coordination."""

    resolved = str(use_context.metadata.get("tool_use_id") or tool_input.get("tool_use_id") or "").strip()
    if not resolved:
        resolved = f"toolu_{uuid.uuid4().hex[:12]}"
        use_context.metadata["tool_use_id"] = resolved
    return resolved


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
    tool_use_id = _resolve_tool_use_id(use_context, normalized_input)
    bridge_decision, permission_source = _bridge_permission_decision(tool, normalized_input, use_context)

    permission_decision = resolve_tool_permission_decision(
        tool,
        normalized_input,
        resolved_permission_context,
        precomputed_decision=bridge_decision,
        config=use_context.config,
        project_id=use_context.project_id,
        record_denial=True,
        actor=use_context.actor,
        source=permission_source,
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
        approval_runtime_id = ""
        if use_context.config is not None and str(use_context.project_id or "").strip():
            approval_runtime = create_or_reuse_approval_runtime(
                use_context.config,
                key=f"tool-permission:{use_context.project_id}:{tool.name}:{tool_use_id}",
                project_id=use_context.project_id,
                runtime_agent_ids=use_context.runtime_agent_ids,
                metadata={
                    "kind": "tool_permission_request",
                    "tool_name": tool.name,
                    "tool_use_id": tool_use_id,
                    "actor": use_context.actor,
                    "source": permission_source,
                },
                publish_pending=True,
                pending_message_type="tool_permission_pending",
                pending_payload={
                    "tool_name": tool.name,
                    "tool_use_id": tool_use_id,
                    "message": permission_decision.message,
                    "behavior": permission_decision.behavior,
                },
            )
            approval_runtime_id = approval_runtime.id
        return ToolRunResult(
            status="approval_required",
            tool_name=tool.name,
            message=permission_decision.message,
            input=normalized_input,
            permission=permission_decision,
            approval_runtime_id=approval_runtime_id,
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
