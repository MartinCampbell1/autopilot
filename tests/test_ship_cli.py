"""Tests for the ship CLI helper."""

from __future__ import annotations

import json

import pytest
from typer import Exit

from autopilot.cli.ship import ship
from autopilot.core.shipping import ShippingError


def test_ship_cli_emits_json_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.ship.ship_repo",
        lambda *args, **kwargs: {
            "repo_root": "/tmp/project",
            "github_repo": "founderos/autopilot",
            "branch": "feature/ship-loop",
            "base_branch": "main",
            "dirty_before_ship": False,
            "commit_created": False,
            "push_performed": True,
            "pr_created": True,
            "bootstrap": {"verification": {"artifact_exists": True}, "github": {"workflow_exists": True}},
            "pull_request": {"number": 9, "url": "https://example.test/pr/9"},
        },
    )

    ship("/tmp/project", json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload["branch"] == "feature/ship-loop"
    assert payload["bootstrap"]["verification"]["artifact_exists"] is True
    assert payload["pull_request"]["number"] == 9


def test_ship_cli_exits_nonzero_on_shipping_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.ship.ship_repo",
        lambda *args, **kwargs: (_ for _ in ()).throw(ShippingError("boom")),
    )

    with pytest.raises(Exit) as exc_info:
        ship("/tmp/project", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert exc_info.value.exit_code == 1
    assert payload == {"ok": False, "error": "boom"}


def test_ship_cli_surfaces_bootstrap_readiness_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "autopilot.cli.ship.ship_repo",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ShippingError("Verifier bootstrap artifact is missing. Run `autopilot init-verifiers /tmp/project` before `autopilot ship`.")
        ),
    )

    with pytest.raises(Exit) as exc_info:
        ship("/tmp/project", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert exc_info.value.exit_code == 1
    assert "autopilot init-verifiers /tmp/project" in payload["error"]
