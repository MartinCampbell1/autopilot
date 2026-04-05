"""V2 downstream chain: outcome and proof routes must find V2 projects."""
from __future__ import annotations

from autopilot.core.brief_metadata import (
    find_project_by_execution_brief_id,
    get_execution_brief_project_metadata,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_projects_registry, save_projects_registry


def _seed_v2_project(config: AutopilotConfig, *, brief_id: str, initiative_id: str) -> str:
    project_path = config.autopilot_home / "projects" / f"v2-test-{brief_id}"
    project_path.mkdir(parents=True, exist_ok=True)
    (project_path / "prd.md").write_text("# Test PRD")

    project_id = f"v2-test-{brief_id}"
    entry = {
        "id": project_id,
        "name": f"V2 Test {brief_id}",
        "path": str(project_path),
        "status": "completed",
        "archived": False,
        "tracker_refs": [],
        "created_at": "2024-01-01T00:00:00+00:00",
        "last_opened_at": None,
        "task_source": {"source_kind": "manual"},
        "control_plane": {
            "execution_brief_v2": {
                "schema_version": "2.0",
                "brief_id": brief_id,
                "revision_id": "rev-001",
                "initiative_id": initiative_id,
                "brief_approval_status": "approved",
                "founder_approval_required": True,
            }
        },
    }
    existing = load_projects_registry(config, include_archived=True)
    existing.append(entry)
    save_projects_registry(config, existing)
    return project_id


def test_find_v2_project_by_brief_id(tmp_path):
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _seed_v2_project(config, brief_id="brief-v2-chain-001", initiative_id="init-001")
    project = find_project_by_execution_brief_id(config, "brief-v2-chain-001")
    assert project is not None
    assert project["id"] == "v2-test-brief-v2-chain-001"


def test_v2_project_metadata_returns_v2_kind(tmp_path):
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _seed_v2_project(config, brief_id="brief-v2-chain-002", initiative_id="init-002")
    project = find_project_by_execution_brief_id(config, "brief-v2-chain-002")
    metadata = get_execution_brief_project_metadata(project)
    assert metadata["kind"] == "v2"
    assert metadata["brief_id"] == "brief-v2-chain-002"
    assert metadata["initiative_id"] == "init-002"


def test_v2_project_not_found_with_wrong_brief_id(tmp_path):
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _seed_v2_project(config, brief_id="brief-v2-chain-003", initiative_id="init-003")
    project = find_project_by_execution_brief_id(config, "nonexistent-brief")
    assert project is None
