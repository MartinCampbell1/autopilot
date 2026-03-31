"""API tests for inbound integration triggers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import integrations as integrations_routes
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import get_project_entry


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(integrations_routes, "get_config", lambda: config)
    app = FastAPI()
    app.include_router(integrations_routes.router, prefix="/api/integrations")
    return TestClient(app)


def test_github_issue_trigger_creates_project_and_links_tracker_ref(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.post(
        "/api/integrations/github/issues",
        json={
            "action": "opened",
            "repository": {
                "id": 1,
                "name": "autopilot",
                "full_name": "martin/autopilot",
                "html_url": "https://github.com/martin/autopilot",
            },
            "issue": {
                "id": 101,
                "number": 42,
                "title": "Add tracker ingestion",
                "body": "- [ ] Parse webhook payload\n- [ ] Link issue to project",
                "html_url": "https://github.com/martin/autopilot/issues/42",
                "labels": [{"name": "backend"}, {"name": "integration"}],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["project"]["stories"][0]["title"] == "Add tracker ingestion"
    assert payload["project"]["stories"][0]["acceptance_criteria"] == [
        "Parse webhook payload",
        "Link issue to project",
    ]

    project = get_project_entry(config, project_id=payload["project"]["id"], include_archived=True)
    assert project is not None
    assert project["tracker_refs"][0]["provider"] == "github"
    assert project["tracker_refs"][0]["external_id"] == "101"


def test_github_issue_trigger_reuses_existing_project_for_same_issue(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    request_payload = {
        "action": "opened",
        "repository": {
            "id": 1,
            "name": "autopilot",
            "full_name": "martin/autopilot",
            "html_url": "https://github.com/martin/autopilot",
        },
        "issue": {
            "id": 202,
            "number": 77,
            "title": "Avoid duplicate project creation",
            "body": "Keep tracker triggers idempotent.",
            "html_url": "https://github.com/martin/autopilot/issues/77",
            "labels": [],
        },
    }

    first = client.post("/api/integrations/github/issues", json=request_payload)
    second = client.post("/api/integrations/github/issues", json=request_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project"]["id"] == second.json()["project"]["id"]
    assert second.json()["created"] is False
