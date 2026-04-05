"""Runtime tool execution lifecycle."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.action_classifier import render_projected_tool_use
from autopilot.core.approval_runtime import (
    annotate_approval_runtime,
    create_or_reuse_approval_runtime,
    get_approval_runtime,
    settle_approval_runtime,
    wait_for_approval_runtime_mailbox_resolution,
    wait_for_approval_runtime_resolution,
)
from autopilot.core.structured_runtime import get_active_structured_io
from autopilot.core.shadow_audit import compose_shadow_audit_decision, create_shadow_audit_record
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
from autopilot.core.tool_permission_runtime import (
    get_tool_permission_runtime,
    get_tool_permission_runtime_decision,
    tool_permission_runtime_key,
)
from autopilot.core.tool_permissions import PermissionDecision, resolve_tool_permission_decision
from autopilot.core.tool_permissions import has_permissions_to_use_tool
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


def _quarantine_tool_result_if_needed(
    *,
    tool: ToolDef,
    tool_result: ToolResult,
    use_context: ToolUseContext,
    tool_use_id: str,
) -> tuple[str, str, str]:
    rendered_content = json.dumps(
        {
            "tool_name": tool.name,
            "tool_use_id": tool_use_id,
            "status": str(tool_result.status or "ok"),
            "message": str(tool_result.message or ""),
            "payload": dict(tool_result.payload or {}),
            "metadata": dict(tool_result.metadata or {}),
        },
        indent=2,
        ensure_ascii=False,
    )
    decision, content, metadata_updates = compose_shadow_audit_decision(
        tool_result.metadata,
        payload=dict(tool_result.payload or {}),
        content=rendered_content,
    )
    if decision is None:
        return "", "", ""

    summary = str(decision.summary or "").strip() or f"Tool `{tool.name}` output was quarantined by shadow audit."
    rendered_content = content or rendered_content

    audit_record_id = ""
    if use_context.config is not None:
        audit_record = create_shadow_audit_record(
            use_context.config,
            project_id=str(use_context.project_id or "").strip(),
            orchestrator_session_id=str(use_context.orchestrator_session_id or "").strip(),
            runtime_agent_ids=list(use_context.runtime_agent_ids),
            source_kind="tool_result",
            source_name=tool.name,
            source_id=tool_use_id,
            action=decision.action,
            summary=summary,
            findings=list(decision.findings),
            content=rendered_content,
            metadata={
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
                "tool_status": str(tool_result.status or "ok"),
                **metadata_updates,
            },
        )
        audit_record_id = audit_record.id

    return summary, audit_record_id, decision.action


def _coerce_optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _pending_tool_permission_wait_settings(use_context: ToolUseContext) -> tuple[bool, float]:
    runtime = get_active_structured_io()
    enabled_raw = use_context.metadata.get("tool_permission_wait_for_resolution")
    if enabled_raw is None and runtime is not None:
        enabled_raw = runtime.metadata.get("tool_permission_wait_for_resolution")
    enabled = _coerce_optional_bool(enabled_raw)

    timeout_raw = use_context.metadata.get("tool_permission_resolution_timeout_sec")
    if timeout_raw is None and runtime is not None:
        timeout_raw = runtime.metadata.get("tool_permission_resolution_timeout_sec")
    try:
        timeout = float(timeout_raw)
    except (TypeError, ValueError):
        timeout = 0.0

    if enabled is None:
        enabled = timeout > 0
    if not enabled or timeout <= 0:
        return False, 0.0
    return True, timeout


def _await_pending_tool_permission_resolution(
    *,
    tool: ToolDef,
    use_context: ToolUseContext,
    tool_use_id: str,
    approval_runtime_id: str = "",
    runtime_key: str = "",
) -> tuple[PermissionDecision | None, str]:
    wait_enabled, wait_timeout_sec = _pending_tool_permission_wait_settings(use_context)
    if not wait_enabled or wait_timeout_sec <= 0 or use_context.config is None:
        return None, ""

    resolved_runtime_key = runtime_key or _tool_permission_runtime_key(tool, use_context, tool_use_id)
    resolved_approval_runtime_id = str(approval_runtime_id or "").strip()
    mailbox_runtime_agent_id = next(
        (str(item).strip() for item in use_context.runtime_agent_ids if str(item).strip()),
        "",
    )
    if mailbox_runtime_agent_id and (resolved_approval_runtime_id or resolved_runtime_key):
        try:
            runtime_record = wait_for_approval_runtime_mailbox_resolution(
                use_context.config,
                approval_runtime_id=resolved_approval_runtime_id,
                key=resolved_runtime_key,
                runtime_agent_id=mailbox_runtime_agent_id,
                wait_timeout_sec=wait_timeout_sec,
            )
        except (KeyError, TimeoutError, ValueError):
            runtime_record = None
        else:
            runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
            if runtime_decision is not None and runtime_decision.behavior in {"allow", "deny"}:
                use_context.metadata["approval_runtime_id"] = runtime_record.id
                return runtime_decision, "tool_runner.pending_runtime_mailbox"

    if not resolved_approval_runtime_id and not resolved_runtime_key:
        return None, ""
    try:
        runtime_record = wait_for_approval_runtime_resolution(
            use_context.config,
            approval_runtime_id=resolved_approval_runtime_id,
            key=resolved_runtime_key,
            wait_timeout_sec=wait_timeout_sec,
        )
    except (KeyError, TimeoutError):
        return None, ""
    runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
    if runtime_decision is not None and runtime_decision.behavior in {"allow", "deny"}:
        use_context.metadata["approval_runtime_id"] = runtime_record.id
        return runtime_decision, "tool_runner.pending_runtime_fallback"
    return None, ""


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
    mode = raw.get("mode") or use_context.metadata.get("permission_classifier_mode")
    if mode is not None:
        payload["mode"] = str(mode).strip() or "sync"
    return payload


def _materialize_pending_classifier_runtime(
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
    *,
    tool_use_id: str,
    permission_decision: PermissionDecision,
    classifier_context: dict[str, Any],
) -> str:
    if use_context.config is None or not str(use_context.project_id or "").strip():
        return ""
    approval_runtime = create_or_reuse_approval_runtime(
        use_context.config,
        key=f"tool-permission:{use_context.project_id}:{tool.name}:{tool_use_id}",
        project_id=use_context.project_id,
        runtime_agent_ids=use_context.runtime_agent_ids,
        metadata={
            "kind": "tool_permission_classifier",
            "tool_name": tool.name,
            "tool_use_id": tool_use_id,
            "actor": use_context.actor,
            "source": "classifier",
            "orchestrator_session_id": str(use_context.orchestrator_session_id or "").strip(),
        },
    )
    annotate_approval_runtime(
        use_context.config,
        approval_runtime_id=approval_runtime.id,
        metadata_updates={
            "classifier": {
                "stage": "pending_classifier",
                "mode": str(classifier_context.get("mode") or "deferred"),
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
            }
        },
        payload_updates={
            "classifier": {
                "message": permission_decision.message,
                "matched_rule": permission_decision.matched_rule,
                "projected_tool_use": render_projected_tool_use(tool, tool_input),
                "user_text": str(classifier_context.get("user_text") or ""),
                "decision_reason": str(classifier_context.get("decision_reason") or ""),
            }
        },
        mailbox_message_type="tool_permission_classifier_pending",
        mailbox_payload={
            "tool_name": tool.name,
            "tool_use_id": tool_use_id,
            "message": permission_decision.message,
            "behavior": permission_decision.behavior,
            "matched_rule": permission_decision.matched_rule,
        },
    )
    return approval_runtime.id


def _materialize_pending_permission_runtime(
    tool: ToolDef,
    use_context: ToolUseContext,
    *,
    tool_use_id: str,
    permission_decision: PermissionDecision,
    stage: str,
    specific_message_type: str,
    source: str,
) -> str:
    if use_context.config is None or not str(use_context.project_id or "").strip():
        return ""
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
            "source": source,
            "orchestrator_session_id": str(use_context.orchestrator_session_id or "").strip(),
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
    annotate_approval_runtime(
        use_context.config,
        approval_runtime_id=approval_runtime.id,
        metadata_updates={
            "pending": {
                "stage": stage,
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
            }
        },
        payload_updates={
            stage: {
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
                "message": permission_decision.message,
                "matched_rule": permission_decision.matched_rule,
                "reasons": list(permission_decision.reasons),
            }
        },
        mailbox_message_type=specific_message_type,
        mailbox_payload={
            "tool_name": tool.name,
            "tool_use_id": tool_use_id,
            "message": permission_decision.message,
            "behavior": permission_decision.behavior,
            "matched_rule": permission_decision.matched_rule,
        },
    )
    return approval_runtime.id


def _tool_permission_runtime_key(
    tool: ToolDef,
    use_context: ToolUseContext,
    tool_use_id: str,
) -> str:
    return tool_permission_runtime_key(
        str(use_context.project_id or ""),
        tool.name,
        tool_use_id,
    )


def _observe_existing_tool_permission_runtime(
    tool: ToolDef,
    use_context: ToolUseContext,
    *,
    tool_use_id: str,
) -> tuple[str, str, PermissionDecision | None]:
    if use_context.config is None:
        return "", "", None
    runtime_key = _tool_permission_runtime_key(tool, use_context, tool_use_id)
    if not runtime_key:
        return "", "", None
    existing_runtime = get_tool_permission_runtime(use_context.config, key=runtime_key)
    if existing_runtime is None:
        return runtime_key, "", None
    _ensure_tool_permission_runtime(
        tool,
        use_context,
        tool_use_id=tool_use_id,
        permission_source="tool_runner.runtime_reuse",
    )
    observed = get_tool_permission_runtime_decision(use_context.config, key=runtime_key)
    if observed is None:
        return runtime_key, "", None
    runtime_record, decision = observed
    use_context.metadata["approval_runtime_id"] = runtime_record.id
    return runtime_key, runtime_record.id, decision


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
            "orchestrator_session_id": str(use_context.orchestrator_session_id or "").strip(),
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
                "classifier_mode": str(classifier_context.get("mode") or "").strip() or None,
                "classifier_fail_open": bool(classifier_context.get("fail_open")),
                "agent_id": use_context.runtime_agent_ids[0] if use_context.runtime_agent_ids else None,
            },
            timeout=timeout,
            request_id=request_id,
        )
    except (TimeoutError, RuntimeError, ValueError):
        return _wait_for_runtime_from_mailbox_or_disk()

    behavior = str(response.get("behavior") or "").strip().lower()
    if behavior not in {"allow", "ask", "deny", "pending_classifier", "pending_user", "pending_hook"}:
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
    approval_runtime_id = str(response.get("approval_runtime_id") or "").strip()
    if approval_runtime_id:
        use_context.metadata["approval_runtime_id"] = approval_runtime_id

    if runtime_key and use_context.config is not None:
        if decision.behavior in {"pending_classifier", "pending_user", "pending_hook"}:
            annotate_approval_runtime(
                use_context.config,
                key=runtime_key,
                metadata_updates={
                    "bridge_decision": {
                        "behavior": decision.behavior,
                        "message": decision.message,
                        "rule_source": decision.rule_source,
                        "matched_rule": decision.matched_rule,
                        "approval_runtime_id": approval_runtime_id,
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


def _coordinate_classifier_permission_decision(
    tool: ToolDef,
    decision: PermissionDecision,
    use_context: ToolUseContext,
    *,
    tool_use_id: str,
    classifier_context: dict[str, Any],
) -> tuple[PermissionDecision, str]:
    if decision.rule_source != "classifier" or not bool(classifier_context.get("enabled")):
        return decision, "tool_runner"
    if use_context.config is None or not str(use_context.project_id or "").strip():
        return decision, "tool_runner.classifier"

    runtime_key = _ensure_tool_permission_runtime(
        tool,
        use_context,
        tool_use_id=tool_use_id,
        permission_source="tool_runner.classifier",
    )
    if not runtime_key:
        return decision, "tool_runner.classifier"

    existing_runtime = get_approval_runtime(use_context.config, key=runtime_key)
    if existing_runtime is not None and existing_runtime.status == "resolved":
        runtime_decision = _permission_decision_from_runtime(runtime_record=existing_runtime)
        if runtime_decision is not None:
            return runtime_decision, "tool_runner.classifier_runtime"

    payload = {
        "reasons": list(decision.reasons),
        "rule_source": decision.rule_source,
        "matched_rule": decision.matched_rule,
        "denial_count": decision.denial_count,
        "escalation_required": decision.escalation_required,
        "tool_name": tool.name,
        "tool_use_id": tool_use_id,
        "user_text_present": bool(str(classifier_context.get("user_text") or "").strip()),
    }
    metadata_updates = {
        "classifier": {
            "matched_rule": decision.matched_rule,
            "message": decision.message,
        }
    }
    if decision.behavior == "ask":
        annotate_approval_runtime(
            use_context.config,
            key=runtime_key,
            metadata_updates={
                **metadata_updates,
                "classifier": {
                    **metadata_updates["classifier"],
                    "stage": "pending_classifier",
                },
            },
            payload_updates={"classifier_decision": payload},
            mailbox_message_type="permission_classifier_pending",
            mailbox_payload=payload,
        )
        return decision, "tool_runner.classifier_pending"

    runtime_record = settle_approval_runtime(
        use_context.config,
        key=runtime_key,
        source="classifier",
        outcome=decision.behavior,
        message=decision.message,
        payload=payload,
        metadata_updates={
            **metadata_updates,
            "classifier": {
                **metadata_updates["classifier"],
                "stage": "resolved",
            },
        },
        mailbox_message_type=f"permission_classifier_{decision.behavior}",
    )
    runtime_decision = _permission_decision_from_runtime(runtime_record=runtime_record)
    if runtime_decision is not None:
        source = "tool_runner.classifier" if runtime_record.winner_source == "classifier" else "tool_runner.classifier_runtime"
        return runtime_decision, source
    return decision, "tool_runner.classifier"


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
    reused_runtime_key, reused_approval_runtime_id, reused_runtime_decision = _observe_existing_tool_permission_runtime(
        tool,
        use_context,
        tool_use_id=tool_use_id,
    )
    if reused_runtime_decision is not None:
        bridge_decision = reused_runtime_decision
        permission_source = (
            "tool_runner.runtime_resolved_reuse"
            if reused_runtime_decision.behavior in {"allow", "deny"}
            else "tool_runner.runtime_pending_reuse"
        )
    else:
        bridge_decision, permission_source = _bridge_permission_decision(tool, normalized_input, use_context)
    classifier_context = _permission_classifier_context_from_use_context(use_context)
    precomputed_decision = bridge_decision
    if precomputed_decision is None:
        precomputed_decision = has_permissions_to_use_tool(
            tool,
            normalized_input,
            resolved_permission_context,
            classifier_context=classifier_context,
        )
        if precomputed_decision.rule_source == "classifier":
            precomputed_decision, permission_source = _coordinate_classifier_permission_decision(
                tool,
                precomputed_decision,
                use_context,
                tool_use_id=tool_use_id,
                classifier_context=classifier_context,
            )

    permission_decision = resolve_tool_permission_decision(
        tool,
        normalized_input,
        resolved_permission_context,
        precomputed_decision=precomputed_decision,
        classifier_context=classifier_context,
        config=use_context.config,
        project_id=use_context.project_id,
        record_denial=True,
        actor=use_context.actor,
        source=permission_source,
    )
    if reused_runtime_decision is None and permission_decision.behavior in {"ask", "pending_classifier", "pending_user"}:
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

    if reused_runtime_decision is not None and permission_decision.behavior in {
        "pending_classifier",
        "pending_hook",
        "pending_user",
    }:
        awaited_decision, awaited_source = _await_pending_tool_permission_resolution(
            tool=tool,
            use_context=use_context,
            tool_use_id=tool_use_id,
            approval_runtime_id=reused_approval_runtime_id,
            runtime_key=reused_runtime_key,
        )
        if awaited_decision is not None:
            permission_decision = awaited_decision
            if awaited_source:
                permission_source = awaited_source
        else:
            return ToolRunResult(
                status="approval_required",
                tool_name=tool.name,
                message=permission_decision.message,
                input=normalized_input,
                permission=permission_decision,
                approval_runtime_id=reused_approval_runtime_id,
                hooks=hook_records,
            )

    if permission_decision.behavior == "pending_classifier":
        approval_runtime_id = _materialize_pending_classifier_runtime(
            tool,
            normalized_input,
            use_context,
            tool_use_id=tool_use_id,
            permission_decision=permission_decision,
            classifier_context=classifier_context,
        )
        awaited_decision, awaited_source = _await_pending_tool_permission_resolution(
            tool=tool,
            use_context=use_context,
            tool_use_id=tool_use_id,
            approval_runtime_id=approval_runtime_id,
        )
        if awaited_decision is None:
            return ToolRunResult(
                status="approval_required",
                tool_name=tool.name,
                message=permission_decision.message,
                input=normalized_input,
                permission=permission_decision,
                approval_runtime_id=approval_runtime_id,
                hooks=hook_records,
            )
        permission_decision = awaited_decision
        if awaited_source:
            permission_source = awaited_source

    if permission_decision.behavior == "pending_hook":
        approval_runtime_id = _materialize_pending_permission_runtime(
            tool,
            use_context,
            tool_use_id=tool_use_id,
            permission_decision=permission_decision,
            stage="pending_hook",
            specific_message_type="tool_permission_hook_pending",
            source="tool_runner.pending_hook",
        )
        awaited_decision, awaited_source = _await_pending_tool_permission_resolution(
            tool=tool,
            use_context=use_context,
            tool_use_id=tool_use_id,
            approval_runtime_id=approval_runtime_id,
        )
        if awaited_decision is None:
            return ToolRunResult(
                status="approval_required",
                tool_name=tool.name,
                message=permission_decision.message,
                input=normalized_input,
                permission=permission_decision,
                approval_runtime_id=approval_runtime_id,
                hooks=hook_records,
            )
        permission_decision = awaited_decision
        if awaited_source:
            permission_source = awaited_source

    if permission_decision.behavior in {"ask", "pending_user"}:
        pending_user_decision = (
            permission_decision
            if permission_decision.behavior == "pending_user"
            else permission_decision.model_copy(update={"behavior": "pending_user"})
        )
        approval_runtime_id = _materialize_pending_permission_runtime(
            tool,
            use_context,
            tool_use_id=tool_use_id,
            permission_decision=pending_user_decision,
            stage="pending_user",
            specific_message_type="tool_permission_user_pending",
            source=permission_source,
        )
        awaited_decision, awaited_source = _await_pending_tool_permission_resolution(
            tool=tool,
            use_context=use_context,
            tool_use_id=tool_use_id,
            approval_runtime_id=approval_runtime_id,
        )
        if awaited_decision is None:
            return ToolRunResult(
                status="approval_required",
                tool_name=tool.name,
                message=pending_user_decision.message,
                input=normalized_input,
                permission=pending_user_decision,
                approval_runtime_id=approval_runtime_id,
                hooks=hook_records,
            )
        permission_decision = awaited_decision
        if awaited_source:
            permission_source = awaited_source

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
    quarantine_message, shadow_audit_id, shadow_audit_action = _quarantine_tool_result_if_needed(
        tool=tool,
        tool_result=tool_result,
        use_context=use_context,
        tool_use_id=tool_use_id,
    )
    if quarantine_message:
        blocked_result = None
        if shadow_audit_id:
            blocked_result = ToolResult(
                status="quarantined",
                message=quarantine_message,
                metadata={"shadow_audit_id": shadow_audit_id, "shadow_audit_action": shadow_audit_action},
            )
        return ToolRunResult(
            status="quarantined",
            tool_name=tool.name,
            message=quarantine_message,
            input=normalized_input,
            permission=permission_decision,
            tool_result=blocked_result,
            hooks=hook_records,
        )

    return ToolRunResult(
        status=str(tool_result.status or "ok"),
        tool_name=tool.name,
        message=tool_result.message,
        input=normalized_input,
        permission=permission_decision,
        tool_result=tool_result,
        hooks=hook_records,
    )
