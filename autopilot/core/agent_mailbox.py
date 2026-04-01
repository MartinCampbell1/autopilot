"""File-backed per-agent mailbox for explicit runtime coordination signals."""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class AgentMailboxMessage(BaseModel):
    """One addressable mailbox message for a specific runtime agent."""

    id: str
    project_id: str
    runtime_agent_id: str
    message_type: str
    status: str = "unacked"
    delivery_sequence: int = 0
    dedupe_key: str = ""
    approval_id: str = ""
    approval_runtime_id: str = ""
    issue_id: str = ""
    permission_sync_key: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    delivered_at: str
    updated_at: str
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None


def agent_mailbox_message_path(config: AutopilotConfig, message_id: str) -> Path:
    """Return the persisted path for one mailbox message."""

    return config.agent_mailbox_dir / f"{message_id}.json"


def _agent_mailbox_meta_dir(config: AutopilotConfig) -> Path:
    return config.agent_mailbox_dir / "_meta"


def _agent_mailbox_sequence_path(config: AutopilotConfig) -> Path:
    return _agent_mailbox_meta_dir(config) / "sequence.json"


def _agent_mailbox_sequence_lock_path(config: AutopilotConfig) -> Path:
    return _agent_mailbox_meta_dir(config) / "sequence.lock"


def _try_claim_sequence_lock(lock_path: Path) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, str(time.time()).encode("utf-8"))
    finally:
        os.close(fd)
    return True


def _release_sequence_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _next_delivery_sequence(config: AutopilotConfig) -> int:
    sequence_path = _agent_mailbox_sequence_path(config)
    lock_path = _agent_mailbox_sequence_lock_path(config)
    deadline = time.monotonic() + 2.0
    while True:
        if _try_claim_sequence_lock(lock_path):
            try:
                try:
                    payload = json.loads(sequence_path.read_text())
                except FileNotFoundError:
                    payload = {}
                except Exception:
                    payload = {}
                next_sequence = int(payload.get("next_sequence") or 0) + 1
                _atomic_write_json(sequence_path, {"next_sequence": next_sequence})
                return next_sequence
            finally:
                _release_sequence_lock(lock_path)
        if time.monotonic() >= deadline:
            raise TimeoutError("Timed out allocating agent mailbox delivery sequence.")
        time.sleep(0.01)


def get_agent_mailbox_message(
    config: AutopilotConfig,
    message_id: str,
) -> AgentMailboxMessage | None:
    """Load one mailbox message if it exists."""

    path = agent_mailbox_message_path(config, message_id)
    if not path.exists():
        return None
    try:
        return AgentMailboxMessage.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_agent_mailbox_message(
    config: AutopilotConfig,
    message: AgentMailboxMessage,
) -> AgentMailboxMessage:
    """Persist one mailbox message."""

    message.updated_at = _utcnow_iso()
    _atomic_write_json(agent_mailbox_message_path(config, message.id), message.model_dump())
    return message


def list_agent_mailbox_messages(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    runtime_agent_id: str | None = None,
    status: str | None = None,
    message_type: str | None = None,
    approval_id: str | None = None,
    approval_runtime_id: str | None = None,
    issue_id: str | None = None,
) -> list[AgentMailboxMessage]:
    """List mailbox messages with lightweight filtering."""

    directory = config.agent_mailbox_dir
    if not directory.exists():
        return []

    records: list[AgentMailboxMessage] = []
    for path in sorted(directory.glob("mail_*.json")):
        try:
            record = AgentMailboxMessage.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if project_id and record.project_id != project_id:
            continue
        if runtime_agent_id and record.runtime_agent_id != runtime_agent_id:
            continue
        if status and record.status != status:
            continue
        if message_type and record.message_type != message_type:
            continue
        if approval_id and record.approval_id != approval_id:
            continue
        if approval_runtime_id and record.approval_runtime_id != approval_runtime_id:
            continue
        if issue_id and record.issue_id != issue_id:
            continue
        records.append(record)
    records.sort(key=lambda item: (item.delivery_sequence, item.delivered_at, item.id))
    return records


def _message_id_for_agent(runtime_agent_id: str, dedupe_key: str) -> str:
    digest = hashlib.sha1(f"{runtime_agent_id}:{dedupe_key}".encode("utf-8")).hexdigest()[:12]
    return f"mail_{digest}"


def publish_agent_mailbox_messages(
    config: AutopilotConfig,
    *,
    project_id: str,
    runtime_agent_ids: list[str] | tuple[str, ...],
    message_type: str,
    payload: dict[str, Any] | None = None,
    dedupe_key: str = "",
    approval_id: str = "",
    approval_runtime_id: str = "",
    issue_id: str = "",
    permission_sync_key: str = "",
    metadata: dict[str, Any] | None = None,
) -> list[AgentMailboxMessage]:
    """Publish one message to each addressed runtime agent."""

    normalized_agent_ids = sorted({str(item).strip() for item in runtime_agent_ids if str(item).strip()})
    if not normalized_agent_ids:
        return []

    now = _utcnow_iso()
    published: list[AgentMailboxMessage] = []
    for runtime_agent_id in normalized_agent_ids:
        delivery_sequence = _next_delivery_sequence(config)
        message_id = (
            _message_id_for_agent(runtime_agent_id, dedupe_key)
            if str(dedupe_key or "").strip()
            else f"mail_{uuid.uuid4().hex[:12]}"
        )
        existing = get_agent_mailbox_message(config, message_id)
        if existing is None:
            message = AgentMailboxMessage(
                id=message_id,
                project_id=str(project_id or "").strip(),
                runtime_agent_id=runtime_agent_id,
                message_type=str(message_type or "").strip(),
                dedupe_key=str(dedupe_key or "").strip(),
                delivery_sequence=delivery_sequence,
                approval_id=str(approval_id or "").strip(),
                approval_runtime_id=str(approval_runtime_id or "").strip(),
                issue_id=str(issue_id or "").strip(),
                permission_sync_key=str(permission_sync_key or "").strip(),
                payload=dict(payload or {}),
                metadata=dict(metadata or {}),
                created_at=now,
                delivered_at=now,
                updated_at=now,
            )
        else:
            message = existing.model_copy(
                update={
                    "project_id": str(project_id or "").strip(),
                    "message_type": str(message_type or "").strip(),
                    "status": "unacked",
                    "delivery_sequence": delivery_sequence,
                    "dedupe_key": str(dedupe_key or "").strip(),
                    "approval_id": str(approval_id or "").strip(),
                    "approval_runtime_id": str(approval_runtime_id or "").strip(),
                    "issue_id": str(issue_id or "").strip(),
                    "permission_sync_key": str(permission_sync_key or "").strip(),
                    "payload": dict(payload or {}),
                    "metadata": dict(metadata or {}),
                    "delivered_at": now,
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                }
            )
        published.append(save_agent_mailbox_message(config, message))
    return published


def poll_agent_mailbox_messages(
    config: AutopilotConfig,
    *,
    runtime_agent_id: str,
    project_id: str | None = None,
    status: str | None = "unacked",
    message_type: str | None = None,
    approval_id: str | None = None,
    approval_runtime_id: str | None = None,
    issue_id: str | None = None,
    after_sequence: int = 0,
    limit: int | None = None,
    acknowledge: bool = False,
    actor: str = "",
) -> list[AgentMailboxMessage]:
    """Return one ordered mailbox page, optionally acknowledging delivered messages."""

    messages = [
        message
        for message in list_agent_mailbox_messages(
            config,
            project_id=project_id,
            runtime_agent_id=runtime_agent_id,
            status=status,
            message_type=message_type,
            approval_id=approval_id,
            approval_runtime_id=approval_runtime_id,
            issue_id=issue_id,
        )
        if message.delivery_sequence > max(after_sequence, 0)
    ]
    if limit is not None:
        messages = messages[: max(limit, 0)]
    if not acknowledge:
        return messages
    normalized_actor = str(actor or "").strip()
    if not normalized_actor:
        raise ValueError("Mailbox acknowledge polling requires `actor`.")
    return [acknowledge_agent_mailbox_message(config, message.id, actor=normalized_actor) for message in messages]


def acknowledge_agent_mailbox_message(
    config: AutopilotConfig,
    message_id: str,
    *,
    actor: str,
) -> AgentMailboxMessage:
    """Mark one mailbox message as acknowledged."""

    message = get_agent_mailbox_message(config, message_id)
    if message is None:
        raise KeyError(message_id)
    if message.status == "acked":
        return message
    message.status = "acked"
    message.acknowledged_at = _utcnow_iso()
    message.acknowledged_by = str(actor or "").strip() or None
    return save_agent_mailbox_message(config, message)


__all__ = [
    "AgentMailboxMessage",
    "acknowledge_agent_mailbox_message",
    "get_agent_mailbox_message",
    "list_agent_mailbox_messages",
    "poll_agent_mailbox_messages",
    "publish_agent_mailbox_messages",
    "save_agent_mailbox_message",
]
