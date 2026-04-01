"""Tests for explicit tool-permission runtime settlement."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.agent_mailbox import list_agent_mailbox_messages
from autopilot.core.approval_runtime import annotate_approval_runtime, create_or_reuse_approval_runtime
from autopilot.core.config import AutopilotConfig
from autopilot.core.tool_permission_runtime import get_tool_permission_runtime, resolve_tool_permission_runtime


def test_resolve_tool_permission_runtime_preserves_pending_payload_and_publishes_mailbox(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    runtime = create_or_reuse_approval_runtime(
        config,
        key="tool-permission:proj_tool_runtime:demo.pause:toolu_123",
        project_id="proj_tool_runtime",
        runtime_agent_ids=["proj_tool_runtime:1:worker:a"],
        metadata={
            "kind": "tool_permission_request",
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_123",
        },
        publish_pending=True,
        pending_message_type="tool_permission_pending",
        pending_payload={
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_123",
            "message": "Need explicit approval.",
            "behavior": "pending_user",
        },
    )
    annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={
            "pending": {
                "stage": "pending_user",
                "tool_name": "demo.pause",
                "tool_use_id": "toolu_123",
            }
        },
        payload_updates={
            "pending_user": {
                "tool_name": "demo.pause",
                "tool_use_id": "toolu_123",
                "message": "Need explicit approval.",
            }
        },
        mailbox_message_type="tool_permission_user_pending",
        mailbox_payload={"tool_name": "demo.pause", "tool_use_id": "toolu_123"},
    )

    resolved = resolve_tool_permission_runtime(
        config,
        runtime.id,
        outcome="allow",
        actor="founderos",
        note="Explicitly allowed.",
    )
    messages = list_agent_mailbox_messages(config, approval_runtime_id=runtime.id)
    stored = get_tool_permission_runtime(config, runtime.id)

    assert resolved.status == "resolved"
    assert resolved.winner_source == "user"
    assert resolved.outcome == "allow"
    assert resolved.payload["pending_user"]["message"] == "Need explicit approval."
    assert resolved.payload["resolution"]["actor"] == "founderos"
    assert resolved.metadata["pending"]["resolved_behavior"] == "allow"
    assert stored is not None
    assert stored.status == "resolved"
    assert any(message.message_type == "approval_runtime_resolved" for message in messages)
    assert any(message.message_type == "tool_permission_user_allow" for message in messages)
