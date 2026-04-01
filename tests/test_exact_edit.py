"""Tests for exact-edit and file snapshot helpers."""

from pathlib import Path
from unittest.mock import patch

from autopilot.core import exact_edit as exact_edit_module
from autopilot.core.exact_edit import ExactEditError, append_with_fresh_snapshot, apply_exact_edit, find_actual_string
from autopilot.core.file_snapshot_store import FileSnapshotStaleError, capture_file_snapshot


def test_find_actual_string_normalizes_quotes_and_trailing_whitespace() -> None:
    content = 'title = “FounderOS”   \nvalue = 1\n'

    actual = find_actual_string(content, 'title = "FounderOS"\n')

    assert actual == 'title = “FounderOS”   \n'


def test_apply_exact_edit_rejects_stale_snapshot(tmp_path: Path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\n")
    snapshot = capture_file_snapshot(path)
    path.write_text("beta\n")

    try:
        apply_exact_edit(path, snapshot, old_string="alpha\n", new_string="gamma\n")
    except FileSnapshotStaleError:
        return
    raise AssertionError("Expected stale snapshot rejection.")


def test_apply_exact_edit_rejects_ambiguous_match(tmp_path: Path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nalpha\n")
    snapshot = capture_file_snapshot(path)

    try:
        apply_exact_edit(path, snapshot, old_string="alpha\n", new_string="beta\n")
    except ExactEditError as exc:
        assert "multiple times" in str(exc) or "ambiguous" in str(exc)
        return
    raise AssertionError("Expected ambiguous match rejection.")


def test_apply_exact_edit_updates_file_when_snapshot_is_current(tmp_path: Path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\nbeta\n")
    snapshot = capture_file_snapshot(path)

    updated = apply_exact_edit(path, snapshot, old_string="alpha\n", new_string="gamma\n")

    assert updated == "gamma\nbeta\n"
    assert path.read_text() == "gamma\nbeta\n"


def test_append_with_fresh_snapshot_retries_after_stale_write(tmp_path: Path) -> None:
    path = tmp_path / "demo.txt"
    path.write_text("alpha\n")
    original_append = exact_edit_module.append_with_snapshot
    calls = {"count": 0}

    def flaky_append(path_arg: Path, snapshot, suffix: str) -> str:
        calls["count"] += 1
        if calls["count"] == 1:
            path_arg.write_text(f"{snapshot.content}other\n")
            raise FileSnapshotStaleError("stale")
        return original_append(path_arg, snapshot, suffix)

    with patch.object(exact_edit_module, "append_with_snapshot", side_effect=flaky_append):
        updated = append_with_fresh_snapshot(
            path,
            build_suffix=lambda existing: f"{'' if not existing or existing.endswith('\n') else '\n'}beta\n",
        )

    assert calls["count"] == 2
    assert updated == "alpha\nother\nbeta\n"
    assert path.read_text() == "alpha\nother\nbeta\n"


def test_append_with_fresh_snapshot_bootstraps_missing_file_with_initial_content(tmp_path: Path) -> None:
    path = tmp_path / "demo.txt"

    updated = append_with_fresh_snapshot(
        path,
        initial_content="# Header\n\n",
        build_suffix=lambda existing: f"{'' if not existing or existing.endswith('\n') else '\n'}- item\n",
    )

    assert updated == "# Header\n\n- item\n"
    assert path.read_text() == "# Header\n\n- item\n"
