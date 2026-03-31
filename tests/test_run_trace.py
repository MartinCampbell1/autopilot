"""Tests for structured run trace helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.cli.trace import trace
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import register_project
from autopilot.core.run_trace import append_trace_entry, build_trace_summary, read_trace_entries


def test_append_and_read_trace_entries(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    append_trace_entry(config, "demo", {"kind": "project_event", "event": "run_started"})
    append_trace_entry(config, "demo", {"kind": "iteration_record", "story_id": 1, "status": "approved"})

    entries = read_trace_entries(config, "demo")
    summary = build_trace_summary(entries)

    assert len(entries) == 2
    assert summary["by_kind"]["project_event"] == 1
    assert summary["stories"][0]["story_id"] == 1


def test_trace_cli_emits_json_payload(tmp_path: Path, monkeypatch, capsys) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "trace-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Trace Project", project_path=project_dir)
    append_trace_entry(config, project["id"], {"kind": "project_event", "event": "run_started"})

    monkeypatch.setenv("AUTOPILOT_HOME", str(config.autopilot_home))

    trace(str(project_dir), None, 10, True)
    payload = json.loads(capsys.readouterr().out)

    assert payload["project_id"] == project["id"]
    assert payload["summary"]["entry_count"] == 1
