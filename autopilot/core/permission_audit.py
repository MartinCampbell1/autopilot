"""Replay-friendly audit trail for permission decisions."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.tool_contracts import ToolDef

if TYPE_CHECKING:
    from autopilot.core.tool_permissions import PermissionDecision


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def permission_audit_path(config: AutopilotConfig, project_id: str = "") -> Path:
    """Return the JSONL audit path for one project scope."""

    normalized_project_id = str(project_id or "").strip() or "_global"
    return config.permission_audit_dir / f"{normalized_project_id}.jsonl"


def _projected_command(tool: ToolDef, tool_input: dict[str, Any] | None) -> str:
    payload = dict(tool_input or {})
    for key in ("command", "cmd", "rule_content"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    for key in ("command", "rule_content"):
        value = str(tool.metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def append_permission_audit_entry(
    config: AutopilotConfig,
    *,
    project_id: str,
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    decision: PermissionDecision,
    actor: str = "",
    source: str = "",
) -> dict[str, Any]:
    """Append one replay-friendly permission audit entry."""

    record = {
        "timestamp": _utcnow_iso(),
        "project_id": str(project_id or "").strip(),
        "tool_name": tool.name,
        "tool_kind": tool.kind,
        "approval_policy": tool.approval_policy,
        "behavior": decision.behavior,
        "message": decision.message,
        "reasons": list(decision.reasons),
        "rule_source": decision.rule_source,
        "matched_rule": decision.matched_rule,
        "denial_count": int(decision.denial_count or 0),
        "escalation_required": bool(decision.escalation_required),
        "actor": str(actor or "").strip(),
        "source": str(source or "").strip(),
        "input_keys": sorted(str(key) for key in dict(tool_input or {}).keys()),
        "projected_command": _projected_command(tool, tool_input),
    }
    path = permission_audit_path(config, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_permission_audit_entries(
    config: AutopilotConfig,
    project_id: str = "",
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Read permission audit entries for one project scope."""

    path = permission_audit_path(config, project_id)
    if not path.exists():
        return []
    entries = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None and limit > 0:
        return entries[-limit:]
    return entries


def build_permission_audit_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a compact replay-friendly summary from permission audit entries."""

    by_behavior = Counter(str(entry.get("behavior") or "unknown") for entry in entries)
    by_source = Counter(str(entry.get("rule_source") or "none") for entry in entries)
    by_tool = Counter(str(entry.get("tool_name") or "unknown") for entry in entries)
    return {
        "entry_count": len(entries),
        "by_behavior": dict(by_behavior),
        "by_source": dict(by_source),
        "by_tool": dict(by_tool),
        "first_timestamp": entries[0]["timestamp"] if entries else None,
        "last_timestamp": entries[-1]["timestamp"] if entries else None,
    }
