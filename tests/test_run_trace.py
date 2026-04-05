"""Tests for structured run trace helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.cli.audit import audit
from autopilot.cli.trace import trace
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import register_project
from autopilot.core.run_trace import (
    append_trace_entry,
    build_trace_audit_bundle,
    build_trace_summary,
    read_trace_entries,
    trace_path,
    verify_trace_chain,
)


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


def test_verify_trace_chain_detects_tampered_stored_history(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    append_trace_entry(config, "demo", {"kind": "project_event", "event": "run_started", "run_id": "sess_demo"})
    append_trace_entry(config, "demo", {"kind": "project_event", "event": "run_finished", "run_id": "sess_demo"})

    path = trace_path(config, "demo")
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["event"] = "run_failed"
    lines[1] = json.dumps(tampered, ensure_ascii=False)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    verification = verify_trace_chain(read_trace_entries(config, "demo"))

    assert verification["verified"] is False
    assert verification["errors"][0]["reason"] in {"payload_digest_mismatch", "entry_hash_mismatch"}


def test_build_trace_audit_bundle_exports_filtered_run_bundle(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "audit-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Audit Project", project_path=project_dir)

    append_trace_entry(config, project["id"], {"kind": "project_event", "event": "run_started", "run_id": "sess_a", "story_id": 1})
    append_trace_entry(config, project["id"], {"kind": "iteration_record", "run_id": "sess_a", "story_id": 1, "status": "approved"})
    append_trace_entry(config, project["id"], {"kind": "project_event", "event": "run_started", "run_id": "sess_b", "story_id": 2})

    bundle = build_trace_audit_bundle(config, project["id"], run_id="sess_a")

    assert bundle["audit_chain"]["chain_kind"] == "trace"
    assert bundle["audit_chain"]["package_chain_kind"] == "trace_export"
    assert bundle["audit_chain"]["verification"]["verified"] is True
    assert bundle["audit_chain"]["source_verification"]["verified"] is True
    assert bundle["summary"]["entry_count"] == 2
    assert bundle["source_summary"]["entry_count"] == 3
    assert bundle["replay"]["run_ids"] == ["sess_a"]
    assert len(bundle["entries"]) == 2
    assert all(entry["audit"]["chain_kind"] == "trace_export" for entry in bundle["entries"])
    assert all(entry["source_audit"]["chain_kind"] == "trace" for entry in bundle["entries"])


def test_audit_cli_emits_json_payload_and_exports_bundle(tmp_path: Path, monkeypatch, capsys) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "audit-cli-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Audit CLI Project", project_path=project_dir)
    append_trace_entry(config, project["id"], {"kind": "project_event", "event": "run_started", "run_id": "sess_cli"})

    monkeypatch.setenv("AUTOPILOT_HOME", str(config.autopilot_home))
    export_path = tmp_path / "audit-bundle.json"

    audit(str(project_dir), None, 10, True, run_id="sess_cli", export_path=str(export_path))
    payload = json.loads(capsys.readouterr().out)
    exported = json.loads(export_path.read_text(encoding="utf-8"))

    assert payload["project_id"] == project["id"]
    assert payload["audit"]["audit_chain"]["verification"]["verified"] is True
    assert payload["audit"]["audit_chain"]["source_verification"]["verified"] is True
    assert exported["audit"]["entries"][0]["source_audit"]["chain_kind"] == "trace"
