"""API tests for the id-based project routes."""

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import projects as projects_routes
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_project_state


class _FakeManager:
    def get_next(self, provider: str):
        if provider != "codex":
            return None
        return object()

    def build_env(self, profile) -> dict[str, str]:
        return {"CODEX_HOME": "/tmp/fake"}


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


def test_patch_budget_policy_route_updates_state(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Budget Project",
            "project_path": str(tmp_path / "budget-project"),
            "prd": {
                "title": "Budget Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]

    response = client.patch(
        f"/api/projects/{project_id}/budget-policy",
        json={
            "project_max_worker_iterations": 12,
            "agent_max_critic_reviews": 4,
            "auto_pause_on_exhaustion": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["budget_policy"]["project_max_worker_iterations"] == 12
    assert payload["budget_policy"]["agent_max_critic_reviews"] == 4
    assert payload["budget_policy"]["auto_pause_on_exhaustion"] is False


def test_runtime_control_route_returns_workspace_policy(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Control Project",
            "project_path": str(tmp_path / "control-project"),
            "prd": {
                "title": "Control Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]

    response = client.get(f"/api/projects/{project_id}/runtime-control")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project_id
    assert "stories" in payload
    assert "leases" in payload


def test_recover_checkout_route_clears_story_checkout(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Recover Project",
            "project_path": str(tmp_path / "recover-project"),
            "prd": {
                "title": "Recover Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]
    state = load_project_state(config, project_id)
    state["story_state"]["1"]["status"] = "merge_blocked"
    state["story_state"]["1"]["ownership"] = {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"}
    state["story_state"]["1"]["checkout"] = {"mode": "worktree", "path": str(tmp_path / "recover-project-story-1"), "branch_name": "story-1"}
    state["story_state"]["1"]["worktree_path"] = str(tmp_path / "recover-project-story-1")
    state["story_state"]["1"]["branch_name"] = "story-1"
    (config.runtime_state_dir / f"{project_id}.json").write_text(json.dumps(state))

    with patch("autopilot.core.workspace_policy.remove_worktree") as mock_remove_worktree:
        response = client.post(
            f"/api/projects/{project_id}/stories/1/recover-checkout",
            json={"cleanup_worktree": False, "reopen_story": True},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reopened"] is True
    updated = load_project_state(config, project_id)
    assert updated["story_state"]["1"]["status"] == "open"
    assert updated["story_state"]["1"]["checkout"] is None
    mock_remove_worktree.assert_not_called()


def test_recover_stale_checkouts_route_returns_recovered_entries(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Sweep Project",
            "project_path": str(tmp_path / "sweep-project"),
            "prd": {
                "title": "Sweep Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]

    monkeypatch.setattr(
        projects_routes,
        "sweep_stale_project_checkouts",
        lambda _config, _project_id, stale_after_sec=900, cleanup_worktrees=True, reopen_stories=True: {
            "project_id": _project_id,
            "stale_after_sec": stale_after_sec,
            "recovered": [{"story_id": 1, "cleanup_performed": True, "reopened": True}],
        },
    )

    response = client.post(
        f"/api/projects/{project_id}/runtime-control/recover-stale",
        json={"cleanup_worktrees": True, "reopen_stories": True, "stale_after_sec": 45},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["stale_after_sec"] == 45
    assert payload["recovered"][0]["story_id"] == 1


@patch("autopilot.api.routes.projects.launch_project_run")
def test_launch_route_accepts_launch_profile(mock_launch_project_run, tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Launch Project",
            "project_path": str(tmp_path / "launch-project"),
            "prd": {
                "title": "Launch Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]
    state = load_project_state(config, project_id)
    state["launch_profile"] = {
        "preset": "team",
        "story_execution_mode": "team",
        "project_concurrency_mode": "sequential",
        "max_parallel_stories": 1,
    }
    (config.runtime_state_dir / f"{project_id}.json").write_text(json.dumps(state))

    mock_launch_project_run.return_value = (True, config.autopilot_home / "logs" / "demo.log", "Background run started.")

    response = client.post(
        f"/api/projects/{project_id}/launch",
        json={
            "launch_profile": {
                "preset": "parallel",
                "story_execution_mode": "team",
                "project_concurrency_mode": "parallel",
                "max_parallel_stories": 2,
            }
        },
    )

    assert response.status_code == 200
    assert response.json()["launch_profile"]["preset"] == "team"
    assert mock_launch_project_run.call_args.kwargs["launch_profile"]["preset"] == "parallel"


@patch("autopilot.api.routes.projects.resume_project_run")
def test_resume_route_serializes_launch_profile(mock_resume_project_run, tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_response = client.post(
        "/api/projects/",
        json={
            "project_name": "Resume Project",
            "project_path": str(tmp_path / "resume-project"),
            "prd": {
                "title": "Resume Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            },
        },
    )
    project_id = create_response.json()["project_id"]
    state = load_project_state(config, project_id)
    state["launch_profile"] = {
        "preset": "team",
        "story_execution_mode": "team",
        "project_concurrency_mode": "sequential",
        "max_parallel_stories": 1,
    }
    (config.runtime_state_dir / f"{project_id}.json").write_text(json.dumps(state))

    mock_resume_project_run.return_value = (True, config.autopilot_home / "logs" / "resume.log", "Background run started.")

    response = client.post(f"/api/projects/{project_id}/resume")

    assert response.status_code == 200
    assert response.json()["launch_profile"]["preset"] == "team"


def test_execution_brief_schema_route_exposes_json_schema(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.get("/api/projects/execution-brief/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "ExecutionBrief"
    assert "properties" in payload
    assert "title" in payload["properties"]
    assert "founder" in payload["properties"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
@patch("autopilot.core.project_store.launch_project_run")
def test_create_project_from_execution_brief(
    mock_launch_project_run,
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    monkeypatch.setattr(projects_routes, "get_account_manager", lambda: _FakeManager())
    client = _build_client(config, monkeypatch)

    mock_generate_prd_from_spec.return_value = {
        "title": "GraphRAG Copilot",
        "description": "Execution-ready brief converted into a PRD.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Set up the project"}],
    }
    mock_launch_project_run.return_value = (True, config.autopilot_home / "logs" / "bridge.log", "Background run started.")

    response = client.post(
        "/api/projects/from-execution-brief",
        json={
            "brief": {
                "title": "GraphRAG Copilot",
                "thesis": "Build a niche affiliate GraphRAG copilot for paid media buyers.",
                "summary": "Bridge a ranked business hypothesis into an execution-ready project.",
                "tags": ["affiliate", "graphrag", "ai"],
                "founder": {
                    "mode": "solo_ai_augmented",
                    "strengths": ["python", "agents", "graphs"],
                    "constraints": ["ship in 30 days"],
                },
                "market": {
                    "icp": "affiliate operators and media buyers",
                    "pain": "fragmented affiliate intel and no structured retrieval",
                    "wedge": "existing research corpus plus graph retrieval",
                },
                "execution": {
                    "mvp_scope": ["ingest corpus", "graph retrieval", "chat workflow"],
                    "required_connectors": ["web_docs", "github"],
                    "existing_repos": ["/Users/example/Desktop/Projects/graphrag-affiliate"],
                },
                "monetization": {
                    "revenue_model": "subscription",
                    "pricing_hint": "$99-$199/mo",
                    "time_to_first_dollar": "2-4 weeks",
                },
                "evaluation": {
                    "success_metrics": ["3 paid pilots", "daily retained usage"],
                    "kill_criteria": ["no clear ICP response after 10 demos"],
                },
                "provenance": {
                    "source_system": "quorum",
                    "source_session_id": "sess_demo",
                    "source_mode": "tournament",
                },
            },
            "project_path": str(tmp_path / "execution-brief-project"),
            "priority": "high",
            "launch": True,
            "launch_profile": {
                "preset": "parallel",
                "story_execution_mode": "team",
                "project_concurrency_mode": "parallel",
                "max_parallel_stories": 2,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["project_name"] == "GraphRAG Copilot"
    assert payload["prd"]["title"] == "GraphRAG Copilot"
    assert payload["launched"] is True
    assert payload["log_path"].endswith("bridge.log")
    assert payload["execution_brief_path"].endswith(".agents/tasks/execution-brief.json")
    assert "Core Thesis" in mock_generate_prd_from_spec.call_args.args[0]
    assert "Founder Context" in mock_generate_prd_from_spec.call_args.args[0]
    assert payload["project"]["source_kind"] == "execution_brief"
    assert mock_launch_project_run.call_args.kwargs["launch_profile"]["preset"] == "parallel"

    state = load_project_state(config, payload["project_id"])
    assert state["launch_profile"]["preset"] == "fast"
