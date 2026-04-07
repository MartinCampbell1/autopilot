"""API tests for the stable execution-plane surface."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import execution_plane as execution_plane_routes
from autopilot.core.agent_mailbox import list_agent_mailbox_messages
from autopilot.core.agent_action_runs import create_agent_action_batch_run
from autopilot.core.approval_runtime import annotate_approval_runtime, create_or_reuse_approval_runtime
from autopilot.core.config import AutopilotConfig
from autopilot.core import execution_plane as execution_plane_core
from autopilot.core.project_store import (
    emit_project_event,
    load_project_state,
    register_project,
    save_project_state,
    update_project_runtime,
    update_story_runtime,
)
from autopilot.core.runtime_agent_tasks import create_or_reuse_runtime_agent_task, link_runtime_agent_task_run
from autopilot.core.shadow_audit import create_shadow_audit_record
from autopilot.core.tool_permissions import PermissionRuleValue, PermissionUpdate, persist_permission_update


class _FakeManager:
    def get_next(self, provider: str):
        if provider != "codex":
            return None
        return object()

    def build_env(self, profile) -> dict[str, str]:
        return {"CODEX_HOME": "/tmp/fake"}


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(execution_plane_routes, "get_config", lambda: config)
    monkeypatch.setattr(execution_plane_routes, "get_account_manager", lambda: _FakeManager())
    app = FastAPI()
    app.include_router(execution_plane_routes.router, prefix="/api/execution-plane")
    return TestClient(app)


def _create_execution_project(client: TestClient, project_root: Path) -> dict:
    response = client.post(
        "/api/execution-plane/projects/from-brief",
        json={
            "brief": {
                "title": "FounderOS Copilot",
                "thesis": "Turn ranked initiatives into shipped execution projects.",
                "summary": "Bridge FounderOS into the Autopilot execution plane.",
                "initiative": {
                    "id": "init_founderos_1",
                    "title": "FounderOS Execution Plane",
                    "stage": "mvp",
                    "hypothesis_id": "hyp_founderos_1",
                    "track": "core",
                },
                "orchestration": {
                    "orchestrator": "founderos",
                    "run_id": "run_123",
                    "initiative_ref": "founderos/init_founderos_1",
                    "project_ref": "founderos/proj_abc",
                    "requested_launch_preset": "parallel",
                },
                "provenance": {
                    "source_system": "quorum",
                    "source_session_id": "sess_founderos_1",
                    "source_mode": "tournament",
                },
                "execution": {
                    "mvp_scope": ["brief ingest", "project mapping", "execution state export"],
                    "required_connectors": ["github"],
                },
            },
            "project_path": str(project_root),
            "priority": "high",
        },
    )
    assert response.status_code == 200
    return response.json()


def _shared_brief_payload() -> dict[str, object]:
    return {
        "brief_id": "brief_execution_plane_1",
        "idea_id": "idea_execution_plane_1",
        "title": "FounderOS Shared Brief",
        "prd_summary": "Bridge Quorum shared briefs into execution-plane projects.",
        "acceptance_criteria": ["Shared brief ingestion works", "Outcome export links back to brief"],
        "risks": [
            {
                "category": "technical",
                "description": "Cross-plane schema drift",
                "level": "high",
                "mitigation": "Use one canonical shared module",
            }
        ],
        "recommended_tech_stack": ["python", "fastapi", "pydantic"],
        "first_stories": [
            {
                "title": "Accept shared brief",
                "description": "Create a project from the shared contract",
                "acceptance_criteria": ["Route accepts payload"],
                "effort": "small",
            }
        ],
        "judge_summary": "The idea is execution-ready.",
        "confidence": "high",
        "effort": "small",
        "urgency": "this_week",
        "budget_tier": "low",
    }


def _create_orchestrator_session(
    client: TestClient,
    *,
    project_ids: list[str] | None = None,
    initiative_id: str = "init_founderos_1",
    orchestrator: str = "founderos",
    actor: str = "external-orchestrator",
    title: str = "FounderOS orchestration loop",
    reason: str = "",
    context: dict[str, object] | None = None,
) -> dict:
    response = client.post(
        "/api/execution-plane/orchestrator-sessions",
        json={
            "orchestrator": orchestrator,
            "actor": actor,
            "title": title,
            "initiative_id": initiative_id,
            "project_ids": project_ids or [],
            "reason": reason,
            "context": context or {},
        },
    )
    assert response.status_code == 200
    return response.json()["session"]


def test_execution_plane_brief_schema_route_exposes_extended_context(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.get("/api/execution-plane/execution-brief/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "ExecutionBrief"
    assert "initiative" in payload["properties"]
    assert "orchestration" in payload["properties"]


def test_execution_plane_shared_brief_schema_route_exposes_cross_seam_contract(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.get("/api/execution-plane/shared-execution-brief/schema")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "ExecutionBrief"
    assert "brief_id" in payload["properties"]
    assert "idea_id" in payload["properties"]


def test_execution_plane_tool_permission_runtime_routes_get_and_resolve(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    runtime = create_or_reuse_approval_runtime(
        config,
        key="tool-permission:proj_runtime_api:demo.pause:toolu_api_1",
        project_id="proj_runtime_api",
        runtime_agent_ids=["proj_runtime_api:1:worker:a"],
        metadata={
            "kind": "tool_permission_request",
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_api_1",
        },
        publish_pending=True,
        pending_message_type="tool_permission_pending",
        pending_payload={
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_api_1",
            "message": "Need explicit approval.",
            "behavior": "pending_user",
        },
    )
    annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={"pending": {"stage": "pending_user", "tool_name": "demo.pause", "tool_use_id": "toolu_api_1"}},
        payload_updates={"pending_user": {"message": "Need explicit approval.", "tool_name": "demo.pause", "tool_use_id": "toolu_api_1"}},
        mailbox_message_type="tool_permission_user_pending",
        mailbox_payload={"tool_name": "demo.pause", "tool_use_id": "toolu_api_1"},
    )

    detail_response = client.get(f"/api/execution-plane/tool-permission-runtimes/{runtime.id}")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()["runtime"]
    assert detail_payload["id"] == runtime.id
    assert detail_payload["metadata"]["pending"]["stage"] == "pending_user"

    allow_response = client.post(
        f"/api/execution-plane/tool-permission-runtimes/{runtime.id}/allow",
        json={"actor": "founderos", "note": "Proceed with the tool.", "source": "user"},
    )
    assert allow_response.status_code == 200
    runtime_payload = allow_response.json()["runtime"]
    mailbox = list_agent_mailbox_messages(config, approval_runtime_id=runtime.id)

    assert runtime_payload["status"] == "resolved"
    assert runtime_payload["winner_source"] == "user"
    assert runtime_payload["outcome"] == "allow"
    assert runtime_payload["payload"]["resolution"]["actor"] == "founderos"
    assert any(message.message_type == "tool_permission_user_allow" for message in mailbox)
    assert any(message.message_type == "approval_runtime_resolved" for message in mailbox)

    repeat_response = client.post(
        f"/api/execution-plane/tool-permission-runtimes/{runtime.id}/deny",
        json={"actor": "founderos", "note": "Too late.", "source": "user"},
    )
    assert repeat_response.status_code == 409


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_surfaces_pending_tool_permission_runtimes_in_project_and_agent_detail(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    created = _create_execution_project(client, tmp_path / "tool-permission-runtime-project")
    project_id = created["project"]["project_id"]
    agents_response = client.get(f"/api/execution-plane/projects/{project_id}/agents")
    assert agents_response.status_code == 200
    runtime_agent_id = agents_response.json()["agents"][0]["agent_id"]

    runtime = create_or_reuse_approval_runtime(
        config,
        key=f"tool-permission:{project_id}:demo.pause:toolu_surface_1",
        project_id=project_id,
        runtime_agent_ids=[runtime_agent_id],
        metadata={
            "kind": "tool_permission_request",
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_surface_1",
        },
        publish_pending=True,
        pending_message_type="tool_permission_pending",
        pending_payload={
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_surface_1",
            "message": "Need explicit approval.",
            "behavior": "pending_user",
        },
    )
    annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={"pending": {"stage": "pending_user", "tool_name": "demo.pause", "tool_use_id": "toolu_surface_1"}},
        payload_updates={"pending_user": {"message": "Need explicit approval.", "tool_name": "demo.pause", "tool_use_id": "toolu_surface_1"}},
        mailbox_message_type="tool_permission_user_pending",
        mailbox_payload={"tool_name": "demo.pause", "tool_use_id": "toolu_surface_1"},
    )

    list_response = client.get(
        "/api/execution-plane/tool-permission-runtimes",
        params={"project_id": project_id, "status": "pending", "pending_stage": "pending_user"},
    )
    assert list_response.status_code == 200
    listed = list_response.json()["runtimes"]
    assert len(listed) == 1
    assert listed[0]["id"] == runtime.id

    project_detail_response = client.get(f"/api/execution-plane/projects/{project_id}")
    assert project_detail_response.status_code == 200
    project_detail = project_detail_response.json()
    assert project_detail["pending_tool_permission_runtime_count"] == 1
    assert len(project_detail["tool_permission_runtimes"]) == 1
    assert project_detail["tool_permission_runtimes"][0]["pending_stage"] == "pending_user"

    agent_detail_response = client.get(f"/api/execution-plane/agents/{runtime_agent_id}")
    assert agent_detail_response.status_code == 200
    agent_detail = agent_detail_response.json()
    assert agent_detail["attention"]["state"] == "needs_approval"
    assert any(item["kind"] == "review_tool_permissions" for item in agent_detail["recommendations"])
    assert agent_detail["history"]["tool_permission_runtime_count"] == 1
    assert agent_detail["history"]["pending_tool_permission_runtime_count"] == 1
    assert len(agent_detail["tool_permission_runtimes"]) == 1
    assert agent_detail["tool_permission_runtimes"][0]["id"] == runtime.id


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_sessions_create_list_detail_and_update(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "orchestrator-session-project")
    project_id = created["project"]["project_id"]

    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Budget sweep",
        reason="Track one founder orchestration pass.",
        context={"mode": "triage"},
    )
    session_id = session["id"]
    assert session["status"] == "open"
    assert session["project_ids"] == [project_id]
    assert session["context"]["mode"] == "triage"

    list_response = client.get(
        "/api/execution-plane/orchestrator-sessions",
        params={"project_id": project_id, "status": "open"},
    )
    assert list_response.status_code == 200
    listed = list_response.json()["sessions"]
    assert len(listed) == 1
    assert listed[0]["id"] == session_id

    summary_response = client.get(
        "/api/execution-plane/orchestrator-sessions/summary",
        params={"project_id": project_id, "orchestrator": "founderos"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["sessions"] >= 1
    assert summary["totals"]["open"] >= 1
    assert summary["by_orchestrator"]["founderos"] >= 1
    assert summary["by_actor"]["founderos"] >= 1

    detail_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == session_id
    assert detail["summary"]["run_count"] == 0
    assert detail["summary"]["approval_count"] == 0
    assert detail["summary"]["issue_count"] == 0

    update_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/status",
        json={"status": "completed", "actor": "founderos", "note": "Loop closed cleanly."},
    )
    assert update_response.status_code == 200
    updated = update_response.json()["session"]
    assert updated["status"] == "completed"
    assert updated["closed_by"] == "founderos"
    assert updated["close_note"] == "Loop closed cleanly."

    detail_after_response = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session_id}",
        params={"event_limit": 10},
    )
    assert detail_after_response.status_code == 200
    detail_after = detail_after_response.json()
    assert detail_after["summary"]["event_count"] >= 2
    assert detail_after["summary"]["by_event"]["execution_plane_orchestrator_session_created"] >= 1
    assert detail_after["summary"]["by_event"]["execution_plane_orchestrator_session_updated"] >= 1
    assert detail_after["control"]["state"] == "closed"

    control_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session_id}/control")
    assert control_response.status_code == 200
    assert control_response.json()["control"]["state"] == "closed"

    session_events_response = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/events",
        params={"limit": 10},
    )
    assert session_events_response.status_code == 200
    session_events = session_events_response.json()["events"]
    assert any(event["event"] == "execution_plane_orchestrator_session_created" for event in session_events)
    assert any(event["event"] == "execution_plane_orchestrator_session_updated" for event in session_events)

    events_response = client.get("/api/execution-plane/events", params={"project_id": project_id})
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert any(event["event"] == "execution_plane_orchestrator_session_created" for event in events)
    assert any(event["event"] == "execution_plane_orchestrator_session_updated" for event in events)


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_actions_feed_preview_and_execute(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created_a = _create_execution_project(client, tmp_path / "session-actions-project-a")
    created_b = _create_execution_project(client, tmp_path / "session-actions-project-b")
    project_ids = [
        created_a["project"]["project_id"],
        created_b["project"]["project_id"],
    ]
    session = _create_orchestrator_session(
        client,
        project_ids=project_ids,
        actor="founderos",
        title="Multi-project maintenance session",
    )
    session_id = session["id"]

    for project_id in project_ids:
        update_story_runtime(
            config,
            project_id,
            1,
            status="in_progress",
            iteration=2,
            agent="codex/worker-a",
            critic="codex/critic-a",
        )
        update_project_runtime(
            config,
            project_id,
            status="running",
            paused=False,
            current_story_id=1,
            current_iteration=2,
            active_worker="codex/worker-a",
            active_critic="codex/critic-a",
            budget_policy={
                "project_max_worker_iterations": 200,
                "project_max_critic_reviews": 200,
                "agent_max_worker_iterations": 3,
                "agent_max_critic_reviews": 60,
                "auto_pause_on_exhaustion": True,
            },
            budget_usage={
                "project": {"worker_iterations": 2, "critic_reviews": 2},
                "agents": {
                    "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                    "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
                },
                "last_exhaustion_reason": None,
                "auto_paused_at": None,
            },
        )

    actions_response = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/actions",
        params={"suggested_command": "update_budget_policy", "command_requires_approval": False},
    )
    assert actions_response.status_code == 200
    actions_payload = actions_response.json()
    assert actions_payload["session_id"] == session_id
    actions = actions_payload["actions"]
    assert len(actions) >= 2
    assert {item["project_id"] for item in actions} == set(project_ids)
    assert all(item["command"] == "update_budget_policy" for item in actions)

    summary_response = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/summary",
        params={"suggested_command": "update_budget_policy", "command_requires_approval": False},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["session_id"] == session_id
    assert summary["totals"]["actions"] >= 2
    assert summary["totals"]["projects"] == 2
    assert summary["by_command"]["update_budget_policy"] >= 2

    control_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session_id}/control")
    assert control_response.status_code == 200
    control = control_response.json()["control"]
    assert control["state"] == "actionable"
    control_kinds = {item["kind"] for item in control["recommendations"]}
    assert "preview_safe_actions" in control_kinds
    assert "execute_safe_actions" in control_kinds

    preview_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/preview",
        json={
            "idempotency_key": "session-preview-1",
            "policy_profile": "safe_budget_maintenance",
            "actor": "founderos",
            "mode": "auto",
            "suggested_command": "update_budget_policy",
            "command_requires_approval": False,
            "limit": 10,
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["session_id"] == session_id
    assert preview["dry_run"] is True
    assert preview["preview_id"] == preview["run"]["id"]
    assert preview["artifact_ref"].endswith(preview["run"]["id"])
    assert preview["approval_required"] is False
    assert preview["apply_mode"] == "manual"
    assert preview["diff_summary"]["command_counts"]["update_budget_policy"] >= 2
    assert len(preview["patch_bundle"]["operations"]) >= 2
    assert preview["run"]["orchestrator_session_id"] == session_id
    assert set(preview["run"]["project_ids"]) == set(project_ids)

    execute_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/execute",
        json={
            "preview_id": preview["preview_id"],
            "idempotency_key": "session-execute-1",
            "policy_profile": "safe_budget_maintenance",
            "actor": "founderos",
            "mode": "auto",
            "suggested_command": "update_budget_policy",
            "command_requires_approval": False,
            "limit": 10,
        },
    )
    assert execute_response.status_code == 200
    execute_payload = execute_response.json()
    assert execute_payload["session_id"] == session_id
    assert execute_payload["status"] == "ok"
    assert execute_payload["preview_id"] == preview["preview_id"]
    assert execute_payload["run"]["preview_id"] == preview["preview_id"]
    assert execute_payload["artifact_ref"].endswith(execute_payload["run"]["id"])
    assert execute_payload["approval_required"] is False
    assert execute_payload["apply_mode"] == "auto"
    assert execute_payload["run"]["orchestrator_session_id"] == session_id
    assert set(execute_payload["run"]["project_ids"]) == set(project_ids)
    assert execute_payload["summary"]["status_counts"]["ok"] >= 2

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session_id}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["summary"]["run_count"] == 2
    assert detail["summary"]["by_event"]["execution_plane_agent_batch_previewed"] >= 1
    assert detail["summary"]["by_event"]["execution_plane_agent_batch_executed"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_control_apply_executes_safe_actions(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "session-control-apply-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Session control apply loop",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    control_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}/control")
    assert control_response.status_code == 200
    control = control_response.json()["control"]
    assert any(item["kind"] == "execute_safe_actions" for item in control["recommendations"])

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "execute_safe_actions",
            "actor": "founderos",
            "reason": "Apply safe session budget actions.",
            "idempotency_key": "session-control-apply-1",
        },
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["status"] == "ok"
    assert apply_payload["recommendation"]["kind"] == "execute_safe_actions"
    assert apply_payload["result"]["status"] == "ok"
    assert apply_payload["result"]["dry_run"] is False
    assert apply_payload["result"]["run"]["orchestrator_session_id"] == session["id"]
    assert apply_payload["result"]["summary"]["status_counts"]["ok"] >= 1

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["summary"]["run_count"] == 1

    session_events = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/events",
        params={"limit": 20},
    )
    assert session_events.status_code == 200
    event_names = {event["event"] for event in session_events.json()["events"]}
    assert "execution_plane_agent_batch_executed" in event_names
    assert "execution_plane_orchestrator_session_recommendation_applied" in event_names


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_control_plan_safe_progress_executes_and_closes(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    profiles_response = client.get("/api/execution-plane/orchestrator-sessions/control/profiles")
    assert profiles_response.status_code == 200
    profiles = {item["name"]: item for item in profiles_response.json()["profiles"]}
    assert "safe_progress" in profiles
    assert profiles["safe_progress"]["default"] is True

    created = _create_execution_project(client, tmp_path / "session-control-plan-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Session control plan loop",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    plan_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply-plan",
        json={
            "profile": "safe_progress",
            "actor": "founderos",
            "reason": "Run the default FounderOS control pass.",
            "max_operations": 5,
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["status"] == "ok"
    assert plan["profile"]["name"] == "safe_progress"
    assert plan["control_pass"]["orchestrator_session_id"] == session["id"]
    assert plan["summary"]["applied"] >= 2
    assert plan["summary"]["final_state"] == "closed"
    assert any(step["recommendation_kind"] == "execute_safe_actions" for step in plan["applied"])
    assert any(step["recommendation_kind"] == "complete_session" for step in plan["applied"])

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["status"] == "completed"
    assert detail["control"]["state"] == "closed"
    assert detail["summary"]["control_pass_count"] == 1
    assert len(detail["control_passes"]) == 1
    assert detail["control_passes"][0]["id"] == plan["control_pass"]["id"]
    assert plan["control_pass"]["id"] in detail["linked_control_pass_ids"]

    session_passes = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/passes",
    )
    assert session_passes.status_code == 200
    assert len(session_passes.json()["control_passes"]) == 1
    assert session_passes.json()["control_passes"][0]["id"] == plan["control_pass"]["id"]

    session_pass_summary = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/passes/summary",
    )
    assert session_pass_summary.status_code == 200
    scoped_summary = session_pass_summary.json()
    assert scoped_summary["session_id"] == session["id"]
    assert scoped_summary["totals"]["control_passes"] == 1
    assert scoped_summary["by_profile"]["safe_progress"] == 1
    assert scoped_summary["by_final_state"]["closed"] == 1
    assert scoped_summary["by_session_status_after"]["completed"] == 1

    pass_detail = client.get(
        f"/api/execution-plane/orchestrator-sessions/control/passes/{plan['control_pass']['id']}",
    )
    assert pass_detail.status_code == 200
    assert pass_detail.json()["id"] == plan["control_pass"]["id"]
    assert pass_detail.json()["summary"]["final_state"] == "closed"

    global_summary = client.get(
        "/api/execution-plane/orchestrator-sessions/control/passes/summary",
        params={"orchestrator_session_id": session["id"]},
    )
    assert global_summary.status_code == 200
    summary_payload = global_summary.json()
    assert summary_payload["totals"]["control_passes"] == 1
    assert summary_payload["totals"]["sessions"] == 1
    assert summary_payload["by_profile"]["safe_progress"] == 1
    assert summary_payload["by_status"]["ok"] == 1

    session_events = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/events",
        params={"limit": 30},
    )
    assert session_events.status_code == 200
    event_names = {event["event"] for event in session_events.json()["events"]}
    assert "execution_plane_orchestrator_session_control_plan_applied" in event_names
    assert "execution_plane_orchestrator_session_control_pass_recorded" in event_names
    assert "execution_plane_orchestrator_session_recommendation_applied" in event_names


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_routes_create_list_and_detail_projects(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [
            {"id": 1, "title": "Bootstrap", "description": "Create the app shell"},
            {"id": 2, "title": "Ship", "description": "Release the first usable MVP"},
        ],
    }

    project_root = tmp_path / "founderos-execution-project"
    payload = _create_execution_project(client, project_root)
    assert payload["status"] == "ok"
    assert payload["launched"] is False
    assert payload["project"]["source_kind"] == "execution_brief"
    assert payload["project"]["task_source"]["source_kind"] == "execution_brief"
    assert payload["project"]["task_source"]["branch_policy"] == "isolated_worktree"
    assert payload["project"]["delivery_loop"]["source"]["source_kind"] == "execution_brief"
    assert payload["project"]["initiative"]["id"] == "init_founderos_1"
    assert payload["project"]["orchestration"]["orchestrator"] == "founderos"
    assert payload["project"]["execution_brief_path"].endswith(".agents/tasks/execution-brief.json")
    assert "Orchestration Context" in mock_generate_prd_from_spec.call_args.args[0]
    assert "Initiative" in mock_generate_prd_from_spec.call_args.args[0]

    brief_path = Path(payload["project"]["execution_brief_path"])
    assert brief_path.exists()
    persisted_brief = json.loads(brief_path.read_text())
    assert persisted_brief["initiative"]["id"] == "init_founderos_1"
    assert persisted_brief["orchestration"]["run_id"] == "run_123"
    assert persisted_brief["task_source"]["source_kind"] == "execution_brief"
    assert persisted_brief["task_source"]["branch_policy"] == "isolated_worktree"

    project_id = payload["project"]["project_id"]
    list_response = client.get("/api/execution-plane/projects", params={"initiative_id": "init_founderos_1"})
    assert list_response.status_code == 200
    projects = list_response.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["project_id"] == project_id

    filtered_response = client.get("/api/execution-plane/projects", params={"orchestrator": "other"})
    assert filtered_response.status_code == 200
    assert filtered_response.json()["projects"] == []

    detail_response = client.get(f"/api/execution-plane/projects/{project_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["brief"]["provenance"]["source_system"] == "quorum"
    assert detail["task_source"]["source_kind"] == "execution_brief"
    assert detail["delivery_loop"]["brief"]["present"] is True
    assert detail["delivery_loop"]["run"]["status"] == "idle"
    assert detail["delivery_status"]["status"] == "ready_to_run"
    assert detail["command_policy"]["parallel_launch_requires_approval"] is True
    assert detail["provider_config"]["family"] == "codex"
    assert detail["runtime_profile"]["id"] == "cloud"
    assert detail["runtime"]["status"] == "idle"
    assert detail["progress"]["stories_total"] == 2
    assert detail["runtime_agent_count"] >= 2
    assert {agent["role"] for agent in detail["runtime_agents"]} >= {"worker", "critic"}
    assert "leases" in detail["runtime_control"]

    agents_response = client.get(f"/api/execution-plane/projects/{project_id}/agents")
    assert agents_response.status_code == 200
    agents_payload = agents_response.json()
    assert agents_payload["runtime_agent_count"] >= 2
    assert {agent["role"] for agent in agents_payload["agents"]} >= {"worker", "critic"}
    assert all("attention" in agent for agent in agents_payload["agents"])
    assert all("budget" in agent for agent in agents_payload["agents"])

    global_agents_response = client.get("/api/execution-plane/agents", params={"initiative_id": "init_founderos_1"})
    assert global_agents_response.status_code == 200
    global_agents = global_agents_response.json()["agents"]
    assert len(global_agents) >= 2
    assert {agent["role"] for agent in global_agents} >= {"worker", "critic"}

    emit_project_event(
        config,
        project_id,
        event="run_started",
        status="ok",
        message="Execution run started.",
    )
    emit_project_event(
        config,
        project_id,
        event="story_completed",
        status="ok",
        message="Bootstrap story completed.",
        story_id=1,
    )

    events_response = client.get(
        "/api/execution-plane/events",
        params={"initiative_id": "init_founderos_1", "limit": 10},
    )
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert len(events) >= 2
    assert events[-1]["project_id"] == project_id
    assert events[-1]["initiative"]["id"] == "init_founderos_1"

    project_events_response = client.get(f"/api/execution-plane/projects/{project_id}/events", params={"limit": 1})
    assert project_events_response.status_code == 200
    project_events = project_events_response.json()["events"]
    assert len(project_events) == 1
    assert project_events[0]["event"] == "story_completed"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_routes_create_project_from_shared_brief(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Shared Brief",
        "description": "Execution-ready shared-brief project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the bridge"}],
    }

    response = client.post(
        "/api/execution-plane/projects/from-shared-brief",
        json={
            "brief": _shared_brief_payload(),
            "project_path": str(tmp_path / "execution-plane-shared-brief-project"),
            "priority": "high",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["brief_id"] == "brief_execution_plane_1"
    assert payload["idea_id"] == "idea_execution_plane_1"
    assert payload["shared_execution_brief_path"].endswith(".agents/tasks/shared-execution-brief.json")
    assert Path(payload["shared_execution_brief_path"]).exists()
    assert payload["project"]["source_kind"] == "execution_brief"
    assert payload["project"]["task_source"]["source_kind"] == "execution_brief"
    assert "Core Thesis" in mock_generate_prd_from_spec.call_args.args[0]

    persisted = json.loads(Path(payload["shared_execution_brief_path"]).read_text())
    assert persisted["brief_id"] == "brief_execution_plane_1"
    assert persisted["recommended_tech_stack"] == ["python", "fastapi", "pydantic"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_command_route_updates_budget_without_approval(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "budget-command-project")
    project_id = created["project"]["project_id"]

    response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/update_budget_policy",
        json={
            "budget_policy": {
                "project_max_worker_iterations": 14,
                "run_max_runtime_seconds": 3600,
                "story_max_runtime_seconds": 900,
                "agent_max_critic_reviews": 3,
                "auto_pause_on_exhaustion": False,
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["budget_policy"]["project_max_worker_iterations"] == 14
    assert payload["budget_policy"]["run_max_runtime_seconds"] == 3600
    assert payload["budget_policy"]["story_max_runtime_seconds"] == 900
    assert payload["budget_policy"]["agent_max_critic_reviews"] == 3
    assert payload["project"]["budget"]["policy"]["auto_pause_on_exhaustion"] is False


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_github_pr_sync_and_reaction_routes(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap shell", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "github-sync-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(client, project_ids=[project_id], actor="founderos", title="GitHub loop")

    sync_response = client.post(
        f"/api/execution-plane/projects/{project_id}/stories/1/github-pr",
        json={
            "number": 12,
            "url": "https://github.com/example/repo/pull/12",
            "title": "Bootstrap shell",
            "state": "open",
            "ci_status": "pending",
            "review_status": "unreviewed",
            "orchestrator_session_id": session["id"],
        },
    )
    assert sync_response.status_code == 200
    sync_payload = sync_response.json()
    assert sync_payload["github_pr"]["number"] == 12
    assert sync_payload["github_pr"]["state"] == "open"
    assert sync_payload["project"]["delivery_loop"]["artifact"]["ref_label"] == "PR #12"
    assert sync_payload["project"]["delivery_loop"]["artifact"]["present"] is True
    assert sync_payload["project"]["delivery_status"]["status"] == "in_review"

    reaction_response = client.post(
        f"/api/execution-plane/projects/{project_id}/stories/1/github-reactions",
        json={
            "reaction_type": "changes_requested",
            "summary": "Reviewer requested changes.",
            "orchestrator_session_id": session["id"],
        },
    )
    assert reaction_response.status_code == 200
    reaction_payload = reaction_response.json()
    assert reaction_payload["github_pr"]["review_status"] == "changes_requested"
    assert reaction_payload["project"]["stories"][0]["github_pr"]["handoff_status"] == "changes_requested"
    assert reaction_payload["project"]["stories"][0]["handoff_artifact"]["ref_label"] == "PR #12"
    assert reaction_payload["project"]["delivery_status"]["status"] == "blocked"

    issues_response = client.get(
        f"/api/execution-plane/projects/{project_id}/issues",
        params={"category": "github_changes_requested"},
    )
    assert issues_response.status_code == 200
    issues = issues_response.json()["issues"]
    assert len(issues) == 1
    assert issues[0]["story_id"] == 1

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert issues[0]["id"] in detail["linked_issue_ids"]
    assert detail["summary"]["by_event"]["github_pr_synced"] >= 1
    assert detail["summary"]["by_event"]["github_changes_requested"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_github_approved_and_green_creates_resume_approval_when_auto_resume_disabled(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap shell", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "github-approved-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(client, project_ids=[project_id], actor="founderos", title="GitHub approve loop")

    update_project_runtime(
        config,
        project_id,
        status="paused",
        paused=True,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
    )
    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
        github_pr={
            "provider": "github",
            "head_branch": "autopilot/founderos-copilot/story-1-bootstrap-shell",
            "base_branch": "main",
            "number": 44,
            "url": "https://github.com/example/repo/pull/44",
            "title": "Bootstrap shell",
            "state": "open",
            "ci_status": "pending",
            "review_status": "commented",
            "handoff_status": "in_review",
            "merge_state": "not_ready",
            "draft": False,
            "author": "",
            "labels": [],
            "comment_count": 0,
            "review_comment_count": 0,
            "last_commit_sha": "",
            "checks_url": "",
            "latest_event": "github_review_comment_received",
            "opened_at": None,
            "merged_at": None,
            "closed_at": None,
            "updated_at": "2026-03-31T00:00:00+00:00",
        },
    )

    reaction_response = client.post(
        f"/api/execution-plane/projects/{project_id}/stories/1/github-reactions",
        json={
            "reaction_type": "approved_and_green",
            "summary": "PR approved and green.",
            "orchestrator_session_id": session["id"],
        },
    )
    assert reaction_response.status_code == 200
    payload = reaction_response.json()
    assert payload["auto_resumed"] is False
    assert payload["approval"]["action"] == "resume"
    assert payload["issue"]["related_command"] == "resume"

    approvals_response = client.get(
        f"/api/execution-plane/projects/{project_id}/approvals",
        params={"status": "pending", "action": "resume"},
    )
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["approvals"]
    assert len(approvals) == 1

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert approvals[0]["id"] in detail["linked_approval_ids"]
    assert detail["summary"]["by_event"]["github_approved_and_green"] >= 1
    assert detail["summary"]["by_event"]["github_auto_resume_approval_requested"] >= 1


@patch("autopilot.core.execution_plane.launch_project_run")
@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_approval_flow_for_launch_command(
    mock_generate_prd_from_spec,
    mock_launch_project_run,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    mock_launch_project_run.return_value = (
        True,
        config.autopilot_home / "logs" / "founderos.log",
        "Background run started.",
    )

    created = _create_execution_project(client, tmp_path / "approval-command-project")
    project_id = created["project"]["project_id"]

    command_response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/launch",
        json={
            "require_approval": True,
            "requested_by": "founderos",
            "reason": "Launch after operator approval.",
            "launch_profile": {
                "preset": "parallel",
                "provider": "ollama",
                "provider_config_id": "ollama-local",
                "runtime_profile_id": "local",
                "story_execution_mode": "team",
                "project_concurrency_mode": "parallel",
                "max_parallel_stories": 2,
            },
        },
    )
    assert command_response.status_code == 200
    command_payload = command_response.json()
    assert command_payload["status"] == "pending_approval"
    approval_id = command_payload["approval"]["id"]
    assert command_payload["approval"]["status"] == "pending"
    assert command_payload["approval"]["issue_id"]
    assert command_payload["approval"]["orchestrator"] == "founderos"
    assert command_payload["issue"]["approval_id"] == approval_id
    issue_id = command_payload["issue"]["id"]

    approvals_response = client.get(f"/api/execution-plane/projects/{project_id}/approvals", params={"status": "pending"})
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["approvals"]
    assert len(approvals) == 1
    assert approvals[0]["id"] == approval_id

    approve_response = client.post(
        f"/api/execution-plane/approvals/{approval_id}/approve",
        json={"actor": "martin", "note": "Looks good."},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["approval"]["status"] == "approved"

    apply_response = client.post(
        f"/api/execution-plane/approvals/{approval_id}/apply",
        json={"actor": "founderos-control"},
    )
    assert apply_response.status_code == 200
    applied = apply_response.json()
    assert applied["approval"]["status"] == "applied"
    assert applied["command_result"]["status"] == "ok"
    assert applied["command_result"]["command"] == "launch"
    assert applied["command_result"]["log_path"].endswith("founderos.log")
    assert mock_launch_project_run.call_args.kwargs["launch_profile"]["preset"] == "parallel"
    assert mock_launch_project_run.call_args.kwargs["launch_profile"]["provider"] == "ollama"
    assert mock_launch_project_run.call_args.kwargs["launch_profile"]["runtime_profile_id"] == "local"

    issue_response = client.get(f"/api/execution-plane/issues/{issue_id}")
    assert issue_response.status_code == 200
    assert issue_response.json()["status"] == "resolved"

    global_approvals = client.get("/api/execution-plane/approvals", params={"initiative_id": "init_founderos_1"})
    assert global_approvals.status_code == 200
    assert len(global_approvals.json()["approvals"]) == 1

    global_issues = client.get("/api/execution-plane/issues", params={"initiative_id": "init_founderos_1"})
    assert global_issues.status_code == 200
    assert len(global_issues.json()["issues"]) == 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_rejected_execution_plane_approval_cannot_be_applied(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "reject-approval-project")
    project_id = created["project"]["project_id"]

    command_response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"require_approval": True, "requested_by": "founderos"},
    )
    approval_id = command_response.json()["approval"]["id"]
    issue_id = command_response.json()["issue"]["id"]

    reject_response = client.post(
        f"/api/execution-plane/approvals/{approval_id}/reject",
        json={"actor": "martin", "note": "Not now."},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["approval"]["status"] == "rejected"

    apply_response = client.post(f"/api/execution-plane/approvals/{approval_id}/apply")
    assert apply_response.status_code == 409

    resolve_response = client.post(
        f"/api/execution-plane/issues/{issue_id}/resolve",
        json={"actor": "martin", "note": "Command intentionally deferred."},
    )
    assert resolve_response.status_code == 200
    assert resolve_response.json()["issue"]["status"] == "resolved"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_policy_based_parallel_launch_auto_creates_issue_and_approval(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "policy-approval-project")
    project_id = created["project"]["project_id"]

    response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/launch",
        json={
            "requested_by": "founderos",
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
    assert payload["status"] == "pending_approval"
    assert payload["policy_triggered"] is True
    assert payload["policy_reasons"]
    assert payload["issue"]["category"] == "policy_approval"
    assert payload["approval"]["issue_id"] == payload["issue"]["id"]
    assert payload["issue"]["root_cause"] == payload["policy_reasons"][0]
    assert payload["issue"]["context"]["command"]["name"] == "launch"
    assert payload["issue"]["context"]["command"]["policy_reasons"] == payload["policy_reasons"]


@patch("autopilot.core.execution_plane.launch_project_run")
@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_command_policy_route_can_allow_parallel_launch_without_approval(
    mock_generate_prd_from_spec,
    mock_launch_project_run,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    mock_launch_project_run.return_value = (
        True,
        config.autopilot_home / "logs" / "policy.log",
        "Background run started.",
    )

    created = _create_execution_project(client, tmp_path / "policy-override-project")
    project_id = created["project"]["project_id"]

    patch_response = client.patch(
        f"/api/execution-plane/projects/{project_id}/command-policy",
        json={
            "parallel_launch_requires_approval": False,
            "max_parallel_stories_without_approval": 3,
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["command_policy"]["max_parallel_stories_without_approval"] == 3

    command_response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/launch",
        json={
            "requested_by": "founderos",
            "launch_profile": {
                "preset": "parallel",
                "story_execution_mode": "team",
                "project_concurrency_mode": "parallel",
                "max_parallel_stories": 2,
            },
        },
    )
    assert command_response.status_code == 200
    command_payload = command_response.json()
    assert command_payload["status"] == "ok"
    assert command_payload["command"] == "launch"
    assert command_payload["async_task"]["status"] == "running"
    assert command_payload["async_task"]["command"] == "launch"
    assert "final completion is not available yet" in command_payload["message"]

    tasks_response = client.get(
        "/api/execution-plane/agents/tasks",
        params={"project_id": project_id, "command": "launch"},
    )
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["id"] == command_payload["async_task"]["id"]

    task_detail = client.get(f"/api/execution-plane/agents/tasks/{tasks[0]['id']}")
    assert task_detail.status_code == 200
    task_payload = task_detail.json()
    assert task_payload["artifact_ref"].endswith(tasks[0]["id"])
    assert task_payload["status"] == "running"
    assert task_payload["transcript_artifact_ref"].endswith(f"/{tasks[0]['id']}/transcript")
    assert task_payload["resume_contract"]["task_id"] == tasks[0]["id"]
    assert task_payload["resume_contract"]["command"] == "launch"
    transcript_response = client.get(f"/api/execution-plane/agents/tasks/{tasks[0]['id']}/transcript")
    assert transcript_response.status_code == 200
    assert transcript_response.json()["task_id"] == tasks[0]["id"]
    assert transcript_response.json()["artifact_ref"].endswith(f"/{tasks[0]['id']}/transcript")
    assert f"Task ID: {tasks[0]['id']}" in transcript_response.json()["content"]


@patch("autopilot.core.execution_plane.launch_project_run")
@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_task_output_live_reads_running_source_log(
    mock_generate_prd_from_spec,
    mock_launch_project_run,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    log_path = config.autopilot_home / "logs" / "task-live.log"
    mock_launch_project_run.return_value = (
        True,
        log_path,
        "Background run started.",
    )

    created = _create_execution_project(client, tmp_path / "async-task-live-output-project")
    project_id = created["project"]["project_id"]

    patch_response = client.patch(
        f"/api/execution-plane/projects/{project_id}/command-policy",
        json={
            "parallel_launch_requires_approval": False,
            "max_parallel_stories_without_approval": 3,
        },
    )
    assert patch_response.status_code == 200

    command_response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/launch",
        json={
            "requested_by": "founderos",
            "launch_profile": {
                "preset": "parallel",
                "story_execution_mode": "team",
                "project_concurrency_mode": "parallel",
                "max_parallel_stories": 2,
            },
        },
    )
    assert command_response.status_code == 200
    task_id = command_response.json()["async_task"]["id"]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    live_output_response = client.get(
        f"/api/execution-plane/agents/tasks/{task_id}/output/live",
        params={"tail_lines": 2},
    )

    assert live_output_response.status_code == 200
    live_output = live_output_response.json()
    assert live_output["task_id"] == task_id
    assert live_output["status"] == "live"
    assert live_output["task_status"] == "running"
    assert live_output["content_source"] == "source_log"
    assert live_output["source_path"] == str(log_path)
    assert "line 1" not in live_output["content"]
    assert "line 2" in live_output["content"]
    assert "line 3" in live_output["content"]
    assert live_output["content_next_offset"] == live_output["content_total_bytes"]
    assert live_output["content_window_truncated"] is True


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_project_runtime_log_route_reads_windowed_log_content(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "project-runtime-log-project")
    project_id = created["project"]["project_id"]
    log_path = config.autopilot_home / "logs" / "project-runtime.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("0123456789abcdef", encoding="utf-8")
    save_project_state(
        config,
        project_id,
        {
            "status": "running",
            "paused": False,
            "started_at": "2026-04-02T00:00:00+00:00",
            "updated_at": "2026-04-02T00:01:00+00:00",
            "log_path": str(log_path),
        },
    )

    runtime_log_response = client.get(
        f"/api/execution-plane/projects/{project_id}/runtime-log",
        params={"offset": 4, "max_bytes": 4},
    )

    assert runtime_log_response.status_code == 200
    runtime_log = runtime_log_response.json()
    assert runtime_log["project_id"] == project_id
    assert runtime_log["status"] == "live"
    assert runtime_log["project_status"] == "running"
    assert runtime_log["paused"] is False
    assert runtime_log["log_path"] == str(log_path)
    assert runtime_log["content"] == "4567"
    assert runtime_log["content_offset"] == 4
    assert runtime_log["content_next_offset"] == 8
    assert runtime_log["content_total_bytes"] == 16
    assert runtime_log["content_window_truncated"] is True


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_tracks_async_tasks_honestly(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "async-session-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Async follow-through loop",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["runtime_state"] == "running"
    assert detail["pending_action"]["kind"] == "inspect_background_tasks"
    assert detail["control"]["state"] == "waiting_async"
    assert detail["control"]["session_state"] == "running"
    assert detail["control"]["pending_action"]["kind"] == "inspect_background_tasks"
    assert detail["summary"]["async_task_count"] == 1
    assert detail["summary"]["active_async_task_count"] == 1
    assert detail["async_tasks"][0]["id"] == task.id
    assert detail["async_tasks"][0]["status"] == "running"
    assert detail["summary"]["by_event"]["execution_plane_runtime_agent_task_started"] >= 1

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "inspect_background_tasks",
            "actor": "founderos",
            "reason": "Inspect live async follow-through before closing the session.",
        },
    )
    assert apply_response.status_code == 200
    apply_payload = apply_response.json()
    assert apply_payload["status"] == "ok"
    assert apply_payload["recommendation"]["kind"] == "inspect_background_tasks"
    assert apply_payload["result"]["counts"]["active_async_tasks"] == 1
    assert apply_payload["result"]["counts"]["pending_async_runs"] == 0
    assert apply_payload["result"]["active_async_tasks"][0]["id"] == task.id

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    log_path = config.autopilot_home / "logs" / f"{project_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished\n", encoding="utf-8")
    state["log_path"] = str(log_path)
    save_project_state(config, project_id, state)

    refreshed_detail_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert refreshed_detail_response.status_code == 200
    refreshed_detail = refreshed_detail_response.json()
    assert refreshed_detail["async_tasks"][0]["id"] == task.id
    assert refreshed_detail["async_tasks"][0]["status"] == "completed"
    assert refreshed_detail["async_tasks"][0]["result_summary"] == "Background run completed."
    assert refreshed_detail["async_tasks"][0]["output_artifact_ref"].endswith(f"/{task.id}/output")
    assert refreshed_detail["async_tasks"][0]["output_origin"] == "source_log"
    assert refreshed_detail["async_tasks"][0]["output_source_available"] is True
    assert refreshed_detail["async_tasks"][0]["transcript_artifact_ref"].endswith(f"/{task.id}/transcript")
    assert refreshed_detail["async_tasks"][0]["resume_contract"]["task_id"] == task.id
    assert refreshed_detail["async_tasks"][0]["resume_contract"]["project_id"] == project_id
    assert refreshed_detail["async_tasks"][0]["resume_contract"]["output_origin"] == "source_log"
    assert refreshed_detail["async_tasks"][0]["resume_contract"]["output_generated_from_project_state"] is False
    assert refreshed_detail["async_tasks"][0]["output_artifact_id"] in refreshed_detail["linked_artifact_ids"]
    assert refreshed_detail["async_tasks"][0]["transcript_artifact_id"] in refreshed_detail["linked_artifact_ids"]
    assert refreshed_detail["runtime_state"] == "requires_action"
    assert refreshed_detail["pending_action"]["kind"] == "complete_session"
    assert refreshed_detail["summary"]["active_async_task_count"] == 0
    assert refreshed_detail["summary"]["by_event"]["execution_plane_runtime_agent_task_completed"] >= 1

    output_response = client.get(f"/api/execution-plane/agents/tasks/{task.id}/output")
    assert output_response.status_code == 200
    output_payload = output_response.json()
    assert output_payload["task_id"] == task.id
    assert output_payload["artifact_ref"].endswith(f"/{task.id}/output")
    assert output_payload["metadata"]["output_origin"] == "source_log"
    assert output_payload["metadata"]["output_source_available"] is True
    assert "launch finished" in output_payload["content"]

    transcript_response = client.get(f"/api/execution-plane/agents/tasks/{task.id}/transcript")
    assert transcript_response.status_code == 200
    transcript_payload = transcript_response.json()
    assert transcript_payload["task_id"] == task.id
    assert transcript_payload["artifact_ref"].endswith(f"/{task.id}/transcript")
    assert f"Task ID: {task.id}" in transcript_payload["content"]
    assert "Background run completed." in transcript_payload["content"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_task_surfaces_cancelled_settlement_provenance(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "async-task-cancelled-api-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Cancelled async task provenance",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
    )

    state = load_project_state(config, project_id)
    state["status"] = "paused"
    state["paused"] = True
    state["paused_at"] = "2026-04-01T12:44:00+00:00"
    save_project_state(config, project_id, state)

    task_detail = client.get(f"/api/execution-plane/agents/tasks/{task.id}")
    assert task_detail.status_code == 200
    payload = task_detail.json()
    assert payload["status"] == "cancelled"
    assert payload["settlement_source"] == "project_state"
    assert payload["settlement_reason"] == "paused"
    assert payload["settlement_state_status"] == "paused"
    assert payload["settlement_state_timestamp"] == "2026-04-01T12:44:00+00:00"
    assert payload["resume_contract"]["settlement_reason"] == "paused"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_task_surfaces_runtime_exited_settlement_provenance(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "async-task-runtime-exited-api-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Runtime exited async task provenance",
    )

    state = load_project_state(config, project_id)
    state["status"] = "running"
    state["paused"] = False
    state["pid"] = 999_999
    state["runtime_session_id"] = "sess_background_owner"
    state["started_at"] = "2026-04-01T12:00:00+00:00"
    save_project_state(config, project_id, state)

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
    )

    task_detail = client.get(f"/api/execution-plane/agents/tasks/{task.id}")
    assert task_detail.status_code == 200
    payload = task_detail.json()
    assert payload["status"] == "failed"
    assert payload["settlement_source"] == "project_state"
    assert payload["settlement_reason"] == "runtime_exited"
    assert payload["settlement_state_status"] == "running"
    assert payload["resume_contract"]["settlement_reason"] == "runtime_exited"
    assert payload["result_summary"] == "Background runtime exited before task settlement."


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_task_cancel_route_pauses_project_and_cancels_task(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "async-task-cancel-route-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Runtime task cancel route",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
    )

    response = client.post(
        f"/api/execution-plane/agents/tasks/{task.id}/cancel",
        json={"actor": "martin", "note": "Stop background follow-through."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["cancel_applied"] is True
    assert "by martin" in payload["message"]
    assert payload["task"]["id"] == task.id
    assert payload["task"]["status"] == "cancelled"
    assert payload["task"]["settlement_reason"] == "paused"
    assert payload["task"]["settlement_source"] == "project_state"

    state = load_project_state(config, project_id)
    assert state["status"] == "paused"
    assert state["paused"] is True


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_task_cancel_route_is_noop_for_terminal_task(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "async-task-cancel-terminal-project")
    project_id = created["project"]["project_id"]

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        runtime_agent_ids=["runtime-agent-1"],
    )

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:50:00+00:00"
    save_project_state(config, project_id, state)

    response = client.post(f"/api/execution-plane/agents/tasks/{task.id}/cancel")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["cancel_applied"] is False
    assert payload["task"]["status"] == "completed"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_detail_surfaces_waiting_async_task_only(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-waiting-async-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
    )

    agents_response = client.get(f"/api/execution-plane/projects/{project_id}/agents")
    assert agents_response.status_code == 200
    worker_agent_id = next(
        agent["agent_id"]
        for agent in agents_response.json()["agents"]
        if agent["role"] == "worker" and agent["status"] == "active"
    )

    create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background follow-through.",
        runtime_agent_ids=[worker_agent_id],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )

    detail_response = client.get(f"/api/execution-plane/agents/{worker_agent_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["attention"]["state"] == "waiting_async"
    assert detail["current"]["attention"]["state"] == "waiting_async"
    assert detail["current"]["active_async_task_count"] == 1
    assert detail["current"]["pending_async_run_count"] == 0
    assert any(rec["kind"] == "inspect_async_follow_through" for rec in detail["recommendations"])

    filtered_response = client.get(
        "/api/execution-plane/agents",
        params={"project_id": project_id, "attention_state": "waiting_async"},
    )
    assert filtered_response.status_code == 200
    assert any(agent["agent_id"] == worker_agent_id for agent in filtered_response.json()["agents"])


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_control_can_inspect_background_tasks(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "inspect-async-session-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Inspect async follow-through",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "inspect_background_tasks",
            "actor": "founderos",
            "reason": "Inspect live async follow-through before declaring completion.",
        },
    )
    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["status"] == "ok"
    assert payload["recommendation"]["kind"] == "inspect_background_tasks"
    assert payload["result"]["counts"]["async_tasks"] == 1
    assert payload["result"]["counts"]["active_async_tasks"] == 1
    assert payload["result"]["counts"]["pending_async_runs"] == 0
    assert payload["result"]["async_tasks"][0]["id"] == task.id
    assert payload["result"]["active_async_tasks"][0]["id"] == task.id


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_command_route_respects_project_deny_rule(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "deny-rule-project")
    project_id = created["project"]["project_id"]
    persist_permission_update(
        config,
        PermissionUpdate(
            type="add_rules",
            destination="project",
            behavior="deny",
            project_id=project_id,
            rules=[PermissionRuleValue(tool_name="execution.pause")],
        ),
    )

    response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"requested_by": "founderos"},
    )

    assert response.status_code == 409
    assert "execution.pause" in response.json()["detail"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_command_route_escalates_after_repeated_denials(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "deny-breaker-project")
    project_id = created["project"]["project_id"]
    persist_permission_update(
        config,
        PermissionUpdate(
            type="add_rules",
            destination="project",
            behavior="deny",
            project_id=project_id,
            rules=[PermissionRuleValue(tool_name="execution.pause")],
        ),
    )

    first = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"requested_by": "founderos"},
    )
    second = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"requested_by": "founderos"},
    )
    third = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"requested_by": "founderos"},
    )

    assert first.status_code == 409
    assert second.status_code == 409
    assert third.status_code == 200
    assert third.json()["status"] == "pending_approval"
    assert "explicit approval" in " ".join(third.json()["policy_reasons"]).lower()


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_issue_routes_surface_runtime_failures(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "runtime-issue-api-project")
    project_id = created["project"]["project_id"]

    emit_project_event(
        config,
        project_id,
        event="worker_failed",
        status="error",
        message="Build command crashed.",
        story_id=1,
    )

    project_issues = client.get(f"/api/execution-plane/projects/{project_id}/issues", params={"status": "open"})
    assert project_issues.status_code == 200
    issues = project_issues.json()["issues"]
    assert len(issues) == 1
    assert issues[0]["category"] == "runtime_worker_failure"
    assert issues[0]["source_event"] == "worker_failed"
    assert issues[0]["root_cause"] == "Build command crashed."
    assert issues[0]["context"]["story"]["title"] == "Bootstrap"
    assert issues[0]["context"]["project"]["status"] == "idle"

    detail = client.get(f"/api/execution-plane/projects/{project_id}").json()
    assert detail["open_issue_count"] == 1
    assert detail["issues"][0]["category"] == "runtime_worker_failure"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_issue_routes_surface_structured_gate_failures(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "runtime-gate-issue-api-project")
    project_id = created["project"]["project_id"]

    emit_project_event(
        config,
        project_id,
        event="story_gate_failed",
        status="error",
        message="Quality gates failed.",
        story_id=1,
        extra={
            "iteration": 2,
            "gate_failures": [
                {
                    "name": "pytest",
                    "cmd": "pytest",
                    "passed": False,
                    "output": "2 tests failed",
                    "required": True,
                    "elapsed_sec": 1.2,
                }
            ],
        },
    )

    project_issues = client.get(f"/api/execution-plane/projects/{project_id}/issues", params={"status": "open"})
    assert project_issues.status_code == 200
    issues = project_issues.json()["issues"]
    assert len(issues) == 1
    assert issues[0]["category"] == "runtime_gate_failure"
    assert issues[0]["root_cause"] == "pytest: 2 tests failed"
    assert issues[0]["context"]["event"]["extra"]["gate_failures"][0]["cmd"] == "pytest"


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_runtime_agent_filters_and_global_agent_counts(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "runtime-agent-filter-project")
    project_id = created["project"]["project_id"]

    worker_agent_id = next(
        agent["agent_id"]
        for agent in client.get(f"/api/execution-plane/projects/{project_id}/agents").json()["agents"]
        if agent["role"] == "worker"
    )

    emit_project_event(
        config,
        project_id,
        event="worker_failed",
        status="error",
        message="Build command crashed.",
        story_id=1,
        extra={"runtime_agent_id": worker_agent_id},
    )

    filtered_issues = client.get("/api/execution-plane/issues", params={"runtime_agent_id": worker_agent_id})
    assert filtered_issues.status_code == 200
    issues = filtered_issues.json()["issues"]
    assert len(issues) == 1
    assert issues[0]["runtime_agent_id"] == worker_agent_id

    filtered_events = client.get("/api/execution-plane/events", params={"runtime_agent_id": worker_agent_id})
    assert filtered_events.status_code == 200
    events = filtered_events.json()["events"]
    assert len(events) >= 1
    assert events[-1]["runtime_agent_id"] == worker_agent_id

    agents_response = client.get("/api/execution-plane/agents", params={"project_id": project_id})
    assert agents_response.status_code == 200
    agents = agents_response.json()["agents"]
    worker_entry = next(agent for agent in agents if agent["agent_id"] == worker_agent_id)
    assert worker_entry["open_issue_count"] == 1
    assert worker_entry["attention"]["state"] == "blocked"
    assert any(rec["kind"] == "resolve_issues" for rec in worker_entry["recommendations"])
    assert worker_entry["suggested_commands"] == []

    attention_filtered = client.get(
        "/api/execution-plane/agents",
        params={"project_id": project_id, "attention_state": "blocked"},
    )
    assert attention_filtered.status_code == 200
    filtered_agents = attention_filtered.json()["agents"]
    assert len(filtered_agents) >= 1
    assert any(agent["agent_id"] == worker_agent_id for agent in filtered_agents)

    actionable_filtered = client.get(
        "/api/execution-plane/agents",
        params={"project_id": project_id, "actionable_only": True, "recommendation_kind": "resolve_issues"},
    )
    assert actionable_filtered.status_code == 200
    actionable_agents = actionable_filtered.json()["agents"]
    assert len(actionable_agents) >= 1
    assert any(agent["agent_id"] == worker_agent_id for agent in actionable_agents)

    action_feed = client.get(
        "/api/execution-plane/agents/actions",
        params={"project_id": project_id, "recommendation_kind": "resolve_issues"},
    )
    assert action_feed.status_code == 200
    actions = action_feed.json()["actions"]
    assert any(
        action["runtime_agent_id"] == worker_agent_id
        and action["action_type"] == "recommendation"
        and action["kind"] == "resolve_issues"
        for action in actions
    )

    summary_response = client.get("/api/execution-plane/agents/summary", params={"project_id": project_id})
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["agents"] >= 2
    assert summary["totals"]["blocked"] >= 1
    assert summary["totals"]["actionable"] >= 1
    assert summary["by_attention_state"]["blocked"] >= 1
    assert summary["by_role"]["worker"] >= 1
    assert summary["by_recommendation_kind"]["resolve_issues"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_pause_approval_tracks_active_runtime_agents(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "pause-approval-runtime-agents-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
    )

    response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"require_approval": True, "requested_by": "founderos"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "pending_approval"
    assert len(payload["approval"]["runtime_agent_ids"]) >= 2
    assert payload["issue"]["context"]["command"]["runtime_agent_ids"] == payload["approval"]["runtime_agent_ids"]

    approvals_response = client.get(
        "/api/execution-plane/approvals",
        params={"runtime_agent_id": payload["approval"]["runtime_agent_ids"][0]},
    )
    assert approvals_response.status_code == 200
    approvals = approvals_response.json()["approvals"]
    assert len(approvals) == 1
    assert approvals[0]["id"] == payload["approval"]["id"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_detail_surfaces_current_and_history(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-detail-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
    )

    agents = client.get(f"/api/execution-plane/projects/{project_id}/agents").json()["agents"]
    worker_agent_id = next(agent["agent_id"] for agent in agents if agent["role"] == "worker" and agent["status"] == "active")

    emit_project_event(
        config,
        project_id,
        event="worker_failed",
        status="error",
        message="Build command crashed.",
        story_id=1,
        extra={"runtime_agent_id": worker_agent_id},
    )
    command_response = client.post(
        f"/api/execution-plane/projects/{project_id}/commands/pause",
        json={"require_approval": True, "requested_by": "founderos"},
    )
    assert command_response.status_code == 200

    detail_response = client.get(f"/api/execution-plane/agents/{worker_agent_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["runtime_agent_id"] == worker_agent_id
    assert detail["project_id"] == project_id
    assert detail["role"] == "worker"
    assert detail["status"] == "active"
    assert detail["current"]["agent_id"] == worker_agent_id
    assert detail["current"]["attention"]["state"] in {"blocked", "needs_approval"}
    assert detail["budget"]["tracked"] is True
    assert detail["attention"]["reasons"]
    assert detail["current"]["recommendations"]
    assert detail["current"]["suggested_commands"] == []
    assert any(rec["kind"] in {"resolve_issues", "review_approvals"} for rec in detail["recommendations"])
    assert detail["history"]["issue_count"] >= 2
    assert detail["history"]["approval_count"] >= 1
    assert detail["history"]["event_count"] >= 1
    assert any(
        issue["runtime_agent_id"] == worker_agent_id or worker_agent_id in issue.get("runtime_agent_ids", [])
        for issue in detail["issues"]
    )
    assert any(worker_agent_id in approval["runtime_agent_ids"] for approval in detail["approvals"])
    assert any(
        worker_agent_id in event.get("runtime_agent_ids", []) or event.get("runtime_agent_id") == worker_agent_id
        for event in detail["events"]
    )


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_attention_surfaces_waiting_async_follow_through(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "waiting-async-agent-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
    )

    agents = client.get(f"/api/execution-plane/projects/{project_id}/agents").json()["agents"]
    worker_agent_id = next(agent["agent_id"] for agent in agents if agent["role"] == "worker" and agent["status"] == "active")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        runtime_agent_ids=[worker_agent_id],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )
    create_agent_action_batch_run(
        config,
        run_kind="single_action",
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[
            {
                "status": "ok",
                "command_result": {"command": "launch"},
                "async_task": {"id": task.id},
            }
        ],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=[worker_agent_id],
    )

    detail_response = client.get(f"/api/execution-plane/agents/{worker_agent_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["attention"]["state"] == "waiting_async"
    assert detail["current"]["attention"]["state"] == "waiting_async"
    async_recommendation = next(
        rec for rec in detail["recommendations"] if rec["kind"] == "inspect_async_follow_through"
    )
    assert async_recommendation["counts"]["active_async_tasks"] == 1
    assert async_recommendation["counts"]["pending_async_runs"] == 1
    assert detail["history"]["active_async_task_count"] == 1
    assert detail["history"]["pending_async_run_count"] == 1

    waiting_agents = client.get(
        "/api/execution-plane/agents",
        params={"project_id": project_id, "attention_state": "waiting_async"},
    )
    assert waiting_agents.status_code == 200
    assert any(agent["agent_id"] == worker_agent_id for agent in waiting_agents.json()["agents"])


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_budget_risk_agent_recommendations(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "budget-risk-agent-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    response = client.get(
        "/api/execution-plane/agents",
        params={"project_id": project_id, "attention_state": "budget_risk"},
    )
    assert response.status_code == 200
    agents = response.json()["agents"]
    worker_entry = next(agent for agent in agents if agent["role"] == "worker")
    assert worker_entry["budget"]["tracked"] is True
    assert worker_entry["budget"]["remaining"] == 1
    assert worker_entry["attention"]["state"] == "budget_risk"
    assert any(rec["kind"] == "rotate_account" for rec in worker_entry["recommendations"])
    assert any(cmd["command"] == "update_budget_policy" for cmd in worker_entry["suggested_commands"])
    assert any(cmd["approval_required"] is False for cmd in worker_entry["suggested_commands"])

    actionable_response = client.get(
        "/api/execution-plane/agents",
        params={
            "project_id": project_id,
            "actionable_only": True,
            "suggested_command": "update_budget_policy",
            "command_requires_approval": False,
        },
    )
    assert actionable_response.status_code == 200
    actionable_agents = actionable_response.json()["agents"]
    assert any(agent["agent_id"] == worker_entry["agent_id"] for agent in actionable_agents)

    action_feed = client.get(
        "/api/execution-plane/agents/actions",
        params={
            "project_id": project_id,
            "suggested_command": "update_budget_policy",
            "command_requires_approval": False,
        },
    )
    assert action_feed.status_code == 200
    actions = action_feed.json()["actions"]
    assert any(
        action["runtime_agent_id"] == worker_entry["agent_id"]
        and action["action_type"] == "suggested_command"
        and action["command"] == "update_budget_policy"
        and action["approval_required"] is False
        for action in actions
    )

    summary_response = client.get(
        "/api/execution-plane/agents/summary",
        params={
            "project_id": project_id,
            "actionable_only": True,
            "suggested_command": "update_budget_policy",
            "command_requires_approval": False,
        },
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["agents"] >= 1
    assert summary["totals"]["actionable"] >= 1
    assert summary["totals"]["with_suggested_commands"] >= 1
    assert summary["by_suggested_command"]["update_budget_policy"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_execute_applies_safe_command(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-safe-command-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    actions_response = client.get(
        "/api/execution-plane/agents/actions",
        params={"project_id": project_id, "suggested_command": "update_budget_policy", "command_requires_approval": False},
    )
    assert actions_response.status_code == 200
    action = next(item for item in actions_response.json()["actions"] if item["command"] == "update_budget_policy")

    action_detail = client.get(f"/api/execution-plane/agents/actions/{action['action_key']}")
    assert action_detail.status_code == 200
    assert action_detail.json()["approval_required"] is False

    execute_response = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "idempotency_key": "single-safe-1",
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert payload["status"] == "ok"
    assert payload["idempotent_replay"] is False
    assert payload["execution_strategy"] == "bounded_blueprint"
    assert payload["execution_blueprint"]["task_family"].startswith("action_batch_")
    assert payload["run"]["execution_blueprint"]["terminal_verdict"]["state"] == "completed"
    assert payload["action"]["action_key"] == action["action_key"]
    assert payload["command_result"]["command"] == "update_budget_policy"
    assert payload["project"]["budget"]["policy"]["agent_max_worker_iterations"] == 8
    assert payload["run"]["run_kind"] == "single_action"
    assert payload["run"]["idempotency_key"] == "single-safe-1"
    runs_response = client.get(
        "/api/execution-plane/agents/action-runs",
        params={"project_id": project_id, "run_kind": "single_action", "idempotency_key": "single-safe-1"},
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()["runs"]
    assert len(runs) == 1
    assert runs[0]["id"] == payload["run"]["id"]
    summary_response = client.get(
        "/api/execution-plane/agents/action-runs/summary",
        params={"project_id": project_id, "run_kind": "single_action"},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["single_action_runs"] >= 1
    assert summary["by_run_kind"]["single_action"] >= 1
    replay_response = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "idempotency_key": "single-safe-1",
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["idempotent_replay"] is True
    assert replay["run"]["id"] == payload["run"]["id"]
    action_events = client.get(
        "/api/execution-plane/events",
        params={"project_id": project_id, "runtime_agent_id": action["runtime_agent_id"]},
    )
    assert action_events.status_code == 200
    assert any(event["event"] == "execution_plane_agent_action_executed" for event in action_events.json()["events"])
    assert any(event["event"] == "execution_plane_agent_action_run_recorded" for event in action_events.json()["events"])


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_execute_escalates_to_approval_when_needed(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-approval-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Approval escalation loop",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 8,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 7, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 7, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    actions_response = client.get(
        "/api/execution-plane/agents/actions",
        params={"project_id": project_id, "suggested_command": "update_budget_policy", "command_requires_approval": True},
    )
    assert actions_response.status_code == 200
    action = next(item for item in actions_response.json()["actions"] if item["command"] == "update_budget_policy")
    assert action["approval_required"] is True

    execute_response = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "orchestrator_session_id": session["id"],
            "idempotency_key": "single-approval-1",
            "actor": "founderos",
            "mode": "auto",
            "reason": "Budget headroom needed before runtime stalls.",
        },
    )
    assert execute_response.status_code == 200
    payload = execute_response.json()
    assert payload["status"] == "pending_approval"
    assert payload["idempotent_replay"] is False
    assert payload["policy_triggered"] is True
    assert payload["approval"]["action"] == "update_budget_policy"
    assert payload["approval"]["runtime_agent_ids"] == [action["runtime_agent_id"]]
    assert payload["issue"]["approval_id"] == payload["approval"]["id"]
    assert payload["issue"]["context"]["command"]["runtime_agent_ids"] == [action["runtime_agent_id"]]
    assert payload["run"]["run_kind"] == "single_action"
    assert payload["run"]["orchestrator_session_id"] == session["id"]
    replay_response = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "orchestrator_session_id": session["id"],
            "idempotency_key": "single-approval-1",
            "actor": "founderos",
            "mode": "auto",
            "reason": "Budget headroom needed before runtime stalls.",
        },
    )
    assert replay_response.status_code == 200
    replay = replay_response.json()
    assert replay["idempotent_replay"] is True
    assert replay["run"]["id"] == payload["run"]["id"]
    approvals = client.get(f"/api/execution-plane/projects/{project_id}/approvals")
    assert approvals.status_code == 200
    assert len(approvals.json()["approvals"]) == 1
    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    linked = session_detail.json()
    assert linked["summary"]["run_count"] == 1
    assert linked["summary"]["approval_count"] == 1
    assert linked["summary"]["pending_approval_count"] == 1
    assert linked["summary"]["issue_count"] == 1
    assert linked["runtime_state"] == "requires_action"
    assert linked["pending_action"]["kind"] == "review_pending_approvals"
    assert linked["control"]["state"] == "needs_approval"
    assert linked["control"]["session_state"] == "requires_action"
    assert linked["control"]["pending_action"]["kind"] == "review_pending_approvals"
    assert any(item["kind"] == "review_pending_approvals" for item in linked["control"]["recommendations"])
    apply_recommendation = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "review_pending_approvals",
            "actor": "founderos",
            "reason": "Inspect approval queue for this session.",
        },
    )
    assert apply_recommendation.status_code == 200
    recommendation_payload = apply_recommendation.json()
    assert recommendation_payload["status"] == "ok"
    assert recommendation_payload["recommendation"]["kind"] == "review_pending_approvals"
    assert recommendation_payload["result"]["counts"]["pending_approvals"] == 1
    assert recommendation_payload["result"]["pending_approvals"][0]["id"] == payload["approval"]["id"]
    assert payload["run"]["id"] in linked["linked_run_ids"]
    assert payload["approval"]["id"] in linked["linked_approval_ids"]
    assert payload["issue"]["id"] in linked["linked_issue_ids"]
    assert action["runtime_agent_id"] in linked["linked_runtime_agent_ids"]
    linked_runs = client.get(
        "/api/execution-plane/agents/action-runs",
        params={"orchestrator_session_id": session["id"]},
    )
    assert linked_runs.status_code == 200
    assert len(linked_runs.json()["runs"]) == 1
    session_events = client.get(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/events",
        params={"limit": 20},
    )
    assert session_events.status_code == 200
    event_names = {event["event"] for event in session_events.json()["events"]}
    assert "execution_plane_agent_action_pending_approval" in event_names
    assert "execution_plane_agent_action_run_recorded" in event_names
    assert "approval_requested" in event_names
    assert "execution_issue_created" in event_names
    assert "execution_plane_orchestrator_session_recommendation_applied" in event_names
    action_events = client.get(
        "/api/execution-plane/events",
        params={"project_id": project_id, "runtime_agent_id": action["runtime_agent_id"]},
    )
    assert action_events.status_code == 200
    assert any(
        event["event"] == "execution_plane_agent_action_pending_approval"
        for event in action_events.json()["events"]
    )
    assert any(event["event"] == "execution_plane_agent_action_run_recorded" for event in action_events.json()["events"])

    plan_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply-plan",
        json={
            "profile": "review_only",
            "actor": "founderos",
            "reason": "Inspect approvals and issues without mutating the session.",
            "max_operations": 5,
        },
    )
    assert plan_response.status_code == 200
    plan = plan_response.json()
    assert plan["status"] == "ok"
    assert plan["profile"]["name"] == "review_only"
    assert plan["control_pass"]["orchestrator_session_id"] == session["id"]
    assert plan["summary"]["applied"] >= 2
    assert plan["summary"]["final_state"] == "needs_approval"
    assert any(step["recommendation_kind"] == "review_pending_approvals" for step in plan["applied"])
    assert any(step["recommendation_kind"] == "triage_open_issues" for step in plan["applied"])

    linked_after_plan = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert linked_after_plan.status_code == 200
    detail_after_plan = linked_after_plan.json()
    assert detail_after_plan["status"] == "open"
    assert detail_after_plan["runtime_state"] == "requires_action"
    assert detail_after_plan["control"]["state"] == "needs_approval"
    assert detail_after_plan["control"]["session_state"] == "requires_action"
    assert detail_after_plan["summary"]["control_pass_count"] == 1

    global_passes = client.get(
        "/api/execution-plane/orchestrator-sessions/control/passes",
        params={"orchestrator_session_id": session["id"], "profile": "review_only"},
    )
    assert global_passes.status_code == 200
    assert len(global_passes.json()["control_passes"]) == 1
    assert global_passes.json()["control_passes"][0]["id"] == plan["control_pass"]["id"]

    review_summary = client.get(
        "/api/execution-plane/orchestrator-sessions/control/passes/summary",
        params={"orchestrator_session_id": session["id"], "profile": "review_only"},
    )
    assert review_summary.status_code == 200
    review_summary_payload = review_summary.json()
    assert review_summary_payload["totals"]["control_passes"] == 1
    assert review_summary_payload["by_profile"]["review_only"] == 1
    assert review_summary_payload["by_final_state"]["needs_approval"] == 1
    assert review_summary_payload["by_session_status_after"]["open"] == 1


def test_execution_plane_orchestrator_session_control_apply_completes_healthy_session(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    session = _create_orchestrator_session(
        client,
        project_ids=[],
        initiative_id="init_empty_session",
        actor="founderos",
        title="FounderOS empty sweep",
    )

    control_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}/control")
    assert control_response.status_code == 200
    control = control_response.json()["control"]
    assert control["state"] == "healthy"
    assert any(item["kind"] == "complete_session" for item in control["recommendations"])

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "complete_session",
            "actor": "founderos",
            "reason": "No remaining work in this session.",
        },
    )
    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["status"] == "ok"
    assert payload["recommendation"]["kind"] == "complete_session"
    assert payload["result"]["session"]["status"] == "completed"

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["status"] == "completed"
    assert detail["runtime_state"] == "idle"
    assert detail["pending_action"] is None
    assert detail["control"]["state"] == "closed"
    assert detail["control"]["session_state"] == "idle"
    assert detail["control"]["pending_action"] is None


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_orchestrator_session_control_surfaces_pending_tool_permissions(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    created = _create_execution_project(client, tmp_path / "session-tool-permission-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        initiative_id="init_founderos_1",
        actor="founderos",
        title="FounderOS tool permission sweep",
    )
    agents_response = client.get(f"/api/execution-plane/projects/{project_id}/agents")
    assert agents_response.status_code == 200
    runtime_agent_id = agents_response.json()["agents"][0]["agent_id"]

    runtime = create_or_reuse_approval_runtime(
        config,
        key=f"tool-permission:{project_id}:demo.pause:toolu_session_1",
        project_id=project_id,
        runtime_agent_ids=[runtime_agent_id],
        metadata={
            "kind": "tool_permission_request",
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_session_1",
        },
        publish_pending=True,
        pending_message_type="tool_permission_pending",
        pending_payload={
            "tool_name": "demo.pause",
            "tool_use_id": "toolu_session_1",
            "message": "Need explicit approval.",
            "behavior": "pending_user",
        },
    )
    annotate_approval_runtime(
        config,
        approval_runtime_id=runtime.id,
        metadata_updates={
            "pending": {
                "stage": "pending_user",
                "tool_name": "demo.pause",
                "tool_use_id": "toolu_session_1",
            }
        },
        payload_updates={
            "pending_user": {
                "message": "Need explicit approval.",
                "tool_name": "demo.pause",
                "tool_use_id": "toolu_session_1",
            }
        },
        mailbox_message_type="tool_permission_user_pending",
        mailbox_payload={"tool_name": "demo.pause", "tool_use_id": "toolu_session_1"},
    )

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["summary"]["tool_permission_runtime_count"] == 1
    assert detail["summary"]["pending_tool_permission_runtime_count"] == 1
    assert detail["runtime_state"] == "requires_action"
    assert detail["pending_action"]["kind"] == "review_pending_tool_permissions"
    assert detail["control"]["state"] == "needs_approval"
    assert detail["control"]["counts"]["pending_tool_permission_runtimes"] == 1
    assert detail["control"]["session_state"] == "requires_action"
    assert detail["control"]["pending_action"]["kind"] == "review_pending_tool_permissions"
    assert any(item["kind"] == "review_pending_tool_permissions" for item in detail["control"]["recommendations"])

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "review_pending_tool_permissions",
            "actor": "founderos",
            "reason": "Inspect pending tool permission requests.",
        },
    )
    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["status"] == "ok"
    assert payload["recommendation"]["kind"] == "review_pending_tool_permissions"
    assert payload["result"]["counts"]["pending_tool_permission_runtimes"] == 1
    assert payload["result"]["pending_tool_permission_runtimes"][0]["id"] == runtime.id


def test_execution_plane_orchestrator_session_control_surfaces_shadow_audit_quarantines(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    session = _create_orchestrator_session(
        client,
        project_ids=["proj_shadow"],
        initiative_id="init_shadow",
        actor="founderos",
        title="FounderOS shadow audit sweep",
    )

    record = create_shadow_audit_record(
        config,
        project_id="proj_shadow",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["proj_shadow:1:worker:a"],
        source_kind="tool_result",
        source_name="demo.inspect",
        source_id="toolu_shadow_1",
        action="quarantine",
        summary="Suspicious tool output was quarantined before downstream handoff.",
        findings=["unverified_generated_patch"],
        content="diff --git a/app.py b/app.py",
    )

    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    detail = session_detail.json()
    assert detail["summary"]["shadow_audit_count"] == 1
    assert detail["summary"]["open_shadow_audit_count"] == 1
    assert detail["runtime_state"] == "requires_action"
    assert detail["pending_action"]["kind"] == "review_shadow_audit_quarantines"
    assert detail["control"]["state"] == "attention_required"
    assert detail["control"]["counts"]["open_shadow_audits"] == 1
    assert detail["control"]["pending_action"]["kind"] == "review_shadow_audit_quarantines"
    assert detail["shadow_audits"][0]["id"] == record.id
    assert any(item["kind"] == "review_shadow_audit_quarantines" for item in detail["control"]["recommendations"])

    apply_response = client.post(
        f"/api/execution-plane/orchestrator-sessions/{session['id']}/control/apply",
        json={
            "recommendation_kind": "review_shadow_audit_quarantines",
            "actor": "founderos",
            "reason": "Inspect quarantined artifacts before resuming progress.",
        },
    )
    assert apply_response.status_code == 200
    payload = apply_response.json()
    assert payload["status"] == "ok"
    assert payload["recommendation"]["kind"] == "review_shadow_audit_quarantines"
    assert payload["result"]["counts"]["open_shadow_audits"] == 1
    assert payload["result"]["open_shadow_audits"][0]["id"] == record.id


def test_execution_plane_runtime_agent_task_output_shadow_audit_requires_explicit_review_and_resolve(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    project_root = tmp_path / "shadow-task-project"
    prd_path = project_root / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Shadow Task Project",
                "description": "Verify quarantined runtime-task outputs.",
                "stories": [
                    {"id": 1, "title": "Launch", "description": "Run background work", "status": "open", "position": 0}
                ],
            }
        ),
        encoding="utf-8",
    )
    project = register_project(
        config,
        name="Shadow Task Project",
        project_path=project_root,
        prd_relpath=".agents/tasks/prd.json",
    )
    project_id = str(project["id"])
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        initiative_id="init_shadow_task",
        actor="founderos",
        title="FounderOS shadow task review",
    )
    log_path = config.autopilot_home / "logs" / "shadow-task.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished cleanly\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=[f"{project_id}:1:worker:a"],
        output_path=str(log_path),
        metadata={
            "shadow_audit": {
                "action": "quarantine",
                "summary": "Background task output requires explicit review before handoff.",
                "findings": ["unverified_subagent_output"],
            }
        },
    )
    save_project_state(
        config,
        project_id,
        {
            "status": "completed",
            "paused": False,
            "finished_at": "2026-04-02T00:00:00+00:00",
            "log_path": str(log_path),
        },
    )

    blocked_output_response = client.get(f"/api/execution-plane/agents/tasks/{task.id}/output")
    assert blocked_output_response.status_code == 200
    blocked_output = blocked_output_response.json()
    audit_id = blocked_output["shadow_audits"][0]["id"]

    blocked_live_output_response = client.get(
        f"/api/execution-plane/agents/tasks/{task.id}/output/live",
        params={"tail_lines": 20},
    )
    assert blocked_live_output_response.status_code == 200
    blocked_live_output = blocked_live_output_response.json()

    assert blocked_output["status"] == "quarantined"
    assert blocked_output["content"] == ""
    assert blocked_output["content_blocked"] is True
    assert blocked_output["quarantined"] is True
    assert blocked_output["shadow_audits"][0]["source_kind"] == "runtime_agent_task_output"
    assert blocked_output["shadow_audits"][0]["blocked_artifact_ref"] == f"/api/execution-plane/agents/tasks/{task.id}/output"
    assert blocked_live_output["status"] == "quarantined"
    assert blocked_live_output["content"] == ""
    assert blocked_live_output["content_blocked"] is True
    assert blocked_live_output["quarantined"] is True

    task_detail_response = client.get(f"/api/execution-plane/agents/tasks/{task.id}")
    assert task_detail_response.status_code == 200
    task_detail = task_detail_response.json()
    assert task_detail["output_quarantined"] is True
    assert task_detail["open_shadow_audit_count"] == 1

    audit_detail_response = client.get(f"/api/execution-plane/shadow-audits/{audit_id}")
    assert audit_detail_response.status_code == 200
    audit_detail = audit_detail_response.json()
    assert audit_detail["id"] == audit_id
    assert audit_detail["blocked_artifact"]["artifact_ref"] == f"/api/execution-plane/agents/tasks/{task.id}/output"
    assert "launch finished cleanly" in audit_detail["blocked_artifact"]["content"]

    session_detail_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail_response.status_code == 200
    session_detail = session_detail_response.json()
    assert session_detail["summary"]["open_shadow_audit_count"] == 1

    resolve_response = client.post(
        f"/api/execution-plane/shadow-audits/{audit_id}/resolve",
        json={"actor": "founderos", "note": "Reviewed and accepted."},
    )
    assert resolve_response.status_code == 200
    resolved_payload = resolve_response.json()
    assert resolved_payload["status"] == "ok"
    assert resolved_payload["shadow_audit"]["status"] == "resolved"

    unblocked_output_response = client.get(f"/api/execution-plane/agents/tasks/{task.id}/output")
    assert unblocked_output_response.status_code == 200
    unblocked_output = unblocked_output_response.json()
    assert unblocked_output["status"] == "ok"
    assert unblocked_output["content_blocked"] is False
    assert unblocked_output["quarantined"] is False
    assert "launch finished cleanly" in unblocked_output["content"]

    refreshed_session_response = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert refreshed_session_response.status_code == 200
    refreshed_session = refreshed_session_response.json()
    assert refreshed_session["summary"]["open_shadow_audit_count"] == 0


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_batch_execute_applies_filtered_safe_actions(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-batch-safe-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Safe batch maintenance loop",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    profiles_response = client.get("/api/execution-plane/agents/actions/policy-profiles")
    assert profiles_response.status_code == 200
    profiles = profiles_response.json()["profiles"]
    assert "safe_budget_maintenance" in profiles

    response = client.post(
        "/api/execution-plane/agents/actions/execute-batch",
        json={
            "orchestrator_session_id": session["id"],
            "idempotency_key": "safe-budget-batch-1",
            "policy_profile": "safe_budget_maintenance",
            "project_id": project_id,
            "actor": "founderos",
            "mode": "auto",
            "limit": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["idempotent_replay"] is False
    assert payload["execution_strategy"] == "bounded_blueprint"
    assert payload["execution_blueprint"]["task_family"].startswith("action_batch_")
    assert payload["run"]["execution_blueprint"]["terminal_verdict"]["state"] == "completed"
    assert payload["selection"]["mode"] == "filters"
    assert payload["policy"]["profile_name"] == "safe_budget_maintenance"
    assert payload["summary"]["selected_count"] >= 1
    assert payload["summary"]["status_counts"]["ok"] >= 1
    assert payload["run"]["idempotency_key"] == "safe-budget-batch-1"
    assert payload["run"]["orchestrator_session_id"] == session["id"]
    assert any(
        result["status"] == "ok" and result["command_result"]["command"] == "update_budget_policy"
        for result in payload["results"]
    )

    runs_response = client.get(
        "/api/execution-plane/agents/action-runs",
        params={"project_id": project_id, "orchestrator_session_id": session["id"]},
    )
    assert runs_response.status_code == 200
    runs = runs_response.json()["runs"]
    assert len(runs) >= 1
    run_id = payload["run"]["id"]
    assert any(run["id"] == run_id for run in runs)

    run_detail = client.get(f"/api/execution-plane/agents/action-runs/{run_id}")
    assert run_detail.status_code == 200
    assert run_detail.json()["id"] == run_id
    assert run_detail.json()["project_ids"] == [project_id]
    assert run_detail.json()["orchestrator_session_id"] == session["id"]

    summary_response = client.get("/api/execution-plane/agents/action-runs/summary", params={"project_id": project_id})
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["runs"] >= 1
    assert summary["totals"]["executions"] >= 1
    assert summary["by_policy_profile"]["safe_budget_maintenance"] >= 1
    assert summary["result_status_counts"]["ok"] >= 1

    run_events = client.get("/api/execution-plane/events", params={"project_id": project_id})
    assert run_events.status_code == 200
    assert any(
        event["event"] == "execution_plane_agent_batch_executed" and event["agent_action_run_id"] == run_id
        for event in run_events.json()["events"]
    )
    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    assert run_id in session_detail.json()["linked_run_ids"]
    assert session_detail.json()["summary"]["by_event"]["execution_plane_agent_batch_executed"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_tracks_pending_async_completion_honestly(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-run-async-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Async action run lifecycle",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[
            {
                "status": "ok",
                "command_result": {"command": "launch"},
                "async_task": {"id": task.id},
            }
        ],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-1"],
    )

    detail_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["completion_state"] == "pending_async"
    assert detail["async_task_count"] == 1
    assert detail["active_async_task_count"] == 1
    assert detail["async_tasks"][0]["id"] == task.id
    assert detail["async_tasks"][0]["resume_contract"]["task_id"] == task.id
    assert detail["resume_contracts"][0]["task_id"] == task.id
    assert detail["resume_contract"]["task_id"] == task.id
    assert detail["completed_at"] is None
    assert "do not treat this run as complete yet" in detail["completion_message"]

    summary_response = client.get(
        "/api/execution-plane/agents/action-runs/summary",
        params={"project_id": project_id},
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["pending_async"] >= 1
    assert summary["by_completion_state"]["pending_async"] >= 1

    pending_events = client.get("/api/execution-plane/events", params={"project_id": project_id})
    assert pending_events.status_code == 200
    assert any(
        event["event"] == "execution_plane_agent_action_run_pending_async"
        and event["agent_action_run_id"] == run.id
        for event in pending_events.json()["events"]
    )

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    state["log_path"] = str(config.autopilot_home / "logs" / f"{project_id}.log")
    save_project_state(config, project_id, state)

    refreshed_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert refreshed_response.status_code == 200
    refreshed = refreshed_response.json()
    assert refreshed["completion_state"] == "completed"
    assert refreshed["async_task_count"] == 1
    assert refreshed["active_async_task_count"] == 0
    assert refreshed["async_tasks"][0]["id"] == task.id
    assert refreshed["resume_contract"]["task_id"] == task.id
    assert refreshed["completed_at"] == "2026-04-01T12:34:56+00:00"
    assert refreshed["async_task_status_counts"]["completed"] == 1
    assert refreshed["completion_message"] == "Async follow-through reached terminal state."

    refreshed_summary = client.get(
        "/api/execution-plane/agents/action-runs/summary",
        params={"project_id": project_id},
    )
    assert refreshed_summary.status_code == 200
    assert refreshed_summary.json()["totals"]["pending_async"] == 0
    assert refreshed_summary.json()["by_completion_state"]["completed"] >= 1

    settled_events = client.get("/api/execution-plane/events", params={"project_id": project_id})
    assert settled_events.status_code == 200
    assert any(
        event["event"] == "execution_plane_agent_action_run_async_settled"
        and event["agent_action_run_id"] == run.id
        for event in settled_events.json()["events"]
    )


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_surfaces_linked_async_task_without_inline_result_payload(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "linked-async-run-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Linked async action run lifecycle",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[
            {
                "status": "ok",
                "message": "Background launch requested.",
                "command_result": {"command": "launch"},
            }
        ],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-1"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id=run.id)

    detail_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["completion_state"] == "pending_async"
    assert detail["async_task_count"] == 1
    assert detail["active_async_task_count"] == 1
    assert detail["async_tasks"][0]["id"] == task.id
    assert detail["resume_contract"]["task_id"] == task.id

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:45:00+00:00"
    log_path = config.autopilot_home / "logs" / f"{project_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished\n", encoding="utf-8")
    state["log_path"] = str(log_path)
    save_project_state(config, project_id, state)

    refreshed_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert refreshed_response.status_code == 200
    refreshed = refreshed_response.json()
    assert refreshed["completion_state"] == "completed"
    assert refreshed["active_async_task_count"] == 0
    assert refreshed["async_task_status_counts"]["completed"] == 1
    assert refreshed["async_tasks"][0]["id"] == task.id


def test_execution_plane_agent_action_run_surfaces_quarantined_linked_async_handoff_until_resolved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    project_root = tmp_path / "action-run-shadow-project"
    prd_path = project_root / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Action Run Shadow Project",
                "description": "Verify quarantined action-run handoff state.",
                "stories": [
                    {"id": 1, "title": "Launch", "description": "Run background work", "status": "open", "position": 0}
                ],
            }
        ),
        encoding="utf-8",
    )
    project = register_project(
        config,
        name="Action Run Shadow Project",
        project_path=project_root,
        prd_relpath=".agents/tasks/prd.json",
    )
    project_id = str(project["id"])
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        initiative_id="init_shadow_run",
        actor="founderos",
        title="FounderOS action-run shadow review",
    )
    log_path = config.autopilot_home / "logs" / "action-run-shadow.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished cleanly\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-shadow"],
        output_path=str(log_path),
        metadata={
            "shadow_audit": {
                "action": "quarantine",
                "summary": "Background task output requires explicit review before action-run handoff.",
                "findings": ["unverified_subagent_output"],
            }
        },
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[{"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task.id}}],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-shadow"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id=run.id)

    pending_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert pending_response.status_code == 200
    assert pending_response.json()["completion_state"] == "pending_async"

    save_project_state(
        config,
        project_id,
        {
            "status": "completed",
            "paused": False,
            "finished_at": "2026-04-02T00:10:00+00:00",
            "log_path": str(log_path),
        },
    )

    quarantined_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert quarantined_response.status_code == 200
    quarantined = quarantined_response.json()
    audit_id = quarantined["shadow_audits"][0]["id"]

    assert quarantined["completion_state"] == "quarantined"
    assert quarantined["handoff_state"] == "quarantined"
    assert quarantined["handoff_blocked"] is True
    assert quarantined["open_shadow_audit_count"] == 1
    assert quarantined["async_task_count"] == 1
    assert quarantined["active_async_task_count"] == 0
    assert quarantined["resume_contract"]["output_quarantined"] is True
    assert quarantined["async_tasks"][0]["output_quarantined"] is True
    assert quarantined["shadow_audits"][0]["source_kind"] == "runtime_agent_task_output"
    assert "require explicit review" in quarantined["completion_message"]

    summary_runs_response = client.get(
        "/api/execution-plane/agents/action-runs",
        params={"project_id": project_id, "summary": True},
    )
    assert summary_runs_response.status_code == 200
    summary_runs = summary_runs_response.json()["runs"]
    summary_run = next(item for item in summary_runs if item["id"] == run.id)
    assert summary_run["completion_state"] == "quarantined"
    assert summary_run["handoff_blocked"] is True
    assert summary_run["open_shadow_audit_count"] == 1
    assert summary_run["summary"]["selected_count"] == 1
    assert summary_run["shadow_audits"][0]["id"] == audit_id
    assert "results" not in summary_run
    assert "async_tasks" not in summary_run
    assert "resume_contracts" not in summary_run
    assert "selection" not in summary_run
    assert "policy" not in summary_run
    assert "diff_summary" not in summary_run
    assert "patch_bundle" not in summary_run

    summary_response = client.get("/api/execution-plane/agents/action-runs/summary", params={"project_id": project_id})
    assert summary_response.status_code == 200
    summary = summary_response.json()
    assert summary["totals"]["quarantined"] >= 1
    assert summary["by_completion_state"]["quarantined"] >= 1

    resolve_response = client.post(
        f"/api/execution-plane/shadow-audits/{audit_id}/resolve",
        json={"actor": "founderos", "note": "Reviewed and accepted."},
    )
    assert resolve_response.status_code == 200

    resolved_run_response = client.get(f"/api/execution-plane/agents/action-runs/{run.id}")
    assert resolved_run_response.status_code == 200
    resolved_run = resolved_run_response.json()
    assert resolved_run["completion_state"] == "completed"
    assert resolved_run["handoff_state"] == "clear"
    assert resolved_run["handoff_blocked"] is False
    assert resolved_run["open_shadow_audit_count"] == 0
    assert resolved_run["resume_contract"]["output_quarantined"] is False


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_wait_for_async_settlement_observes_linked_task_mailbox(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "action-run-mailbox-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Async action run mailbox lifecycle",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}.log"),
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[{"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task.id}}],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-1"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id=run.id)

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:55:00+00:00"
    log_path = config.autopilot_home / "logs" / f"{project_id}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("launch started\nlaunch finished\n", encoding="utf-8")
    state["log_path"] = str(log_path)
    save_project_state(config, project_id, state)

    response = client.get(
        f"/api/execution-plane/agents/action-runs/{run.id}",
        params={"wait_for_async_settlement": "true", "runtime_agent_id": "runtime-agent-1", "wait_timeout_ms": 200},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["completion_state"] == "completed"
    assert payload["active_async_task_count"] == 0
    assert payload["async_tasks"][0]["id"] == task.id
    mailbox = list_agent_mailbox_messages(
        config,
        project_id=project_id,
        runtime_agent_id="runtime-agent-1",
        message_type="runtime_agent_task_resolved",
    )
    assert any(message.payload["task_id"] == task.id for message in mailbox)


@patch("autopilot.core.execution_plane.wait_for_runtime_agent_task_mailbox_resolution")
@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_wait_for_async_settlement_routes_tasks_to_their_runtime_agent(
    mock_generate_prd_from_spec,
    mock_wait_for_runtime_agent_task_mailbox_resolution,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "action-run-multi-agent-mailbox-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Async action run multi-agent routing",
    )

    task_a = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution A.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-task-a"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}-a.log"),
    )
    task_b = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution B.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-task-b"],
        output_path=str(config.autopilot_home / "logs" / f"{project_id}-b.log"),
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 2, "processed_count": 2, "status_counts": {"ok": 2}},
        results=[
            {"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task_a.id}},
            {"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task_b.id}},
        ],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-run"],
    )
    link_runtime_agent_task_run(config, task_a.id, agent_action_run_id=run.id)
    link_runtime_agent_task_run(config, task_b.id, agent_action_run_id=run.id)
    mock_wait_for_runtime_agent_task_mailbox_resolution.side_effect = [task_a, task_b]

    payload = execution_plane_core.wait_for_execution_plane_agent_action_run_async_settlement(
        config,
        run.id,
        wait_timeout_sec=0.1,
    )

    assert payload["completion_state"] == "pending_async"
    observed_routes = {
        (
            str(call.kwargs.get("task_id") or ""),
            str(call.kwargs.get("runtime_agent_id") or ""),
        )
        for call in mock_wait_for_runtime_agent_task_mailbox_resolution.call_args_list
    }
    assert observed_routes == {
        (task_a.id, "runtime-agent-task-a"),
        (task_b.id, "runtime-agent-task-b"),
    }


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_cancel_async_route_pauses_projects_and_settles_run(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "action-run-cancel-async-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Action run cancel async",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[{"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task.id}}],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-1"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id=run.id)

    response = client.post(
        f"/api/execution-plane/agents/action-runs/{run.id}/cancel-async",
        json={"actor": "martin", "note": "Stop async follow-through."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["cancel_applied"] is True
    assert payload["cancelled_task_ids"] == [task.id]
    assert payload["run"]["id"] == run.id
    assert payload["run"]["completion_state"] == "completed"
    assert payload["run"]["async_task_status_counts"]["cancelled"] == 1
    assert payload["run"]["async_tasks"][0]["id"] == task.id
    assert payload["run"]["async_tasks"][0]["status"] == "cancelled"
    assert payload["run"]["async_tasks"][0]["settlement_reason"] == "paused"

    state = load_project_state(config, project_id)
    assert state["status"] == "paused"
    assert state["paused"] is True


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_run_cancel_async_route_is_noop_without_active_tasks(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "action-run-cancel-async-noop-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Action run cancel async noop",
    )

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command="launch",
        actor="founderos",
        reason="Launch background execution.",
        orchestrator_session_id=session["id"],
        runtime_agent_ids=["runtime-agent-1"],
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=session["id"],
        actor="founderos",
        mode="auto",
        selection={"mode": "single_action", "project_id": project_id},
        summary={"selected_count": 1, "processed_count": 1, "status_counts": {"ok": 1}},
        results=[{"status": "ok", "command_result": {"command": "launch"}, "async_task": {"id": task.id}}],
        status="ok",
        project_ids=[project_id],
        runtime_agent_ids=["runtime-agent-1"],
    )
    link_runtime_agent_task_run(config, task.id, agent_action_run_id=run.id)

    state = load_project_state(config, project_id)
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T13:00:00+00:00"
    save_project_state(config, project_id, state)

    response = client.post(f"/api/execution-plane/agents/action-runs/{run.id}/cancel-async")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["cancel_applied"] is False
    assert payload["cancelled_task_ids"] == []
    assert payload["run"]["completion_state"] == "completed"
    assert payload["run"]["async_task_status_counts"]["completed"] == 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_batch_execute_escalates_filtered_actions(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-batch-approval-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 8,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 8, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 8, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    response = client.post(
        "/api/execution-plane/agents/actions/execute-batch",
        json={
            "idempotency_key": "approval-batch-1",
            "policy_profile": "budget_maintenance_with_high_priority_escalation",
            "project_id": project_id,
            "actor": "founderos",
            "mode": "auto",
            "limit": 5,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["policy"]["profile_name"] == "budget_maintenance_with_high_priority_escalation"
    assert payload["summary"]["selected_count"] >= 1
    assert payload["summary"]["status_counts"]["pending_approval"] >= 1
    assert any(
        result["status"] == "pending_approval" and result["approval"]["action"] == "update_budget_policy"
        for result in payload["results"]
    )
    assert payload["run"]["idempotency_key"] == "approval-batch-1"

    replay = client.post(
        "/api/execution-plane/agents/actions/execute-batch",
        json={
            "idempotency_key": "approval-batch-1",
            "policy_profile": "budget_maintenance_with_high_priority_escalation",
            "project_id": project_id,
            "actor": "founderos",
            "mode": "auto",
            "limit": 5,
        },
    )
    assert replay.status_code == 200
    replay_payload = replay.json()
    assert replay_payload["idempotent_replay"] is True
    assert replay_payload["run"]["id"] == payload["run"]["id"]

    approvals = client.get(f"/api/execution-plane/projects/{project_id}/approvals")
    assert approvals.status_code == 200
    assert len(approvals.json()["approvals"]) == 1


def test_execution_plane_agent_action_batch_requires_scope_or_action_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.post(
        "/api/execution-plane/agents/actions/execute-batch",
        json={"actor": "founderos", "mode": "auto"},
    )
    assert response.status_code == 400
    assert "requires explicit action_keys or a project/initiative/orchestrator scope" in response.json()["detail"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_batch_preview_is_non_mutating(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "agent-action-batch-preview-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Preview maintenance loop",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    preview_response = client.post(
        "/api/execution-plane/agents/actions/preview-batch",
        json={
            "orchestrator_session_id": session["id"],
            "idempotency_key": "preview-batch-1",
            "project_id": project_id,
            "policy_profile": "safe_budget_maintenance",
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["dry_run"] is True
    assert preview["idempotent_replay"] is False
    assert preview["execution_strategy"] == "bounded_blueprint"
    assert preview["execution_blueprint"]["task_family"].startswith("action_batch_")
    assert preview["run"]["execution_blueprint"]["terminal_verdict"]["state"] == "completed"
    assert preview["preview_id"] == preview["run"]["id"]
    assert preview["artifact_ref"].endswith(preview["run"]["id"])
    assert preview["approval_required"] is False
    assert preview["apply_mode"] == "manual"
    assert preview["summary"]["status_counts"]["planned_execute"] >= 1
    assert preview["diff_summary"]["command_counts"]["update_budget_policy"] >= 1
    assert len(preview["patch_bundle"]["operations"]) >= 1
    assert preview["run"]["idempotency_key"] == "preview-batch-1"
    assert preview["run"]["orchestrator_session_id"] == session["id"]
    preview_runs = client.get("/api/execution-plane/agents/action-runs", params={"project_id": project_id, "dry_run": True})
    assert preview_runs.status_code == 200
    assert any(run["id"] == preview["run"]["id"] for run in preview_runs.json()["runs"])
    preview_summary = client.get("/api/execution-plane/agents/action-runs/summary", params={"project_id": project_id, "dry_run": True})
    assert preview_summary.status_code == 200
    assert preview_summary.json()["totals"]["dry_runs"] >= 1
    assert preview_summary.json()["by_policy_profile"]["safe_budget_maintenance"] >= 1

    detail = client.get(f"/api/execution-plane/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["budget"]["policy"]["agent_max_worker_iterations"] == 3

    approvals = client.get(f"/api/execution-plane/projects/{project_id}/approvals")
    assert approvals.status_code == 200
    assert approvals.json()["approvals"] == []

    events = client.get("/api/execution-plane/events", params={"project_id": project_id})
    assert events.status_code == 200
    assert not any(
        event["event"] in {"execution_plane_agent_action_executed", "execution_plane_agent_action_pending_approval"}
        for event in events.json()["events"]
    )
    assert any(
        event["event"] == "execution_plane_agent_batch_previewed" and event["agent_action_run_id"] == preview["run"]["id"]
        for event in events.json()["events"]
    )
    session_detail = client.get(f"/api/execution-plane/orchestrator-sessions/{session['id']}")
    assert session_detail.status_code == 200
    linked = session_detail.json()
    assert linked["summary"]["run_count"] == 1
    assert preview["run"]["id"] in linked["linked_run_ids"]
    assert linked["summary"]["by_event"]["execution_plane_agent_batch_previewed"] >= 1


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_batch_idempotency_key_conflict(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }
    created = _create_execution_project(client, tmp_path / "conflict-project")
    project_id = created["project"]["project_id"]

    ok = client.post(
        "/api/execution-plane/agents/actions/preview-batch",
        json={
            "idempotency_key": "conflict-key-1",
            "project_id": project_id,
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert ok.status_code == 200

    conflict = client.post(
        "/api/execution-plane/agents/actions/preview-batch",
        json={
            "idempotency_key": "conflict-key-1",
            "project_id": project_id,
            "actor": "founderos",
            "mode": "execute_now",
        },
    )
    assert conflict.status_code == 409
    assert "already used for a different batch action request" in conflict.json()["detail"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_batch_execute_rejects_mismatched_preview_mode(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "mismatched-preview-project")
    project_id = created["project"]["project_id"]
    session = _create_orchestrator_session(
        client,
        project_ids=[project_id],
        actor="founderos",
        title="Preview apply mismatch session",
    )

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    preview_response = client.post(
        "/api/execution-plane/agents/actions/preview-batch",
        json={
            "orchestrator_session_id": session["id"],
            "project_id": project_id,
            "policy_profile": "safe_budget_maintenance",
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()

    execute_response = client.post(
        "/api/execution-plane/agents/actions/execute-batch",
        json={
            "preview_id": preview["preview_id"],
            "orchestrator_session_id": session["id"],
            "project_id": project_id,
            "policy_profile": "safe_budget_maintenance",
            "actor": "founderos",
            "mode": "execute_now",
        },
    )
    assert execute_response.status_code == 409
    assert "was created with mode `auto`, not `execute_now`" in execute_response.json()["detail"]


@patch("autopilot.core.execution_plane.generate_prd_from_spec")
def test_execution_plane_agent_action_single_idempotency_key_conflict(
    mock_generate_prd_from_spec,
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)
    mock_generate_prd_from_spec.return_value = {
        "title": "FounderOS Copilot",
        "description": "Execution-ready FounderOS project.",
        "stories": [{"id": 1, "title": "Bootstrap", "description": "Create the app shell"}],
    }

    created = _create_execution_project(client, tmp_path / "single-conflict-project")
    project_id = created["project"]["project_id"]

    update_story_runtime(
        config,
        project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        critic="codex/critic-a",
    )
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=1,
        current_iteration=2,
        active_worker="codex/worker-a",
        active_critic="codex/critic-a",
        budget_policy={
            "project_max_worker_iterations": 200,
            "project_max_critic_reviews": 200,
            "agent_max_worker_iterations": 3,
            "agent_max_critic_reviews": 60,
            "auto_pause_on_exhaustion": True,
        },
        budget_usage={
            "project": {"worker_iterations": 2, "critic_reviews": 2},
            "agents": {
                "codex/worker-a": {"worker_iterations": 2, "critic_reviews": 0},
                "codex/critic-a": {"worker_iterations": 0, "critic_reviews": 2},
            },
            "last_exhaustion_reason": None,
            "auto_paused_at": None,
        },
    )

    actions = client.get(
        "/api/execution-plane/agents/actions",
        params={"project_id": project_id, "suggested_command": "update_budget_policy", "command_requires_approval": False},
    )
    assert actions.status_code == 200
    action = next(item for item in actions.json()["actions"] if item["command"] == "update_budget_policy")

    first = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "idempotency_key": "single-conflict-1",
            "actor": "founderos",
            "mode": "auto",
        },
    )
    assert first.status_code == 200

    conflict = client.post(
        "/api/execution-plane/agents/actions/execute",
        json={
            "action_key": action["action_key"],
            "idempotency_key": "single-conflict-1",
            "actor": "founderos",
            "mode": "execute_now",
        },
    )
    assert conflict.status_code == 409
    assert "already used for a different runtime-agent action request" in conflict.json()["detail"]
