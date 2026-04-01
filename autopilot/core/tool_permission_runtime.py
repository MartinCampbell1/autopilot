"""Domain helpers for tool-permission approval runtimes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from autopilot.core.approval_runtime import ApprovalRuntimeRecord, get_approval_runtime, settle_approval_runtime
from autopilot.core.config import AutopilotConfig

ToolPermissionResolutionOutcome = Literal["allow", "deny"]
ToolPermissionResolutionSource = Literal["user", "channel"]


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_tool_permission_runtime(record: ApprovalRuntimeRecord) -> bool:
    kind = str(record.metadata.get("kind") or "").strip().lower()
    return kind.startswith("tool_permission")


def get_tool_permission_runtime(
    config: AutopilotConfig,
    approval_runtime_id: str,
) -> ApprovalRuntimeRecord | None:
    """Return one tool-permission runtime if it exists."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id)
    if record is None or not _is_tool_permission_runtime(record):
        return None
    return record


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
    "resolve_tool_permission_runtime",
]
