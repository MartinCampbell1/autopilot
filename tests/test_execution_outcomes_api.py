"""API tests for shared execution outcome exports."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import execution_outcomes as execution_outcomes_routes
from autopilot.api.routes import projects as projects_routes
from autopilot.cli.run import _mark_run_finished
from autopilot.core.github_reactions import ingest_story_github_reaction, sync_story_github_pr
from autopilot.core.config import AutopilotConfig
from autopilot.core.evals.feedback import append_feedback_record
from autopilot.core.execution_outcomes import execution_outcome_path
from autopilot.core.initiative_lineage import load_initiative_lineage
from autopilot.core.project_store import (
    auto_pause_project_run,
    emit_project_event,
    load_project_state,
    save_project_state,
)
from autopilot.core.runtime_agent_tasks import (
    create_or_reuse_runtime_agent_task,
    link_runtime_agent_task_run,
)


class _FakeManager:
    def get_next(self, provider: str):
        if provider != "codex":
            return None
        return object()

    def build_env(self, profile) -> dict[str, str]:
        return {"CODEX_HOME": "/tmp/fake"}


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(projects_routes, "get_config", lambda: config)
    monkeypatch.setattr(projects_routes, "get_account_manager", lambda: _FakeManager())
    monkeypatch.setattr(execution_outcomes_routes, "get_config", lambda: config)
    app = FastAPI()
    app.include_router(projects_routes.router, prefix="/api/projects")
    app.include_router(execution_outcomes_routes.router, prefix="/api/execution-outcomes")
    return TestClient(app)


def _shared_brief_payload() -> dict[str, object]:
    return {
        "brief_id": "brief_outcome_api_1",
        "idea_id": "idea_outcome_api_1",
        "title": "Execution Outcome Export Brief",
        "prd_summary": "Export a shared execution outcome after the run finishes.",
        "acceptance_criteria": ["Persist outcome by brief_id"],
        "risks": [],
        "recommended_tech_stack": ["python", "fastapi"],
        "first_stories": [
            {
                "title": "Export outcome",
                "description": "Build and persist the outcome bundle",
                "acceptance_criteria": ["Bundle can be fetched by brief_id"],
                "effort": "small",
            }
        ],
    }


def _v2_brief_payload() -> dict[str, object]:
    return {
        "schema_version": "2.0",
        "brief_id": "brief_outcome_v2_1",
        "revision_id": "rev-001",
        "initiative_id": "idea_outcome_v2_1",
        "title": "Execution Outcome Export Brief V2",
        "initiative_summary": "Export outcome and proof bundles for canonical V2 projects.",
        "winner_rationale": "",
        "research_summary": "",
        "success_criteria": ["Persist V2 outcome by brief_id"],
        "budget_policy": {"tier": "low"},
        "approval_policy": {"founder_approval_required": True},
        "recommended_tech_stack": ["python", "fastapi"],
        "story_breakdown": [
            {
                "title": "Export outcome",
                "description": "Build and persist the outcome bundle",
                "acceptance_criteria": ["Bundle can be fetched by brief_id"],
                "effort": "small",
            }
        ],
        "risks": [],
        "repo_dna_snapshot": {},
        "citations": [],
        "evidence": None,
        "source_pack_ref": None,
        "repo_instruction_refs": [],
        "brief_approval_status": "approved",
        "approved_by": "founder",
        "created_at": "2026-04-05T00:00:00Z",
        "updated_at": "2026-04-05T00:00:00Z",
    }


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_outcome_route_exports_bundle_for_shared_brief_project(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Execution Outcome Export Brief",
        "description": "Project created from shared brief.",
        "stories": [{"id": 1, "title": "Ship", "description": "Finish the project"}],
    }

    create_response = client.post(
        "/api/projects/from-shared-execution-brief",
        json={
            "brief": _shared_brief_payload(),
            "project_path": str(tmp_path / "execution-outcome-project"),
            "priority": "high",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()
    project_id = created["project_id"]

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_outcome_1"
    state["started_at"] = "2026-04-02T09:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 4.25
    state["cost_usage"]["run"]["estimated_cost_usd"] = 4.25
    state["story_state"]["1"]["status"] = "done"
    save_project_state(config, project_id, state)

    emit_project_event(
        config,
        project_id,
        event="run_completed",
        status="completed",
        message="Shared-brief run completed.",
        story_id=1,
        extra={"timestamp": "2026-04-02T09:15:00+00:00"},
    )

    response = client.get("/api/execution-outcomes/brief_outcome_api_1")

    assert response.status_code == 200
    payload = response.json()
    bundle = payload["bundle"]
    assert payload["status"] == "ok"
    assert payload["brief_id"] == "brief_outcome_api_1"
    assert payload["project_id"] == project_id
    assert bundle["brief_id"] == "brief_outcome_api_1"
    assert bundle["idea_id"] == "idea_outcome_api_1"
    assert bundle["status"] == "validated"
    assert bundle["verdict"] == "pass"
    assert bundle["stories_passed"] == 1
    assert bundle["total_cost_usd"] == 4.25
    assert Path(payload["path"]).exists()

    persisted = json.loads(execution_outcome_path(config, "brief_outcome_api_1").read_text())
    assert persisted["brief_id"] == "brief_outcome_api_1"
    assert persisted["status"] == "validated"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_outcome_and_proof_routes_support_v2_projects(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Execution Outcome Export Brief V2",
        "description": "Project created from canonical V2 brief.",
        "stories": [{"id": 1, "title": "Ship", "description": "Finish the project"}],
    }

    dispatched: list[dict[str, object]] = []

    def _dispatch_stub(**kwargs):
        dispatched.append(kwargs)
        on_success = kwargs.get("on_success")
        if callable(on_success):
            on_success()

    monkeypatch.setattr("autopilot.core.execution_outcomes.dispatch_learning_postback", _dispatch_stub)

    create_response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(),
            "project_path": str(tmp_path / "execution-outcome-v2-project"),
            "priority": "high",
            "launch": False,
        },
    )

    assert create_response.status_code == 200, create_response.text
    project = create_response.json()["project"]
    project_id = project["project_id"]

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_old_run"
    state["story_state"]["1"]["github_pr"] = {
        "number": 43,
        "url": "https://github.com/example/repo/pull/43",
        "ci_status": "failed",
        "review_status": "changes_requested",
        "handoff_status": "ci_failed",
    }
    save_project_state(config, project_id, state)

    emit_project_event(
        config,
        project_id,
        event="story_progressed",
        status="ok",
        message="Old run handoff snapshot.",
        story_id=1,
    )

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_outcome_v2_1"
    state["started_at"] = "2026-04-05T09:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 2.75
    state["cost_usage"]["run"]["estimated_cost_usd"] = 2.75
    state["story_state"]["1"]["status"] = "done"
    state["story_state"]["1"]["github_pr"] = {
        "number": 44,
        "url": "https://github.com/example/repo/pull/44",
        "ci_status": "success",
        "review_status": "approved",
        "handoff_status": "approved_and_green",
    }
    save_project_state(config, project_id, state)

    emit_project_event(
        config,
        project_id,
        event="artifact_generated",
        status="ok",
        message="Generated src/app.py",
        story_id=1,
        extra={"path": "src/app.py"},
    )

    emit_project_event(
        config,
        project_id,
        event="execution_issue_created",
        status="high",
        message="GitHub checks needed follow-up",
        story_id=1,
        extra={"issue_id": "iss_123"},
    )

    append_feedback_record(
        config,
        project_id,
        {
            "feedback_id": "fb-old-run",
            "run_id": "sess_old_run",
            "story_id": 1,
            "iteration": 1,
            "kind": "review_phase",
            "summary": "Old run requested changes.",
            "approved": False,
        },
    )
    append_feedback_record(
        config,
        project_id,
        {
            "feedback_id": "fb-current-run",
            "run_id": "sess_outcome_v2_1",
            "story_id": 1,
            "iteration": 2,
            "kind": "review_phase",
            "summary": "Current run approved for release.",
            "approved": True,
        },
    )

    emit_project_event(
        config,
        project_id,
        event="run_completed",
        status="completed",
        message="V2 run completed.",
        story_id=1,
        extra={"timestamp": "2026-04-05T09:15:00+00:00"},
    )

    outcome_response = client.get("/api/execution-outcomes/brief_outcome_v2_1")
    assert outcome_response.status_code == 200, outcome_response.text
    outcome_payload = outcome_response.json()
    bundle = outcome_payload["bundle"]
    assert bundle["brief_id"] == "brief_outcome_v2_1"
    assert bundle["idea_id"] == "idea_outcome_v2_1"
    assert bundle["status"] == "validated"
    assert outcome_payload["project_id"] == project_id

    proof_response = client.get("/api/execution-outcomes/brief_outcome_v2_1/proof")
    assert proof_response.status_code == 200, proof_response.text
    proof_bundle = proof_response.json()["proof_bundle"]
    assert proof_bundle["brief_id"] == "brief_outcome_v2_1"
    assert proof_bundle["initiative_id"] == "idea_outcome_v2_1"
    assert proof_bundle["outcome_status"] == "validated"
    assert "src/app.py" in proof_bundle["changed_files"]
    assert "iss_123" in proof_bundle["linked_issues"]
    assert "CI success" in proof_bundle["ci_summary"]
    assert "failed" not in proof_bundle["ci_summary"]
    assert proof_bundle["review_summary"] == "Current run approved for release."
    assert "changes_requested" not in proof_bundle["review_summary"]
    assert proof_bundle["operator_summary"] == "V2 run completed."
    assert proof_bundle["next_recommended_action"]

    assert len(dispatched) == 1
    assert dispatched[0]["idea_id"] == "idea_outcome_v2_1"

    lineage = load_initiative_lineage(config, "idea_outcome_v2_1")
    assert lineage is not None
    assert lineage.lifecycle_state.value == "learning_applied"
    assert lineage.outcome_id == bundle["outcome_id"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_proof_bundle_keeps_github_event_snapshots_when_agent_action_run_id_is_present(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Execution Outcome Export Brief V2",
        "description": "Project created from canonical V2 brief.",
        "stories": [{"id": 1, "title": "Ship", "description": "Finish the project"}],
    }

    monkeypatch.setattr("autopilot.core.execution_outcomes.dispatch_learning_postback", lambda **kwargs: None)

    create_response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(),
            "project_path": str(tmp_path / "execution-outcome-v2-agent-run-project"),
            "priority": "high",
            "launch": False,
        },
    )

    assert create_response.status_code == 200, create_response.text
    project_id = create_response.json()["project"]["project_id"]

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_runtime_scope_1"
    state["started_at"] = "2026-04-05T10:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 1.0
    state["cost_usage"]["run"]["estimated_cost_usd"] = 1.0
    state["story_state"]["1"]["status"] = "done"
    save_project_state(config, project_id, state)

    emit_project_event(
        config,
        project_id,
        event="run_completed",
        status="completed",
        message="Runtime-scoped run completed.",
        story_id=1,
    )

    sync_story_github_pr(
        config,
        project_id=project_id,
        story_id=1,
        payload={
            "number": 55,
            "url": "https://github.com/example/repo/pull/55",
            "ci_status": "success",
            "review_status": "approved",
            "handoff_status": "approved_and_green",
        },
        actor="github",
        agent_action_run_id="aar_123",
        emit_event_record=True,
    )

    proof_response = client.get("/api/execution-outcomes/brief_outcome_v2_1/proof")
    assert proof_response.status_code == 200, proof_response.text
    proof_bundle = proof_response.json()["proof_bundle"]
    assert "CI success" in proof_bundle["ci_summary"]
    assert "approved" in proof_bundle["review_summary"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_outcome_bundle_supports_cli_mark_run_finished_success_path(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Execution Outcome Export Brief V2",
        "description": "Project created from canonical V2 brief.",
        "stories": [{"id": 1, "title": "Ship", "description": "Finish the project"}],
    }

    monkeypatch.setattr("autopilot.core.execution_outcomes.dispatch_learning_postback", lambda **kwargs: None)

    create_response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(),
            "project_path": str(tmp_path / "execution-outcome-v2-cli-project"),
            "priority": "high",
            "launch": False,
        },
    )

    assert create_response.status_code == 200, create_response.text
    project_id = create_response.json()["project"]["project_id"]

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_cli_finish_1"
    state["started_at"] = "2026-04-05T11:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 3.5
    state["cost_usage"]["run"]["estimated_cost_usd"] = 3.5
    state["story_state"]["1"]["status"] = "done"
    save_project_state(config, project_id, state)

    _mark_run_finished(config, project_id, failed=False, message="All stories completed.")

    outcome_response = client.get("/api/execution-outcomes/brief_outcome_v2_1")
    assert outcome_response.status_code == 200, outcome_response.text
    outcome_bundle = outcome_response.json()["bundle"]
    assert outcome_bundle["status"] == "validated"
    assert outcome_bundle["verdict"] == "pass"

    proof_response = client.get("/api/execution-outcomes/brief_outcome_v2_1/proof")
    assert proof_response.status_code == 200, proof_response.text
    proof_bundle = proof_response.json()["proof_bundle"]
    assert proof_bundle["operator_summary"] == "All stories completed."
    assert proof_bundle["next_recommended_action"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_proof_bundle_keeps_post_pause_github_issue_context_on_same_run(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Execution Outcome Export Brief V2",
        "description": "Project created from canonical V2 brief.",
        "stories": [{"id": 1, "title": "Ship", "description": "Finish the project"}],
    }

    monkeypatch.setattr("autopilot.core.execution_outcomes.dispatch_learning_postback", lambda **kwargs: None)

    create_response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(),
            "project_path": str(tmp_path / "execution-outcome-v2-paused-project"),
            "priority": "high",
            "launch": False,
        },
    )

    assert create_response.status_code == 200, create_response.text
    project_id = create_response.json()["project"]["project_id"]

    state = load_project_state(config, project_id)
    state["runtime_session_id"] = "sess_pause_scope_1"
    state["started_at"] = "2026-04-05T12:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 4.0
    state["cost_usage"]["run"]["estimated_cost_usd"] = 4.0
    state["story_state"]["1"]["status"] = "in_progress"
    save_project_state(config, project_id, state)

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="resume",
        actor="github",
        runtime_agent_ids=["agent-2"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id="aar_pause_1")

    auto_pause_project_run(
        config,
        project_id,
        message="Budget exhausted for this run.",
        story_id=1,
    )

    payload = ingest_story_github_reaction(
        config,
        project_id=project_id,
        story_id=1,
        reaction_type="approved_and_green",
        actor="github",
        agent_action_run_id="aar_pause_1",
    )

    proof_response = client.get("/api/execution-outcomes/brief_outcome_v2_1/proof")
    assert proof_response.status_code == 200, proof_response.text
    proof_bundle = proof_response.json()["proof_bundle"]
    assert "CI green" in proof_bundle["ci_summary"]
    assert payload["issue"] is not None
    assert payload["issue"]["id"] in proof_bundle["linked_issues"]
    assert payload["approval"] is not None
    assert payload["approval"]["id"] in proof_bundle["approvals"]
