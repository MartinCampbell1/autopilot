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


def test_review_cli_can_emit_github_markdown(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.review.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.review.build_local_review",
        lambda *args, **kwargs: {
            "project_path": "/tmp/project",
            "verdict": "PARTIAL",
            "repo": {"github_repo": "founderos/autopilot"},
            "findings": [],
            "gates": [],
            "checks": [],
            "summary": {"command_backed_evidence": True, "adversarial_probe_status": "PASS"},
            "judge": {"pack_id": "execution_claims", "verdict": "PARTIAL", "summary": "Need more evidence."},
        },
    )

    review("/tmp/project", github_markdown=True)
    output = capsys.readouterr().out

    assert "## Autopilot Review" in output
    assert "Review event: `COMMENT`" in output
    assert "Judge pack: `execution_claims`" in output


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
