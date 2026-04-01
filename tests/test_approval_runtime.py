"""Tests for resolve-once approval runtime contexts."""

from __future__ import annotations

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from autopilot.core.agent_mailbox import list_agent_mailbox_messages
from autopilot.core.approval_runtime import (
    ApprovalRuntimeClaim,
    annotate_approval_runtime,
    approval_runtime_lock_path,
    create_or_reuse_approval_runtime,
    get_approval_runtime,
    settle_approval_runtime,
)
from autopilot.core.config import AutopilotConfig


def test_create_or_reuse_approval_runtime_publishes_pending_mailbox(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    first = create_or_reuse_approval_runtime(
        config,
        key="approval:apr_123",
        project_id="proj_123",
        approval_id="apr_123",
        issue_id="iss_123",
        runtime_agent_ids=["agt_1", "agt_2"],
        publish_pending=True,
    )
    second = create_or_reuse_approval_runtime(
        config,
        key="approval:apr_123",
        project_id="proj_123",
        approval_id="apr_123",
        issue_id="iss_123",
        runtime_agent_ids=["agt_2", "agt_3"],
        publish_pending=True,
    )

    messages = list_agent_mailbox_messages(config, approval_runtime_id=first.id)

    assert first.id == second.id
    assert second.runtime_agent_ids == ["agt_1", "agt_2", "agt_3"]
    assert len(messages) == 3
    assert all(message.message_type == "approval_pending" for message in messages)


def test_settle_approval_runtime_is_first_writer_wins_under_race(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    runtime = create_or_reuse_approval_runtime(
        config,
        key="approval:apr_race",
        project_id="proj_123",
        approval_id="apr_race",
        runtime_agent_ids=["agt_1"],
        publish_pending=True,
    )
    barrier = threading.Barrier(2)

    def settle(source: str, outcome: str):
        barrier.wait()
        return settle_approval_runtime(
            config,
            approval_runtime_id=runtime.id,
            source=source,
            outcome=outcome,
            message=f"{source}:{outcome}",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(settle, "hook:auto", "allow")
        right = pool.submit(settle, "user", "deny")
        first = left.result()
        second = right.result()

    stored = get_approval_runtime(config, approval_runtime_id=runtime.id)
    messages = list_agent_mailbox_messages(config, approval_runtime_id=runtime.id)

    assert stored is not None
    assert first.id == second.id == stored.id
    assert first.outcome == second.outcome == stored.outcome
    assert first.winner_source == second.winner_source == stored.winner_source
    assert stored.status == "resolved"
    assert len(stored.settlement_attempts) == 2
    assert sum(1 for attempt in stored.settlement_attempts if attempt["applied"] is True) == 1
    assert sum(1 for attempt in stored.settlement_attempts if attempt["ignored_reason"] == "already_resolved") == 1
    assert any(message.message_type.startswith("approval_") and message.message_type != "approval_pending" for message in messages)


def test_annotate_approval_runtime_can_publish_applied_message(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    runtime = create_or_reuse_approval_runtime(
        config,
        key="approval:apr_apply",
        project_id="proj_123",
        approval_id="apr_apply",
        runtime_agent_ids=["agt_1"],
        publish_pending=True,
    )
    settle_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        source="user",
        outcome="approved",
        message="Approved.",
    )
    updated = annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={"lifecycle": {"stage": "applied"}},
        mailbox_message_type="approval_applied",
        mailbox_payload={"actor": "founderos"},
    )

    messages = list_agent_mailbox_messages(config, approval_runtime_id=runtime.id)

    assert updated.metadata["lifecycle"]["stage"] == "applied"
    assert any(message.message_type == "approval_applied" for message in messages)


def test_settle_approval_runtime_reclaims_stale_lock_and_records_resolution_ids(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    runtime = create_or_reuse_approval_runtime(
        config,
        key="approval:apr_stale",
        project_id="proj_123",
        approval_id="apr_stale",
    )
    lock_path = approval_runtime_lock_path(config, runtime.id)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    claim = ApprovalRuntimeClaim(
        id="apprtclaim_stale",
        key=runtime.key,
        source="hook:auto",
        outcome="deny",
        created_at="2026-04-01T00:00:00+00:00",
    )
    lock_path.write_text(claim.model_dump_json())
    stale_time = time.time() - 120
    os.utime(lock_path, (stale_time, stale_time))

    resolved = settle_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        source="user",
        outcome="approved",
        message="Recovered after stale lock.",
        wait_timeout_sec=0.5,
        stale_after_sec=0.05,
    )

    stored = get_approval_runtime(config, approval_runtime_id=runtime.id)

    assert resolved.status == "resolved"
    assert resolved.claim_id
    assert resolved.resolution_id
    assert stored is not None
    assert stored.winner_source == "user"
    assert not lock_path.exists()
