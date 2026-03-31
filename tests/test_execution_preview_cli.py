"""Tests for explicit execution preview/apply CLI helpers."""

from __future__ import annotations

import json

from autopilot.cli.execution_preview import apply_preview, preview_actions
from autopilot.core.agent_action_runs import AgentActionBatchRunRecord


def test_preview_actions_uses_safe_defaults(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("autopilot.cli.execution_preview._config", lambda: object())

    def fake_preview(config, session_id: str, **kwargs):
        captured["config"] = config
        captured["session_id"] = session_id
        captured["kwargs"] = kwargs
        return {
            "status": "ok",
            "preview_id": "aar_preview_1",
            "apply_mode": "manual",
            "approval_required": False,
            "artifact_ref": "/api/execution-plane/agents/action-runs/aar_preview_1",
            "run": {"id": "aar_preview_1", "summary": {"selected_count": 1, "processed_count": 1}},
            "diff_summary": {"selected_count": 1, "processed_count": 1, "command_counts": {"update_budget_policy": 1}},
        }

    monkeypatch.setattr(
        "autopilot.cli.execution_preview.execute_execution_plane_orchestrator_session_actions",
        fake_preview,
    )

    preview_actions("sess_123", json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "sess_123"
    assert payload["preview_id"] == "aar_preview_1"
    assert captured["session_id"] == "sess_123"
    assert captured["kwargs"] == {
        "actor": "cli-control-plane",
        "mode": "auto",
        "reason": "",
        "policy_profile": "safe_budget_maintenance",
        "dry_run": True,
        "actionable_only": True,
        "command_requires_approval": False,
        "limit": 20,
    }


def test_apply_preview_reuses_preview_contract(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr("autopilot.cli.execution_preview._config", lambda: object())
    preview_record = AgentActionBatchRunRecord(
        id="aar_preview_1",
        run_kind="batch",
        orchestrator_session_id="sess_123",
        idempotency_key="",
        request_fingerprint="",
        actor="founderos",
        mode="auto",
        reason="Preview before apply",
        dry_run=True,
        policy_profile="safe_budget_maintenance",
        policy={},
        selection={
            "selected_action_keys": ["agent-a:command:update_budget_policy"],
            "limit": 1,
            "include_non_executable": False,
        },
        summary={"selected_count": 1, "processed_count": 1},
        diff_summary={},
        patch_bundle={},
        preview_id="aar_preview_1",
        artifact_ref="/api/execution-plane/agents/action-runs/aar_preview_1",
        approval_required=False,
        apply_mode="manual",
        results=[],
        status="ok",
        project_ids=["proj_123"],
        initiative_ids=[],
        orchestrators=["founderos"],
        runtime_agent_ids=["agent-a"],
        created_at="2026-03-31T00:00:00Z",
        updated_at="2026-03-31T00:00:00Z",
        completed_at="2026-03-31T00:00:00Z",
    )

    monkeypatch.setattr(
        "autopilot.cli.execution_preview.get_agent_action_batch_run",
        lambda config, preview_id: preview_record if preview_id == "aar_preview_1" else None,
    )

    def fake_apply(config, session_id: str, **kwargs):
        captured["config"] = config
        captured["session_id"] = session_id
        captured["kwargs"] = kwargs
        return {
            "status": "ok",
            "preview_id": "aar_preview_1",
            "apply_mode": "auto",
            "approval_required": False,
            "artifact_ref": "/api/execution-plane/agents/action-runs/aar_apply_1",
            "run": {"id": "aar_apply_1", "summary": {"selected_count": 1, "processed_count": 1}},
            "diff_summary": {"selected_count": 1, "processed_count": 1, "command_counts": {"update_budget_policy": 1}},
        }

    monkeypatch.setattr(
        "autopilot.cli.execution_preview.execute_execution_plane_orchestrator_session_actions",
        fake_apply,
    )

    apply_preview("aar_preview_1", json_output=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["session_id"] == "sess_123"
    assert payload["run"]["id"] == "aar_apply_1"
    assert captured["session_id"] == "sess_123"
    assert captured["kwargs"] == {
        "action_keys": ["agent-a:command:update_budget_policy"],
        "preview_id": "aar_preview_1",
        "actor": "cli-control-plane",
        "mode": "auto",
        "reason": "CLI applied preview aar_preview_1",
        "policy_profile": "safe_budget_maintenance",
        "limit": 1,
        "include_non_executable": False,
        "continue_on_error": True,
        "dry_run": False,
    }


def test_preview_actions_renders_gate_reasons_and_why(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.execution_preview._config", lambda: object())

    monkeypatch.setattr(
        "autopilot.cli.execution_preview.execute_execution_plane_orchestrator_session_actions",
        lambda config, session_id, **kwargs: {
            "status": "ok",
            "preview_id": "aar_preview_2",
            "apply_mode": "policy",
            "approval_required": True,
            "artifact_ref": "/api/execution-plane/agents/action-runs/aar_preview_2",
            "run": {"id": "aar_preview_2", "summary": {"selected_count": 2, "processed_count": 2}},
            "results": [],
            "diff_summary": {
                "selected_count": 2,
                "processed_count": 2,
                "command_counts": {"update_budget_policy": 2},
                "policy_reason_counts": {"parallel_launch_requires_approval": 2},
                "why": ["Parallel launch exceeded the safe limit."],
            },
        },
    )

    preview_actions("sess_approval")

    output = capsys.readouterr().out
    assert "Session Preview sess_approval" in output
    assert "parallel_launch_requires_approval" in output
    assert "Parallel launch exceeded the safe limit." in output
    assert "This preview is approval-gated." in output


def test_apply_preview_renders_created_approvals_and_issues(monkeypatch, capsys) -> None:
    monkeypatch.setattr("autopilot.cli.execution_preview._config", lambda: object())
    preview_record = AgentActionBatchRunRecord(
        id="aar_preview_gate",
        run_kind="batch",
        orchestrator_session_id="sess_gate",
        idempotency_key="",
        request_fingerprint="",
        actor="founderos",
        mode="auto",
        reason="Preview before approval apply",
        dry_run=True,
        policy_profile="balanced_safe",
        policy={},
        selection={
            "selected_action_keys": ["agent-a:command:update_budget_policy"],
            "limit": 1,
            "include_non_executable": False,
        },
        summary={"selected_count": 1, "processed_count": 1},
        diff_summary={},
        patch_bundle={},
        preview_id="aar_preview_gate",
        artifact_ref="/api/execution-plane/agents/action-runs/aar_preview_gate",
        approval_required=True,
        apply_mode="policy",
        results=[],
        status="ok",
        project_ids=["proj_123"],
        initiative_ids=[],
        orchestrators=["founderos"],
        runtime_agent_ids=["agent-a"],
        created_at="2026-03-31T00:00:00Z",
        updated_at="2026-03-31T00:00:00Z",
        completed_at="2026-03-31T00:00:00Z",
    )

    monkeypatch.setattr(
        "autopilot.cli.execution_preview.get_agent_action_batch_run",
        lambda config, preview_id: preview_record if preview_id == "aar_preview_gate" else None,
    )
    monkeypatch.setattr(
        "autopilot.cli.execution_preview.execute_execution_plane_orchestrator_session_actions",
        lambda config, session_id, **kwargs: {
            "status": "partial",
            "preview_id": "aar_preview_gate",
            "apply_mode": "policy",
            "approval_required": True,
            "artifact_ref": "/api/execution-plane/agents/action-runs/aar_apply_gate",
            "run": {"id": "aar_apply_gate", "summary": {"selected_count": 1, "processed_count": 1}},
            "results": [
                {
                    "status": "pending_approval",
                    "approval": {
                        "id": "apr_123",
                        "status": "pending",
                        "action": "update_budget_policy",
                        "issue_id": "iss_123",
                    },
                    "issue": {
                        "id": "iss_123",
                        "status": "open",
                        "category": "policy_approval",
                        "approval_id": "apr_123",
                    },
                }
            ],
            "diff_summary": {
                "selected_count": 1,
                "processed_count": 1,
                "command_counts": {"update_budget_policy": 1},
            },
        },
    )

    apply_preview("aar_preview_gate")

    output = capsys.readouterr().out
    assert "Applied Preview aar_preview_gate" in output
    assert "apr_123" in output
    assert "iss_123" in output
    assert "Approvals were created from this preview path." in output
