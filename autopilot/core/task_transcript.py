"""Durable transcript sidecars for async tasks."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.artifact_store import get_artifact, persist_artifact
from autopilot.core.config import AutopilotConfig

TASK_TRANSCRIPT_PREVIEW_CHARS = 4000


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def task_transcript_id(owner_kind: str, owner_id: str) -> str:
    digest = hashlib.sha1(f"{owner_kind}:{owner_id}".encode("utf-8")).hexdigest()[:12]
    return f"ttr_{digest}"


class TaskTranscriptRecord(BaseModel):
    """Persisted transcript artifact metadata."""

    id: str
    owner_kind: str
    owner_id: str
    content_path: str
    preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


def task_transcript_metadata_path(config: AutopilotConfig, transcript_id: str) -> Path:
    """Return metadata path for one transcript artifact."""

    return config.task_transcripts_dir / f"{transcript_id}.json"


def task_transcript_content_path(config: AutopilotConfig, transcript_id: str) -> Path:
    """Return content path for one transcript artifact."""

    artifact = get_artifact(config, transcript_id)
    if artifact is not None and str(artifact.content_path or "").strip():
        return Path(str(artifact.content_path))
    return config.task_transcripts_dir / f"{transcript_id}.md"


def get_task_transcript(config: AutopilotConfig, transcript_id: str) -> TaskTranscriptRecord | None:
    """Load transcript metadata if available."""

    path = task_transcript_metadata_path(config, transcript_id)
    if not path.exists():
        return None
    try:
        return TaskTranscriptRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def read_task_transcript_text(config: AutopilotConfig, transcript_id: str) -> str:
    """Read transcript content if available."""

    record = get_task_transcript(config, transcript_id)
    if record is None:
        raise KeyError(transcript_id)
    path = Path(record.content_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def persist_task_transcript(
    config: AutopilotConfig,
    *,
    owner_kind: str,
    owner_id: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> TaskTranscriptRecord:
    """Persist one deterministic transcript artifact for an async task owner."""

    normalized_owner_kind = str(owner_kind or "").strip() or "task"
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        raise ValueError("owner_id is required")

    transcript_id = task_transcript_id(normalized_owner_kind, normalized_owner_id)
    stored_content = str(content or "")
    artifact = persist_artifact(
        config,
        artifact_id=transcript_id,
        content=stored_content,
        artifact_type="task_transcript",
        stage="verified",
        owner_kind=normalized_owner_kind,
        owner_id=normalized_owner_id,
        media_type="text/markdown",
        file_extension=".md",
        metadata=dict(metadata or {}),
    )

    now = _utcnow_iso()
    existing = get_task_transcript(config, transcript_id)
    created_at = existing.created_at if existing is not None else now
    record = TaskTranscriptRecord(
        id=transcript_id,
        owner_kind=normalized_owner_kind,
        owner_id=normalized_owner_id,
        content_path=str(artifact.content_path),
        preview=stored_content[:TASK_TRANSCRIPT_PREVIEW_CHARS],
        metadata=dict(metadata or {}),
        created_at=created_at,
        updated_at=now,
    )
    _atomic_write_json(task_transcript_metadata_path(config, transcript_id), record.model_dump())
    return record


__all__ = [
    "TASK_TRANSCRIPT_PREVIEW_CHARS",
    "TaskTranscriptRecord",
    "get_task_transcript",
    "persist_task_transcript",
    "read_task_transcript_text",
    "task_transcript_id",
    "task_transcript_content_path",
    "task_transcript_metadata_path",
]
