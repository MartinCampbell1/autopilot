"""Snapshot helpers for stale-write-safe file updates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

BOM_UTF8 = b"\xef\xbb\xbf"
DEFAULT_SNAPSHOT_MAX_BYTES = 1_000_000


class FileSnapshotError(RuntimeError):
    """Base error for snapshot-based file operations."""


class FileSnapshotStaleError(FileSnapshotError):
    """Raised when the file changed after the snapshot was captured."""


class FileSnapshotTooLargeError(FileSnapshotError):
    """Raised when a file is too large for fail-closed snapshot editing."""


@dataclass(frozen=True)
class FileSnapshot:
    """One read-time snapshot of a file."""

    path: str
    content: str
    mtime_ns: int
    sha1: str
    encoding: str = "utf-8"
    size_bytes: int = 0


def _read_snapshot_bytes(path: Path, *, max_bytes: int | None = None) -> bytes:
    data = path.read_bytes()
    limit = DEFAULT_SNAPSHOT_MAX_BYTES if max_bytes is None else max_bytes
    if len(data) > limit:
        raise FileSnapshotTooLargeError(
            f"File `{path}` is {len(data)} bytes, which exceeds the exact-edit safety limit of {limit} bytes."
        )
    return data


def _decode_snapshot_bytes(data: bytes, *, path: Path) -> tuple[str, str]:
    encoding = "utf-8-sig" if data.startswith(BOM_UTF8) else "utf-8"
    try:
        return data.decode(encoding), encoding
    except UnicodeDecodeError as exc:
        raise FileSnapshotError(f"File `{path}` is not valid {encoding} text and cannot be edited safely.") from exc


def _snapshot_sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def capture_file_snapshot(path: Path) -> FileSnapshot:
    """Read a file and capture deterministic stale-write metadata."""

    resolved = path.resolve()
    data = _read_snapshot_bytes(resolved)
    content, encoding = _decode_snapshot_bytes(data, path=resolved)
    stat = resolved.stat()
    return FileSnapshot(
        path=str(resolved),
        content=content,
        mtime_ns=stat.st_mtime_ns,
        sha1=_snapshot_sha1(data),
        encoding=encoding,
        size_bytes=len(data),
    )


def ensure_snapshot_is_current(path: Path, snapshot: FileSnapshot) -> None:
    """Reject writes when the on-disk file no longer matches the captured snapshot."""

    resolved = path.resolve()
    if str(resolved) != snapshot.path:
        raise FileSnapshotStaleError("File path changed after snapshot capture.")
    current_data = _read_snapshot_bytes(resolved)
    current_stat = resolved.stat()
    current_sha1 = _snapshot_sha1(current_data)
    if current_stat.st_mtime_ns != snapshot.mtime_ns or current_sha1 != snapshot.sha1:
        raise FileSnapshotStaleError("File changed after it was read; refresh the snapshot before editing.")
