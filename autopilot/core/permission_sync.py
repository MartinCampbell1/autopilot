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

_MAILBOX_LOCK = threading.Lock()
_MAILBOX: dict[str, "PermissionSyncRecord"] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class PermissionSyncRecord(BaseModel):
    """Resolved or failed permission-sync decision for one dedupe key."""

    id: str
    key: str
    owner_request_id: str
    request_ids: list[str] = Field(default_factory=list)
    status: str = "resolved"
    payload: dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    resolved_at: str | None = None


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


def save_permission_sync(config: AutopilotConfig, record: PermissionSyncRecord) -> PermissionSyncRecord:
    """Persist one sync record and publish it to the in-process mailbox."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(permission_sync_path(config, record.key), record.model_dump())
    with _MAILBOX_LOCK:
        _MAILBOX[record.key] = record
    return record


def clear_permission_sync_mailbox() -> None:
    """Clear the in-process mailbox used for sync fast-paths."""

    with _MAILBOX_LOCK:
        _MAILBOX.clear()


def _mailbox_record(sync_key: str) -> PermissionSyncRecord | None:
    with _MAILBOX_LOCK:
        record = _MAILBOX.get(sync_key)
        return record.model_copy(deep=True) if record is not None else None


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


def _try_claim_lock(lock_path: Path, request_id: str) -> bool:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    try:
        os.write(fd, str(request_id or "").encode("utf-8"))
    finally:
        os.close(fd)
    return True


def _release_lock(lock_path: Path) -> None:
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
    record = _mailbox_record(sync_key)
    if record is None:
        record = get_permission_sync(config, sync_key)
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
) -> PermissionSyncRecord:
    deadline = time.monotonic() + wait_timeout_sec
    lock_path = permission_sync_lock_path(config, sync_key)
    while time.monotonic() < deadline:
        record = _current_resolution(config, sync_key=sync_key, request_id=request_id)
        if record is not None:
            return record
        try:
            age = time.time() - lock_path.stat().st_mtime
        except FileNotFoundError:
            age = 0.0
        if age >= stale_after_sec:
            _release_lock(lock_path)
            break
        time.sleep(0.02)

    record = _current_resolution(config, sync_key=sync_key, request_id=request_id)
    if record is not None:
        return record
    raise TimeoutError(f"Timed out waiting for permission sync `{sync_key}`.")


def resolve_permission_sync(
    config: AutopilotConfig,
    *,
    sync_key: str,
    resolver: PermissionSyncResolver,
    request_id: str = "",
    metadata: dict[str, Any] | None = None,
    wait_timeout_sec: float = 2.0,
    stale_after_sec: float = 30.0,
) -> PermissionSyncRecord:
    """Resolve one permission race exactly once across concurrent callers."""

    normalized_key = str(sync_key or "").strip()
    if not normalized_key:
        raise ValueError("Permission sync requires `sync_key`.")
    normalized_request_id = str(request_id or "").strip() or f"psreq_{uuid.uuid4().hex[:12]}"

    existing = _current_resolution(config, sync_key=normalized_key, request_id=normalized_request_id)
    if existing is not None:
        if existing.status == "failed":
            raise RuntimeError(existing.error or f"Permission sync `{normalized_key}` previously failed.")
        return existing

    lock_path = permission_sync_lock_path(config, normalized_key)
    if not _try_claim_lock(lock_path, normalized_request_id):
        record = _wait_for_resolution(
            config,
            sync_key=normalized_key,
            request_id=normalized_request_id,
            wait_timeout_sec=wait_timeout_sec,
            stale_after_sec=stale_after_sec,
        )
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
            request_ids=[normalized_request_id],
            status="resolved",
            payload=payload,
            metadata=dict(metadata or {}),
            created_at=created_at,
            updated_at=created_at,
            resolved_at=created_at,
        )
        return save_permission_sync(config, record)
    except Exception as exc:
        failed_at = _utcnow_iso()
        record = PermissionSyncRecord(
            id=f"psync_{uuid.uuid4().hex[:10]}",
            key=normalized_key,
            owner_request_id=normalized_request_id,
            request_ids=[normalized_request_id],
            status="failed",
            error=str(exc),
            metadata=dict(metadata or {}),
            created_at=failed_at,
            updated_at=failed_at,
            resolved_at=failed_at,
        )
        save_permission_sync(config, record)
        raise
    finally:
        _release_lock(lock_path)


__all__ = [
    "PermissionSyncRecord",
    "clear_permission_sync_mailbox",
    "get_permission_sync",
    "permission_sync_path",
    "resolve_permission_sync",
]
