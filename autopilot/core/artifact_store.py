"""Schema-versioned shared artifact manifests for file-backed collaboration."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig

ARTIFACT_STORE_SCHEMA_VERSION = 1
ARTIFACT_PREVIEW_CHARS = 4000
ARTIFACT_STAGES = {"temporary", "verified", "final"}


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


def artifact_store_dir(config: AutopilotConfig) -> Path:
    """Return the root directory for the shared artifact store."""

    return config.control_plane_state_dir / "artifacts"


def artifact_manifests_dir(config: AutopilotConfig) -> Path:
    """Return the manifests directory for the shared artifact store."""

    return artifact_store_dir(config) / "manifests"


def artifact_objects_dir(config: AutopilotConfig) -> Path:
    """Return the objects directory for the shared artifact store."""

    return artifact_store_dir(config) / "objects"


def artifact_manifest_path(config: AutopilotConfig, artifact_id: str) -> Path:
    """Return the manifest path for one artifact."""

    return artifact_manifests_dir(config) / f"{artifact_id}.json"


def _normalize_extension(extension: str | None) -> str:
    normalized = str(extension or "").strip()
    if not normalized:
        return ".txt"
    return normalized if normalized.startswith(".") else f".{normalized}"


def artifact_content_path(
    config: AutopilotConfig,
    artifact_id: str,
    *,
    extension: str | None = None,
) -> Path:
    """Return the object content path for one artifact."""

    return artifact_objects_dir(config) / f"{artifact_id}{_normalize_extension(extension)}"


class ArtifactRecord(BaseModel):
    """Persisted manifest for one shared file-backed artifact."""

    schema_version: int = ARTIFACT_STORE_SCHEMA_VERSION
    id: str
    artifact_type: str
    stage: str = "temporary"
    owner_kind: str = ""
    owner_id: str = ""
    source_artifact_id: str = ""
    project_id: str = ""
    orchestrator_session_id: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    manifest_path: str
    content_path: str
    content_bytes: int = 0
    sha256: str = ""
    media_type: str = "text/plain"
    file_extension: str = ".txt"
    preview: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


def get_artifact(config: AutopilotConfig, artifact_id: str) -> ArtifactRecord | None:
    """Load one shared artifact manifest if present."""

    path = artifact_manifest_path(config, artifact_id)
    if not path.exists():
        return None
    try:
        return ArtifactRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


def read_artifact_text(config: AutopilotConfig, artifact_id: str) -> str:
    """Read one shared artifact content blob."""

    record = get_artifact(config, artifact_id)
    if record is None:
        raise KeyError(artifact_id)
    path = Path(record.content_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def list_artifacts(
    config: AutopilotConfig,
    *,
    artifact_id: str | None = None,
    artifact_type: str | None = None,
    stage: str | None = None,
    owner_kind: str | None = None,
    owner_id: str | None = None,
    project_id: str | None = None,
    orchestrator_session_id: str | None = None,
    runtime_agent_id: str | None = None,
) -> list[ArtifactRecord]:
    """List shared artifact manifests with lightweight filtering."""

    directory = artifact_manifests_dir(config)
    if not directory.exists():
        return []

    records: list[ArtifactRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = ArtifactRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        if artifact_id and record.id != artifact_id:
            continue
        if artifact_type and record.artifact_type != artifact_type:
            continue
        if stage and record.stage != stage:
            continue
        if owner_kind and record.owner_kind != owner_kind:
            continue
        if owner_id and record.owner_id != owner_id:
            continue
        if project_id and record.project_id != project_id:
            continue
        if orchestrator_session_id and record.orchestrator_session_id != orchestrator_session_id:
            continue
        if runtime_agent_id and runtime_agent_id not in record.runtime_agent_ids:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return records


def persist_artifact(
    config: AutopilotConfig,
    *,
    content: str,
    artifact_type: str,
    stage: str = "temporary",
    owner_kind: str = "",
    owner_id: str = "",
    artifact_id: str | None = None,
    source_artifact_id: str = "",
    project_id: str = "",
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | tuple[str, ...] | None = None,
    media_type: str = "text/plain",
    file_extension: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ArtifactRecord:
    """Persist one schema-versioned artifact manifest and content blob."""

    normalized_stage = str(stage or "").strip() or "temporary"
    if normalized_stage not in ARTIFACT_STAGES:
        raise ValueError(f"Unsupported artifact stage: {normalized_stage}")

    normalized_artifact_id = str(artifact_id or "").strip() or f"artf_{uuid.uuid4().hex[:12]}"
    normalized_extension = _normalize_extension(file_extension)
    content_path = artifact_content_path(config, normalized_artifact_id, extension=normalized_extension)
    stored_content = str(content or "")
    _atomic_write_text(content_path, stored_content)

    existing = get_artifact(config, normalized_artifact_id)
    now = _utcnow_iso()
    created_at = existing.created_at if existing is not None else now
    payload_bytes = stored_content.encode("utf-8")
    record = ArtifactRecord(
        id=normalized_artifact_id,
        artifact_type=str(artifact_type or "").strip() or "artifact",
        stage=normalized_stage,
        owner_kind=str(owner_kind or "").strip(),
        owner_id=str(owner_id or "").strip(),
        source_artifact_id=str(source_artifact_id or "").strip(),
        project_id=str(project_id or "").strip(),
        orchestrator_session_id=str(orchestrator_session_id or "").strip(),
        runtime_agent_ids=sorted({str(item).strip() for item in (runtime_agent_ids or []) if str(item).strip()}),
        manifest_path=str(artifact_manifest_path(config, normalized_artifact_id)),
        content_path=str(content_path),
        content_bytes=len(payload_bytes),
        sha256=hashlib.sha256(payload_bytes).hexdigest(),
        media_type=str(media_type or "").strip() or "text/plain",
        file_extension=normalized_extension,
        preview=stored_content[:ARTIFACT_PREVIEW_CHARS],
        metadata=dict(metadata or {}),
        created_at=created_at,
        updated_at=now,
    )
    _atomic_write_json(artifact_manifest_path(config, normalized_artifact_id), record.model_dump())
    return record


def persist_json_artifact(
    config: AutopilotConfig,
    *,
    payload: Any,
    artifact_type: str,
    stage: str = "temporary",
    owner_kind: str = "",
    owner_id: str = "",
    artifact_id: str | None = None,
    source_artifact_id: str = "",
    project_id: str = "",
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | tuple[str, ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ArtifactRecord:
    """Persist one JSON artifact in the shared artifact store."""

    return persist_artifact(
        config,
        content=json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        artifact_type=artifact_type,
        stage=stage,
        owner_kind=owner_kind,
        owner_id=owner_id,
        artifact_id=artifact_id,
        source_artifact_id=source_artifact_id,
        project_id=project_id,
        orchestrator_session_id=orchestrator_session_id,
        runtime_agent_ids=runtime_agent_ids,
        media_type="application/json",
        file_extension=".json",
        metadata=metadata,
    )


def promote_artifact(
    config: AutopilotConfig,
    artifact_id: str,
    *,
    stage: str,
    artifact_type: str | None = None,
    owner_kind: str | None = None,
    owner_id: str | None = None,
    project_id: str | None = None,
    orchestrator_session_id: str | None = None,
    runtime_agent_ids: list[str] | tuple[str, ...] | None = None,
    metadata_updates: dict[str, Any] | None = None,
    target_artifact_id: str | None = None,
) -> ArtifactRecord:
    """Promote one artifact into a higher-confidence stage with a new manifest."""

    record = get_artifact(config, artifact_id)
    if record is None:
        raise KeyError(artifact_id)
    return persist_artifact(
        config,
        artifact_id=target_artifact_id,
        content=read_artifact_text(config, artifact_id),
        artifact_type=str(artifact_type or record.artifact_type or "").strip() or "artifact",
        stage=stage,
        owner_kind=str(owner_kind if owner_kind is not None else record.owner_kind or "").strip(),
        owner_id=str(owner_id if owner_id is not None else record.owner_id or "").strip(),
        source_artifact_id=record.id,
        project_id=str(project_id if project_id is not None else record.project_id or "").strip(),
        orchestrator_session_id=str(
            orchestrator_session_id if orchestrator_session_id is not None else record.orchestrator_session_id or ""
        ).strip(),
        runtime_agent_ids=list(runtime_agent_ids) if runtime_agent_ids is not None else list(record.runtime_agent_ids),
        media_type=record.media_type,
        file_extension=record.file_extension,
        metadata={**dict(record.metadata or {}), **dict(metadata_updates or {})},
    )


__all__ = [
    "ARTIFACT_PREVIEW_CHARS",
    "ARTIFACT_STORE_SCHEMA_VERSION",
    "ARTIFACT_STAGES",
    "ArtifactRecord",
    "artifact_content_path",
    "artifact_manifest_path",
    "artifact_manifests_dir",
    "artifact_objects_dir",
    "artifact_store_dir",
    "get_artifact",
    "list_artifacts",
    "persist_artifact",
    "persist_json_artifact",
    "promote_artifact",
    "read_artifact_text",
]
