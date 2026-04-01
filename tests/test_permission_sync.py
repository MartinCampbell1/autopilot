"""Tests for deterministic permission sync and approval race resolution."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from autopilot.core.approvals import list_approvals
from autopilot.core.config import AutopilotConfig
from autopilot.core.control_plane_issues import list_issues
from autopilot.core.execution_plane import create_execution_command_approval, create_execution_command_issue
from autopilot.core.permission_sync import clear_permission_sync_mailbox, get_permission_sync, resolve_permission_sync
from autopilot.core.project_store import ensure_project_state, register_project


def _create_project(config: AutopilotConfig, root: Path) -> dict[str, object]:
    root.mkdir(parents=True, exist_ok=True)
    prd_path = root / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Permission Sync Demo",
                "description": "Project for permission sync tests.",
                "stories": [
                    {
                        "id": 1,
                        "title": "Bootstrap",
                        "description": "Create the app shell",
                        "position": 0,
                        "status": "open",
                    }
                ],
            }
        )
    )
    project = register_project(
        config,
        name="Permission Sync Demo",
        project_path=root,
        prd_relpath=".agents/tasks/prd.json",
    )
    ensure_project_state(config, project, seed_mode="migrate")
    return project


def test_resolve_permission_sync_runs_resolver_once_for_duplicate_calls(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    calls = 0

    def resolver() -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"approval_id": "apr_sync"}

    first = resolve_permission_sync(config, sync_key="approval:proj:pause", request_id="req_1", resolver=resolver)
    second = resolve_permission_sync(
        config,
        sync_key="approval:proj:pause",
        request_id="req_2",
        resolver=lambda: {"approval_id": "apr_other"},
    )

    assert calls == 1
    assert first.id == second.id
    assert first.payload == {"approval_id": "apr_sync"}
    stored = get_permission_sync(config, "approval:proj:pause")
    assert stored is not None
    assert stored.request_ids == ["req_1", "req_2"]


def test_resolve_permission_sync_shares_resolution_across_concurrent_waiters(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    barrier = threading.Barrier(2)
    calls = 0
    calls_lock = threading.Lock()

    def resolver() -> dict[str, object]:
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.1)
        return {"approval_id": "apr_race"}

    def run(request_id: str):
        barrier.wait()
        return resolve_permission_sync(
            config,
            sync_key="approval:proj:resume",
            request_id=request_id,
            resolver=resolver,
            wait_timeout_sec=3.0,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, "req_a")
        second = pool.submit(run, "req_b")
        left = first.result()
        right = second.result()

    assert calls == 1
    assert left.id == right.id
    assert left.payload == {"approval_id": "apr_race"}
    stored = get_permission_sync(config, "approval:proj:resume")
    assert stored is not None
    assert stored.request_ids == ["req_a", "req_b"]


def test_execution_command_issue_sync_reuses_single_open_issue_for_concurrent_agents(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project")
    barrier = threading.Barrier(2)

    def run(agent_id: str) -> dict[str, object]:
        barrier.wait()
        return create_execution_command_issue(
            config,
            project_id=str(project["id"]),
            command="pause",
            requested_by="founderos",
            reason="Pause until operator review.",
            policy_reasons=["Parallel work needs explicit approval."],
            runtime_agent_ids=[agent_id],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, "agt_1")
        second = pool.submit(run, "agt_2")
        left = first.result()
        right = second.result()

    issues = list_issues(config, project_id=str(project["id"]), status="open")
    assert len(issues) == 1
    assert left["id"] == right["id"] == issues[0].id
    assert issues[0].runtime_agent_ids == ["agt_1", "agt_2"]


def test_execution_command_approval_sync_reuses_single_pending_approval_for_concurrent_agents(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project")
    issue = create_execution_command_issue(
        config,
        project_id=str(project["id"]),
        command="pause",
        requested_by="founderos",
        reason="Pause until operator review.",
        policy_reasons=["Parallel work needs explicit approval."],
        runtime_agent_ids=["agt_0"],
    )
    barrier = threading.Barrier(2)

    def run(agent_id: str) -> dict[str, object]:
        barrier.wait()
        return create_execution_command_approval(
            config,
            project_id=str(project["id"]),
            command="pause",
            payload={},
            requested_by="founderos",
            reason="Pause until operator review.",
            issue_id=str(issue["id"]),
            runtime_agent_ids=[agent_id],
            policy_reasons=["Parallel work needs explicit approval."],
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, "agt_1")
        second = pool.submit(run, "agt_2")
        left = first.result()
        right = second.result()

    approvals = list_approvals(config, project_id=str(project["id"]), action="pause", status="pending")
    assert len(approvals) == 1
    assert left["id"] == right["id"] == approvals[0].id
    assert approvals[0].runtime_agent_ids == ["agt_1", "agt_2"]
