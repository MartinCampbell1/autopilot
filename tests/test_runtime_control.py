"""Tests for runtime ownership and atomic checkout leases."""

from pathlib import Path

import pytest

from autopilot.core.config import AutopilotConfig
from autopilot.core.runtime_control import (
    RuntimeAgentRole,
    WorkItemLeaseConflict,
    build_runtime_control_channel_status,
    claim_work_item_lease,
    list_project_work_item_leases,
    load_work_item_lease,
    refresh_work_item_lease,
    release_work_item_lease,
)
from autopilot.core.worktree import worktree_collaboration_dir, worktree_collaboration_manifest_path


def test_claim_and_release_work_item_lease(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    lease = claim_work_item_lease(
        config,
        project_id="demo-project",
        story_id=7,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=tmp_path / "project",
        checkout_path=tmp_path / "project-story-7",
        branch_name="story-7",
    )

    assert lease.owner == "run:123"
    assert lease.collaboration_root == str(worktree_collaboration_dir(tmp_path / "project-story-7"))
    assert lease.collaboration_manifest_path == str(worktree_collaboration_manifest_path(tmp_path / "project-story-7"))
    assert load_work_item_lease(config, "demo-project", 7) is not None
    assert release_work_item_lease(config, project_id="demo-project", story_id=7, owner="run:123") is True
    assert load_work_item_lease(config, "demo-project", 7) is None


def test_claim_work_item_lease_conflict_returns_existing_owner(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    claim_work_item_lease(
        config,
        project_id="demo-project",
        story_id=7,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=tmp_path / "project",
    )

    with pytest.raises(WorkItemLeaseConflict) as exc_info:
        claim_work_item_lease(
            config,
            project_id="demo-project",
            story_id=7,
            role=RuntimeAgentRole.COORDINATOR,
            owner="run:456",
            project_path=tmp_path / "project",
        )

    assert exc_info.value.lease.owner == "run:123"


def test_list_project_work_item_leases(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    claim_work_item_lease(
        config,
        project_id="demo-project",
        story_id=1,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=tmp_path / "project",
    )
    claim_work_item_lease(
        config,
        project_id="demo-project",
        story_id=2,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        project_path=tmp_path / "project",
    )

    leases = list_project_work_item_leases(config, "demo-project")

    assert [lease.story_id for lease in leases] == [1, 2]


def test_refresh_work_item_lease_updates_metadata(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    claim_work_item_lease(
        config,
        project_id="demo-project",
        story_id=7,
        role=RuntimeAgentRole.COORDINATOR,
        owner="run:123",
        runtime_pid=123,
        project_path=tmp_path / "project",
        checkout_path=tmp_path / "project-story-7",
        branch_name="story-7",
    )

    refreshed = refresh_work_item_lease(
        config,
        project_id="demo-project",
        story_id=7,
        owner="run:123",
        status="merge_blocked",
        branch_name="story-7b",
    )

    assert refreshed is not None
    assert refreshed.status == "merge_blocked"
    assert refreshed.branch_name == "story-7b"


def test_build_runtime_control_channel_status_stays_wall_enforced() -> None:
    payload = build_runtime_control_channel_status(
        project_id="demo-project",
        runtime_session_id="sess_demo",
        runtime_control_available=True,
    )

    assert payload["id"] == "runtime_control"
    assert payload["status"] == "live"
    assert payload["approval_capable"] is True
    assert payload["wall_enforced"] is True
