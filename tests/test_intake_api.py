"""API tests for intake chat and session bootstrap flows."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import intake as intake_routes
from autopilot.core.config import AutopilotConfig


class _FakeProfile:
    provider = "codex"
    name = "default"


class _FakeManager:
    def get_next(self, provider: str):
        if provider != "codex":
            return None
        return _FakeProfile()

    def build_env(self, profile) -> dict[str, str]:
        return {"PATH": "/usr/bin"}


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(intake_routes, "get_config", lambda: config)
    monkeypatch.setattr(intake_routes, "get_account_manager", lambda: _FakeManager())
    intake_routes.sessions.clear()
    app = FastAPI()
    app.include_router(intake_routes.router, prefix="/api/intake")
    return TestClient(app)


def test_intake_message_returns_spec_bootstrap(tmp_path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    def fake_run_intake_turn(session, user_message, provider, env, **kwargs):
        session.add_user_message(user_message)
        session.add_agent_message("What integrations are required?")
        session.spec_bootstrap = {
            "title": "FastAPI dashboard in an existing repo with Slack alerts.",
            "summary": "Build a FastAPI dashboard in an existing repo with Slack alerts.",
            "goals": ["Build a FastAPI dashboard in an existing repo with Slack alerts."],
            "tech_stack": ["Python", "Slack"],
            "execution_context": ["Existing repository"],
            "integrations": ["Slack"],
            "constraints": [],
            "deliverables": ["Build a FastAPI dashboard in an existing repo with Slack alerts."],
            "open_questions": ["What constraints, deadlines, or non-negotiable requirements must the plan preserve?"],
            "rendered_spec": "# FastAPI dashboard in an existing repo with Slack alerts.",
        }
        return "What integrations are required?"

    monkeypatch.setattr(intake_routes, "run_intake_turn", fake_run_intake_turn)

    response = client.post(
        "/api/intake/message",
        json={"message": "Build a FastAPI dashboard in an existing repo with Slack alerts."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["prd_ready"] is False
    assert payload["can_generate_prd"] is True
    assert payload["spec_bootstrap"]["tech_stack"] == ["Python", "Slack"]
    assert "Existing repository" in payload["spec_bootstrap"]["execution_context"]


def test_intake_generate_prd_uses_existing_session(tmp_path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    def fake_run_intake_turn(session, user_message, provider, env, **kwargs):
        session.add_user_message(user_message)
        session.add_agent_message("What integrations are required?")
        session.spec_bootstrap = {
            "title": "FastAPI bug tracker.",
            "summary": "Build a FastAPI bug tracker.",
            "goals": ["Build a FastAPI bug tracker."],
            "tech_stack": ["Python"],
            "execution_context": [],
            "integrations": [],
            "constraints": [],
            "deliverables": ["Build a FastAPI bug tracker."],
            "open_questions": [],
            "rendered_spec": "# FastAPI bug tracker.",
        }
        return "What integrations are required?"

    monkeypatch.setattr(intake_routes, "run_intake_turn", fake_run_intake_turn)
    create_response = client.post(
        "/api/intake/message",
        json={"message": "Build a FastAPI bug tracker."},
    )
    session_id = create_response.json()["session_id"]

    monkeypatch.setattr(
        intake_routes,
        "generate_prd_from_session_bootstrap",
        lambda session, provider, env, **kwargs: {
            "title": "Bug Tracker",
            "description": "Track bugs",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start", "status": "open"}],
        },
    )

    response = client.post("/api/intake/generate-prd", json={"session_id": session_id})

    assert response.status_code == 200
    assert response.json()["prd"]["title"] == "Bug Tracker"
