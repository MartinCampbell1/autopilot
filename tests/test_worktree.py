"""Tests for git worktree management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.github_prs import stable_story_branch_name
from autopilot.core.worktree import create_worktree, merge_worktree, remove_worktree, worktree_path


class TestWorktree:
    def test_worktree_path(self) -> None:
        result = worktree_path(Path("/Users/example/project"), story_id=3)
        assert result == Path("/Users/example/project-story-3")

    @patch("autopilot.core.worktree.subprocess.run")
    def test_create_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        branch_name = stable_story_branch_name("Project", 3, "Bootstrap dashboard shell")
        result = create_worktree(Path("/Users/example/project"), story_id=3, branch_name=branch_name)
        assert result == Path("/Users/example/project-story-3")
        assert mock_run.call_count == 2

        cleanup_call = mock_run.call_args_list[0][0][0]
        assert cleanup_call == ["git", "branch", "-D", branch_name]

        add_call = mock_run.call_args_list[1][0][0]
        assert "worktree" in add_call
        assert "add" in add_call
        assert branch_name in add_call

    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        remove_worktree(Path("/Users/example/project"), Path("/Users/example/project-story-3"))
        assert mock_run.called

    @patch("autopilot.core.worktree.subprocess.run")
    def test_merge_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        success = merge_worktree(
            main_path=Path("/Users/example/project"),
            worktree_path=Path("/Users/example/project-story-3"),
            branch_name="story-3",
        )
        assert success is True
