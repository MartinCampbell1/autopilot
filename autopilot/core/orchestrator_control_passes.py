"""File-backed orchestration-pass records for session-level control plans."""

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


class OrchestratorControlPassRecord(BaseModel):
    """Stable persisted record for one session-level control pass."""

    id: str
    orchestrator_session_id: str
    actor: str
    reason: str = ""
    profile: str = "safe_progress"
    customized: bool = False
    recommendation_kinds: list[str] = Field(default_factory=list)
    control_before: dict[str, Any] = Field(default_factory=dict)
    control_after: dict[str, Any] = Field(default_factory=dict)
    applied: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    status: str = "ok"
    project_ids: list[str] = Field(default_factory=list)
    initiative_id: str = ""
    orchestrator: str = ""
    created_at: str
    updated_at: str
    completed_at: str | None = None


def orchestrator_control_pass_path(config: AutopilotConfig, pass_id: str) -> Path:
    """Return the persisted path for one control-pass record."""

    return config.control_plane_state_dir / "orchestrator_control_passes" / f"{pass_id}.json"


def get_orchestrator_control_pass(
    config: AutopilotConfig,
    pass_id: str,
) -> OrchestratorControlPassRecord | None:
    """Load one control-pass record if it exists."""

    path = orchestrator_control_pass_path(config, pass_id)
    if not path.exists():
        return None
    try:
        return OrchestratorControlPassRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_orchestrator_control_pass(
    config: AutopilotConfig,
    record: OrchestratorControlPassRecord,
) -> OrchestratorControlPassRecord:
    """Persist one control-pass record."""

    record.updated_at = _utcnow_iso()
    _atomic_write_json(orchestrator_control_pass_path(config, record.id), record.model_dump())
    return record


def create_orchestrator_control_pass(
    config: AutopilotConfig,
    *,
    orchestrator_session_id: str,
    actor: str,
    reason: str = "",
    profile: str = "safe_progress",
    customized: bool = False,
    recommendation_kinds: list[str] | None = None,
    control_before: dict[str, Any] | None = None,
    control_after: dict[str, Any] | None = None,
    applied: list[dict[str, Any]] | None = None,
    errors: list[dict[str, Any]] | None = None,
    summary: dict[str, Any] | None = None,
    status: str = "ok",
    project_ids: list[str] | None = None,
    initiative_id: str = "",
    orchestrator: str = "",
) -> OrchestratorControlPassRecord:
    """Create and persist one completed orchestration-pass record."""

    created_at = _utcnow_iso()
    record = OrchestratorControlPassRecord(
        id=f"ocp_{uuid.uuid4().hex[:10]}",
        orchestrator_session_id=orchestrator_session_id.strip(),
        actor=actor,
        reason=reason.strip(),
        profile=profile.strip() or "safe_progress",
        customized=customized,
        recommendation_kinds=sorted(
            {str(item) for item in (recommendation_kinds or []) if str(item).strip()}
        ),
        control_before=dict(control_before or {}),
        control_after=dict(control_after or {}),
        applied=list(applied or []),
        errors=list(errors or []),
        summary=dict(summary or {}),
        status=status,
        project_ids=sorted({str(item) for item in (project_ids or []) if str(item).strip()}),
        initiative_id=initiative_id.strip(),
        orchestrator=orchestrator.strip(),
        created_at=created_at,
        updated_at=created_at,
        completed_at=created_at,
    )
    return save_orchestrator_control_pass(config, record)


def list_orchestrator_control_passes(
    config: AutopilotConfig,
    *,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    profile: str | None = None,
    status: str | None = None,
) -> list[OrchestratorControlPassRecord]:
    """List persisted control-pass records with lightweight filtering."""

    directory = config.control_plane_state_dir / "orchestrator_control_passes"
    if not directory.exists():
        return []

    records: list[OrchestratorControlPassRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = OrchestratorControlPassRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if orchestrator_session_id and record.orchestrator_session_id != orchestrator_session_id:
            continue
        if project_id and project_id not in record.project_ids:
            continue
        if initiative_id and record.initiative_id != initiative_id:
            continue
        if orchestrator and record.orchestrator != orchestrator:
            continue
        if actor and record.actor != actor:
            continue
        if profile and record.profile != profile:
            continue
        if status and record.status != status:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return records
