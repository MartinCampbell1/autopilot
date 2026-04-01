"""Tests for deterministic permission sync and approval race resolution."""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import autopilot.core.permission_sync as permission_sync_module
from autopilot.core.approvals import decide_approval, list_approvals, mark_approval_applied
from autopilot.core.config import AutopilotConfig
from autopilot.core.control_plane_issues import list_issues, resolve_issue
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


def test_resolve_permission_sync_records_claim_and_resolution_ids(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    record = resolve_permission_sync(
        config,
        sync_key="approval:proj:tokens",
        request_id="req_tokens",
        resolver=lambda: {"approval_id": "apr_tokens"},
    )

    stored = get_permission_sync(config, "approval:proj:tokens")

    assert stored is not None
    assert record.claim_id.startswith("psclaim_")
    assert record.resolution_id.startswith("psyncres_")
    assert stored.claim_id == record.claim_id
    assert stored.resolution_id == record.resolution_id


def test_resolve_permission_sync_can_retry_failed_record_with_new_request_id(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    try:
        resolve_permission_sync(
            config,
            sync_key="approval:proj:retry_failed",
            request_id="req_fail_1",
            allow_failed_retries=True,
            resolver=lambda: (_ for _ in ()).throw(RuntimeError("transient failure")),
        )
    except RuntimeError as exc:
        assert "transient failure" in str(exc)
    else:
        raise AssertionError("Expected initial permission sync failure.")

    recovered = resolve_permission_sync(
        config,
        sync_key="approval:proj:retry_failed",
        request_id="req_fail_2",
        allow_failed_retries=True,
        resolver=lambda: {"approval_id": "apr_recovered"},
    )

    stored = get_permission_sync(config, "approval:proj:retry_failed")

    assert recovered.payload == {"approval_id": "apr_recovered"}
    assert stored is not None
    assert stored.status == "resolved"
    assert stored.request_ids == ["req_fail_2"]


def test_resolve_permission_sync_waiter_can_settle_from_mailbox_without_disk_lookup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    resolver_started = threading.Event()
    original_get = permission_sync_module.get_permission_sync

    def flaky_get_permission_sync(config_obj: AutopilotConfig, sync_key: str):
        if resolver_started.is_set():
            return None
        return original_get(config_obj, sync_key)

    monkeypatch.setattr(permission_sync_module, "get_permission_sync", flaky_get_permission_sync)

    def owner_resolver() -> dict[str, object]:
        resolver_started.set()
        time.sleep(0.08)
        return {"approval_id": "apr_mailbox"}

    with ThreadPoolExecutor(max_workers=2) as pool:
        owner = pool.submit(
            resolve_permission_sync,
            config,
            sync_key="approval:proj:mailbox",
            request_id="req_owner",
            resolver=owner_resolver,
            wait_timeout_sec=1.0,
        )
        resolver_started.wait(timeout=0.5)
        waiter = pool.submit(
            resolve_permission_sync,
            config,
            sync_key="approval:proj:mailbox",
            request_id="req_waiter",
            resolver=lambda: {"approval_id": "apr_other"},
            wait_timeout_sec=1.0,
        )
        owner_record = owner.result()
        waiter_record = waiter.result()

    assert owner_record.id == waiter_record.id
    assert waiter_record.payload == {"approval_id": "apr_mailbox"}


def test_resolve_permission_sync_does_not_allow_stale_claim_to_overwrite_newer_resolution(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    slow_started = threading.Event()
    results: dict[str, object] = {}

    def slow_resolver() -> dict[str, object]:
        slow_started.set()
        time.sleep(0.2)
        return {"approval_id": "apr_stale_old"}

    def run_slow() -> None:
        results["slow"] = resolve_permission_sync(
            config,
            sync_key="approval:proj:stale",
            request_id="req_old",
            resolver=slow_resolver,
            wait_timeout_sec=1.0,
            stale_after_sec=0.05,
        )

    def run_fast() -> None:
        slow_started.wait(timeout=0.5)
        time.sleep(0.08)
        results["fast"] = resolve_permission_sync(
            config,
            sync_key="approval:proj:stale",
            request_id="req_new",
            resolver=lambda: {"approval_id": "apr_new"},
            wait_timeout_sec=1.0,
            stale_after_sec=0.05,
        )

    slow_thread = threading.Thread(target=run_slow)
    fast_thread = threading.Thread(target=run_fast)
    slow_thread.start()
    fast_thread.start()
    slow_thread.join(timeout=2.0)
    fast_thread.join(timeout=2.0)

    slow_record = results["slow"]
    fast_record = results["fast"]
    stored = get_permission_sync(config, "approval:proj:stale")

    assert stored is not None
    assert slow_record.payload == {"approval_id": "apr_new"}
    assert fast_record.payload == {"approval_id": "apr_new"}
    assert stored.payload == {"approval_id": "apr_new"}
    assert stored.claim_id == fast_record.claim_id


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


def test_execution_command_issue_sync_creates_fresh_issue_after_resolution(tmp_path: Path) -> None:
    clear_permission_sync_mailbox()
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project")

    first = create_execution_command_issue(
        config,
        project_id=str(project["id"]),
        command="pause",
        requested_by="founderos",
        reason="Pause until operator review.",
        policy_reasons=["Parallel work needs explicit approval."],
        runtime_agent_ids=["agt_1"],
    )
    resolve_issue(config, first["id"], actor="founderos", note="Closed for replay test.")

    second = create_execution_command_issue(
        config,
        project_id=str(project["id"]),
        command="pause",
        requested_by="founderos",
        reason="Pause until operator review again.",
        policy_reasons=["Parallel work needs explicit approval."],
        runtime_agent_ids=["agt_2"],
    )

    open_issues = list_issues(config, project_id=str(project["id"]), status="open")
    all_issues = list_issues(config, project_id=str(project["id"]))

    assert second["id"] != first["id"]
    assert len(open_issues) == 1
    assert open_issues[0].id == second["id"]
    assert len(all_issues) == 2


def test_execution_command_issue_sync_publishes_resolution_settlement(tmp_path: Path) -> None:
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
        runtime_agent_ids=["agt_1"],
    )
    sync_key = str(issue["permission_sync_key"])
    created_record = get_permission_sync(config, sync_key)
    resolve_issue(config, issue["id"], actor="founderos", note="Closed for settlement test.")
    resolved_record = get_permission_sync(config, sync_key)

    assert created_record is not None
    assert created_record.metadata["settlement"]["stage"] == "issue_open"
    assert resolved_record is not None
    assert resolved_record.metadata["settlement"]["stage"] == "issue_resolved"
    assert resolved_record.metadata["settlement"]["actor"] == "founderos"


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


def test_execution_command_approval_sync_creates_fresh_pending_approval_after_decision(tmp_path: Path) -> None:
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
    first = create_execution_command_approval(
        config,
        project_id=str(project["id"]),
        command="pause",
        payload={},
        requested_by="founderos",
        reason="Pause until operator review.",
        issue_id=str(issue["id"]),
        runtime_agent_ids=["agt_1"],
        policy_reasons=["Parallel work needs explicit approval."],
    )
    decide_approval(config, first["id"], decision="approved", actor="founderos", note="Approved once.")

    second = create_execution_command_approval(
        config,
        project_id=str(project["id"]),
        command="pause",
        payload={},
        requested_by="founderos",
        reason="Pause until operator review again.",
        issue_id=str(issue["id"]),
        runtime_agent_ids=["agt_2"],
        policy_reasons=["Parallel work needs explicit approval."],
    )

    pending = list_approvals(config, project_id=str(project["id"]), action="pause", status="pending")
    all_approvals = list_approvals(config, project_id=str(project["id"]), action="pause")

    assert second["id"] != first["id"]
    assert len(pending) == 1
    assert pending[0].id == second["id"]
    assert len(all_approvals) == 2


def test_execution_command_approval_sync_publishes_decision_and_apply_settlement(tmp_path: Path) -> None:
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
    approval = create_execution_command_approval(
        config,
        project_id=str(project["id"]),
        command="pause",
        payload={},
        requested_by="founderos",
        reason="Pause until operator review.",
        issue_id=str(issue["id"]),
        runtime_agent_ids=["agt_1"],
        policy_reasons=["Parallel work needs explicit approval."],
    )
    sync_key = str(approval["permission_sync_key"])

    pending_record = get_permission_sync(config, sync_key)
    decided = decide_approval(config, approval["id"], decision="approved", actor="founderos", note="Approved.")
    decided_record = get_permission_sync(config, sync_key)
    applied = mark_approval_applied(config, decided.id, actor="founderos")
    applied_record = get_permission_sync(config, sync_key)

    assert pending_record is not None
    assert pending_record.metadata["settlement"]["stage"] == "pending"
    assert decided_record is not None
    assert decided_record.metadata["settlement"]["stage"] == "approved"
    assert decided_record.metadata["settlement"]["note"] == "Approved."
    assert applied.status == "applied"
    assert applied_record is not None
    assert applied_record.metadata["settlement"]["stage"] == "applied"
