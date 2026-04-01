"""Tests for runtime path validation helpers."""

from pathlib import Path

from autopilot.core.path_permissions import validate_story_worktree_path


def test_validate_story_worktree_path_accepts_expected_layout(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"
    candidate = tmp_path / "demo-project-story-3"

    result = validate_story_worktree_path(project_path, candidate, expected_story_id=3)

    assert result.allowed is True
    assert result.normalized_path == candidate.resolve(strict=False)


def test_validate_story_worktree_path_rejects_shell_expansion_syntax(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"

    result = validate_story_worktree_path(project_path, "~/demo-project-story-3", expected_story_id=3)

    assert result.allowed is False
    assert "shell expansion" in result.reason.lower()


def test_validate_story_worktree_path_rejects_outside_parent_directory(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"
    candidate = tmp_path / "nested" / "demo-project-story-3"

    result = validate_story_worktree_path(project_path, candidate, expected_story_id=3)

    assert result.allowed is False
    assert "parent directory" in result.reason.lower()
