"""File-backed approval primitives for execution-plane control actions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import emit_project_event


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class ApprovalRecord(BaseModel):
    """Stable approval record for external control-plane commands."""

    id: str
    project_id: str
    project_name: str
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    requested_by: str = ""
    reason: str = ""
    initiative_id: str = ""
    orchestrator: str = ""
    orchestration_run_id: str = ""
    issue_id: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    policy_reasons: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_note: str = ""
    applied_at: str | None = None
    applied_by: str | None = None


def approval_path(config: AutopilotConfig, approval_id: str) -> Path:
    """Return the approval record path."""

    return config.control_plane_state_dir / "approvals" / f"{approval_id}.json"


def _build_project_context(project: dict[str, Any]) -> tuple[str, str, str]:
    control_plane = project.get("control_plane") or {}
    initiative = control_plane.get("initiative") or {}
    orchestration = control_plane.get("orchestration") or {}
    return (
        str(initiative.get("id") or ""),
        str(orchestration.get("orchestrator") or ""),
        str(orchestration.get("run_id") or ""),
    )


def get_approval(config: AutopilotConfig, approval_id: str) -> ApprovalRecord | None:
    """Load a single approval record if it exists."""

    path = approval_path(config, approval_id)
    if not path.exists():
        return None
    try:
        return ApprovalRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_approval(config: AutopilotConfig, approval: ApprovalRecord) -> ApprovalRecord:
    """Persist an approval record."""

    approval.updated_at = _utcnow_iso()
    _atomic_write_json(approval_path(config, approval.id), approval.model_dump())
    return approval


def create_approval(
    config: AutopilotConfig,
    *,
    project: dict[str, Any],
    action: str,
    payload: dict[str, Any] | None = None,
    requested_by: str = "",
    reason: str = "",
    issue_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    policy_reasons: list[str] | None = None,
) -> ApprovalRecord:
    """Create a pending approval request for a control-plane action."""

    created_at = _utcnow_iso()
    initiative_id, orchestrator, orchestration_run_id = _build_project_context(project)
    approval = ApprovalRecord(
        id=f"apr_{uuid.uuid4().hex[:10]}",
        project_id=str(project["id"]),
        project_name=str(project["name"]),
        action=action,
        payload=payload or {},
        status="pending",
        requested_by=requested_by,
        reason=reason,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        orchestration_run_id=orchestration_run_id,
        issue_id=issue_id,
        runtime_agent_ids=list(runtime_agent_ids or []),
        policy_reasons=list(policy_reasons or []),
        created_at=created_at,
        updated_at=created_at,
    )
    save_approval(config, approval)
    emit_project_event(
        config,
        approval.project_id,
        event="approval_requested",
        status="pending",
        message=f"Approval requested for `{action}`.",
        extra={
            "approval_id": approval.id,
            "approval_action": action,
            "requested_by": requested_by,
            "issue_id": issue_id,
            "runtime_agent_ids": approval.runtime_agent_ids,
        },
    )
    return approval


def list_approvals(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    action: str | None = None,
    issue_id: str | None = None,
    runtime_agent_id: str | None = None,
) -> list[ApprovalRecord]:
    """List approval records with lightweight filtering."""

    directory = config.control_plane_state_dir / "approvals"
    if not directory.exists():
        return []

    approvals: list[ApprovalRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            approval = ApprovalRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if project_id and approval.project_id != project_id:
            continue
        if initiative_id and approval.initiative_id != initiative_id:
            continue
        if orchestrator and approval.orchestrator != orchestrator:
            continue
        if status and approval.status != status:
            continue
        if action and approval.action != action:
            continue
        if issue_id and approval.issue_id != issue_id:
            continue
        if runtime_agent_id and runtime_agent_id not in approval.runtime_agent_ids:
            continue
        approvals.append(approval)

    approvals.sort(key=lambda item: (item.created_at, item.id))
    return approvals


def decide_approval(
    config: AutopilotConfig,
    approval_id: str,
    *,
    decision: str,
    actor: str,
    note: str = "",
) -> ApprovalRecord:
    """Approve or reject a pending approval record."""

    approval = get_approval(config, approval_id)
    if approval is None:
        raise KeyError(approval_id)
    if approval.status != "pending":
        raise RuntimeError(f"Approval {approval_id} is already {approval.status}.")
    if decision not in {"approved", "rejected"}:
        raise ValueError(f"Unsupported approval decision: {decision}")

    approval.status = decision
    approval.decided_at = _utcnow_iso()
    approval.decided_by = actor
    approval.decision_note = note
    save_approval(config, approval)
    emit_project_event(
        config,
        approval.project_id,
        event=f"approval_{decision}",
        status=decision,
        message=f"Approval `{approval.action}` {decision} by {actor}.",
        extra={
            "approval_id": approval.id,
            "approval_action": approval.action,
            "actor": actor,
            "runtime_agent_ids": approval.runtime_agent_ids,
        },
    )
    return approval


def mark_approval_applied(
    config: AutopilotConfig,
    approval_id: str,
    *,
    actor: str,
) -> ApprovalRecord:
    """Mark an approved approval as applied."""

    approval = get_approval(config, approval_id)
    if approval is None:
        raise KeyError(approval_id)
    if approval.status != "approved":
        raise RuntimeError(f"Approval {approval_id} must be approved before apply.")
    if approval.applied_at is not None:
        raise RuntimeError(f"Approval {approval_id} has already been applied.")

    approval.status = "applied"
    approval.applied_at = _utcnow_iso()
    approval.applied_by = actor
    save_approval(config, approval)
    emit_project_event(
        config,
        approval.project_id,
        event="approval_applied",
        status="ok",
        message=f"Approved action `{approval.action}` applied by {actor}.",
        extra={
            "approval_id": approval.id,
            "approval_action": approval.action,
            "actor": actor,
            "runtime_agent_ids": approval.runtime_agent_ids,
        },
    )
    return approval
