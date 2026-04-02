"""Tests for the GitHub bootstrap CLI helper."""

from __future__ import annotations

import json

import pytest
from typer import Exit

from autopilot.cli.github import github
from autopilot.core.github_repo_setup import GitHubBootstrapError


def test_github_cli_emits_json_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.github.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.github.bootstrap_github_repo",
        lambda *args, **kwargs: {
            "project_path": "/tmp/project",
            "project_id": "proj_123",
            "project_registered": True,
            "github_repo": "founderos/autopilot",
            "gh_authenticated": True,
            "current_branch": "feature/bootstrap",
            "default_branch": "main",
            "compare_url": "https://github.com/founderos/autopilot/compare/main...feature/bootstrap?expand=1",
            "workflow_url": "https://github.com/founderos/autopilot/actions/workflows/autopilot-bootstrap.yml",
            "install_workflow": True,
            "workflow": {"workflow_path": "/tmp/project/.github/workflows/autopilot-bootstrap.yml", "changed": True},
            "checks": [],
            "tooling": {"stacks": ["node"], "gates": []},
        },
    )

    github("/tmp/project", json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload["project_path"] == "/tmp/project"
    assert payload["github_repo"] == "founderos/autopilot"
    assert payload["workflow"]["changed"] is True


def test_github_cli_exits_nonzero_on_bootstrap_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.github.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.github.bootstrap_github_repo",
        lambda *args, **kwargs: (_ for _ in ()).throw(GitHubBootstrapError("boom")),
    )

    with pytest.raises(Exit) as exc_info:
        github("/tmp/project", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert exc_info.value.exit_code == 1
    assert payload == {"ok": False, "error": "boom"}
