"""Tests for workspace/worktree policy inspection and recovery."""

from pathlib import Path
from unittest.mock import patch

import pytest

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import ensure_project_state, register_project, save_project_prd, save_project_state
from autopilot.core.runtime_control import RuntimeAgentRole, claim_work_item_lease
from autopilot.core.workspace_policy import inspect_project_workspace_policy, recover_story_checkout, sweep_stale_project_checkouts
from autopilot.core.project_store import normalize_prd, load_project_state


def _setup_project(config: AutopilotConfig, project_dir: Path) -> dict:
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Workspace Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Workspace Project",
            "stories": [
                {"id": 1, "title": "One", "description": "Start"},
                {"id": 2, "title": "Two", "description": "Continue"},
            ],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")
    return project


def test_inspect_project_workspace_policy_detects_missing_checkout_and_orphaned_worktree(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "workspace-project"
    project = _setup_project(config, project_dir)
    state = load_project_state(config, project["id"])
    state["story_state"]["1"]["status"] = "in_progress"
    state["story_state"]["1"]["ownership"] = {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"}
    state["story_state"]["1"]["checkout"] = {"mode": "worktree", "path": str(project_dir.parent / "workspace-project-story-1"), "branch_name": "story-1"}
    save_project_state(config, project["id"], state)
    claim_work_item_lease(
        config,
        project_id=project["id"],
        story_id=1,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=project_dir,
        checkout_path=project_dir.parent / "workspace-project-story-1",
        branch_name="story-1",
    )
    (project_dir.parent / "workspace-project-story-2").mkdir()

    inspection = inspect_project_workspace_policy(config, project["id"])

    story_one = next(item for item in inspection["stories"] if item["story_id"] == 1)
    assert story_one["health"]["status"] == "degraded"
    assert "does not exist" in story_one["health"]["issues"][0]
    assert inspection["orphaned_worktrees"][0]["story_id"] == 2


@patch("autopilot.core.workspace_policy.remove_worktree")
def test_recover_story_checkout_clears_metadata_and_can_reopen(mock_remove_worktree, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "workspace-project"
    project = _setup_project(config, project_dir)
    checkout_dir = project_dir.parent / "workspace-project-story-1"
    checkout_dir.mkdir()

    state = load_project_state(config, project["id"])
    state["story_state"]["1"].update(
        {
            "status": "merge_blocked",
            "ownership": {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"},
            "checkout": {"mode": "worktree", "path": str(checkout_dir), "branch_name": "story-1"},
            "worktree_path": str(checkout_dir),
            "branch_name": "story-1",
        }
    )
    save_project_state(config, project["id"], state)
    claim_work_item_lease(
        config,
        project_id=project["id"],
        story_id=1,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=project_dir,
        checkout_path=checkout_dir,
        branch_name="story-1",
    )

    result = recover_story_checkout(config, project["id"], 1, cleanup_worktree=True, reopen_story=True)
    repaired = load_project_state(config, project["id"])

    assert result["cleanup_performed"] is True
    assert result["reopened"] is True
    assert repaired["story_state"]["1"]["status"] == "open"
    assert repaired["story_state"]["1"]["ownership"] is None
    assert repaired["story_state"]["1"]["checkout"] is None
    mock_remove_worktree.assert_called_once()


def test_recover_story_checkout_rejects_active_run(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "workspace-project"
    project = _setup_project(config, project_dir)
    state = load_project_state(config, project["id"])
    state["pid"] = 1234
    save_project_state(config, project["id"], state)

    with patch("autopilot.core.project_store._is_pid_running", return_value=True):
        with pytest.raises(RuntimeError):
            recover_story_checkout(config, project["id"], 1)


def test_inspect_project_workspace_policy_marks_stale_lease(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "workspace-project"
    project = _setup_project(config, project_dir)

    state = load_project_state(config, project["id"])
    state["story_state"]["1"]["status"] = "in_progress"
    state["story_state"]["1"]["ownership"] = {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"}
    state["story_state"]["1"]["checkout"] = {"mode": "worktree", "path": str(project_dir.parent / "workspace-project-story-1"), "branch_name": "story-1"}
    save_project_state(config, project["id"], state)
    lease = claim_work_item_lease(
        config,
        project_id=project["id"],
        story_id=1,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        runtime_pid=99999,
        project_path=project_dir,
        checkout_path=project_dir.parent / "workspace-project-story-1",
        branch_name="story-1",
    )
    lease_path = config.control_plane_state_dir / "leases" / project["id"] / "story-1.json"
    lease_payload = lease_path.read_text().replace(lease.updated_at, "2020-01-01T00:00:00+00:00")
    lease_path.write_text(lease_payload)
    monkeypatch.setattr("autopilot.core.workspace_policy._pid_is_running", lambda pid: False)

    inspection = inspect_project_workspace_policy(config, project["id"], stale_after_sec=30)

    story_one = next(item for item in inspection["stories"] if item["story_id"] == 1)
    assert story_one["health"]["status"] == "stale"
    assert story_one["health"]["lease_status"] == "stale"


@patch("autopilot.core.workspace_policy.remove_worktree")
def test_sweep_stale_project_checkouts_recovers_all_stale(mock_remove_worktree, tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "workspace-project"
    project = _setup_project(config, project_dir)
    checkout_dir = project_dir.parent / "workspace-project-story-1"
    checkout_dir.mkdir()

    state = load_project_state(config, project["id"])
    state["story_state"]["1"].update(
        {
            "status": "in_progress",
            "ownership": {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"},
            "checkout": {"mode": "worktree", "path": str(checkout_dir), "branch_name": "story-1"},
            "worktree_path": str(checkout_dir),
            "branch_name": "story-1",
        }
    )
    save_project_state(config, project["id"], state)
    lease = claim_work_item_lease(
        config,
        project_id=project["id"],
        story_id=1,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        runtime_pid=99999,
        project_path=project_dir,
        checkout_path=checkout_dir,
        branch_name="story-1",
    )
    lease_path = config.control_plane_state_dir / "leases" / project["id"] / "story-1.json"
    lease_payload = lease_path.read_text().replace(lease.updated_at, "2020-01-01T00:00:00+00:00")
    lease_path.write_text(lease_payload)
    monkeypatch.setattr("autopilot.core.workspace_policy._pid_is_running", lambda pid: False)

    result = sweep_stale_project_checkouts(config, project["id"], stale_after_sec=30)
    repaired = load_project_state(config, project["id"])

    assert len(result["recovered"]) == 1
    assert repaired["story_state"]["1"]["status"] == "open"
    mock_remove_worktree.assert_called_once()
