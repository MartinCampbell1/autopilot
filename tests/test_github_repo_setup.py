"""Tests for GitHub bootstrap helpers."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from autopilot.core.config import AutopilotConfig
from autopilot.core.github_repo_setup import (
    GITHUB_BOOTSTRAP_MANAGED_HEADER,
    GITHUB_BOOTSTRAP_WORKFLOW_RELPATH,
    GitHubBootstrapError,
    bootstrap_github_repo,
)
from autopilot.core.project_store import get_project_entry, register_project


def _completed(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_bootstrap_github_repo_writes_managed_workflow_and_updates_project(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "package.json").write_text(
        json.dumps(
            {
                "name": "repo",
                "scripts": {
                    "lint": "eslint .",
                    "test": "vitest run",
                    "typecheck": "tsc --noEmit",
                },
            }
        )
    )
    (repo_root / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'")
    verifiers_path = repo_root / ".agents" / "tasks"
    verifiers_path.mkdir(parents=True)
    (verifiers_path / "verifiers.json").write_text(
        json.dumps(
            {
                "checks": [
                    {"name": "lint", "command": "pnpm run lint", "kind": "quality_gate"},
                    {"name": "test", "command": "pnpm run test", "kind": "quality_gate"},
                    {"name": "typecheck", "command": "pnpm run typecheck", "kind": "acceptance_check"},
                ]
            }
        )
    )
    project = register_project(config, name="GitHub Project", project_path=repo_root)

    monkeypatch.setattr("autopilot.core.github_repo_setup.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.github_repo_setup.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.github_repo_setup._run_gh",
        lambda cwd, args: _completed(args, stdout="Logged in to github.com\n"),
    )
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_current_branch", lambda path: "feature/bootstrap")
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_default_branch", lambda path: "main")

    payload = bootstrap_github_repo(config, project_path=repo_root)

    workflow_path = repo_root / GITHUB_BOOTSTRAP_WORKFLOW_RELPATH
    assert payload["project_id"] == project["id"]
    assert payload["workflow"]["changed"] is True
    assert payload["compare_url"].endswith("main...feature/bootstrap?expand=1")
    assert workflow_path.exists()
    workflow_content = workflow_path.read_text()
    assert workflow_content.startswith(GITHUB_BOOTSTRAP_MANAGED_HEADER)
    assert "pnpm/action-setup@v4" in workflow_content
    assert "pnpm run typecheck" in workflow_content

    refreshed = get_project_entry(config, project_id=project["id"])
    assert refreshed is not None
    assert refreshed["github_bootstrap"]["workflow_relpath"] == GITHUB_BOOTSTRAP_WORKFLOW_RELPATH
    assert refreshed["github_bootstrap"]["workflow_changed"] is True


def test_bootstrap_github_repo_rejects_protected_branch_install(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "package.json").write_text(json.dumps({"name": "repo", "scripts": {"lint": "eslint ."}}))

    monkeypatch.setattr("autopilot.core.github_repo_setup.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.github_repo_setup.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.github_repo_setup._run_gh",
        lambda cwd, args: _completed(args, stdout="Logged in to github.com\n"),
    )
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_current_branch", lambda path: "main")
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_default_branch", lambda path: "main")

    with pytest.raises(GitHubBootstrapError, match="protected branch `main`"):
        bootstrap_github_repo(config, project_path=repo_root)


def test_bootstrap_github_repo_rejects_unmanaged_existing_workflow_without_overwrite(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    (repo_root / ".git").mkdir()
    (repo_root / "package.json").write_text(json.dumps({"name": "repo", "scripts": {"lint": "eslint ."}}))
    workflow_path = repo_root / GITHUB_BOOTSTRAP_WORKFLOW_RELPATH
    workflow_path.parent.mkdir(parents=True)
    workflow_path.write_text("name: Existing\n")

    monkeypatch.setattr("autopilot.core.github_repo_setup.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.github_repo_setup.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.github_repo_setup._run_gh",
        lambda cwd, args: _completed(args, stdout="Logged in to github.com\n"),
    )
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_current_branch", lambda path: "feature/bootstrap")
    monkeypatch.setattr("autopilot.core.github_repo_setup.get_default_branch", lambda path: "main")

    with pytest.raises(GitHubBootstrapError, match="--overwrite"):
        bootstrap_github_repo(config, project_path=repo_root)
