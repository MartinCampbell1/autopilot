"""Exact-match file editing helpers with stale-write protection."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from autopilot.core.file_snapshot_store import (
    FileSnapshot,
    FileSnapshotStaleError,
    capture_file_snapshot,
    ensure_snapshot_is_current,
)


class ExactEditError(RuntimeError):
    """Raised when an exact edit cannot be applied safely."""


_QUOTE_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def _normalize_match_line(line: str) -> str:
    return line.translate(_QUOTE_TRANSLATION).rstrip()


def find_actual_string(content: str, target: str, *, replace_all: bool = False) -> str:
    """Find the actual on-disk substring for a target, allowing limited quote/whitespace normalization."""

    if target in content:
        return target

    target_lines = target.splitlines(keepends=True)
    content_lines = content.splitlines(keepends=True)
    if not target_lines:
        raise ExactEditError("Target string is empty.")
    if len(target_lines) > len(content_lines):
        raise ExactEditError("Target string does not exist in the current file.")

    normalized_target = [_normalize_match_line(line) for line in target_lines]
    matches: list[str] = []
    for index in range(len(content_lines) - len(target_lines) + 1):
        window = content_lines[index : index + len(target_lines)]
        normalized_window = [_normalize_match_line(line) for line in window]
        if normalized_window == normalized_target:
            matches.append("".join(window))

    if not matches:
        raise ExactEditError("Target string does not exist in the current file.")
    if len(matches) > 1 and not replace_all:
        raise ExactEditError("Target string is ambiguous; provide more context or use replace_all.")
    return matches[0]


def apply_exact_edit(
    path: Path,
    snapshot: FileSnapshot,
    *,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """Apply one exact edit after confirming the file has not changed since read-time."""

    ensure_snapshot_is_current(path, snapshot)
    actual_old_string = find_actual_string(snapshot.content, old_string, replace_all=replace_all)
    replacements = snapshot.content.count(actual_old_string)
    if replacements > 1 and not replace_all:
        raise ExactEditError("Target string appears multiple times; provide a more specific old_string.")
    if replacements == 0:
        raise ExactEditError("Target string no longer exists in the current file.")

    updated = snapshot.content.replace(actual_old_string, new_string, -1 if replace_all else 1)
    path.write_text(updated)
    return updated


def append_with_snapshot(path: Path, snapshot: FileSnapshot, suffix: str) -> str:
    """Append to a file only if the original snapshot is still current."""

    ensure_snapshot_is_current(path, snapshot)
    updated = f"{snapshot.content}{suffix}"
    path.write_text(updated)
    return updated


def append_with_fresh_snapshot(
    path: Path,
    *,
    build_suffix: Callable[[str], str],
    initial_content: str = "",
    max_attempts: int = 2,
) -> str:
    """Append text using a fresh snapshot, retrying if a concurrent write races us."""

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    if not path.exists():
        suffix = build_suffix(initial_content)
        updated = f"{initial_content}{suffix}"
        path.write_text(updated)
        return updated

    last_error: FileSnapshotStaleError | None = None
    for _ in range(max_attempts):
        snapshot = capture_file_snapshot(path)
        suffix = build_suffix(snapshot.content)
        if not suffix:
            return snapshot.content
        try:
            return append_with_snapshot(path, snapshot, suffix)
        except FileSnapshotStaleError as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ExactEditError("Failed to append with a fresh snapshot.")
