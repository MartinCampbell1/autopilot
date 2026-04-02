"""Tests for git repo identity and path mapping helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.repo_registry import (
    build_repo_registry_key,
    find_canonical_git_root,
    get_github_repo,
    get_known_paths_for_repo,
    get_repo_registry_entry,
    update_repo_path_mapping,
)


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


def test_find_canonical_git_root_returns_repo_root_for_nested_path(tmp_path: Path) -> None:
    repo_root = _init_git_repo(tmp_path / "repo")
    nested = repo_root / "apps" / "api"
    nested.mkdir(parents=True, exist_ok=True)

    assert find_canonical_git_root(nested) == repo_root.resolve()


def test_get_github_repo_parses_ssh_and_https_remotes(tmp_path: Path) -> None:
    ssh_repo = _init_git_repo(
        tmp_path / "ssh-repo",
        remote_url="git@github.com:FounderOS/Autopilot.git",
    )
    https_repo = _init_git_repo(
        tmp_path / "https-repo",
        remote_url="https://github.com/FounderOS/Autopilot.git",
    )

    assert get_github_repo(ssh_repo) == "founderos/autopilot"
    assert get_github_repo(https_repo) == "founderos/autopilot"


def test_update_repo_path_mapping_tracks_same_repo_across_clones(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    remote_url = "git@github.com:FounderOS/Autopilot.git"
    clone_a = _init_git_repo(tmp_path / "clone-a", remote_url=remote_url)
    clone_b = _init_git_repo(tmp_path / "clone-b", remote_url=remote_url)
    observed_nested_path = clone_b / "packages" / "web"
    observed_nested_path.mkdir(parents=True, exist_ok=True)

    first = update_repo_path_mapping(config, clone_a)
    second = update_repo_path_mapping(config, observed_nested_path)

    assert first is not None
    assert second is not None
    assert build_repo_registry_key(clone_a) == "github:founderos/autopilot"
    assert build_repo_registry_key(clone_b) == "github:founderos/autopilot"

    entry = get_repo_registry_entry(config, project_path=clone_a)
    assert entry is not None
    assert entry["repo_key"] == "github:founderos/autopilot"
    assert entry["github_repo"] == "founderos/autopilot"
    assert entry["remote_url"] == remote_url
    assert set(get_known_paths_for_repo(config, repo_key=entry["repo_key"])) == {
        str(clone_a.resolve()),
        str(clone_b.resolve()),
        str(observed_nested_path.resolve()),
    }
