"""File-backed batch run records for execution-plane runtime-agent actions."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class AgentActionBatchRunRecord(BaseModel):
    """Stable persisted report for one batch preview/execution run."""

    id: str
    run_kind: str = "batch"
    orchestrator_session_id: str = ""
    idempotency_key: str = ""
    request_fingerprint: str = ""
    actor: str
    mode: str
    reason: str = ""
    dry_run: bool = False
    policy_profile: str = ""
    policy: dict[str, Any] = Field(default_factory=dict)
    selection: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    results: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "ok"
    project_ids: list[str] = Field(default_factory=list)
    initiative_ids: list[str] = Field(default_factory=list)
    orchestrators: list[str] = Field(default_factory=list)
    runtime_agent_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    completed_at: str | None = None


def agent_action_batch_run_path(config: AutopilotConfig, run_id: str) -> Path:
    """Return the persisted path for one batch run record."""

    return config.control_plane_state_dir / "agent_action_runs" / f"{run_id}.json"


def get_agent_action_batch_run(config: AutopilotConfig, run_id: str) -> AgentActionBatchRunRecord | None:
    """Load one batch run record if it exists."""

    path = agent_action_batch_run_path(config, run_id)
    if not path.exists():
        return None
    try:
        return AgentActionBatchRunRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_agent_action_batch_run(
    config: AutopilotConfig,
    record: AgentActionBatchRunRecord,
) -> AgentActionBatchRunRecord:
    """Persist one batch run record."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(agent_action_batch_run_path(config, record.id), record.model_dump())
    return record


def create_agent_action_batch_run(
    config: AutopilotConfig,
    *,
    run_kind: str = "batch",
    orchestrator_session_id: str = "",
    idempotency_key: str = "",
    request_fingerprint: str = "",
    actor: str,
    mode: str,
    reason: str = "",
    dry_run: bool = False,
    policy_profile: str = "",
    policy: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
    results: list[dict[str, Any]] | None = None,
    status: str = "ok",
    project_ids: list[str] | None = None,
    initiative_ids: list[str] | None = None,
    orchestrators: list[str] | None = None,
    runtime_agent_ids: list[str] | None = None,
) -> AgentActionBatchRunRecord:
    """Create and persist one completed batch run record."""

    created_at = _utcnow_iso()
    record = AgentActionBatchRunRecord(
        id=f"aar_{uuid.uuid4().hex[:10]}",
        run_kind=run_kind,
        orchestrator_session_id=orchestrator_session_id.strip(),
        idempotency_key=idempotency_key.strip(),
        request_fingerprint=request_fingerprint,
        actor=actor,
        mode=mode,
        reason=reason,
        dry_run=dry_run,
        policy_profile=policy_profile,
        policy=dict(policy or {}),
        selection=dict(selection or {}),
        summary=dict(summary or {}),
        results=list(results or []),
        status=status,
        project_ids=sorted({str(item) for item in (project_ids or []) if str(item).strip()}),
        initiative_ids=sorted({str(item) for item in (initiative_ids or []) if str(item).strip()}),
        orchestrators=sorted({str(item) for item in (orchestrators or []) if str(item).strip()}),
        runtime_agent_ids=sorted({str(item) for item in (runtime_agent_ids or []) if str(item).strip()}),
        created_at=created_at,
        updated_at=created_at,
        completed_at=created_at,
    )
    return save_agent_action_batch_run(config, record)


def list_agent_action_batch_runs(
    config: AutopilotConfig,
    *,
    run_kind: str | None = None,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    dry_run: bool | None = None,
    status: str | None = None,
    idempotency_key: str | None = None,
) -> list[AgentActionBatchRunRecord]:
    """List persisted batch run records with lightweight filtering."""

    directory = config.control_plane_state_dir / "agent_action_runs"
    if not directory.exists():
        return []

    records: list[AgentActionBatchRunRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = AgentActionBatchRunRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if run_kind and record.run_kind != run_kind:
            continue
        if orchestrator_session_id and record.orchestrator_session_id != orchestrator_session_id:
            continue
        if project_id and project_id not in record.project_ids:
            continue
        if initiative_id and initiative_id not in record.initiative_ids:
            continue
        if orchestrator and orchestrator not in record.orchestrators:
            continue
        if actor and record.actor != actor:
            continue
        if dry_run is not None and record.dry_run is not dry_run:
            continue
        if status and record.status != status:
            continue
        if idempotency_key and record.idempotency_key != idempotency_key:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return records


def find_agent_action_batch_run_by_idempotency_key(
    config: AutopilotConfig,
    idempotency_key: str,
) -> AgentActionBatchRunRecord | None:
    """Return the latest batch run record for one idempotency key."""

    normalized = idempotency_key.strip()
    if not normalized:
        return None
    matches = list_agent_action_batch_runs(config, idempotency_key=normalized)
    return matches[0] if matches else None
