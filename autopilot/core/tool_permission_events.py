"""Project-event helpers for tool-permission runtime lifecycle."""

from __future__ import annotations

from typing import Any

from autopilot.core.config import AutopilotConfig


def _string_value(value: Any) -> str:
    return str(value or "").strip()


def _dict_value(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _runtime_details(record: Any) -> dict[str, Any]:
    metadata = _dict_value(getattr(record, "metadata", {}))
    payload = _dict_value(getattr(record, "payload", {}))
    pending = _dict_value(metadata.get("pending"))
    resolution = _dict_value(payload.get("resolution"))
    pending_stage = _string_value(pending.get("stage"))
    pending_payload = _dict_value(payload.get(pending_stage))
    tool_name = (
        _string_value(metadata.get("tool_name"))
        or _string_value(pending.get("tool_name"))
        or _string_value(resolution.get("tool_name"))
        or _string_value(pending_payload.get("tool_name"))
    )
    tool_use_id = (
        _string_value(metadata.get("tool_use_id"))
        or _string_value(pending.get("tool_use_id"))
        or _string_value(resolution.get("tool_use_id"))
        or _string_value(pending_payload.get("tool_use_id"))
    )
    pending_message = (
        _string_value(pending_payload.get("message"))
        or _string_value(payload.get("message"))
        or _string_value(getattr(record, "message", ""))
    )
    resolution_note = _string_value(resolution.get("note"))
    resolved_message = resolution_note or _string_value(getattr(record, "message", "")) or pending_message
    return {
        "approval_runtime_id": _string_value(getattr(record, "id", "")),
        "project_id": _string_value(getattr(record, "project_id", "")),
        "runtime_agent_ids": list(getattr(record, "runtime_agent_ids", []) or []),
        "approval_id": _string_value(getattr(record, "approval_id", "")),
        "issue_id": _string_value(getattr(record, "issue_id", "")),
        "permission_sync_key": _string_value(getattr(record, "permission_sync_key", "")),
        "kind": _string_value(metadata.get("kind")),
        "status": _string_value(getattr(record, "status", "")),
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "pending_stage": pending_stage,
        "pending_message": pending_message,
        "outcome": _string_value(getattr(record, "outcome", "")),
        "winner_source": _string_value(getattr(record, "winner_source", "")),
        "resolved_behavior": _string_value(pending.get("resolved_behavior")) or _string_value(getattr(record, "outcome", "")),
        "resolved_by": _string_value(pending.get("resolved_by")) or _string_value(resolution.get("actor")),
        "resolved_source": _string_value(pending.get("resolved_source")) or _string_value(resolution.get("source")) or _string_value(getattr(record, "winner_source", "")),
        "resolved_at": _string_value(getattr(record, "resolved_at", "")) or _string_value(resolution.get("resolved_at")),
        "pending_payload": pending_payload,
        "resolution": resolution,
        "resolved_message": resolved_message,
    }


def emit_tool_permission_pending_event(
    config: AutopilotConfig,
    record: Any,
    *,
    event_source: str = "",
) -> dict[str, Any]:
    """Append one project/event-log record for a pending tool-permission runtime."""

    details = _runtime_details(record)
    if not details["project_id"] or not details["pending_stage"]:
        return {}
    from autopilot.core.project_store import emit_project_event

    tool_name = details["tool_name"] or "unknown tool"
    pending_stage = details["pending_stage"].replace("_", " ")
    message = details["pending_message"] or f"Tool `{tool_name}` is waiting for {pending_stage}."
    return emit_project_event(
        config,
        details["project_id"],
        event="tool_permission_runtime_pending",
        status="pending",
        message=message,
        extra={
            "approval_runtime_id": details["approval_runtime_id"],
            "approval_id": details["approval_id"],
            "issue_id": details["issue_id"],
            "permission_sync_key": details["permission_sync_key"],
            "runtime_agent_ids": details["runtime_agent_ids"],
            "runtime_agent_id": details["runtime_agent_ids"][0] if details["runtime_agent_ids"] else "",
            "tool_name": details["tool_name"],
            "tool_use_id": details["tool_use_id"],
            "pending_stage": details["pending_stage"],
            "kind": details["kind"],
            "event_source": _string_value(event_source),
        },
    )


def emit_tool_permission_resolved_event(
    config: AutopilotConfig,
    record: Any,
    *,
    event_source: str = "",
) -> dict[str, Any]:
    """Append one project/event-log record for a resolved tool-permission runtime."""

    details = _runtime_details(record)
    if not details["project_id"]:
        return {}
    from autopilot.core.project_store import emit_project_event

    tool_name = details["tool_name"] or "unknown tool"
    outcome = details["resolved_behavior"] or details["outcome"] or "resolved"
    message = details["resolved_message"] or f"Tool `{tool_name}` permission runtime {outcome}."
    return emit_project_event(
        config,
        details["project_id"],
        event="tool_permission_runtime_resolved",
        status="resolved",
        message=message,
        extra={
            "approval_runtime_id": details["approval_runtime_id"],
            "approval_id": details["approval_id"],
            "issue_id": details["issue_id"],
            "permission_sync_key": details["permission_sync_key"],
            "runtime_agent_ids": details["runtime_agent_ids"],
            "runtime_agent_id": details["runtime_agent_ids"][0] if details["runtime_agent_ids"] else "",
            "tool_name": details["tool_name"],
            "tool_use_id": details["tool_use_id"],
            "pending_stage": details["pending_stage"],
            "resolved_behavior": details["resolved_behavior"] or details["outcome"],
            "resolved_by": details["resolved_by"],
            "resolved_source": details["resolved_source"] or details["winner_source"],
            "resolved_at": details["resolved_at"],
            "kind": details["kind"],
            "event_source": _string_value(event_source),
        },
    )


__all__ = [
    "emit_tool_permission_pending_event",
    "emit_tool_permission_resolved_event",
]
