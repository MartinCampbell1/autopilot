"""Disk-backed storage for large runtime tool results."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from autopilot.core.artifact_store import persist_json_artifact
from autopilot.core.config import AutopilotConfig
from autopilot.core.orchestrator_sessions import link_orchestrator_session_entities
from autopilot.core.tool_contracts import ToolResult, ToolUseContext


def _storage_scope(use_context: ToolUseContext) -> str:
    candidates = (
        str(use_context.project_id or "").strip(),
        str(use_context.orchestrator_session_id or "").strip(),
        str(use_context.actor or "").strip(),
    )
    for candidate in candidates:
        if candidate:
            return candidate.replace("/", "_")
    return "runtime"


def _tool_result_envelope(tool_name: str, tool_result: ToolResult, use_context: ToolUseContext) -> dict[str, Any]:
    return {
        "tool_name": tool_name,
        "status": str(tool_result.status or "ok"),
        "message": str(tool_result.message or ""),
        "payload": dict(tool_result.payload or {}),
        "metadata": dict(tool_result.metadata or {}),
        "actor": str(use_context.actor or ""),
        "project_id": str(use_context.project_id or ""),
        "orchestrator_session_id": str(use_context.orchestrator_session_id or ""),
    }


def store_large_tool_result(
    tool_name: str,
    tool_result: ToolResult,
    use_context: ToolUseContext,
) -> ToolResult:
    """Persist oversized tool results to disk and replace inline payload with a reference."""

    config = use_context.config
    if not isinstance(config, AutopilotConfig):
        return tool_result

    envelope = _tool_result_envelope(tool_name, tool_result, use_context)
    serialized = json.dumps(envelope, ensure_ascii=False, sort_keys=True, default=str)
    inline_limit = max(int(config.tool_result_inline_bytes_limit or 0), 0)
    if inline_limit <= 0 or len(serialized.encode("utf-8")) <= inline_limit:
        return tool_result

    payload_hash = hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]
    artifact = persist_json_artifact(
        config,
        payload=envelope,
        artifact_type="tool_result",
        stage="temporary",
        owner_kind="tool_result",
        owner_id=f"{_storage_scope(use_context)}:{tool_name}:{payload_hash}",
        project_id=str(use_context.project_id or ""),
        orchestrator_session_id=str(use_context.orchestrator_session_id or ""),
        runtime_agent_ids=list(use_context.runtime_agent_ids or ()),
        metadata={
            "tool_name": tool_name,
            "actor": str(use_context.actor or ""),
            "storage_scope": _storage_scope(use_context),
            "payload_hash": payload_hash,
        },
    )
    if str(use_context.orchestrator_session_id or "").strip():
        try:
            link_orchestrator_session_entities(
                config,
                str(use_context.orchestrator_session_id or "").strip(),
                project_ids=[str(use_context.project_id or "").strip()] if str(use_context.project_id or "").strip() else None,
                linked_runtime_agent_ids=list(use_context.runtime_agent_ids or ()),
                linked_artifact_ids=[artifact.id],
            )
        except KeyError:
            pass

    preview_chars = max(int(config.tool_result_preview_chars or 0), 120)
    preview = serialized[:preview_chars].strip()
    if len(serialized) > preview_chars:
        preview = f"{preview}..."

    metadata = dict(tool_result.metadata or {})
    metadata.update(
        {
            "stored_result": True,
            "stored_result_artifact_id": artifact.id,
            "stored_result_path": str(artifact.content_path),
            "stored_result_manifest_path": str(artifact.manifest_path),
            "stored_result_stage": artifact.stage,
            "stored_result_bytes": len(serialized.encode("utf-8")),
            "stored_result_preview": preview,
        }
    )
    payload = {
        "stored_result": True,
        "stored_result_artifact_id": artifact.id,
        "stored_result_path": str(artifact.content_path),
        "stored_result_manifest_path": str(artifact.manifest_path),
        "stored_result_stage": artifact.stage,
        "stored_result_bytes": metadata["stored_result_bytes"],
        "stored_result_preview": preview,
    }
    message = str(tool_result.message or "").strip() or f"Stored large tool result at {artifact.content_path}."

    return tool_result.model_copy(update={"message": message, "payload": payload, "metadata": metadata})
