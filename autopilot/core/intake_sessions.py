"""File-backed intake interview session storage."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json
from autopilot.core.config import AutopilotConfig
from autopilot.core.intake import IntakeSession

SAFE_INTAKE_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_atomic_write_json(path, payload)


class IntakeSessionRecord(BaseModel):
    session_id: str
    messages: list[dict[str, Any]] = Field(default_factory=list)
    prd: dict[str, Any] | None = None
    spec_bootstrap: dict[str, Any] | None = None
    project_name: str = ""
    linked_project_id: str = ""
    linked_project_name: str = ""
    created_at: str
    updated_at: str


def _validated_session_id(session_id: str) -> str:
    normalized = str(session_id or "").strip()
    if not normalized or not SAFE_INTAKE_SESSION_ID_RE.fullmatch(normalized):
        raise ValueError(f"Invalid intake session id: {session_id}")
    return normalized


def intake_session_path(config: AutopilotConfig, session_id: str) -> Path:
    return config.intake_sessions_dir / f"{_validated_session_id(session_id)}.json"


def _record_to_session(record: IntakeSessionRecord) -> IntakeSession:
    return IntakeSession(
        session_id=record.session_id,
        messages=[dict(message) for message in record.messages],
        prd=dict(record.prd) if isinstance(record.prd, dict) else record.prd,
        spec_bootstrap=(
            dict(record.spec_bootstrap) if isinstance(record.spec_bootstrap, dict) else record.spec_bootstrap
        ),
        project_name=record.project_name,
        linked_project_id=record.linked_project_id,
        linked_project_name=record.linked_project_name,
    )


def get_intake_session_record(
    config: AutopilotConfig,
    session_id: str,
) -> IntakeSessionRecord | None:
    try:
        path = intake_session_path(config, session_id)
    except ValueError:
        return None
    if not path.exists():
        return None
    try:
        return IntakeSessionRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def get_intake_session(
    config: AutopilotConfig,
    session_id: str,
) -> IntakeSession | None:
    record = get_intake_session_record(config, session_id)
    if record is None:
        return None
    return _record_to_session(record)


def save_intake_session(
    config: AutopilotConfig,
    session: IntakeSession,
) -> IntakeSession:
    now = _utcnow_iso()
    existing = get_intake_session_record(config, session.session_id)
    record = IntakeSessionRecord(
        session_id=session.session_id,
        messages=[dict(message) for message in session.messages],
        prd=dict(session.prd) if isinstance(session.prd, dict) else session.prd,
        spec_bootstrap=(
            dict(session.spec_bootstrap)
            if isinstance(session.spec_bootstrap, dict)
            else session.spec_bootstrap
        ),
        project_name=session.project_name,
        linked_project_id=session.linked_project_id,
        linked_project_name=session.linked_project_name,
        created_at=existing.created_at if existing is not None else now,
        updated_at=now,
    )
    _atomic_write_json(intake_session_path(config, session.session_id), record.model_dump())
    return session


def list_intake_session_records(config: AutopilotConfig) -> list[IntakeSessionRecord]:
    directory = config.intake_sessions_dir
    if not directory.exists():
        return []

    records: list[IntakeSessionRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = IntakeSessionRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        records.append(record)

    records.sort(key=lambda record: (record.updated_at, record.session_id), reverse=True)
    return records


def list_intake_sessions(config: AutopilotConfig) -> list[IntakeSession]:
    return [_record_to_session(record) for record in list_intake_session_records(config)]


def link_intake_session_project(
    config: AutopilotConfig,
    *,
    session_id: str,
    project_id: str,
    project_name: str,
) -> IntakeSession | None:
    record = get_intake_session_record(config, session_id)
    if record is None:
        return None

    linked_project_id = str(project_id or "").strip()
    linked_project_name = str(project_name or "").strip()
    if not linked_project_id:
        return _record_to_session(record)

    record.linked_project_id = linked_project_id
    record.linked_project_name = linked_project_name
    if not str(record.project_name or "").strip() and linked_project_name:
        record.project_name = linked_project_name
    record.updated_at = _utcnow_iso()
    _atomic_write_json(intake_session_path(config, record.session_id), record.model_dump())
    return _record_to_session(record)
