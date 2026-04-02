"""Tests for the review CLI helper."""

from __future__ import annotations

import json

import pytest
from typer import Exit

from autopilot.cli.review import review


def test_review_cli_emits_json_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.review.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.review.build_local_review",
        lambda *args, **kwargs: {
            "project_path": "/tmp/project",
            "verdict": "PASS",
            "findings": [],
            "gates": [],
            "checks": [],
            "summary": {},
        },
    )

    review("/tmp/project", json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload["project_path"] == "/tmp/project"
    assert payload["verdict"] == "PASS"


def test_review_cli_uses_nonzero_exit_for_fail_verdict(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.review.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.review.build_local_review",
        lambda *args, **kwargs: {
            "project_path": "/tmp/project",
            "verdict": "FAIL",
            "findings": [],
            "gates": [],
            "checks": [],
            "summary": {},
        },
    )

    with pytest.raises(Exit) as exc_info:
        review("/tmp/project", json_output=True)

    payload = json.loads(capsys.readouterr().out.strip())
    assert exc_info.value.exit_code == 1
    assert payload["verdict"] == "FAIL"
