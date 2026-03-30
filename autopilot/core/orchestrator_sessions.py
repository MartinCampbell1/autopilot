"""File-backed orchestrator sessions for external FounderOS control loops."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import emit_project_event

SUPPORTED_ORCHESTRATOR_SESSION_STATUSES = {
    "open",
    "completed",
    "archived",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class OrchestratorSessionRecord(BaseModel):
    """Stable session record for one external orchestration loop."""

    id: str
    orchestrator: str = ""
    actor: str = ""
    title: str = ""
    initiative_id: str = ""
    project_ids: list[str] = Field(default_factory=list)
    status: str = "open"
    reason: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    linked_run_ids: list[str] = Field(default_factory=list)
    linked_control_pass_ids: list[str] = Field(default_factory=list)
    linked_approval_ids: list[str] = Field(default_factory=list)
    linked_issue_ids: list[str] = Field(default_factory=list)
    linked_runtime_agent_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    closed_at: str | None = None
    closed_by: str = ""
    close_note: str = ""


def orchestrator_session_path(config: AutopilotConfig, session_id: str) -> Path:
    """Return the persisted path for one orchestrator session."""

    return config.control_plane_state_dir / "orchestrator_sessions" / f"{session_id}.json"


def get_orchestrator_session(
    config: AutopilotConfig,
    session_id: str,
) -> OrchestratorSessionRecord | None:
    """Load one orchestrator session if it exists."""

    path = orchestrator_session_path(config, session_id)
    if not path.exists():
        return None
    try:
        return OrchestratorSessionRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_orchestrator_session(
    config: AutopilotConfig,
    session: OrchestratorSessionRecord,
) -> OrchestratorSessionRecord:
    """Persist one orchestrator session record."""

    session.updated_at = _utcnow_iso()
    _atomic_write_json(orchestrator_session_path(config, session.id), session.model_dump())
    return session


def create_orchestrator_session(
    config: AutopilotConfig,
    *,
    orchestrator: str,
    actor: str,
    title: str = "",
    initiative_id: str = "",
    project_ids: list[str] | None = None,
    reason: str = "",
    context: dict[str, Any] | None = None,
) -> OrchestratorSessionRecord:
    """Create and persist one orchestrator session."""

    created_at = _utcnow_iso()
    session = OrchestratorSessionRecord(
        id=f"ors_{uuid.uuid4().hex[:10]}",
        orchestrator=orchestrator.strip(),
        actor=actor.strip(),
        title=title.strip(),
        initiative_id=initiative_id.strip(),
        project_ids=sorted({str(item) for item in (project_ids or []) if str(item).strip()}),
        status="open",
        reason=reason.strip(),
        context=dict(context or {}),
        created_at=created_at,
        updated_at=created_at,
    )
    save_orchestrator_session(config, session)
    for project_id in session.project_ids:
        emit_project_event(
            config,
            project_id,
            event="execution_plane_orchestrator_session_created",
            status="ok",
            message=f"Orchestrator session `{session.id}` created.",
            extra={
                "orchestrator_session_id": session.id,
                "orchestrator": session.orchestrator,
                "actor": session.actor,
            },
        )
    return session


def list_orchestrator_sessions(
    config: AutopilotConfig,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    status: str | None = None,
) -> list[OrchestratorSessionRecord]:
    """List persisted orchestrator sessions with lightweight filtering."""

    directory = config.control_plane_state_dir / "orchestrator_sessions"
    if not directory.exists():
        return []

    sessions: list[OrchestratorSessionRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            session = OrchestratorSessionRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if session_id and session.id != session_id:
            continue
        if project_id and project_id not in session.project_ids:
            continue
        if initiative_id and session.initiative_id != initiative_id:
            continue
        if orchestrator and session.orchestrator != orchestrator:
            continue
        if actor and session.actor != actor:
            continue
        if status and session.status != status:
            continue
        sessions.append(session)

    sessions.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return sessions


def update_orchestrator_session_status(
    config: AutopilotConfig,
    session_id: str,
    *,
    status: str,
    actor: str,
    note: str = "",
) -> OrchestratorSessionRecord:
    """Update the lifecycle status for one orchestrator session."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)
    if status not in SUPPORTED_ORCHESTRATOR_SESSION_STATUSES:
        raise ValueError(f"Unsupported orchestrator session status: {status}")

    session.status = status
    if status in {"completed", "archived"}:
        session.closed_at = _utcnow_iso()
        session.closed_by = actor
        session.close_note = note
    save_orchestrator_session(config, session)
    for project_id in session.project_ids:
        emit_project_event(
            config,
            project_id,
            event="execution_plane_orchestrator_session_updated",
            status=status,
            message=f"Orchestrator session `{session.id}` marked `{status}`.",
            extra={
                "orchestrator_session_id": session.id,
                "orchestrator": session.orchestrator,
                "actor": actor,
                "session_status": status,
            },
        )
    return session


def link_orchestrator_session_entities(
    config: AutopilotConfig,
    session_id: str,
    *,
    project_ids: list[str] | None = None,
    linked_run_ids: list[str] | None = None,
    linked_control_pass_ids: list[str] | None = None,
    linked_approval_ids: list[str] | None = None,
    linked_issue_ids: list[str] | None = None,
    linked_runtime_agent_ids: list[str] | None = None,
) -> OrchestratorSessionRecord:
    """Merge linked entities into one orchestrator session."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    session.project_ids = sorted({*session.project_ids, *(str(item) for item in (project_ids or []) if str(item).strip())})
    session.linked_run_ids = sorted({*session.linked_run_ids, *(str(item) for item in (linked_run_ids or []) if str(item).strip())})
    session.linked_control_pass_ids = sorted(
        {*session.linked_control_pass_ids, *(str(item) for item in (linked_control_pass_ids or []) if str(item).strip())}
    )
    session.linked_approval_ids = sorted(
        {*session.linked_approval_ids, *(str(item) for item in (linked_approval_ids or []) if str(item).strip())}
    )
    session.linked_issue_ids = sorted({*session.linked_issue_ids, *(str(item) for item in (linked_issue_ids or []) if str(item).strip())})
    session.linked_runtime_agent_ids = sorted(
        {*session.linked_runtime_agent_ids, *(str(item) for item in (linked_runtime_agent_ids or []) if str(item).strip())}
    )
    return save_orchestrator_session(config, session)
