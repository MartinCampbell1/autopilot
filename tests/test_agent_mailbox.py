"""Tests for per-agent mailbox primitives."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.agent_mailbox import (
    acknowledge_agent_mailbox_message,
    list_agent_mailbox_messages,
    publish_agent_mailbox_messages,
)
from autopilot.core.config import AutopilotConfig


def test_publish_agent_mailbox_messages_dedupes_per_agent_and_can_acknowledge(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    first = publish_agent_mailbox_messages(
        config,
        project_id="proj_123",
        runtime_agent_ids=["agt_1", "agt_2"],
        message_type="approval_pending",
        payload={"approval_id": "apr_123"},
        dedupe_key="apr_123:pending",
        approval_id="apr_123",
    )
    second = publish_agent_mailbox_messages(
        config,
        project_id="proj_123",
        runtime_agent_ids=["agt_1", "agt_2"],
        message_type="approval_pending",
        payload={"approval_id": "apr_123", "updated": True},
        dedupe_key="apr_123:pending",
        approval_id="apr_123",
    )

    assert [item.id for item in first] == [item.id for item in second]
    messages = list_agent_mailbox_messages(config, project_id="proj_123")
    assert len(messages) == 2
    assert messages[0].payload["updated"] is True

    acked = acknowledge_agent_mailbox_message(config, messages[0].id, actor="founderos")
    assert acked.status == "acked"
    assert acked.acknowledged_by == "founderos"
    assert len(list_agent_mailbox_messages(config, status="unacked")) == 1
