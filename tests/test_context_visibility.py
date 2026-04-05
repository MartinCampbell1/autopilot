"""Tests for operator-facing context visibility helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.context_visibility import build_context_snapshot
from autopilot.core.project_store import (
    append_guidance,
    emit_project_event,
    ensure_project_state,
    register_project,
    save_project_prd,
    save_project_state,
    update_project_entry,
)
from autopilot.core.run_trace import append_trace_entry


def test_build_context_snapshot_surfaces_instruction_layers_and_recent_events(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "context-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Context Project", project_path=project_dir)
    save_project_prd(
        project,
        {
            "title": "Context Project",
            "description": "Inspect context visibility",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start", "status": "open"}],
        },
    )
    state = ensure_project_state(config, project, seed_mode="new")
    state["status"] = "running"
    state["current_story_id"] = 1
    state["runtime_session_id"] = "sess_ctx"
    state["discoveries"] = [
        {
            "id": "discovery-1",
            "story_id": 1,
            "source": "runtime",
            "kind": "constraint",
            "title": "Need env",
            "detail": "Requires API key",
            "status": "active",
            "created_at": "2026-04-02T00:00:00+00:00",
            "updated_at": "2026-04-02T00:00:00+00:00",
            "metadata": {},
        }
    ]
    save_project_state(config, project["id"], state)
    append_guidance(config, project["id"], "Do not regress the auth callback flow.", story_id=1)
    emit_project_event(
        config,
        project["id"],
        event="iteration_started",
        status="in_progress",
        story_id=1,
        message="Iteration 1 started.",
    )
    append_trace_entry(config, project["id"], {"kind": "project_event", "event": "iteration_started", "story_id": 1})
    project["verification_bootstrap"] = {
        "artifact_relpath": ".agents/tasks/verifiers.json",
        "updated_at": "2026-04-02T00:00:00+00:00",
        "check_count": 2,
    }
    project["github_bootstrap"] = {
        "workflow_relpath": ".github/workflows/autopilot-bootstrap.yml",
        "updated_at": "2026-04-02T00:00:00+00:00",
        "github_repo": "founderos/autopilot",
    }
    update_project_entry(config, project)
    (project_dir / ".agents" / "tasks").mkdir(parents=True, exist_ok=True)
    (project_dir / ".agents" / "tasks" / "verifiers.json").write_text("{}")
    (project_dir / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
    (project_dir / ".github" / "workflows" / "autopilot-bootstrap.yml").write_text("name: Autopilot Checks\n")

    payload = build_context_snapshot(config, project_path=project_dir, event_limit=5)

    assert payload["project_id"] == project["id"]
    assert payload["status"]["runtime_session_id"] == "sess_ctx"
    assert payload["instruction_layers"]["guardrails"]["present"] is True
    assert payload["instruction_layers"]["discoveries"]["count"] == 1
    assert payload["bootstrap"]["verification"]["artifact_exists"] is True
    assert payload["bootstrap"]["github"]["workflow_exists"] is True
    assert payload["recent_events"][-1]["event"] == "iteration_started"
    assert payload["trace"]["summary"]["entry_count"] >= 1
    assert "monitoring" in payload
    assert payload["audit"]["source_verification"]["verified"] is True
    assert "status=running" in payload["microcompact"]


def test_build_context_snapshot_uses_project_id_disambiguation(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "context-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Context Project", project_path=project_dir)

    called: dict[str, object] = {}
    original = __import__("autopilot.core.context_visibility", fromlist=["resolve_runtime_project_entry"]).resolve_runtime_project_entry

    def fake_resolve(*args, **kwargs):
        called["project_id"] = kwargs.get("project_id")
        return original(*args, **kwargs)

    monkeypatch.setattr("autopilot.core.context_visibility.resolve_runtime_project_entry", fake_resolve)

    payload = build_context_snapshot(config, project_path=project_dir, project_id=project["id"])

    assert called["project_id"] == project["id"]
    assert payload["project_id"] == project["id"]
