"""Snapshot helpers for stale-write-safe file updates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


class FileSnapshotError(RuntimeError):
    """Base error for snapshot-based file operations."""


class FileSnapshotStaleError(FileSnapshotError):
    """Raised when the file changed after the snapshot was captured."""


@dataclass(frozen=True)
class FileSnapshot:
    """One read-time snapshot of a file."""

    path: str
    content: str
    mtime_ns: int
    sha1: str


def capture_file_snapshot(path: Path) -> FileSnapshot:
    """Read a file and capture deterministic stale-write metadata."""

    resolved = path.resolve()
    content = resolved.read_text()
    stat = resolved.stat()
    sha1 = hashlib.sha1(content.encode("utf-8")).hexdigest()
    return FileSnapshot(
        path=str(resolved),
        content=content,
        mtime_ns=stat.st_mtime_ns,
        sha1=sha1,
    )


def ensure_snapshot_is_current(path: Path, snapshot: FileSnapshot) -> None:
    """Reject writes when the on-disk file no longer matches the captured snapshot."""

    resolved = path.resolve()
    if str(resolved) != snapshot.path:
        raise FileSnapshotStaleError("File path changed after snapshot capture.")
    current_content = resolved.read_text()
    current_stat = resolved.stat()
    current_sha1 = hashlib.sha1(current_content.encode("utf-8")).hexdigest()
    if current_stat.st_mtime_ns != snapshot.mtime_ns or current_sha1 != snapshot.sha1:
        raise FileSnapshotStaleError("File changed after it was read; refresh the snapshot before editing.")
