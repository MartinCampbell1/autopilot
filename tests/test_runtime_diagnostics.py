"""Tests for runtime/context diagnostics used by doctor flows."""

from __future__ import annotations

import subprocess
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import register_project, save_project_state
from autopilot.core.runtime_diagnostics import EVENT_LOG_WARN_BYTES, build_runtime_diagnostics
from autopilot.core.worktree import worktree_metadata_path


def _init_git_repo(path: Path, *, remote_url: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "init"],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode == 0, result.stderr
    if remote_url:
        result = subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        assert result.returncode == 0, result.stderr
    return path


def test_build_runtime_diagnostics_flags_repo_identity_missing_for_git_repo_without_remote(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    config_path = tmp_path / ".autopilot" / "config.yaml"
    project_root = _init_git_repo(tmp_path / "project")

    payload = build_runtime_diagnostics(
        config=config,
        config_path=config_path,
        project_path=project_root,
    )

    codes = {item["code"] for item in payload["diagnostics"]}
    assert "config_missing" in codes
    assert "repo_identity_missing" in codes


def test_build_runtime_diagnostics_surfaces_story_worktree_stale_runtime_and_large_events_log(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    config_path = tmp_path / ".autopilot" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("providers_order: []\n", encoding="utf-8")

    project_root = _init_git_repo(tmp_path / "project", remote_url="git@github.com:FounderOS/Autopilot.git")
    worktree_root = _init_git_repo(tmp_path / "project-story-7", remote_url="git@github.com:FounderOS/Autopilot.git")
    worktree_metadata_path(worktree_root).write_text(
        (
            "{"
            f"\"project_path\": \"{project_root}\", "
            "\"story_id\": 7, "
            "\"branch_name\": \"story-7\", "
            "\"created_at\": \"2026-04-02T00:00:00+00:00\", "
            "\"runtime_pid\": null"
            "}"
        ),
        encoding="utf-8",
    )

    project = register_project(config, name="Doctor Project", project_path=project_root)
    save_project_state(
        config,
        project["id"],
        {
            "project_id": project["id"],
            "status": "running",
            "pid": 999999,
            "runtime_session_id": "sess_dead",
        },
    )
    config.events_log_path.parent.mkdir(parents=True, exist_ok=True)
    config.events_log_path.write_text("x" * EVENT_LOG_WARN_BYTES, encoding="utf-8")

    payload = build_runtime_diagnostics(
        config=config,
        config_path=config_path,
        project_path=worktree_root,
    )

    codes = {item["code"] for item in payload["diagnostics"]}
    assert "story_worktree_detected" in codes
    assert "stale_runtime_pid" in codes
    assert "events_log_large" in codes
