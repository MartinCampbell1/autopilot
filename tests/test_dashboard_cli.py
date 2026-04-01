"""Tests for the dashboard CLI entrypoint."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from autopilot.cli.dashboard import dashboard


@patch("autopilot.cli.dashboard.webbrowser.open")
@patch("autopilot.cli.dashboard.time.sleep")
@patch("autopilot.cli.dashboard.subprocess.Popen")
@patch("autopilot.cli.dashboard._repo_root")
def test_dashboard_builds_then_serves(
    mock_repo_root: MagicMock,
    mock_popen: MagicMock,
    mock_sleep: MagicMock,
    mock_open: MagicMock,
    tmp_path: Path,
) -> None:
    (tmp_path / "dashboard").mkdir()
    mock_repo_root.return_value = tmp_path
    process = MagicMock()
    process.wait.return_value = 0
    mock_popen.return_value = process

    dashboard(port=9000, frontend_port=3030, no_browser=True)

    assert mock_popen.call_args.args[0] == ["npm", "run", "dev"]
    assert mock_popen.call_args.kwargs["cwd"] == str(tmp_path / "dashboard")
    assert mock_popen.call_args.kwargs["env"]["AUTOPILOT_API_PORT"] == "9000"
    assert mock_popen.call_args.kwargs["env"]["AUTOPILOT_FRONTEND_PORT"] == "3030"
    mock_sleep.assert_called_once_with(2)
    mock_open.assert_not_called()

@patch("autopilot.cli.dashboard._repo_root")
def test_dashboard_exits_when_dashboard_dir_missing(
    mock_repo_root: MagicMock,
    tmp_path: Path,
) -> None:
    mock_repo_root.return_value = tmp_path

    with pytest.raises(typer.Exit) as exc_info:
        dashboard(port=8420, frontend_port=3020, no_browser=True)

    assert exc_info.value.exit_code == 1
