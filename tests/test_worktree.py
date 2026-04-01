"""Tests for git worktree management."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.github_prs import stable_story_branch_name
from autopilot.core.worktree import create_worktree, merge_worktree, remove_worktree, worktree_path


class TestWorktree:
    def test_worktree_path(self) -> None:
        result = worktree_path(Path("/Users/martin/project"), story_id=3)
        assert result == Path("/Users/martin/project-story-3")

    @patch("autopilot.core.worktree.subprocess.run")
    def test_create_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        branch_name = stable_story_branch_name("Project", 3, "Bootstrap dashboard shell")
        result = create_worktree(Path("/Users/martin/project"), story_id=3, branch_name=branch_name)
        assert result == Path("/Users/martin/project-story-3")
        assert mock_run.call_count == 3

        prune_call = mock_run.call_args_list[0][0][0]
        assert prune_call == ["git", "worktree", "prune"]

        cleanup_call = mock_run.call_args_list[1][0][0]
        assert cleanup_call == ["git", "branch", "-D", branch_name]

        add_call = mock_run.call_args_list[2][0][0]
        assert "worktree" in add_call
        assert "add" in add_call
        assert branch_name in add_call
        assert "--force" in add_call
        assert add_call[-1] == "HEAD"

    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        remove_worktree(Path("/Users/martin/project"), Path("/Users/martin/project-story-3"))
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == ["git", "worktree", "remove", "/Users/martin/project-story-3", "--force"]
        assert mock_run.call_args_list[1][0][0] == ["git", "worktree", "prune"]

    def test_remove_worktree_rejects_unsafe_path(self) -> None:
        try:
            remove_worktree(Path("/Users/martin/project"), Path("/tmp/not-this-project"))
        except ValueError as exc:
            assert "naming contract" in str(exc) or "parent directory" in str(exc)
        else:
            raise AssertionError("Expected unsafe worktree path to be rejected.")

    @patch("autopilot.core.worktree.shutil.rmtree")
    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree_cleans_residual_path(self, mock_run: MagicMock, mock_rmtree: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        project_path = tmp_path / "project"
        project_path.mkdir()
        wt_path = project_path.parent / "project-story-3"
        wt_path.mkdir()

        remove_worktree(project_path, wt_path)

        mock_rmtree.assert_called_once_with(wt_path, ignore_errors=True)

    @patch("autopilot.core.worktree.subprocess.run")
    def test_merge_worktree(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        success = merge_worktree(
            main_path=Path("/Users/martin/project"),
            worktree_path=Path("/Users/martin/project-story-3"),
            branch_name="story-3",
        )
        assert success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert calls[0] == ["git", "status", "--porcelain"]
        assert calls[1] == ["git", "merge", "story-3", "--no-edit"]
        assert calls[2] == ["git", "worktree", "remove", "/Users/martin/project-story-3", "--force"]
        assert calls[3] == ["git", "worktree", "prune"]
        assert calls[4] == ["git", "branch", "-d", "story-3"]

    @patch("autopilot.core.worktree.subprocess.run")
    def test_merge_worktree_commits_when_dirty(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=" M app.py\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        success = merge_worktree(
            main_path=Path("/Users/martin/project"),
            worktree_path=Path("/Users/martin/project-story-3"),
            branch_name="story-3",
        )

        assert success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert ["git", "add", "-A"] in calls
        assert ["git", "commit", "-m", "Autopilot story merge: story-3"] in calls
