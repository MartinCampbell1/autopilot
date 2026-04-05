"""API tests for intake routes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import intake as intake_routes
from autopilot.core.config import AutopilotConfig


class _FakeManager:
    def get_next(self, provider: str):
        if provider != "codex":
            return None
        return object()

    def build_env(self, profile) -> dict[str, str]:
        return {"CODEX_HOME": "/tmp/fake"}


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(intake_routes, "get_config", lambda: config)
    monkeypatch.setattr(intake_routes, "get_account_manager", lambda: _FakeManager())
    app = FastAPI()
    app.include_router(intake_routes.router, prefix="/api/intake")
    return TestClient(app)


def _shared_brief_payload() -> dict[str, object]:
    return {
        "brief_id": "brief_intake_1",
        "idea_id": "idea_intake_1",
        "title": "Shared Intake Brief",
        "prd_summary": "Accept Quorum briefs directly in intake.",
        "acceptance_criteria": ["Generate a PRD from the shared brief"],
        "risks": [],
        "recommended_tech_stack": ["fastapi", "python"],
        "first_stories": [
            {
                "title": "Accept shared brief",
                "description": "Parse shared payloads",
                "acceptance_criteria": ["Route validates shared contract"],
                "effort": "small",
            }
        ],
    }


@patch("autopilot.api.routes.intake.generate_prd_from_spec")
def test_intake_route_accepts_shared_execution_brief(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "Shared Intake Brief",
        "description": "Generated from shared brief",
        "stories": [{"id": 1, "title": "Bridge", "description": "Implement bridge"}],
    }

    response = client.post("/api/intake/shared-brief", json={"brief": _shared_brief_payload()})

    assert response.status_code == 200
    payload = response.json()
    assert payload["prd"]["title"] == "Shared Intake Brief"
    spec = mock_generate_prd_from_spec.call_args.args[0]
    assert "Core Thesis" in spec
    assert "Accept Quorum briefs directly in intake." in spec


@patch("autopilot.api.routes.intake.run_intake_turn")
def test_intake_route_returns_session_detail(
    mock_run_intake_turn,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    def _fake_run_intake_turn(*, session, user_message, **_kwargs) -> str:
        session.add_user_message(user_message)
        session.add_agent_message("What runtime and repo context should this use?")
        session.spec_bootstrap = {
            "title": "Route-aware intake",
            "summary": "Persist intake state behind a stable session URL.",
            "open_questions": ["What runtime profile should launch use?"],
            "rendered_spec": "Route-aware intake spec",
        }
        return "What runtime and repo context should this use?"

    mock_run_intake_turn.side_effect = _fake_run_intake_turn

    post_response = client.post("/api/intake/message", json={"message": "Build a route-aware intake flow"})
    assert post_response.status_code == 200
    session_id = post_response.json()["session_id"]
    restarted_client = _build_client(config, monkeypatch)

    list_response = restarted_client.get("/api/intake/sessions")
    assert list_response.status_code == 200
    list_payload = list_response.json()["sessions"]
    assert list_payload[0]["id"] == session_id
    assert list_payload[0]["title"] == "Route-aware intake"
    assert list_payload[0]["updated_at"]
    assert list_payload[0]["last_message"] == "What runtime and repo context should this use?"

    response = restarted_client.get(f"/api/intake/sessions/{session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["title"] == "Route-aware intake"
    assert payload["updated_at"]
    assert payload["bootstrap_ready"] is True
    assert payload["can_generate_prd"] is True
    assert payload["spec_bootstrap"]["title"] == "Route-aware intake"
    assert payload["messages"] == [
        {"role": "user", "content": "Build a route-aware intake flow"},
        {
            "role": "assistant",
            "content": "What runtime and repo context should this use?",
        },
    ]


@patch("autopilot.api.routes.intake.generate_prd_from_session_bootstrap")
@patch("autopilot.api.routes.intake.run_intake_turn")
def test_intake_route_persists_generated_prd_across_client_rebuild(
    mock_run_intake_turn,
    mock_generate_prd_from_session_bootstrap,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    def _fake_run_intake_turn(*, session, user_message, **_kwargs) -> str:
        session.add_user_message(user_message)
        session.add_agent_message("Which repo should this land in?")
        session.spec_bootstrap = {
            "title": "Durable intake",
            "summary": "Persist interview sessions across backend restarts.",
            "open_questions": ["Which repo should this land in?"],
            "rendered_spec": "Durable intake spec",
        }
        return "Which repo should this land in?"

    def _fake_generate_prd(*args, **kwargs) -> dict:
        session = args[0]
        session.prd = {
            "title": "Durable intake",
            "description": "PRD generated from a persisted intake session.",
            "stories": [
                {
                    "id": 1,
                    "title": "Persist intake sessions",
                    "description": "Save and restore intake sessions from disk.",
                }
            ],
        }
        return session.prd

    mock_run_intake_turn.side_effect = _fake_run_intake_turn
    mock_generate_prd_from_session_bootstrap.side_effect = _fake_generate_prd

    create_response = client.post("/api/intake/message", json={"message": "Make intake durable"})
    assert create_response.status_code == 200
    session_id = create_response.json()["session_id"]

    restarted_client = _build_client(config, monkeypatch)
    generate_response = restarted_client.post("/api/intake/generate-prd", json={"session_id": session_id})
    assert generate_response.status_code == 200
    assert generate_response.json()["prd"]["title"] == "Durable intake"

    refreshed_client = _build_client(config, monkeypatch)
    detail_response = refreshed_client.get(f"/api/intake/sessions/{session_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["prd"]["title"] == "Durable intake"
