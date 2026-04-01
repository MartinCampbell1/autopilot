"""Disk-backed storage for large runtime tool results."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
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

    scope_dir = config.tool_results_dir / _storage_scope(use_context)
    scope_dir.mkdir(parents=True, exist_ok=True)
    payload_hash = hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]
    storage_path = scope_dir / f"{int(time.time())}-{tool_name.replace('/', '_')}-{payload_hash}.json"
    storage_path.write_text(json.dumps(envelope, indent=2, ensure_ascii=False, sort_keys=True))

    preview_chars = max(int(config.tool_result_preview_chars or 0), 120)
    preview = serialized[:preview_chars].strip()
    if len(serialized) > preview_chars:
        preview = f"{preview}..."

    metadata = dict(tool_result.metadata or {})
    metadata.update(
        {
            "stored_result": True,
            "stored_result_path": str(storage_path),
            "stored_result_bytes": len(serialized.encode("utf-8")),
            "stored_result_preview": preview,
        }
    )
    payload = {
        "stored_result": True,
        "stored_result_path": str(storage_path),
        "stored_result_bytes": metadata["stored_result_bytes"],
        "stored_result_preview": preview,
    }
    message = str(tool_result.message or "").strip() or f"Stored large tool result at {storage_path}."

    return tool_result.model_copy(update={"message": message, "payload": payload, "metadata": metadata})
