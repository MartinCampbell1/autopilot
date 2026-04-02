"""Tests for the resume CLI helper."""

from __future__ import annotations

import json

from autopilot.cli.resume import resume


def test_resume_cli_emits_json_discovery(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.resume.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.resume.build_resume_discovery",
        lambda config, project_path: {
            "current_path": project_path,
            "current_project_id": "proj_123",
            "projects": [],
        },
    )

    resume("/tmp/project", json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload["current_path"] == "/tmp/project"
    assert payload["current_project_id"] == "proj_123"


def test_resume_cli_can_resume_specific_project(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.resume.load_config", lambda path: object())
    monkeypatch.setattr(
        "autopilot.cli.resume.resume_project_run",
        lambda config, project_id: (True, None, f"Resumed {project_id}"),
    )

    resume("/tmp/project", project_id="proj_123", json_output=True)
    payload = json.loads(capsys.readouterr().out.strip())

    assert payload == {
        "project_id": "proj_123",
        "launched": True,
        "log_path": None,
        "message": "Resumed proj_123",
    }
