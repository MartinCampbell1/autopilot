"""Domain helpers for tool-permission approval runtimes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from autopilot.core.approval_runtime import (
    ApprovalRuntimeRecord,
    get_approval_runtime,
    list_approval_runtimes,
    settle_approval_runtime,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.tool_permissions import PermissionDecision

ToolPermissionResolutionOutcome = Literal["allow", "deny"]
ToolPermissionResolutionSource = Literal["user", "channel"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_tool_permission_runtime(record: ApprovalRuntimeRecord) -> bool:
    kind = str(record.metadata.get("kind") or "").strip().lower()
    return kind.startswith("tool_permission")


def tool_permission_runtime_key(project_id: str, tool_name: str, tool_use_id: str) -> str:
    """Return the stable runtime key for one tool-permission request."""

    normalized_project_id = str(project_id or "").strip()
    normalized_tool_name = str(tool_name or "").strip()
    normalized_tool_use_id = str(tool_use_id or "").strip()
    if not normalized_project_id or not normalized_tool_name or not normalized_tool_use_id:
        return ""
    return f"tool-permission:{normalized_project_id}:{normalized_tool_name}:{normalized_tool_use_id}"


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _string_value(value: Any) -> str:
    return str(value or "").strip()


def _first_string(candidates: list[dict[str, Any]], key: str) -> str:
    for candidate in candidates:
        value = _string_value(candidate.get(key))
        if value:
            return value
    return ""


def _first_reasons(candidates: list[dict[str, Any]]) -> list[str]:
    for candidate in candidates:
        reasons = [str(reason).strip() for reason in candidate.get("reasons") or [] if str(reason).strip()]
        if reasons:
            return reasons
    return []


def _pending_stage(record: ApprovalRuntimeRecord) -> str:
    pending = _dict_value(record.metadata.get("pending"))
    stage = _string_value(pending.get("stage"))
    if stage:
        return stage
    classifier = _dict_value(record.metadata.get("classifier"))
    stage = _string_value(classifier.get("stage"))
    if stage == "pending_classifier":
        return stage
    return ""


def permission_decision_from_tool_permission_runtime(
    record: ApprovalRuntimeRecord,
) -> PermissionDecision | None:
    """Project one persisted tool-permission runtime into a permission decision."""

    if not _is_tool_permission_runtime(record):
        return None

    status = _string_value(record.status)
    if status == "resolved":
        behavior = _string_value(record.outcome).lower()
    elif status == "pending":
        behavior = _pending_stage(record)
    else:
        behavior = ""
    if behavior not in {"allow", "deny", "pending_classifier", "pending_user", "pending_hook"}:
        return None

    payload = _dict_value(record.payload)
    metadata_bridge = _dict_value(record.metadata.get("bridge_decision"))
    metadata_classifier = _dict_value(record.metadata.get("classifier"))
    candidates: list[dict[str, Any]] = []
    if behavior:
        candidates.append(_dict_value(payload.get(behavior)))
    if behavior == "pending_classifier":
        candidates.append(_dict_value(payload.get("classifier")))
        candidates.append(_dict_value(payload.get("classifier_decision")))
        candidates.append(metadata_classifier)
    candidates.append(_dict_value(payload.get("bridge_decision")))
    candidates.append(metadata_bridge)
    candidates.append(_dict_value(payload.get("resolution")))
    candidates.append(payload)

    message = _string_value(record.message) or _first_string(candidates, "message")
    reasons = _first_reasons(candidates)
    if not reasons and message:
        reasons = [message]
    rule_source = _first_string(candidates, "rule_source") or (
        "classifier" if behavior == "pending_classifier" else ""
    )
    matched_rule = _first_string(candidates, "matched_rule")
    denial_count_raw = _first_string(candidates, "denial_count")
    try:
        denial_count = int(denial_count_raw or 0)
    except ValueError:
        denial_count = 0
    escalation_required = any(bool(candidate.get("escalation_required")) for candidate in candidates)

    return PermissionDecision(
        behavior=behavior,
        message=message,
        reasons=reasons,
        rule_source=rule_source or None,
        matched_rule=matched_rule or None,
        denial_count=denial_count,
        escalation_required=escalation_required,
    )


def get_tool_permission_runtime(
    config: AutopilotConfig,
    approval_runtime_id: str = "",
    *,
    key: str = "",
) -> ApprovalRuntimeRecord | None:
    """Return one tool-permission runtime if it exists."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None or not _is_tool_permission_runtime(record):
        return None
    return record


def get_tool_permission_runtime_decision(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str = "",
    key: str = "",
) -> tuple[ApprovalRuntimeRecord, PermissionDecision] | None:
    """Return the current pending/resolved decision for one tool-permission runtime."""

    record = get_tool_permission_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None:
        return None
    decision = permission_decision_from_tool_permission_runtime(record)
    if decision is None:
        return None
    return record, decision


def list_tool_permission_runtimes(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    runtime_agent_id: str | None = None,
    status: str | None = None,
    pending_stage: str | None = None,
) -> list[ApprovalRuntimeRecord]:
    """List tool-permission runtimes with lightweight filters."""

    records = list_approval_runtimes(
        config,
        project_id=project_id,
        status=status,
        runtime_agent_id=runtime_agent_id,
    )
    normalized_pending_stage = str(pending_stage or "").strip()
    filtered: list[ApprovalRuntimeRecord] = []
    for record in records:
        if not _is_tool_permission_runtime(record):
            continue
        if normalized_pending_stage:
            current_pending_stage = str((record.metadata.get("pending") or {}).get("stage") or "").strip()
            if current_pending_stage != normalized_pending_stage:
                continue
        filtered.append(record)
    filtered.sort(key=lambda item: (item.created_at, item.id))
    return filtered


def serialize_tool_permission_runtime(record: ApprovalRuntimeRecord) -> dict[str, object]:
    """Normalize one tool-permission runtime for control-plane consumers."""

    pending = dict(record.metadata.get("pending") or {})
    resolution = dict(record.payload.get("resolution") or {})
    return {
        **record.model_dump(),
        "kind": str(record.metadata.get("kind") or ""),
        "pending_stage": str(pending.get("stage") or ""),
        "tool_name": str(record.metadata.get("tool_name") or pending.get("tool_name") or ""),
        "tool_use_id": str(record.metadata.get("tool_use_id") or pending.get("tool_use_id") or ""),
        "resolved_behavior": str(pending.get("resolved_behavior") or record.outcome or ""),
        "resolved_by": str(pending.get("resolved_by") or resolution.get("actor") or ""),
        "resolved_source": str(pending.get("resolved_source") or resolution.get("source") or record.winner_source or ""),
    }


def resolve_tool_permission_runtime(
    config: AutopilotConfig,
    approval_runtime_id: str,
    *,
    outcome: ToolPermissionResolutionOutcome,
    actor: str,
    note: str = "",
    source: ToolPermissionResolutionSource = "user",
) -> ApprovalRuntimeRecord:
    """Resolve one pending tool-permission runtime through an explicit user/channel decision."""

    record = get_tool_permission_runtime(config, approval_runtime_id)
    if record is None:
        raise KeyError(approval_runtime_id)
    if record.status == "resolved":
        raise RuntimeError(f"Tool-permission runtime {approval_runtime_id} is already resolved.")

    normalized_actor = str(actor or "").strip() or "human"
    normalized_note = str(note or "").strip()
    pending_metadata = dict(record.metadata.get("pending") or {})
    pending_stage = str(pending_metadata.get("stage") or "").strip()
    tool_name = str(record.metadata.get("tool_name") or pending_metadata.get("tool_name") or "").strip()
    tool_use_id = str(record.metadata.get("tool_use_id") or pending_metadata.get("tool_use_id") or "").strip()
    outcome_label = "allowed" if outcome == "allow" else "denied"
    message = normalized_note or (
        f"Tool `{tool_name or 'unknown'}` {outcome_label} by {source} decision from {normalized_actor}."
    )
    resolution_payload = {
        "actor": normalized_actor,
        "note": normalized_note,
        "source": source,
        "outcome": outcome,
        "pending_stage": pending_stage,
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "resolved_at": _utcnow_iso(),
    }
    payload = {
        **dict(record.payload or {}),
        "resolution": resolution_payload,
    }
    return settle_approval_runtime(
        config,
        approval_runtime_id=record.id,
        source=source,
        outcome=outcome,
        message=message,
        payload=payload,
        metadata_updates={
            "lifecycle": {
                "stage": "resolved",
                "source": source,
                "actor": normalized_actor,
                "pending_stage": pending_stage,
            },
            "pending": {
                "stage": pending_stage,
                "resolved_behavior": outcome,
                "resolved_by": normalized_actor,
                "resolved_source": source,
                "resolved_at": resolution_payload["resolved_at"],
            },
        },
        mailbox_message_type=f"tool_permission_{source}_{outcome}",
    )


__all__ = [
    "ToolPermissionResolutionOutcome",
    "ToolPermissionResolutionSource",
    "get_tool_permission_runtime",
    "get_tool_permission_runtime_decision",
    "list_tool_permission_runtimes",
    "permission_decision_from_tool_permission_runtime",
    "serialize_tool_permission_runtime",
    "resolve_tool_permission_runtime",
    "tool_permission_runtime_key",
]
