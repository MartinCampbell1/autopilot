"""Tests for the init-verifiers CLI helper."""

from __future__ import annotations

import json

import pytest
from typer import Exit

from autopilot.cli.init_verifiers import init_verifiers
from autopilot.core.verification_bootstrap import VerificationBootstrapError


def test_init_verifiers_cli_emits_json_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.init_verifiers.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.init_verifiers.build_verification_bootstrap",
        lambda *args, **kwargs: {
            "project_path": "/tmp/project",
            "project_id": "proj_123",
            "project_registered": True,
            "artifact_path": "/tmp/project/.agents/tasks/verifiers.json",
            "artifact_written": False,
            "repo": {"repo_root": "/tmp/project", "github_repo": "founderos/autopilot"},
            "tooling": {"stacks": ["python"], "package_manager": None, "gates": []},
            "checks": [],
            "recommendations": [],
        },
    )

    init_verifiers("/tmp/project", project_id="proj_123", write_artifact=False, json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload["project_path"] == "/tmp/project"
    assert payload["project_id"] == "proj_123"
    assert payload["artifact_written"] is False


def test_init_verifiers_cli_exits_nonzero_on_bootstrap_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.init_verifiers.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.init_verifiers.build_verification_bootstrap",
        lambda *args, **kwargs: (_ for _ in ()).throw(VerificationBootstrapError("boom")),
    )

    with pytest.raises(Exit) as exc_info:
        init_verifiers("/tmp/project", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert exc_info.value.exit_code == 1
    assert payload == {"ok": False, "error": "boom"}
