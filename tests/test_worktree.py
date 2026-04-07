"""Tests for git worktree management."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.github_prs import stable_story_branch_name
from autopilot.core.worktree import (
    DEFAULT_WORKTREE_STALE_AFTER_SEC,
    create_worktree,
    gc_stale_worktrees,
    merge_worktree,
    read_worktree_metadata,
    read_worktree_collaboration_manifest,
    remove_worktree,
    resolve_story_worktree_owner,
    worktree_collaboration_dir,
    worktree_collaboration_manifest_path,
    worktree_metadata_path,
    worktree_path,
)


class TestWorktree:
    def test_worktree_path(self) -> None:
        result = worktree_path(Path("/tmp/project"), story_id=3)
        assert result == Path("/tmp/project-story-3")

    @patch("autopilot.core.worktree.subprocess.run")
    def test_create_worktree(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        project_path = tmp_path / "project"
        project_path.mkdir()
        branch_name = stable_story_branch_name("Project", 3, "Bootstrap dashboard shell")
        result = create_worktree(project_path, story_id=3, branch_name=branch_name)
        assert result == tmp_path / "project-story-3"
        assert mock_run.call_count == 4

        prune_call = mock_run.call_args_list[0][0][0]
        assert prune_call == ["git", "worktree", "prune"]

        branch_list_call = mock_run.call_args_list[1][0][0]
        assert branch_list_call == ["git", "branch", "--list", branch_name]

        add_call = mock_run.call_args_list[2][0][0]
        assert "worktree" in add_call
        assert "add" in add_call
        assert branch_name in add_call
        assert "--force" in add_call
        assert add_call[-1] == "HEAD"

        config_call = mock_run.call_args_list[3][0][0]
        assert config_call == ["git", "config", "--local", "core.hooksPath", os.devnull]

        metadata = read_worktree_metadata(result)
        assert metadata is not None
        assert metadata.story_id == 3
        assert metadata.branch_name == branch_name
        assert metadata.project_path == str(project_path)
        collaboration = read_worktree_collaboration_manifest(result)
        assert collaboration is not None
        assert collaboration.story_id == 3
        assert collaboration.branch_name == branch_name
        assert collaboration.artifact_dir == str(worktree_collaboration_dir(result))
        assert worktree_collaboration_manifest_path(result).exists()

    @patch("autopilot.core.worktree.subprocess.run")
    def test_create_worktree_deletes_existing_branch_when_present(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="  story-3\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        project_path = tmp_path / "project"
        project_path.mkdir()
        create_worktree(project_path, story_id=3, branch_name="story-3")

        calls = [call.args[0] for call in mock_run.call_args_list]
        assert ["git", "branch", "-D", "story-3"] in calls

    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0)
        remove_worktree(Path("/tmp/project"), Path("/tmp/project-story-3"))
        assert mock_run.call_count == 2
        assert mock_run.call_args_list[0][0][0] == [
            "git",
            "worktree",
            "remove",
            str(Path("/tmp/project-story-3").resolve()),
            "--force",
        ]
        assert mock_run.call_args_list[1][0][0] == ["git", "worktree", "prune"]

    @patch("autopilot.core.worktree.subprocess.run")
    def test_remove_worktree_cleans_metadata_branch_when_requested(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
            MagicMock(returncode=0, stdout="  story-3\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        project_path = tmp_path / "project"
        project_path.mkdir()
        wt_path = tmp_path / "project-story-3"
        wt_path.mkdir()
        worktree_metadata_path(wt_path).write_text(
            json.dumps(
                {
                    "project_path": str(project_path),
                    "story_id": 3,
                    "branch_name": "story-3",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "runtime_pid": None,
                }
            ),
            encoding="utf-8",
        )

        remove_worktree(project_path, wt_path, cleanup_branch=True)

        calls = [call.args[0] for call in mock_run.call_args_list]
        assert ["git", "branch", "--list", "story-3"] in calls
        assert ["git", "branch", "-D", "story-3"] in calls

    def test_remove_worktree_rejects_unsafe_path(self) -> None:
        try:
            remove_worktree(Path("/tmp/project"), Path("/var/tmp/not-this-project"))
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
            MagicMock(returncode=0, stdout="  story-3\n", stderr=""),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        success = merge_worktree(
            main_path=Path("/tmp/project"),
            worktree_path=Path("/tmp/project-story-3"),
            branch_name="story-3",
        )
        assert success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert calls[0] == ["git", "status", "--porcelain"]
        assert calls[1] == ["git", "merge", "story-3", "--no-edit"]
        assert calls[2] == ["git", "worktree", "remove", str(Path("/tmp/project-story-3").resolve()), "--force"]
        assert calls[3] == ["git", "worktree", "prune"]
        assert calls[4] == ["git", "branch", "--list", "story-3"]
        assert calls[5] == ["git", "branch", "-d", "story-3"]

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
            main_path=Path("/tmp/project"),
            worktree_path=Path("/tmp/project-story-3"),
            branch_name="story-3",
        )

        assert success is True
        calls = [call.args[0] for call in mock_run.call_args_list]
        assert ["git", "add", "-A"] in calls
        assert ["git", "commit", "-m", "Autopilot story merge: story-3"] in calls

    @patch("autopilot.core.worktree.remove_worktree")
    def test_gc_stale_worktrees_removes_dead_old_worktrees(self, mock_remove: MagicMock, tmp_path: Path) -> None:
        project_path = tmp_path / "project"
        project_path.mkdir()
        stale_path = tmp_path / "project-story-7"
        stale_path.mkdir()
        worktree_metadata_path(stale_path).write_text(
            (
                '{"project_path": "%s", "story_id": 7, "branch_name": "story-7", '
                '"created_at": "%s", "runtime_pid": 999999}'
            )
            % (
                str(project_path),
                (datetime.now(timezone.utc) - timedelta(seconds=DEFAULT_WORKTREE_STALE_AFTER_SEC + 30)).isoformat(),
            ),
            encoding="utf-8",
        )

        removed = gc_stale_worktrees(project_path, stale_after_sec=DEFAULT_WORKTREE_STALE_AFTER_SEC)

        assert removed == [stale_path]
        mock_remove.assert_called_once_with(project_path, stale_path, cleanup_branch=True)

    def test_resolve_story_worktree_owner_returns_owner_for_nested_path(self, tmp_path: Path) -> None:
        project_path = tmp_path / "project"
        project_path.mkdir()
        wt_path = tmp_path / "project-story-7"
        nested_path = wt_path / "apps" / "api"
        nested_path.mkdir(parents=True)
        worktree_metadata_path(wt_path).write_text(
            json.dumps(
                {
                    "project_path": str(project_path),
                    "story_id": 7,
                    "branch_name": "story-7",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "runtime_pid": None,
                }
            ),
            encoding="utf-8",
        )

        resolved = resolve_story_worktree_owner(nested_path)

        assert resolved == (project_path.resolve(), wt_path.resolve())

    def test_resolve_story_worktree_owner_returns_none_outside_story_worktree(self, tmp_path: Path) -> None:
        project_path = tmp_path / "project"
        project_path.mkdir()

        assert resolve_story_worktree_owner(project_path) is None
