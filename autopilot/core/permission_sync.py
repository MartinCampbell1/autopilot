"""Deterministic permission-sync helpers for multi-agent approval races."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig

PermissionSyncResolver = Callable[[], dict[str, Any]]
PermissionSyncReuseChecker = Callable[["PermissionSyncRecord"], bool]

_MAILBOX_LOCK = threading.Lock()
_MAILBOX: dict[str, "PermissionSyncRecord"] = {}
_MAILBOX_EVENTS: dict[str, threading.Event] = {}


class _PermissionSyncReclaimableWait(Exception):
    """Internal signal that a stale lock was released and claim can be retried."""


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_sync_token(prefix: str) -> str:
    """Build one replay-resistant sync token."""

    return f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class PermissionSyncRecord(BaseModel):
    """Resolved or failed permission-sync decision for one dedupe key."""

    id: str
    key: str
    owner_request_id: str
    claim_id: str = ""
    resolution_id: str = ""
    request_ids: list[str] = Field(default_factory=list)
    status: str = "resolved"
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    resolved_at: str | None = None


class PermissionSyncClaim(BaseModel):
    """Exclusive claim over one in-flight permission sync resolution."""

    id: str
    key: str
    request_id: str
    created_at: str


def permission_sync_path(config: AutopilotConfig, sync_key: str) -> Path:
    """Return the persisted path for one sync key."""

    digest = hashlib.sha1(str(sync_key).encode("utf-8")).hexdigest()
    return config.permission_sync_dir / f"{digest}.json"


def permission_sync_lock_path(config: AutopilotConfig, sync_key: str) -> Path:
    """Return the lock path for one sync key."""

    return permission_sync_path(config, sync_key).with_suffix(".lock")


def get_permission_sync(config: AutopilotConfig, sync_key: str) -> PermissionSyncRecord | None:
    """Load one resolved sync record if it exists."""

    path = permission_sync_path(config, sync_key)
    if not path.exists():
        return None
    try:
        record = PermissionSyncRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None
    with _MAILBOX_LOCK:
        _MAILBOX[sync_key] = record
    return record


def clear_permission_sync(config: AutopilotConfig, sync_key: str) -> None:
    """Delete one persisted/mailbox sync record so a fresh cycle can start."""

    path = permission_sync_path(config, sync_key)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    with _MAILBOX_LOCK:
        _MAILBOX.pop(sync_key, None)
        event = _MAILBOX_EVENTS.get(sync_key)
    if event is not None:
        event.clear()


def annotate_permission_sync(
    config: AutopilotConfig,
    sync_key: str,
    *,
    metadata_updates: dict[str, Any] | None = None,
    payload_updates: dict[str, Any] | None = None,
) -> PermissionSyncRecord | None:
    """Update one existing sync record and republish it through the mailbox."""

    record = get_permission_sync(config, sync_key)
    if record is None:
        return None

    metadata = dict(record.metadata)
    for key, value in (metadata_updates or {}).items():
        if isinstance(value, dict) and isinstance(metadata.get(key), dict):
            metadata[key] = {**dict(metadata.get(key) or {}), **value}
        else:
            metadata[key] = value

    payload = dict(record.payload)
    for key, value in (payload_updates or {}).items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key] = {**dict(payload.get(key) or {}), **value}
        else:
            payload[key] = value

    updated = record.model_copy(update={"metadata": metadata, "payload": payload})
    return save_permission_sync(config, updated)


def save_permission_sync(config: AutopilotConfig, record: PermissionSyncRecord) -> PermissionSyncRecord:
    """Persist one sync record and publish it to the in-process mailbox."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(permission_sync_path(config, record.key), record.model_dump())
    with _MAILBOX_LOCK:
        _MAILBOX[record.key] = record
        event = _MAILBOX_EVENTS.get(record.key)
    if event is not None:
        event.set()
    return record


def clear_permission_sync_mailbox() -> None:
    """Clear the in-process mailbox used for sync fast-paths."""

    with _MAILBOX_LOCK:
        _MAILBOX.clear()
        _MAILBOX_EVENTS.clear()


def _mailbox_record(sync_key: str) -> PermissionSyncRecord | None:
    with _MAILBOX_LOCK:
        record = _MAILBOX.get(sync_key)
        return record.model_copy(deep=True) if record is not None else None


def _mailbox_event(sync_key: str) -> threading.Event:
    with _MAILBOX_LOCK:
        event = _MAILBOX_EVENTS.get(sync_key)
        if event is None:
            event = threading.Event()
            _MAILBOX_EVENTS[sync_key] = event
        return event


def _peek_resolution(config: AutopilotConfig, sync_key: str) -> PermissionSyncRecord | None:
    record = _mailbox_record(sync_key)
    if record is None:
        record = get_permission_sync(config, sync_key)
    return record


def _remember_request_id(
    config: AutopilotConfig,
    record: PermissionSyncRecord,
    request_id: str,
) -> PermissionSyncRecord:
    normalized_request_id = str(request_id or "").strip()
    if not normalized_request_id or normalized_request_id in record.request_ids:
        return record
    record.request_ids = sorted({*record.request_ids, normalized_request_id})
    return save_permission_sync(config, record)


def _read_lock_claim(lock_path: Path) -> PermissionSyncClaim | None:
    try:
        raw = lock_path.read_text().strip()
    except FileNotFoundError:
        return None
    if not raw:
        return None
    try:
        return PermissionSyncClaim.model_validate(json.loads(raw))
    except Exception:
        return PermissionSyncClaim(
            id="",
            key="",
            request_id=raw,
            created_at="",
        )


def _try_claim_lock(lock_path: Path, sync_key: str, request_id: str) -> PermissionSyncClaim | None:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    claim = PermissionSyncClaim(
        id=_new_sync_token("psclaim"),
        key=str(sync_key or "").strip(),
        request_id=str(request_id or "").strip(),
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


def _current_resolution(
    config: AutopilotConfig,
    *,
    sync_key: str,
    request_id: str,
) -> PermissionSyncRecord | None:
    record = _peek_resolution(config, sync_key)
    if record is None:
        return None
    return _remember_request_id(config, record, request_id)


def _wait_for_resolution(
    config: AutopilotConfig,
    *,
    sync_key: str,
    request_id: str,
    wait_timeout_sec: float,
    stale_after_sec: float,
    allow_stale_reclaim: bool = False,
) -> PermissionSyncRecord:
    deadline = time.monotonic() + wait_timeout_sec
    lock_path = permission_sync_lock_path(config, sync_key)
    mailbox_event = _mailbox_event(sync_key)
    while time.monotonic() < deadline:
        record = _current_resolution(config, sync_key=sync_key, request_id=request_id)
        if record is not None:
            return record
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            age = 0.0
        if age >= stale_after_sec:
            _release_lock(lock_path, force=True)
            if allow_stale_reclaim:
                raise _PermissionSyncReclaimableWait(sync_key)
            break
        remaining = max(deadline - time.monotonic(), 0.0)
        mailbox_event.wait(timeout=min(0.05, remaining))

    record = _current_resolution(config, sync_key=sync_key, request_id=request_id)
    if record is not None:
        return record
    raise TimeoutError(f"Timed out waiting for permission sync `{sync_key}`.")


def _settle_claim_record(
    config: AutopilotConfig,
    *,
    claim: PermissionSyncClaim,
    record: PermissionSyncRecord,
    wait_timeout_sec: float,
    stale_after_sec: float,
) -> PermissionSyncRecord:
    lock_path = permission_sync_lock_path(config, claim.key)
    current_claim = _read_lock_claim(lock_path)
    if current_claim is not None and current_claim.id == claim.id:
        return save_permission_sync(config, record)

    existing = _current_resolution(config, sync_key=claim.key, request_id=claim.request_id)
    if existing is not None:
        return existing

    return _wait_for_resolution(
        config,
        sync_key=claim.key,
        request_id=claim.request_id,
        wait_timeout_sec=wait_timeout_sec,
        stale_after_sec=stale_after_sec,
    )


def resolve_permission_sync(
    config: AutopilotConfig,
    *,
    sync_key: str,
    resolver: PermissionSyncResolver,
    request_id: str = "",
    metadata: dict[str, Any] | None = None,
    wait_timeout_sec: float = 2.0,
    stale_after_sec: float = 30.0,
    reuse_checker: PermissionSyncReuseChecker | None = None,
    allow_failed_retries: bool = False,
) -> PermissionSyncRecord:
    """Resolve one permission race exactly once across concurrent callers."""

    normalized_key = str(sync_key or "").strip()
    if not normalized_key:
        raise ValueError("Permission sync requires `sync_key`.")
    normalized_request_id = str(request_id or "").strip() or f"psreq_{uuid.uuid4().hex[:12]}"

    while True:
        existing = _peek_resolution(config, normalized_key)
        if existing is not None:
            reusable = True
            if reuse_checker is not None and not reuse_checker(existing):
                reusable = False
            elif (
                existing.status == "failed"
                and allow_failed_retries
                and normalized_request_id not in existing.request_ids
            ):
                reusable = False

            if reusable:
                existing = _remember_request_id(config, existing, normalized_request_id)
                if existing.status == "failed":
                    raise RuntimeError(existing.error or f"Permission sync `{normalized_key}` previously failed.")
                return existing

            clear_permission_sync(config, normalized_key)
            continue

        lock_path = permission_sync_lock_path(config, normalized_key)
        claim = _try_claim_lock(lock_path, normalized_key, normalized_request_id)
        if claim is None:
            try:
                record = _wait_for_resolution(
                    config,
                    sync_key=normalized_key,
                    request_id=normalized_request_id,
                    wait_timeout_sec=wait_timeout_sec,
                    stale_after_sec=stale_after_sec,
                    allow_stale_reclaim=True,
                )
            except _PermissionSyncReclaimableWait:
                continue
            if record.status == "failed":
                raise RuntimeError(record.error or f"Permission sync `{normalized_key}` failed.")
            return record

        created_at = _utcnow_iso()
        try:
            payload = dict(resolver() or {})
            record = PermissionSyncRecord(
                id=f"psync_{uuid.uuid4().hex[:10]}",
                key=normalized_key,
                owner_request_id=normalized_request_id,
                claim_id=claim.id,
                resolution_id=_new_sync_token("psyncres"),
                request_ids=[normalized_request_id],
                status="resolved",
                payload=payload,
                metadata=dict(metadata or {}),
                created_at=created_at,
                updated_at=created_at,
                resolved_at=created_at,
            )
            return _settle_claim_record(
                config,
                claim=claim,
                record=record,
                wait_timeout_sec=wait_timeout_sec,
                stale_after_sec=stale_after_sec,
            )
        except Exception as exc:
            failed_at = _utcnow_iso()
            record = PermissionSyncRecord(
                id=f"psync_{uuid.uuid4().hex[:10]}",
                key=normalized_key,
                owner_request_id=normalized_request_id,
                claim_id=claim.id,
                resolution_id=_new_sync_token("psyncres"),
                request_ids=[normalized_request_id],
                status="failed",
                error=str(exc),
                metadata=dict(metadata or {}),
                created_at=failed_at,
                updated_at=failed_at,
                resolved_at=failed_at,
            )
            settled = _settle_claim_record(
                config,
                claim=claim,
                record=record,
                wait_timeout_sec=wait_timeout_sec,
                stale_after_sec=stale_after_sec,
            )
            if settled.claim_id != claim.id:
                if settled.status == "failed":
                    raise RuntimeError(settled.error or f"Permission sync `{normalized_key}` failed.")
                return settled
            raise
        finally:
            _release_lock(lock_path, claim_id=claim.id)


__all__ = [
    "annotate_permission_sync",
    "PermissionSyncClaim",
    "PermissionSyncRecord",
    "clear_permission_sync",
    "clear_permission_sync_mailbox",
    "get_permission_sync",
    "permission_sync_path",
    "resolve_permission_sync",
]
