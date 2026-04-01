"""Tests for per-agent mailbox primitives."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.agent_mailbox import (
    acknowledge_agent_mailbox_message,
    list_agent_mailbox_messages,
    poll_agent_mailbox_messages,
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
    assert messages[0].delivery_sequence > 0
    assert messages[1].delivery_sequence > 0

    acked = acknowledge_agent_mailbox_message(config, messages[0].id, actor="founderos")
    assert acked.status == "acked"
    assert acked.acknowledged_by == "founderos"
    assert len(list_agent_mailbox_messages(config, status="unacked")) == 1


def test_poll_agent_mailbox_messages_uses_delivery_sequence_cursor_and_acknowledges(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    publish_agent_mailbox_messages(
        config,
        project_id="proj_123",
        runtime_agent_ids=["agt_1"],
        message_type="approval_pending",
        payload={"approval_id": "apr_1"},
        dedupe_key="apr_1:pending",
        approval_id="apr_1",
    )
    publish_agent_mailbox_messages(
        config,
        project_id="proj_123",
        runtime_agent_ids=["agt_1"],
        message_type="approval_pending",
        payload={"approval_id": "apr_2"},
        dedupe_key="apr_2:pending",
        approval_id="apr_2",
    )
    republished = publish_agent_mailbox_messages(
        config,
        project_id="proj_123",
        runtime_agent_ids=["agt_1"],
        message_type="approval_pending",
        payload={"approval_id": "apr_1", "republished": True},
        dedupe_key="apr_1:pending",
        approval_id="apr_1",
    )[0]

    first_page = poll_agent_mailbox_messages(config, runtime_agent_id="agt_1", project_id="proj_123", limit=1)
    second_page = poll_agent_mailbox_messages(
        config,
        runtime_agent_id="agt_1",
        project_id="proj_123",
        after_sequence=first_page[-1].delivery_sequence,
        acknowledge=True,
        actor="worker:a",
    )

    assert len(first_page) == 1
    assert first_page[0].approval_id == "apr_2"
    assert len(second_page) == 1
    assert second_page[0].id == republished.id
    assert second_page[0].status == "acked"
    assert second_page[0].acknowledged_by == "worker:a"
    assert second_page[0].delivery_sequence > first_page[0].delivery_sequence
