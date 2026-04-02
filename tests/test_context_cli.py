"""Tests for the context CLI helper."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer import Exit

from autopilot.cli.context import context


def test_context_cli_emits_json_payload(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.context.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.context.build_context_snapshot",
        lambda *args, **kwargs: {
            "project_id": "proj_123",
            "project_name": "Context Project",
            "project_path": str(tmp_path / "project"),
            "recent_events": [],
            "microcompact": "status=idle",
        },
    )

    context(str(tmp_path / "project"), json_output=True)
    payload = json.loads(capsys.readouterr().out)

    assert payload["project_id"] == "proj_123"
    assert payload["microcompact"] == "status=idle"


def test_context_cli_exits_nonzero_when_project_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("autopilot.cli.context.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.context.build_context_snapshot",
        lambda *args, **kwargs: (_ for _ in ()).throw(KeyError("missing")),
    )

    with pytest.raises(Exit) as exc_info:
        context(str(tmp_path / "project"), json_output=True)

    assert exc_info.value.exit_code == 1
