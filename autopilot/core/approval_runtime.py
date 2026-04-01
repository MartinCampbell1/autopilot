"""Resolve-once approval runtime contexts for deterministic settlement."""

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

from autopilot.core.agent_mailbox import poll_agent_mailbox_messages, publish_agent_mailbox_messages
from autopilot.core.config import AutopilotConfig
from autopilot.core.tool_permission_events import (
    emit_tool_permission_pending_event,
    emit_tool_permission_resolved_event,
)

_MAX_SETTLEMENT_ATTEMPTS = 25
_TOOL_PERMISSION_PENDING_MESSAGE_TYPES = {
    "permission_hook_pending",
    "tool_permission_classifier_pending",
    "tool_permission_hook_pending",
    "tool_permission_pending",
    "tool_permission_user_pending",
}


class _ApprovalRuntimeReclaimableWait(Exception):
    """Internal signal that a stale runtime lock was reclaimed."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_runtime_token(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


def _runtime_id_for_key(key: str) -> str:
    digest = hashlib.sha1(str(key or "").encode("utf-8")).hexdigest()[:12]
    return f"apprt_{digest}"


class ApprovalRuntimeRecord(BaseModel):
    """One resolve-once approval context for approval or permission decisions."""

    id: str
    key: str
    project_id: str
    status: str = "pending"
    claim_id: str = ""
    resolution_id: str = ""
    approval_id: str = ""
    issue_id: str = ""
    permission_sync_key: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    winner_source: str = ""
    outcome: str = ""
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    settlement_attempts: list[dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class ApprovalRuntimeClaim(BaseModel):
    """Exclusive claim over one in-flight approval runtime settlement."""

    id: str
    key: str
    source: str
    outcome: str
    created_at: str


def approval_runtime_path(config: AutopilotConfig, approval_runtime_id: str) -> Path:
    """Return the persisted path for one approval runtime context."""

    return config.approval_runtime_dir / f"{approval_runtime_id}.json"


def approval_runtime_lock_path(config: AutopilotConfig, approval_runtime_id: str) -> Path:
    """Return the resolve-once lock path for one approval runtime context."""

    return approval_runtime_path(config, approval_runtime_id).with_suffix(".lock")


def get_approval_runtime(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str = "",
    key: str = "",
) -> ApprovalRuntimeRecord | None:
    """Load one approval runtime context by id or key."""

    normalized_id = str(approval_runtime_id or "").strip() or _runtime_id_for_key(str(key or "").strip())
    if not normalized_id:
        return None
    path = approval_runtime_path(config, normalized_id)
    if not path.exists():
        return None
    try:
        return ApprovalRuntimeRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_approval_runtime(
    config: AutopilotConfig,
    record: ApprovalRuntimeRecord,
) -> ApprovalRuntimeRecord:
    """Persist one approval runtime context."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(approval_runtime_path(config, record.id), record.model_dump())
    return record


def list_approval_runtimes(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    approval_id: str | None = None,
    issue_id: str | None = None,
    status: str | None = None,
    runtime_agent_id: str | None = None,
) -> list[ApprovalRuntimeRecord]:
    """List approval runtime contexts with lightweight filtering."""

    directory = config.approval_runtime_dir
    if not directory.exists():
        return []
    records: list[ApprovalRuntimeRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = ApprovalRuntimeRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if project_id and record.project_id != project_id:
            continue
        if approval_id and record.approval_id != approval_id:
            continue
        if issue_id and record.issue_id != issue_id:
            continue
        if status and record.status != status:
            continue
        if runtime_agent_id and runtime_agent_id not in record.runtime_agent_ids:
            continue
        records.append(record)
    records.sort(key=lambda item: (item.created_at, item.id))
    return records


def _read_lock_claim(lock_path: Path) -> ApprovalRuntimeClaim | None:
    try:
        raw = lock_path.read_text().strip()
    except FileNotFoundError:
        return None
    if not raw:
        return None
    try:
        return ApprovalRuntimeClaim.model_validate(json.loads(raw))
    except Exception:
        return ApprovalRuntimeClaim(
            id="",
            key="",
            source="",
            outcome="",
            created_at="",
        )


def _try_claim_lock(lock_path: Path, *, key: str, source: str, outcome: str) -> ApprovalRuntimeClaim | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    claim = ApprovalRuntimeClaim(
        id=_new_runtime_token("apprtclaim"),
        key=str(key or "").strip(),
        source=str(source or "").strip(),
        outcome=str(outcome or "").strip(),
        created_at=_utcnow_iso(),
    )
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return None
    try:
        os.write(fd, json.dumps(claim.model_dump(), ensure_ascii=False).encode("utf-8"))
    finally:
        os.close(fd)
    return claim


def _release_lock(lock_path: Path, *, claim_id: str | None = None, force: bool = False) -> None:
    if not force:
        current_claim = _read_lock_claim(lock_path)
        normalized_claim_id = str(claim_id or "").strip()
        if current_claim is None or not normalized_claim_id or current_claim.id != normalized_claim_id:
            return
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def _merge_metadata(
    base: dict[str, Any],
    updates: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(base)
    for key, value in (updates or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**dict(merged.get(key) or {}), **value}
        else:
            merged[key] = value
    return merged


def _approval_runtime_mailbox_payload(record: ApprovalRuntimeRecord) -> dict[str, Any]:
    return {
        "approval_runtime_id": record.id,
        "approval_id": record.approval_id,
        "issue_id": record.issue_id,
        "permission_sync_key": record.permission_sync_key,
        "status": record.status,
        "claim_id": record.claim_id,
        "resolution_id": record.resolution_id,
        "source": record.winner_source,
        "outcome": record.outcome,
        "message": record.message,
        "payload": dict(record.payload or {}),
        "metadata": dict(record.metadata or {}),
        "resolved_at": record.resolved_at,
    }


def _publish_runtime_resolution_messages(
    config: AutopilotConfig,
    record: ApprovalRuntimeRecord,
    *,
    specific_message_type: str | None = None,
) -> None:
    if not record.runtime_agent_ids:
        return
    canonical_message_type = "approval_runtime_resolved"
    payload = _approval_runtime_mailbox_payload(record)
    publish_agent_mailbox_messages(
        config,
        project_id=record.project_id,
        runtime_agent_ids=record.runtime_agent_ids,
        message_type=canonical_message_type,
        payload=payload,
        dedupe_key=f"{record.id}:{canonical_message_type}",
        approval_id=record.approval_id,
        approval_runtime_id=record.id,
        issue_id=record.issue_id,
        permission_sync_key=record.permission_sync_key,
    )
    normalized_specific_type = str(specific_message_type or "").strip()
    if not normalized_specific_type or normalized_specific_type == canonical_message_type:
        return
    publish_agent_mailbox_messages(
        config,
        project_id=record.project_id,
        runtime_agent_ids=record.runtime_agent_ids,
        message_type=normalized_specific_type,
        payload=payload,
        dedupe_key=f"{record.id}:{normalized_specific_type}",
        approval_id=record.approval_id,
        approval_runtime_id=record.id,
        issue_id=record.issue_id,
        permission_sync_key=record.permission_sync_key,
    )


def _append_settlement_attempt(
    record: ApprovalRuntimeRecord,
    *,
    attempt_id: str,
    source: str,
    outcome: str,
    message: str = "",
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    applied: bool,
    ignored_reason: str = "",
) -> ApprovalRuntimeRecord:
    attempts = list(record.settlement_attempts)
    if any(str(existing.get("id") or "") == attempt_id for existing in attempts):
        return record
    attempts.append(
        {
            "id": attempt_id,
            "source": str(source or "").strip(),
            "outcome": str(outcome or "").strip(),
            "message": str(message or "").strip(),
            "payload": dict(payload or {}),
            "metadata": dict(metadata or {}),
            "applied": bool(applied),
            "ignored_reason": str(ignored_reason or "").strip(),
            "created_at": _utcnow_iso(),
        }
    )
    return record.model_copy(update={"settlement_attempts": attempts[-_MAX_SETTLEMENT_ATTEMPTS:]})


def _is_tool_permission_runtime(record: ApprovalRuntimeRecord) -> bool:
    kind = str(record.metadata.get("kind") or "").strip().lower()
    return kind.startswith("tool_permission")


def _should_emit_tool_permission_pending_event(
    previous: ApprovalRuntimeRecord,
    updated: ApprovalRuntimeRecord,
    mailbox_message_type: str | None,
) -> bool:
    normalized_message_type = str(mailbox_message_type or "").strip()
    if normalized_message_type not in _TOOL_PERMISSION_PENDING_MESSAGE_TYPES:
        return False
    if not _is_tool_permission_runtime(updated) or str(updated.status or "").strip() != "pending":
        return False
    updated_pending = dict(updated.metadata.get("pending") or {})
    if not str(updated_pending.get("stage") or "").strip():
        return False
    previous_pending = dict(previous.metadata.get("pending") or {})
    if str(previous.status or "").strip() == "pending" and previous_pending == updated_pending:
        return False
    return True


def _wait_for_runtime_resolution(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str,
    wait_timeout_sec: float,
    stale_after_sec: float,
    allow_stale_reclaim: bool = False,
) -> ApprovalRuntimeRecord:
    deadline = time.monotonic() + wait_timeout_sec
    lock_path = approval_runtime_lock_path(config, approval_runtime_id)
    while time.monotonic() < deadline:
        current = get_approval_runtime(config, approval_runtime_id=approval_runtime_id)
        if current is None:
            raise KeyError(approval_runtime_id)
        if current.status == "resolved":
            return current
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            age = 0.0
        if age >= stale_after_sec:
            _release_lock(lock_path, force=True)
            if allow_stale_reclaim:
                raise _ApprovalRuntimeReclaimableWait(approval_runtime_id)
            break
        time.sleep(0.02)

    current = get_approval_runtime(config, approval_runtime_id=approval_runtime_id)
    if current is not None and current.status == "resolved":
        return current
    raise TimeoutError(f"Timed out settling approval runtime `{approval_runtime_id}`.")


def _record_ignored_attempt(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str,
    attempt_id: str,
    source: str,
    outcome: str,
    message: str = "",
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    wait_timeout_sec: float,
    stale_after_sec: float,
) -> ApprovalRuntimeRecord:
    lock_path = approval_runtime_lock_path(config, approval_runtime_id)
    deadline = time.monotonic() + wait_timeout_sec
    while True:
        current = get_approval_runtime(config, approval_runtime_id=approval_runtime_id)
        if current is None:
            raise KeyError(approval_runtime_id)
        claim = _try_claim_lock(lock_path, key=current.key, source=source, outcome=outcome)
        if claim is not None:
            try:
                latest = get_approval_runtime(config, approval_runtime_id=approval_runtime_id)
                if latest is None:
                    raise KeyError(approval_runtime_id)
                ignored = _append_settlement_attempt(
                    latest,
                    attempt_id=attempt_id,
                    source=source,
                    outcome=outcome,
                    message=message,
                    payload=payload,
                    metadata=metadata,
                    applied=False,
                    ignored_reason="already_resolved" if latest.status == "resolved" else "superseded",
                )
                return save_approval_runtime(config, ignored)
            finally:
                _release_lock(lock_path, claim_id=claim.id)
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            age = 0.0
        if age >= stale_after_sec:
            _release_lock(lock_path, force=True)
            continue
        if time.monotonic() >= deadline:
            return current
        time.sleep(0.02)


def create_or_reuse_approval_runtime(
    config: AutopilotConfig,
    *,
    key: str,
    project_id: str,
    approval_id: str = "",
    issue_id: str = "",
    permission_sync_key: str = "",
    runtime_agent_ids: list[str] | tuple[str, ...] = (),
    metadata: dict[str, Any] | None = None,
    publish_pending: bool = False,
    pending_message_type: str = "approval_pending",
    pending_payload: dict[str, Any] | None = None,
) -> ApprovalRuntimeRecord:
    """Create or reuse one approval runtime context by stable key."""

    normalized_key = str(key or "").strip()
    if not normalized_key:
        raise ValueError("Approval runtime requires `key`.")
    runtime_id = _runtime_id_for_key(normalized_key)
    existing = get_approval_runtime(config, approval_runtime_id=runtime_id)
    desired_runtime_agent_ids = sorted({str(item).strip() for item in runtime_agent_ids if str(item).strip()})
    if existing is None:
        now = _utcnow_iso()
        record = ApprovalRuntimeRecord(
            id=runtime_id,
            key=normalized_key,
            project_id=str(project_id or "").strip(),
            approval_id=str(approval_id or "").strip(),
            issue_id=str(issue_id or "").strip(),
            permission_sync_key=str(permission_sync_key or "").strip(),
            runtime_agent_ids=desired_runtime_agent_ids,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
    else:
        merged_metadata = dict(existing.metadata)
        merged_metadata.update(dict(metadata or {}))
        record = existing.model_copy(
            update={
                "project_id": str(project_id or "").strip() or existing.project_id,
                "approval_id": str(approval_id or "").strip() or existing.approval_id,
                "issue_id": str(issue_id or "").strip() or existing.issue_id,
                "permission_sync_key": str(permission_sync_key or "").strip() or existing.permission_sync_key,
                "runtime_agent_ids": sorted({*existing.runtime_agent_ids, *desired_runtime_agent_ids}),
                "metadata": merged_metadata,
            }
        )
    saved = save_approval_runtime(config, record)
    if publish_pending and saved.runtime_agent_ids:
        publish_agent_mailbox_messages(
            config,
            project_id=saved.project_id,
            runtime_agent_ids=saved.runtime_agent_ids,
            message_type=pending_message_type,
            payload={
                "approval_runtime_id": saved.id,
                "approval_id": saved.approval_id,
                "issue_id": saved.issue_id,
                "permission_sync_key": saved.permission_sync_key,
                **dict(pending_payload or {}),
            },
            dedupe_key=f"{saved.id}:{pending_message_type}",
            approval_id=saved.approval_id,
            approval_runtime_id=saved.id,
            issue_id=saved.issue_id,
            permission_sync_key=saved.permission_sync_key,
        )
    return saved


def settle_approval_runtime(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str = "",
    key: str = "",
    source: str,
    outcome: str,
    message: str = "",
    payload: dict[str, Any] | None = None,
    metadata_updates: dict[str, Any] | None = None,
    mailbox_message_type: str | None = None,
    wait_timeout_sec: float = 2.0,
    stale_after_sec: float = 30.0,
) -> ApprovalRuntimeRecord:
    """Resolve one approval runtime exactly once; later writers observe the winner."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None:
        raise KeyError(approval_runtime_id or key)
    attempt_id = _new_runtime_token("apprtattempt")
    lock_path = approval_runtime_lock_path(config, record.id)
    while True:
        claim = _try_claim_lock(lock_path, key=record.key, source=source, outcome=outcome)
        if claim is not None:
            try:
                latest = get_approval_runtime(config, approval_runtime_id=record.id)
                if latest is None:
                    raise KeyError(record.id)
                if latest.status == "resolved":
                    latest = _append_settlement_attempt(
                        latest,
                        attempt_id=attempt_id,
                        source=source,
                        outcome=outcome,
                        message=message,
                        payload=payload,
                        metadata=metadata_updates,
                        applied=False,
                        ignored_reason="already_resolved",
                    )
                    return save_approval_runtime(config, latest)
                merged_metadata = _merge_metadata(latest.metadata, metadata_updates)
                resolved = latest.model_copy(
                    update={
                        "status": "resolved",
                        "claim_id": claim.id,
                        "resolution_id": _new_runtime_token("apprtres"),
                        "winner_source": str(source or "").strip(),
                        "outcome": str(outcome or "").strip(),
                        "message": str(message or "").strip(),
                        "payload": dict(payload or {}),
                        "metadata": merged_metadata,
                        "resolved_at": _utcnow_iso(),
                    }
                )
                resolved = _append_settlement_attempt(
                    resolved,
                    attempt_id=attempt_id,
                    source=source,
                    outcome=outcome,
                    message=message,
                    payload=payload,
                    metadata=metadata_updates,
                    applied=True,
                )
                resolved = save_approval_runtime(config, resolved)
                resolved_message_type = (
                    str(mailbox_message_type).strip()
                    if mailbox_message_type is not None
                    else f"approval_{resolved.outcome or 'resolved'}"
                )
                _publish_runtime_resolution_messages(
                    config,
                    resolved,
                    specific_message_type=resolved_message_type,
                )
                if _is_tool_permission_runtime(resolved):
                    emit_tool_permission_resolved_event(
                        config,
                        resolved,
                        event_source=resolved_message_type,
                    )
                return resolved
            finally:
                _release_lock(lock_path, claim_id=claim.id)
        try:
            _wait_for_runtime_resolution(
                config,
                approval_runtime_id=record.id,
                wait_timeout_sec=wait_timeout_sec,
                stale_after_sec=stale_after_sec,
                allow_stale_reclaim=True,
            )
        except _ApprovalRuntimeReclaimableWait:
            continue
        return _record_ignored_attempt(
            config,
            approval_runtime_id=record.id,
            attempt_id=attempt_id,
            source=source,
            outcome=outcome,
            message=message,
            payload=payload,
            metadata=metadata_updates,
            wait_timeout_sec=wait_timeout_sec,
            stale_after_sec=stale_after_sec,
        )


def annotate_approval_runtime(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str = "",
    key: str = "",
    metadata_updates: dict[str, Any] | None = None,
    payload_updates: dict[str, Any] | None = None,
    mailbox_message_type: str | None = None,
    mailbox_payload: dict[str, Any] | None = None,
) -> ApprovalRuntimeRecord:
    """Update one approval runtime context without changing its winner."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None:
        raise KeyError(approval_runtime_id or key)
    metadata = dict(record.metadata)
    for meta_key, value in (metadata_updates or {}).items():
        if isinstance(value, dict) and isinstance(metadata.get(meta_key), dict):
            metadata[meta_key] = {**dict(metadata.get(meta_key) or {}), **value}
        else:
            metadata[meta_key] = value
    payload = dict(record.payload)
    for payload_key, value in (payload_updates or {}).items():
        if isinstance(value, dict) and isinstance(payload.get(payload_key), dict):
            payload[payload_key] = {**dict(payload.get(payload_key) or {}), **value}
        else:
            payload[payload_key] = value
    updated = record.model_copy(update={"metadata": metadata, "payload": payload})
    updated = save_approval_runtime(config, updated)
    if mailbox_message_type and updated.runtime_agent_ids:
        publish_agent_mailbox_messages(
            config,
            project_id=updated.project_id,
            runtime_agent_ids=updated.runtime_agent_ids,
            message_type=str(mailbox_message_type).strip(),
            payload={
                "approval_runtime_id": updated.id,
                "approval_id": updated.approval_id,
                "issue_id": updated.issue_id,
                "permission_sync_key": updated.permission_sync_key,
                **dict(mailbox_payload or {}),
            },
            dedupe_key=f"{updated.id}:{str(mailbox_message_type).strip()}",
            approval_id=updated.approval_id,
            approval_runtime_id=updated.id,
            issue_id=updated.issue_id,
            permission_sync_key=updated.permission_sync_key,
        )
    if _should_emit_tool_permission_pending_event(record, updated, mailbox_message_type):
        emit_tool_permission_pending_event(
            config,
            updated,
            event_source=str(mailbox_message_type or "").strip(),
        )
    return updated


def wait_for_approval_runtime_resolution(
    config: AutopilotConfig,
    *,
    approval_runtime_id: str = "",
    key: str = "",
    wait_timeout_sec: float = 0.5,
    stale_after_sec: float = 30.0,
) -> ApprovalRuntimeRecord:
    """Wait for one approval runtime to resolve without attempting settlement."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None:
        raise KeyError(approval_runtime_id or key)
    if record.status == "resolved":
        return record
    return _wait_for_runtime_resolution(
        config,
        approval_runtime_id=record.id,
        wait_timeout_sec=wait_timeout_sec,
        stale_after_sec=stale_after_sec,
    )


def wait_for_approval_runtime_mailbox_resolution(
    config: AutopilotConfig,
    *,
    runtime_agent_id: str,
    approval_runtime_id: str = "",
    key: str = "",
    after_sequence: int = 0,
    wait_timeout_sec: float = 0.5,
) -> ApprovalRuntimeRecord:
    """Wait for a canonical mailbox settlement message for one approval runtime."""

    record = get_approval_runtime(config, approval_runtime_id=approval_runtime_id, key=key)
    if record is None:
        raise KeyError(approval_runtime_id or key)
    if record.status == "resolved":
        return record
    normalized_runtime_agent_id = str(runtime_agent_id or "").strip()
    if not normalized_runtime_agent_id:
        raise ValueError("Mailbox wait requires `runtime_agent_id`.")

    deadline = time.monotonic() + max(float(wait_timeout_sec), 0.0)
    cursor = max(int(after_sequence or 0), 0)
    while True:
        messages = poll_agent_mailbox_messages(
            config,
            runtime_agent_id=normalized_runtime_agent_id,
            approval_runtime_id=record.id,
            message_type="approval_runtime_resolved",
            status=None,
            after_sequence=cursor,
        )
        if messages:
            cursor = max(cursor, max(message.delivery_sequence for message in messages))
            refreshed = get_approval_runtime(config, approval_runtime_id=record.id)
            if refreshed is not None and refreshed.status == "resolved":
                return refreshed
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for mailbox settlement of approval runtime `{record.id}`.")
        time.sleep(0.02)


__all__ = [
    "ApprovalRuntimeClaim",
    "ApprovalRuntimeRecord",
    "annotate_approval_runtime",
    "approval_runtime_lock_path",
    "create_or_reuse_approval_runtime",
    "get_approval_runtime",
    "list_approval_runtimes",
    "save_approval_runtime",
    "settle_approval_runtime",
    "wait_for_approval_runtime_mailbox_resolution",
    "wait_for_approval_runtime_resolution",
]
