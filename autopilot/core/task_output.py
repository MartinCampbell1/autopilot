"""Durable disk-backed output artifacts for async tasks."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig

TASK_OUTPUT_MAX_CHARS = 65536
TASK_OUTPUT_PREVIEW_CHARS = 4000


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


def _task_output_id(owner_kind: str, owner_id: str) -> str:
    digest = hashlib.sha1(f"{owner_kind}:{owner_id}".encode("utf-8")).hexdigest()[:12]
    return f"tout_{digest}"


def _truncate_content(content: str) -> tuple[str, bool]:
    normalized = str(content or "")
    if len(normalized) <= TASK_OUTPUT_MAX_CHARS:
        return normalized, False
    return normalized[:TASK_OUTPUT_MAX_CHARS].rstrip() + "\n\n[truncated]", True


class TaskOutputRecord(BaseModel):
    """Persisted output artifact for one async task-like owner."""

    id: str
    owner_kind: str
    owner_id: str
    source_path: str = ""
    content_path: str
    content_bytes: int = 0
    truncated: bool = False
    preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


def task_output_metadata_path(config: AutopilotConfig, output_id: str) -> Path:
    """Return metadata path for one output artifact."""

    return config.task_outputs_dir / f"{output_id}.json"


def task_output_content_path(config: AutopilotConfig, output_id: str) -> Path:
    """Return content path for one output artifact."""

    return config.task_outputs_dir / f"{output_id}.txt"


def get_task_output(config: AutopilotConfig, output_id: str) -> TaskOutputRecord | None:
    """Load one output artifact metadata record."""

    path = task_output_metadata_path(config, output_id)
    if not path.exists():
        return None
    try:
        return TaskOutputRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def read_task_output_text(config: AutopilotConfig, output_id: str) -> str:
    """Read artifact content text if present."""

    record = get_task_output(config, output_id)
    if record is None:
        raise KeyError(output_id)
    path = Path(record.content_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def persist_task_output(
    config: AutopilotConfig,
    *,
    owner_kind: str,
    owner_id: str,
    content: str,
    source_path: str = "",
    metadata: dict[str, Any] | None = None,
) -> TaskOutputRecord:
    """Persist one deterministic output artifact for an async task owner."""

    normalized_owner_kind = str(owner_kind or "").strip() or "task"
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        raise ValueError("owner_id is required")

    output_id = _task_output_id(normalized_owner_kind, normalized_owner_id)
    content_path = task_output_content_path(config, output_id)
    stored_content, truncated = _truncate_content(str(content or ""))
    _atomic_write_text(content_path, stored_content)

    now = _utcnow_iso()
    existing = get_task_output(config, output_id)
    created_at = existing.created_at if existing is not None else now
    record = TaskOutputRecord(
        id=output_id,
        owner_kind=normalized_owner_kind,
        owner_id=normalized_owner_id,
        source_path=str(source_path or "").strip(),
        content_path=str(content_path),
        content_bytes=len(stored_content.encode("utf-8")),
        truncated=truncated,
        preview=stored_content[:TASK_OUTPUT_PREVIEW_CHARS],
        metadata=dict(metadata or {}),
        created_at=created_at,
        updated_at=now,
    )
    _atomic_write_json(task_output_metadata_path(config, output_id), record.model_dump())
    return record


def load_text_from_source(source_path: str) -> str:
    """Best-effort read from one source text path."""

    normalized = str(source_path or "").strip()
    if not normalized:
        return ""
    path = Path(normalized)
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


__all__ = [
    "TASK_OUTPUT_MAX_CHARS",
    "TASK_OUTPUT_PREVIEW_CHARS",
    "TaskOutputRecord",
    "get_task_output",
    "load_text_from_source",
    "persist_task_output",
    "read_task_output_text",
    "task_output_content_path",
    "task_output_metadata_path",
]
