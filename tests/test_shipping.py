"""Tests for safe shipping helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from autopilot.core.shipping import ShippingError, ship_repo


def _completed(
    args: list[str],
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def _ready_bootstrap_status(repo_root: Path) -> dict[str, object]:
    return {
        "verification": {
            "artifact_exists": True,
            "artifact_path": str(repo_root / ".agents/tasks/verifiers.json"),
        },
        "github": {
            "github_repo": "founderos/autopilot",
            "workflow_exists": True,
            "workflow_path": str(repo_root / ".github/workflows/autopilot-bootstrap.yml"),
        },
    }


def test_ship_repo_rejects_protected_branch(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="main\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)

    with pytest.raises(ShippingError, match="protected branch `main`"):
        ship_repo(repo_root)


def test_ship_repo_requires_verifier_bootstrap(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.bootstrap_visibility.build_bootstrap_status",
        lambda project_path: {
            "verification": {
                "artifact_exists": False,
                "artifact_path": str(repo_root / ".agents/tasks/verifiers.json"),
            },
            "github": {
                "github_repo": "founderos/autopilot",
                "workflow_exists": True,
                "workflow_path": str(repo_root / ".github/workflows/autopilot-bootstrap.yml"),
            },
        },
    )

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="feature/ship-loop\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)

    with pytest.raises(ShippingError, match="autopilot init-verifiers"):
        ship_repo(repo_root)


def test_ship_repo_requires_managed_github_workflow(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.bootstrap_visibility.build_bootstrap_status",
        lambda project_path: {
            "verification": {
                "artifact_exists": True,
                "artifact_path": str(repo_root / ".agents/tasks/verifiers.json"),
            },
            "github": {
                "github_repo": "founderos/autopilot",
                "workflow_exists": False,
                "workflow_path": str(repo_root / ".github/workflows/autopilot-bootstrap.yml"),
            },
        },
    )

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="feature/ship-loop\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)

    with pytest.raises(ShippingError, match="autopilot github"):
        ship_repo(repo_root)


def test_ship_repo_requires_commit_message_for_dirty_tree(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.bootstrap_visibility.build_bootstrap_status",
        lambda project_path: _ready_bootstrap_status(repo_root),
    )

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="feature/ship-loop\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        if args == ["status", "--porcelain"]:
            return _completed(args, stdout=" M app.py\n")
        raise AssertionError(f"Unexpected git args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)

    with pytest.raises(ShippingError, match="Pass --message"):
        ship_repo(repo_root)


def test_ship_repo_commits_pushes_and_creates_pull_request(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    git_calls: list[list[str]] = []
    gh_calls: list[list[str]] = []
    pr_list_payloads = [
        "[]",
        (
            '[{"number": 42, "url": "https://github.com/founderos/autopilot/pull/42", '
            '"state": "OPEN", "isDraft": true, "title": "Ship feature", '
            '"headRefName": "feature/ship-loop", "baseRefName": "main"}]'
        ),
    ]

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.bootstrap_visibility.build_bootstrap_status",
        lambda project_path: _ready_bootstrap_status(repo_root),
    )

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        git_calls.append(list(args))
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="feature/ship-loop\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        if args == ["status", "--porcelain"]:
            return _completed(args, stdout=" M app.py\n")
        if args == ["add", "-A"]:
            return _completed(args)
        if args == ["commit", "-m", "Ship latest changes"]:
            return _completed(args)
        if args == ["push", "--set-upstream", "origin", "feature/ship-loop"]:
            return _completed(args)
        if args == ["rev-parse", "--verify", "refs/remotes/origin/main"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        if args == ["diff", "--quiet", "origin/main...HEAD", "--"]:
            return _completed(args, returncode=1)
        raise AssertionError(f"Unexpected git args: {args}")

    def fake_run_gh(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        gh_calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            return _completed(args, stdout=pr_list_payloads.pop(0))
        if args[:2] == ["pr", "create"]:
            return _completed(args, stdout="https://github.com/founderos/autopilot/pull/42\n")
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)
    monkeypatch.setattr("autopilot.core.shipping._run_gh", fake_run_gh)

    payload = ship_repo(
        repo_root,
        commit_message="Ship latest changes",
        title="Ship feature",
        body="Ready for review.",
        draft=True,
    )

    assert payload["branch"] == "feature/ship-loop"
    assert payload["base_branch"] == "main"
    assert payload["dirty_before_ship"] is True
    assert payload["commit_created"] is True
    assert payload["pr_created"] is True
    assert payload["pull_request"]["number"] == 42
    assert payload["pull_request"]["draft"] is True
    assert payload["bootstrap"]["verification"]["artifact_exists"] is True
    assert ["add", "-A"] in git_calls
    assert ["commit", "-m", "Ship latest changes"] in git_calls
    assert ["push", "--set-upstream", "origin", "feature/ship-loop"] in git_calls
    assert any(call[:2] == ["pr", "create"] for call in gh_calls)


def test_ship_repo_reuses_existing_pull_request(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gh_calls: list[list[str]] = []

    monkeypatch.setattr("autopilot.core.shipping.find_canonical_git_root", lambda path: repo_root)
    monkeypatch.setattr("autopilot.core.shipping.get_github_repo", lambda path: "founderos/autopilot")
    monkeypatch.setattr("autopilot.core.shipping.shutil.which", lambda name: "/usr/bin/gh")
    monkeypatch.setattr(
        "autopilot.core.bootstrap_visibility.build_bootstrap_status",
        lambda project_path: _ready_bootstrap_status(repo_root),
    )

    def fake_run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        if args == ["branch", "--show-current"]:
            return _completed(args, stdout="feature/ship-loop\n")
        if args == ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]:
            return _completed(args, stdout="refs/remotes/origin/main\n")
        if args == ["status", "--porcelain"]:
            return _completed(args, stdout="")
        if args == ["push", "--set-upstream", "origin", "feature/ship-loop"]:
            return _completed(args)
        raise AssertionError(f"Unexpected git args: {args}")

    def fake_run_gh(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
        gh_calls.append(list(args))
        if args[:2] == ["pr", "list"]:
            return _completed(
                args,
                stdout=(
                    '[{"number": 7, "url": "https://github.com/founderos/autopilot/pull/7", '
                    '"state": "OPEN", "isDraft": false, "title": "Existing PR", '
                    '"headRefName": "feature/ship-loop", "baseRefName": "main"}]'
                ),
            )
        raise AssertionError(f"Unexpected gh args: {args}")

    monkeypatch.setattr("autopilot.core.shipping._run_git", fake_run_git)
    monkeypatch.setattr("autopilot.core.shipping._run_gh", fake_run_gh)

    payload = ship_repo(repo_root)

    assert payload["commit_created"] is False
    assert payload["pr_created"] is False
    assert payload["pull_request"]["number"] == 7
    assert not any(call[:2] == ["pr", "create"] for call in gh_calls)
