"""Runtime tool execution lifecycle."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.approval_runtime import (
    annotate_approval_runtime,
    create_or_reuse_approval_runtime,
    settle_approval_runtime,
    wait_for_approval_runtime_mailbox_resolution,
    wait_for_approval_runtime_resolution,
)
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


def _permission_classifier_context_from_use_context(use_context: ToolUseContext) -> dict[str, Any]:
    raw = dict(use_context.metadata.get("permission_classifier") or {})
    enabled = raw.get("enabled")
    if enabled is None:
        enabled = True if raw else bool(use_context.metadata.get("permission_classifier_enabled"))
    user_text = str(
        raw.get("user_text")
        or use_context.metadata.get("permission_classifier_user_text")
        or ""
    ).strip()
    decision_reason = str(
        raw.get("decision_reason")
        or use_context.metadata.get("permission_decision_reason")
        or ""
    ).strip()
    fail_open = raw.get("fail_open")
    if fail_open is None:
        fail_open = bool(use_context.metadata.get("permission_classifier_fail_open"))
    max_user_text_chars = raw.get("max_user_text_chars")
    if not enabled and not raw:
        return {}
    payload: dict[str, Any] = {
        "enabled": bool(enabled),
        "user_text": user_text,
        "decision_reason": decision_reason,
        "fail_open": bool(fail_open),
    }
    if max_user_text_chars is not None:
        payload["max_user_text_chars"] = max_user_text_chars
    return payload


def _tool_permission_runtime_key(
    tool: ToolDef,
    use_context: ToolUseContext,
    tool_use_id: str,
) -> str:
    normalized_project_id = str(use_context.project_id or "").strip()
    normalized_tool_use_id = str(tool_use_id or "").strip()
    if not normalized_project_id or not normalized_tool_use_id:
        return ""
    return f"tool-permission:{normalized_project_id}:{tool.name}:{normalized_tool_use_id}"


def _ensure_tool_permission_runtime(
    tool: ToolDef,
    use_context: ToolUseContext,
    *,
    tool_use_id: str,
    permission_source: str,
) -> str:
    if use_context.config is None:
        return ""
    runtime_key = _tool_permission_runtime_key(tool, use_context, tool_use_id)
    if not runtime_key:
        return ""
    runtime = create_or_reuse_approval_runtime(
        use_context.config,
        key=runtime_key,
        project_id=use_context.project_id,
        runtime_agent_ids=use_context.runtime_agent_ids,
        metadata={
            "kind": "tool_permission_request",
            "tool_name": tool.name,
            "tool_use_id": tool_use_id,
            "actor": use_context.actor,
            "source": permission_source,
        },
    )
    use_context.metadata["approval_runtime_id"] = runtime.id
    return runtime_key


def _permission_decision_from_runtime(
    *,
    runtime_record: Any,
) -> PermissionDecision | None:
    behavior = str(getattr(runtime_record, "outcome", "") or "").strip().lower()
    if behavior not in {"allow", "ask", "deny"}:
        return None
    payload = dict(getattr(runtime_record, "payload", {}) or {})
    reasons = [str(reason) for reason in payload.get("reasons") or [] if str(reason).strip()]
    message = str(getattr(runtime_record, "message", "") or payload.get("message") or "").strip()
    if not reasons and message:
        reasons = [message]
    return PermissionDecision(
        behavior=behavior,
        message=message,
        reasons=reasons,
        rule_source=payload.get("rule_source"),
        matched_rule=payload.get("matched_rule"),
        denial_count=int(payload.get("denial_count") or 0),
        escalation_required=bool(payload.get("escalation_required")),
    )


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
    runtime_key = _ensure_tool_permission_runtime(
        tool,
        use_context,
        tool_use_id=tool_use_id,
        permission_source="tool_runner.bridge",
    )
    request_id = f"perm_{tool_use_id}"
    classifier_context = _permission_classifier_context_from_use_context(use_context)

    def _wait_for_runtime_from_mailbox_or_disk() -> tuple[PermissionDecision | None, str]:
        if not runtime_key or use_context.config is None:
            return None, "tool_runner.bridge_fallback"
        mailbox_runtime_agent_id = next(
            (str(item).strip() for item in use_context.runtime_agent_ids if str(item).strip()),
            "",
        )
        if mailbox_runtime_agent_id:
            try:
                runtime_record = wait_for_approval_runtime_mailbox_resolution(
                    use_context.config,
                    key=runtime_key,
                    runtime_agent_id=mailbox_runtime_agent_id,
                    wait_timeout_sec=timeout,
                )
            except (KeyError, TimeoutError, ValueError):
                runtime_record = None
            else:
                runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
                if runtime_decision is not None:
                    return runtime_decision, "tool_runner.bridge_mailbox_fallback"
        try:
            runtime_record = wait_for_approval_runtime_resolution(
                use_context.config,
                key=runtime_key,
                wait_timeout_sec=timeout,
            )
        except (KeyError, TimeoutError):
            return None, "tool_runner.bridge_fallback"
        runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
        if runtime_decision is not None:
            return runtime_decision, "tool_runner.bridge_runtime_fallback"
        return None, "tool_runner.bridge_fallback"

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
                "user_text": str(classifier_context.get("user_text") or "").strip() or None,
                "classifier_enabled": bool(classifier_context.get("enabled")),
                "classifier_fail_open": bool(classifier_context.get("fail_open")),
                "agent_id": use_context.runtime_agent_ids[0] if use_context.runtime_agent_ids else None,
            },
            timeout=timeout,
            request_id=request_id,
        )
    except (TimeoutError, RuntimeError, ValueError):
        return _wait_for_runtime_from_mailbox_or_disk()

    behavior = str(response.get("behavior") or "").strip().lower()
    if behavior not in {"allow", "ask", "deny"}:
        return _wait_for_runtime_from_mailbox_or_disk()

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

    if runtime_key and use_context.config is not None:
        if decision.behavior == "ask":
            annotate_approval_runtime(
                use_context.config,
                key=runtime_key,
                metadata_updates={
                    "bridge_decision": {
                        "behavior": decision.behavior,
                        "message": decision.message,
                        "rule_source": decision.rule_source,
                        "matched_rule": decision.matched_rule,
                    }
                },
                payload_updates={
                    "bridge_decision": {
                        "reasons": list(decision.reasons),
                        "tool_name": tool.name,
                        "tool_use_id": tool_use_id,
                    }
                },
            )
            return decision, "tool_runner.bridge"
        runtime_record = settle_approval_runtime(
            use_context.config,
            key=runtime_key,
            source="bridge",
            outcome=decision.behavior,
            message=decision.message,
            payload={
                "reasons": list(decision.reasons),
                "rule_source": decision.rule_source,
                "matched_rule": decision.matched_rule,
                "denial_count": decision.denial_count,
                "escalation_required": decision.escalation_required,
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
            },
            mailbox_message_type=f"permission_bridge_{decision.behavior}",
        )
        runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
        if runtime_decision is not None:
            bridge_source = "tool_runner.bridge" if runtime_record.winner_source == "bridge" else "tool_runner.bridge_runtime"
            return runtime_decision, bridge_source

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
    classifier_context = _permission_classifier_context_from_use_context(use_context)

    permission_decision = resolve_tool_permission_decision(
        tool,
        normalized_input,
        resolved_permission_context,
        precomputed_decision=bridge_decision,
        classifier_context=classifier_context,
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
