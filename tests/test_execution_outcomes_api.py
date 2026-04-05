"""API tests for shared execution outcome exports."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import execution_outcomes as execution_outcomes_routes
from autopilot.api.routes import projects as projects_routes
from autopilot.core.config import AutopilotConfig
from autopilot.core.execution_outcomes import execution_outcome_path
from autopilot.core.initiative_lineage import load_initiative_lineage
from autopilot.core.project_store import emit_project_event, load_project_state, save_project_state


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
    state["runtime_session_id"] = "sess_outcome_v2_1"
    state["started_at"] = "2026-04-05T09:00:00+00:00"
    state["cost_usage"]["project"]["estimated_cost_usd"] = 2.75
    state["cost_usage"]["run"]["estimated_cost_usd"] = 2.75
    state["story_state"]["1"]["status"] = "done"
    save_project_state(config, project_id, state)

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

    assert len(dispatched) == 1
    assert dispatched[0]["idea_id"] == "idea_outcome_v2_1"

    lineage = load_initiative_lineage(config, "idea_outcome_v2_1")
    assert lineage is not None
    assert lineage.lifecycle_state.value == "learning_applied"
    assert lineage.outcome_id == bundle["outcome_id"]
