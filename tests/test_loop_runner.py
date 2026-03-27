"""Tests for loop runner."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.loop_runner import (
    check_git_diff_empty,
    check_ralph_installed,
    init_ralph_project,
    read_progress,
    run_ralph_iteration,
    write_critic_feedback,
)


class TestLoopRunner:
    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_ralph_installed(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="0.1.3")
        assert check_ralph_installed() is True

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_ralph_not_installed(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError()
        assert check_ralph_installed() is False

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_init_ralph_project(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        assert init_ralph_project(tmp_path) is True

    def test_write_and_read_critic_feedback(self, tmp_path: Path) -> None:
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()

        write_critic_feedback(tmp_path, "- callback URL hardcoded\n- no tests")
        content = (ralph_dir / "critic-feedback.md").read_text()
        assert "callback URL" in content

    def test_read_progress_missing(self, tmp_path: Path) -> None:
        result = read_progress(tmp_path)
        assert result == ""

    def test_read_progress_exists(self, tmp_path: Path) -> None:
        ralph_dir = tmp_path / ".ralph"
        ralph_dir.mkdir()
        (ralph_dir / "progress.md").write_text("# Progress\n- Story 1 done")

        result = read_progress(tmp_path)
        assert "Story 1 done" in result

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_true(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        assert check_git_diff_empty(Path("/tmp")) is True

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_check_git_diff_empty_false(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="+new line")
        assert check_git_diff_empty(Path("/tmp")) is False

    @patch("autopilot.core.loop_runner.subprocess.run")
    def test_run_ralph_iteration_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="done", stderr="")
        success, output, rate_limited = run_ralph_iteration(tmp_path, {"PATH": "/usr/bin"})
        assert success is True
        assert output == "done"
        assert rate_limited is False
