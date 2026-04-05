"""Integration test: V2 launch gate blocks unapproved briefs on the live path.

This test validates the audit requirement P0.1: founder approval gate must
block execution launch on the actual V2 ingestion path, not just on helpers.

It also validates P0.1 containment: the legacy shared-brief route returns
409 when launch=True (regardless of approval status).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from autopilot.api.routes import execution_plane, projects
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_projects_registry


# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

class _FakeManager:
    def __init__(self, *, profile: object | None = None):
        self._profile = profile
        self.get_next_calls = 0

    def get_next(self, provider: str):
        self.get_next_calls += 1
        return self._profile

    def build_env(self, profile):
        return {}


def _build_client(config: AutopilotConfig, manager: _FakeManager, monkeypatch) -> TestClient:
    from fastapi import FastAPI

    monkeypatch.setattr(projects, "get_config", lambda: config)
    monkeypatch.setattr(projects, "get_account_manager", lambda: manager)
    monkeypatch.setattr(execution_plane, "get_config", lambda: config)
    monkeypatch.setattr(execution_plane, "get_account_manager", lambda: manager)

    app = FastAPI()
    app.include_router(projects.router, prefix="/api/projects")
    app.include_router(execution_plane.router, prefix="/api/execution-plane")
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# V2 brief payloads
# ---------------------------------------------------------------------------

def _v2_brief_payload(*, approval_status: str = "pending") -> dict:
    return {
        "schema_version": "2.0",
        "brief_id": "brief-gate-test",
        "revision_id": "rev-001",
        "initiative_id": "init-001",
        "title": "Gate test initiative",
        "initiative_summary": "Test that approval gate works on live path",
        "winner_rationale": "",
        "research_summary": "",
        "success_criteria": ["Gate blocks unapproved launch"],
        "budget_policy": {"tier": "low"},
        "approval_policy": {"founder_approval_required": True},
        "recommended_tech_stack": ["python"],
        "story_breakdown": [
            {
                "title": "Verify gate",
                "description": "Ensure launch is blocked",
                "acceptance_criteria": ["409 returned"],
                "effort": "small",
            }
        ],
        "risks": [],
        "repo_dna_snapshot": {},
        "citations": [],
        "evidence": None,
        "source_pack_ref": None,
        "repo_instruction_refs": [],
        "brief_approval_status": approval_status,
        "created_at": "2026-04-05T00:00:00Z",
        "updated_at": "2026-04-05T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_v2_route_blocks_unapproved_launch(monkeypatch, tmp_path):
    """V2 route returns 409 when brief is pending and launch=True."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("planner should not run before approval gate")),
    )

    response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": True,
        },
    )
    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
    assert "approved" in response.json().get("detail", "").lower()
    assert manager.get_next_calls == 0
    assert load_projects_registry(config, include_archived=True) == []


def test_v2_route_skips_gate_when_launch_false(monkeypatch, tmp_path):
    """V2 route does not block when launch=False even if brief is pending."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=None)
    client = _build_client(config, manager, monkeypatch)

    response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
        },
    )
    # Gate doesn't fire (launch=False), so it proceeds to account lookup which fails
    assert response.status_code == 503
    assert "no available accounts" in response.json().get("detail", "").lower()
    assert manager.get_next_calls == 1


def test_launch_route_blocks_pending_v2_project(monkeypatch, tmp_path):
    """Pending V2 projects cannot be re-launched through /api/projects/{id}/launch."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for launch gate regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Keep route blocked"}],
        },
    )
    monkeypatch.setattr(
        projects,
        "launch_project_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("launch route should block before launch_project_run")),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
            "project_path": str(tmp_path / "pending-v2-project"),
        },
    )

    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    launch = client.post(f"/api/projects/{project_id}/launch", json={})
    assert launch.status_code == 409
    assert "approved" in launch.json().get("detail", "").lower()


def test_launch_route_allows_approved_v2_project(monkeypatch, tmp_path):
    """Approved V2 projects can still be launched through the standard route."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for launch gate regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Allow approved relaunch"}],
        },
    )
    monkeypatch.setattr(
        projects,
        "launch_project_run",
        lambda *args, **kwargs: (True, None, "Project launched."),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="approved"),
            "launch": False,
            "project_path": str(tmp_path / "approved-v2-project"),
        },
    )

    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    launch = client.post(f"/api/projects/{project_id}/launch", json={})
    assert launch.status_code == 200
    assert launch.json()["launched"] is True


def test_v2_route_rejects_duplicate_brief_ingest(monkeypatch, tmp_path):
    """Canonical V2 ingest deduplicates by brief_id before creating a second project."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for dedup regression coverage.",
            "stories": [{"id": 1, "title": "Verify dedup", "description": "Reject duplicate brief"}],
        },
    )

    first = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="approved"),
            "launch": False,
            "project_path": str(tmp_path / "first-v2-project"),
        },
    )
    assert first.status_code == 200, first.text

    second = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="approved"),
            "launch": False,
            "project_path": str(tmp_path / "second-v2-project"),
        },
    )
    assert second.status_code == 409
    assert "already linked to project" in second.json().get("detail", "").lower()


def test_v2_ingest_reject_leaves_no_artifacts(monkeypatch, tmp_path):
    """Pending brief + launch=True produces 409 with zero project/PRD/lineage artifacts.

    Validates P0.2 auditor requirement: approval gate fires before ANY side effects.
    """
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)

    # If planner runs, the gate was too late
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *a, **kw: (_ for _ in ()).throw(
            AssertionError("planner must not run before approval gate")
        ),
    )

    response = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": True,
            "project_path": str(tmp_path / "rejected-project"),
        },
    )

    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
    assert "approved" in response.json().get("detail", "").lower()

    # No projects created
    assert load_projects_registry(config, include_archived=True) == []

    # No PRD directories created
    projects_dir = tmp_path / ".autopilot" / "projects"
    if projects_dir.exists():
        assert list(projects_dir.iterdir()) == []

    # Account manager never consulted
    assert manager.get_next_calls == 0


def test_resume_route_blocks_pending_v2_project(monkeypatch, tmp_path):
    """Pending V2 projects cannot be resumed through /api/projects/{id}/resume."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for resume gate regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Block resume"}],
        },
    )
    monkeypatch.setattr(
        projects,
        "resume_project_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resume should block before resume_project_run")),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
            "project_path": str(tmp_path / "pending-resume-project"),
        },
    )
    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    resume = client.post(f"/api/projects/{project_id}/resume")
    assert resume.status_code == 409
    assert "approved" in resume.json().get("detail", "").lower()


def test_execution_plane_command_launch_blocks_pending_v2_project(monkeypatch, tmp_path):
    """Pending V2 projects cannot launch through the execution-plane command route."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for command gate regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Keep command route blocked"}],
        },
    )
    monkeypatch.setattr(
        "autopilot.core.execution_plane.launch_project_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("execution-plane launch command should block before launch_project_run")
        ),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
            "project_path": str(tmp_path / "pending-command-launch-project"),
        },
    )
    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    command = client.post(f"/api/execution-plane/projects/{project_id}/commands/launch", json={})
    assert command.status_code == 409
    assert "approved" in command.json().get("detail", "").lower()


def test_execution_plane_command_resume_blocks_pending_v2_project(monkeypatch, tmp_path):
    """Pending V2 projects cannot resume through the execution-plane command route."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for resume command gate regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Keep resume command blocked"}],
        },
    )
    monkeypatch.setattr(
        "autopilot.core.execution_plane.resume_project_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("execution-plane resume command should block before resume_project_run")
        ),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
            "project_path": str(tmp_path / "pending-command-resume-project"),
        },
    )
    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    command = client.post(f"/api/execution-plane/projects/{project_id}/commands/resume", json={})
    assert command.status_code == 409
    assert "approved" in command.json().get("detail", "").lower()


def test_execution_plane_approval_apply_blocks_pending_v2_project(monkeypatch, tmp_path):
    """Applying a pre-created launch approval still cannot bypass founder approval."""
    from autopilot.core.approvals import decide_approval
    from autopilot.core.execution_plane import create_execution_command_approval

    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for approval-apply regression coverage.",
            "stories": [{"id": 1, "title": "Verify gate", "description": "Block approval apply"}],
        },
    )
    monkeypatch.setattr(
        "autopilot.core.execution_plane.launch_project_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("approval apply should block before launch_project_run")
        ),
    )

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": _v2_brief_payload(approval_status="pending"),
            "launch": False,
            "project_path": str(tmp_path / "pending-approval-apply-project"),
        },
    )
    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    approval = create_execution_command_approval(
        config,
        project_id=project_id,
        command="launch",
        payload={},
        requested_by="founderos",
        reason="Ensure apply path still respects founder gate.",
    )
    approval_id = approval["id"]
    decide_approval(config, approval_id, decision="approved", actor="founder")

    apply_response = client.post(
        f"/api/execution-plane/approvals/{approval_id}/apply",
        json={"actor": "founderos-control"},
    )
    assert apply_response.status_code == 409
    assert "approved" in apply_response.json().get("detail", "").lower()


def test_existing_pending_v2_project_becomes_launchable_after_sync(monkeypatch, tmp_path):
    """Syncing an approved V2 brief refreshes the existing project instead of requiring a new one."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=object())
    client = _build_client(config, manager, monkeypatch)
    monkeypatch.setattr(
        "autopilot.core.execution_plane.generate_prd_from_spec",
        lambda *args, **kwargs: {
            "title": "Gate test initiative",
            "description": "Created for approval sync coverage.",
            "stories": [{"id": 1, "title": "Verify sync", "description": "Allow launch after sync"}],
        },
    )
    monkeypatch.setattr(
        projects,
        "launch_project_run",
        lambda *args, **kwargs: (True, None, "Project launched."),
    )

    pending = _v2_brief_payload(approval_status="pending")
    pending["brief_id"] = "brief-sync-test"
    pending["initiative_id"] = "init-sync-test"

    create = client.post(
        "/api/projects/from-brief-v2",
        json={
            "brief": pending,
            "launch": False,
            "project_path": str(tmp_path / "pending-sync-project"),
        },
    )
    assert create.status_code == 200, create.text
    project_id = create.json()["project"]["project_id"]

    approved = dict(pending)
    approved["brief_approval_status"] = "approved"
    approved["approved_by"] = "founder"

    sync = client.post(
        "/api/projects/briefs/brief-sync-test/sync-v2",
        json={"brief": approved},
    )
    assert sync.status_code == 200, sync.text
    assert sync.json()["brief_approval_status"] == "approved"

    launch = client.post(f"/api/projects/{project_id}/launch", json={})
    assert launch.status_code == 200, launch.text
    assert launch.json()["launched"] is True


def test_legacy_shared_brief_route_blocks_launch(monkeypatch, tmp_path):
    """Legacy /from-shared-brief returns 409 when launch=True (containment fix)."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=None)
    client = _build_client(config, manager, monkeypatch)
    response = client.post(
        "/api/execution-plane/projects/from-shared-brief",
        json={
            "brief": {
                "brief_id": "test-shared-001",
                "idea_id": "idea-001",
                "title": "Test shared brief",
                "prd_summary": "A test shared brief",
                "acceptance_criteria": ["works"],
                "risks": [],
                "recommended_tech_stack": ["python"],
                "first_stories": [
                    {
                        "title": "Story 1",
                        "description": "Do something",
                        "acceptance_criteria": ["done"],
                        "effort": "small",
                    }
                ],
                "confidence": "medium",
                "effort": "medium",
                "urgency": "backlog",
                "budget_tier": "medium",
            },
            "launch": True,
        },
    )
    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
    assert "disabled" in response.json().get("detail", "").lower()


def test_legacy_shared_brief_route_allows_import_without_launch(monkeypatch, tmp_path):
    """Legacy /from-shared-brief allows import (launch=False) for backward compat."""
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    manager = _FakeManager(profile=None)
    client = _build_client(config, manager, monkeypatch)
    response = client.post(
        "/api/execution-plane/projects/from-shared-brief",
        json={
            "brief": {
                "brief_id": "test-shared-002",
                "idea_id": "idea-002",
                "title": "Test shared import",
                "prd_summary": "A test shared brief",
                "acceptance_criteria": ["works"],
                "risks": [],
                "recommended_tech_stack": ["python"],
                "first_stories": [
                    {
                        "title": "Story 1",
                        "description": "Do something",
                        "acceptance_criteria": ["done"],
                        "effort": "small",
                    }
                ],
                "confidence": "medium",
                "effort": "medium",
                "urgency": "backlog",
                "budget_tier": "medium",
            },
            "launch": False,
        },
    )
    assert response.status_code == 503
    assert "no available accounts" in response.json().get("detail", "").lower()
