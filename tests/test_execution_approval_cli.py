"""Tests for explicit execution approval CLI helpers."""

from __future__ import annotations

import json

from autopilot.cli.execution_approval import (
    apply_approval,
    approve_approval,
    list_execution_approvals,
    reject_approval,
    show_approval,
)
from autopilot.core.approvals import ApprovalRecord
from autopilot.core.control_plane_issues import ExecutionIssueRecord


def _approval_record(*, status: str = "pending", decision_note: str = "", applied_at: str | None = None) -> ApprovalRecord:
    return ApprovalRecord(
        id="apr_123",
        project_id="proj_123",
        project_name="FounderOS",
        action="update_budget_policy",
        payload={"budget_policy": {"project_max_worker_iterations": 3}},
        status=status,
        requested_by="founderos",
        reason="Launch exceeded the safe parallelism limit.",
        initiative_id="init_123",
        orchestrator="founderos",
        orchestration_run_id="run_123",
        issue_id="iss_123",
        runtime_agent_ids=["agent_123"],
        policy_reasons=["parallel_launch_requires_approval"],
        created_at="2026-03-31T00:00:00Z",
        updated_at="2026-03-31T00:00:00Z",
        decided_at="2026-03-31T00:05:00Z" if status in {"approved", "rejected", "applied"} else None,
        decided_by="operator" if status in {"approved", "rejected", "applied"} else None,
        decision_note=decision_note,
        applied_at=applied_at,
        applied_by="operator" if applied_at else None,
    )


def _issue_record(*, status: str = "open") -> ExecutionIssueRecord:
    return ExecutionIssueRecord(
        id="iss_123",
        project_id="proj_123",
        project_name="FounderOS",
        title="Approval required for budget change",
        description="Budget policy update must be approved first.",
        root_cause="Policy gate",
        category="policy_approval",
        severity="medium",
        status=status,
        source_event="approval_requested",
        related_command="update_budget_policy",
        story_id=1,
        runtime_agent_id="agent_123",
        runtime_agent_ids=["agent_123"],
        approval_id="apr_123",
        dedupe_key="policy_approval:proj_123:update_budget_policy",
        initiative_id="init_123",
        orchestrator="founderos",
        orchestration_run_id="run_123",
        context={},
        created_at="2026-03-31T00:00:00Z",
        updated_at="2026-03-31T00:00:00Z",
        resolved_at=None,
        resolved_by=None,
        resolution_note="",
    )


def test_list_execution_approvals_uses_pending_default(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("autopilot.cli.execution_approval._config", lambda: object())

    def fake_list_approvals(config, **kwargs):
        captured["config"] = config
        captured["kwargs"] = kwargs
        return [_approval_record()]

    monkeypatch.setattr("autopilot.cli.execution_approval.list_approvals", fake_list_approvals)

    list_execution_approvals(json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["approvals"][0]["id"] == "apr_123"
    assert captured["kwargs"] == {
        "project_id": None,
        "initiative_id": None,
        "orchestrator": None,
        "status": "pending",
        "action": None,
        "issue_id": None,
        "runtime_agent_id": None,
    }


def test_show_approval_renders_issue_and_next_step(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.execution_approval._config", lambda: object())
    monkeypatch.setattr("autopilot.cli.execution_approval.get_approval", lambda config, approval_id: _approval_record())
    monkeypatch.setattr("autopilot.cli.execution_approval.get_issue", lambda config, issue_id: _issue_record())

    show_approval("apr_123")

    output = capsys.readouterr().out
    assert "Approval apr_123" in output
    assert "parallel_launch_requires_approval" in output
    assert "Linked Issue" in output
    assert "autopilot approve-approval apr_123" in output


def test_approve_approval_uses_actor_and_note(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}
    sentinel_config = object()

    monkeypatch.setattr("autopilot.cli.execution_approval._config", lambda: sentinel_config)

    def fake_decide_approval(config, approval_id: str, *, decision: str, actor: str, note: str):
        captured.update(
            {
                "config": config,
                "approval_id": approval_id,
                "decision": decision,
                "actor": actor,
                "note": note,
            }
        )
        return _approval_record(status="approved", decision_note=note)

    monkeypatch.setattr("autopilot.cli.execution_approval.decide_approval", fake_decide_approval)
    monkeypatch.setattr("autopilot.cli.execution_approval.get_issue", lambda config, issue_id: _issue_record())

    approve_approval("apr_123", actor="founderos", note="LGTM", json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["approval"]["status"] == "approved"
    assert payload["approval"]["decision_note"] == "LGTM"
    assert captured == {
        "config": sentinel_config,
        "approval_id": "apr_123",
        "decision": "approved",
        "actor": "founderos",
        "note": "LGTM",
    }


def test_reject_approval_uses_actor_and_note(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}
    sentinel_config = object()

    monkeypatch.setattr("autopilot.cli.execution_approval._config", lambda: sentinel_config)

    def fake_decide_approval(config, approval_id: str, *, decision: str, actor: str, note: str):
        captured.update(
            {
                "config": config,
                "approval_id": approval_id,
                "decision": decision,
                "actor": actor,
                "note": note,
            }
        )
        return _approval_record(status="rejected", decision_note=note)

    monkeypatch.setattr("autopilot.cli.execution_approval.decide_approval", fake_decide_approval)
    monkeypatch.setattr("autopilot.cli.execution_approval.get_issue", lambda config, issue_id: _issue_record())

    reject_approval("apr_123", actor="founderos", note="Not safe", json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["approval"]["status"] == "rejected"
    assert captured == {
        "config": sentinel_config,
        "approval_id": "apr_123",
        "decision": "rejected",
        "actor": "founderos",
        "note": "Not safe",
    }


def test_apply_approval_renders_command_result_and_issue(monkeypatch, capsys) -> None:
    sentinel_config = object()
    captured: dict[str, object] = {}

    monkeypatch.setattr("autopilot.cli.execution_approval._config", lambda: sentinel_config)

    def fake_apply_execution_command_approval(config, *, approval_id: str, actor: str):
        captured.update({"config": config, "approval_id": approval_id, "actor": actor})
        return {
            "status": "ok",
            "approval": _approval_record(status="applied", applied_at="2026-03-31T00:10:00Z").model_dump(),
            "command_result": {
                "status": "ok",
                "message": "Budget policy updated.",
                "project": {"id": "proj_123", "name": "FounderOS"},
            },
        }

    monkeypatch.setattr(
        "autopilot.cli.execution_approval.apply_execution_command_approval",
        fake_apply_execution_command_approval,
    )
    monkeypatch.setattr(
        "autopilot.cli.execution_approval.get_issue",
        lambda config, issue_id: _issue_record(status="resolved"),
    )

    apply_approval("apr_123", actor="founderos")

    output = capsys.readouterr().out
    assert "Applied apr_123" in output
    assert "Command Result" in output
    assert "Budget policy updated." in output
    assert captured == {
        "config": sentinel_config,
        "approval_id": "apr_123",
        "actor": "founderos",
    }
