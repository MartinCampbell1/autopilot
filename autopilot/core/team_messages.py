"""Explicit teammate message channel for worker/specialist coordination."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

TEAM_MESSAGE_LIMIT = 50


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class TeamMessage(BaseModel):
    """One observable message shared between teammate roles."""

    id: str
    dedupe_key: str = ""
    story_id: int | None = None
    source_role: str
    target_role: str = "worker"
    message_type: str
    title: str
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class TeamMessageState(BaseModel):
    """Persisted team-message payload."""

    messages: list[TeamMessage] = Field(default_factory=list)


def team_messages_path(project_path: Path) -> Path:
    """Return the explicit teammate message channel path."""

    return project_path / ".ralph" / "team-messages.json"


def load_team_messages(project_path: Path) -> list[TeamMessage]:
    """Load all explicit team messages for one project path."""

    path = team_messages_path(project_path)
    if not path.exists():
        return []
    try:
        payload = TeamMessageState.model_validate(json.loads(path.read_text()))
    except Exception:
        return []
    return list(payload.messages)


def save_team_messages(project_path: Path, messages: list[TeamMessage]) -> list[TeamMessage]:
    """Persist the explicit team-message channel."""

    normalized = list(messages)[-TEAM_MESSAGE_LIMIT:]
    _atomic_write_json(
        team_messages_path(project_path),
        TeamMessageState(messages=normalized).model_dump(),
    )
    return normalized


def upsert_team_message(
    project_path: Path,
    *,
    dedupe_key: str,
    source_role: str,
    message_type: str,
    title: str,
    content: str = "",
    target_role: str = "worker",
    story_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> TeamMessage:
    """Insert or replace one explicit teammate message by stable dedupe key."""

    now = _utcnow_iso()
    normalized_dedupe_key = str(dedupe_key or "").strip()
    normalized_content = str(content or "").strip()
    if len(normalized_content) > 12000:
        normalized_content = normalized_content[:12000].rstrip() + "\n\n[truncated]"

    existing = load_team_messages(project_path)
    for index, message in enumerate(existing):
        if message.dedupe_key != normalized_dedupe_key:
            continue
        existing[index] = message.model_copy(
            update={
                "story_id": story_id if story_id is not None else message.story_id,
                "source_role": str(source_role or "").strip(),
                "target_role": str(target_role or "").strip() or "worker",
                "message_type": str(message_type or "").strip(),
                "title": str(title or "").strip(),
                "content": normalized_content,
                "metadata": dict(metadata or {}),
                "updated_at": now,
            }
        )
        save_team_messages(project_path, existing)
        return existing[index]

    created = TeamMessage(
        id=f"tmsg_{uuid.uuid4().hex[:12]}",
        dedupe_key=normalized_dedupe_key,
        story_id=story_id,
        source_role=str(source_role or "").strip(),
        target_role=str(target_role or "").strip() or "worker",
        message_type=str(message_type or "").strip(),
        title=str(title or "").strip(),
        content=normalized_content,
        metadata=dict(metadata or {}),
        created_at=now,
        updated_at=now,
    )
    existing.append(created)
    save_team_messages(project_path, existing)
    return created


__all__ = [
    "TEAM_MESSAGE_LIMIT",
    "TeamMessage",
    "load_team_messages",
    "save_team_messages",
    "team_messages_path",
    "upsert_team_message",
]
