"""API tests for inbound integration triggers."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import integrations as integrations_routes
from autopilot.core.config import AutopilotConfig, TrackerConfig
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
    assert project["task_source"]["source_kind"] == "github_issue"
    assert project["task_source"]["branch_policy"] == "isolated_worktree"


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


def test_generic_tracker_trigger_creates_project_and_links_tracker_ref(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        trackers=[
            TrackerConfig(
                id="linear",
                display_name="Linear",
                kind="issue_tracker",
                transport="webhook",
                endpoint="https://linear.example.com/hooks/autopilot",
                auth_strategy="bearer",
                event_kinds=["issue.created"],
            )
        ],
    )
    client = _build_client(config, monkeypatch)

    response = client.post(
        "/api/integrations/tracker-items",
        json={
            "tracker_id": "linear",
            "action": "issue.created",
            "item_kind": "issue",
            "repository": {
                "id": 11,
                "name": "founderos",
                "full_name": "team/founderos",
                "url": "https://linear.example.com/team/founderos",
            },
            "item": {
                "external_id": "ENG-42",
                "title": "Ship notifier registry",
                "body": "- [ ] Surface configured channels\n- [ ] Show readiness state",
                "url": "https://linear.example.com/issue/ENG-42",
                "labels": ["backend", "platform"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["created"] is True
    assert payload["project"]["stories"][0]["title"] == "Ship notifier registry"
    assert payload["project"]["stories"][0]["acceptance_criteria"] == [
        "Surface configured channels",
        "Show readiness state",
    ]
    project = get_project_entry(config, project_id=payload["project"]["id"], include_archived=True)
    assert project is not None
    assert project["tracker_refs"][0]["provider"] == "linear"
    assert project["tracker_refs"][0]["external_id"] == "ENG-42"
    assert project["task_source"]["source_kind"] == "tracker_item"
    assert project["task_source"]["branch_policy"] == "isolated_worktree"


def test_generic_tracker_trigger_reuses_existing_project_for_same_item(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        trackers=[
            TrackerConfig(
                id="jira",
                display_name="Jira",
                kind="issue_tracker",
                transport="webhook",
                endpoint="https://jira.example.com/hooks/autopilot",
                auth_strategy="bearer",
                event_kinds=["issue_created"],
            )
        ],
    )
    client = _build_client(config, monkeypatch)
    request_payload = {
        "tracker_id": "jira",
        "action": "issue_created",
        "item_kind": "ticket",
        "repository": {
            "id": 22,
            "name": "platform",
            "full_name": "eng/platform",
            "url": "https://jira.example.com/projects/PLAT",
        },
        "item": {
            "external_id": "PLAT-7",
            "title": "Keep tracker triggers idempotent",
            "body": "Do not create duplicate projects.",
            "url": "https://jira.example.com/browse/PLAT-7",
            "labels": [],
        },
    }

    first = client.post("/api/integrations/tracker-items", json=request_payload)
    second = client.post("/api/integrations/tracker-items", json=request_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project"]["id"] == second.json()["project"]["id"]
    assert second.json()["created"] is False
