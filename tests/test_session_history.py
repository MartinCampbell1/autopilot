"""Tests for repo-aware resume discovery helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import ensure_project_state, register_project, save_project_state
from autopilot.core.repo_registry import update_repo_path_mapping
from autopilot.core.session_history import build_resume_discovery
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


def test_build_resume_discovery_distinguishes_current_same_repo_and_cross_project(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    repo_remote = "git@github.com:FounderOS/Autopilot.git"
    current_root = _init_git_repo(tmp_path / "current", remote_url=repo_remote)
    same_repo_root = _init_git_repo(tmp_path / "same-repo", remote_url=repo_remote)
    other_root = _init_git_repo(tmp_path / "other", remote_url="git@github.com:FounderOS/Other.git")

    current_project = register_project(config, name="Current", project_path=current_root)
    same_repo_project = register_project(config, name="Same Repo", project_path=same_repo_root)
    other_project = register_project(config, name="Other", project_path=other_root)

    same_repo_state = ensure_project_state(config, same_repo_project, seed_mode="new")
    same_repo_state["status"] = "paused"
    same_repo_state["paused"] = True
    save_project_state(config, same_repo_project["id"], same_repo_state)

    other_state = ensure_project_state(config, other_project, seed_mode="new")
    other_state["status"] = "running"
    other_state["pid"] = 999999
    save_project_state(config, other_project["id"], other_state)

    nested_current_path = current_root / "apps" / "api"
    nested_current_path.mkdir(parents=True, exist_ok=True)

    discovery = build_resume_discovery(config, nested_current_path)
    candidates = {candidate["project_id"]: candidate for candidate in discovery["projects"]}

    assert discovery["current_project_id"] == current_project["id"]
    assert discovery["current_repo_key"] == "github:founderos/autopilot"
    assert candidates[current_project["id"]]["relation"] == "current_project"
    assert candidates[same_repo_project["id"]]["relation"] == "same_repo"
    assert candidates[other_project["id"]]["relation"] == "cross_project"
    assert candidates[same_repo_project["id"]]["can_resume"] is True


def test_build_resume_discovery_surfaces_story_worktree_and_unregistered_same_repo_paths(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    repo_remote = "git@github.com:FounderOS/Autopilot.git"
    canonical_root = _init_git_repo(tmp_path / "canonical", remote_url=repo_remote)
    worktree_root = _init_git_repo(tmp_path / "canonical-story-7", remote_url=repo_remote)
    unregistered_clone = _init_git_repo(tmp_path / "other-clone", remote_url=repo_remote)

    registered_project = register_project(config, name="Canonical", project_path=canonical_root)
    ensure_project_state(config, registered_project, seed_mode="new")
    register_project(config, name="Story WT", project_path=worktree_root)
    worktree_metadata_path(worktree_root).write_text(
        json.dumps(
            {
                "project_path": str(canonical_root),
                "story_id": 7,
                "branch_name": "story-7",
                "created_at": "2026-04-02T00:00:00+00:00",
                "runtime_pid": None,
            }
        ),
        encoding="utf-8",
    )

    nested_unregistered_path = unregistered_clone / "packages" / "web"
    nested_unregistered_path.mkdir(parents=True, exist_ok=True)
    update_repo_path_mapping(config, nested_unregistered_path)

    discovery = build_resume_discovery(config, worktree_root)
    candidates = {candidate["name"]: candidate for candidate in discovery["projects"]}

    assert discovery["current_project_id"] == registered_project["id"]
    assert candidates["Story WT"]["relation"] == "same_repo"
    assert discovery["unregistered_same_repo_paths"] == [str(unregistered_clone.resolve())]
