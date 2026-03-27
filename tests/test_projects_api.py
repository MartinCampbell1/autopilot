"""API tests for the id-based project routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import projects as projects_routes
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_project_state


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(projects_routes, "get_config", lambda: config)
    app = FastAPI()
    app.include_router(projects_routes.router, prefix="/api/projects")
    return TestClient(app)


def test_create_list_detail_and_pause_project(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "API Project",
            "project_path": str(tmp_path / "api-project"),
            "prd": {
                "title": "API Project",
                "description": "Dashboard contract test",
                "stories": [
                    {"id": 1, "title": "Bootstrap", "description": "Start", "status": "in_progress"},
                    {"id": 2, "title": "Ship", "description": "Finish", "status": "done"},
                ],
            },
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    project_id = created["project_id"]

    list_response = client.get("/api/projects/")
    assert list_response.status_code == 200
    projects = list_response.json()["projects"]
    assert projects[0]["id"] == project_id
    assert projects[0]["archived"] is False

    detail_response = client.get(f"/api/projects/{project_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["stories"][0]["status"] == "open"
    assert detail["stories"][1]["status"] == "open"

    pause_response = client.post(f"/api/projects/{project_id}/pause")
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "ok"
    assert load_project_state(config, project_id)["status"] == "paused"


def test_skip_guidance_and_archive_routes(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Archive Project",
            "project_path": str(tmp_path / "archive-project"),
            "prd": {
                "title": "Archive Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]

    guidance_response = client.post(
        f"/api/projects/{project_id}/stories/1/guidance",
        json={"payload": "Use smaller commits."},
    )
    assert guidance_response.status_code == 200

    skip_response = client.post(f"/api/projects/{project_id}/stories/1/skip")
    assert skip_response.status_code == 200
    assert load_project_state(config, project_id)["story_state"]["1"]["status"] == "skipped"

    archive_response = client.post(f"/api/projects/{project_id}/archive")
    assert archive_response.status_code == 200
    list_response = client.get("/api/projects/")
    assert list_response.json()["projects"] == []
