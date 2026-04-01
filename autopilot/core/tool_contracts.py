"""Runtime tool contracts for deterministic tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from pydantic import BaseModel, Field

ToolInputJSONSchema = dict[str, Any]


class ToolResult(BaseModel):
    """Normalized result returned by a runtime tool."""

    status: str = "ok"
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolPermissionContext(BaseModel):
    """Permission state used by the runtime tool layer."""

    mode: str = "default"
    always_allow_rules: dict[str, list[str]] = Field(default_factory=dict)
    always_deny_rules: dict[str, list[str]] = Field(default_factory=dict)
    always_ask_rules: dict[str, list[str]] = Field(default_factory=dict)
    tool_reasons: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_empty_tool_permission_context() -> ToolPermissionContext:
    """Return an empty permission context."""

    return ToolPermissionContext()


@dataclass(slots=True)
class ToolUseContext:
    """Execution context shared across one tool run."""

    config: Any | None = None
    actor: str = ""
    project_id: str = ""
    runtime_agent_ids: tuple[str, ...] = ()
    dry_run: bool = False
    orchestrator_session_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


ToolExecutor = Callable[[dict[str, Any], ToolUseContext], ToolResult]


@dataclass(slots=True)
class ToolDef:
    """Executable tool definition."""

    name: str
    description: str
    input_schema: ToolInputJSONSchema
    execute: ToolExecutor
    kind: str = "generic"
    scope: str = "workspace"
    approval_policy: str = "manual"
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def build_tool(
    *,
    name: str,
    description: str,
    input_schema: ToolInputJSONSchema | None = None,
    execute: ToolExecutor,
    kind: str = "generic",
    scope: str = "workspace",
    approval_policy: str = "manual",
    tags: Iterable[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ToolDef:
    """Build one runtime tool definition."""

    return ToolDef(
        name=name,
        description=description,
        input_schema=input_schema or {"type": "object", "properties": {}},
        execute=execute,
        kind=kind,
        scope=scope,
        approval_policy=approval_policy,
        tags=tuple(tags or ()),
        metadata=dict(metadata or {}),
    )


def tool_matches_name(tool: ToolDef, name: str) -> bool:
    """Return whether a tool matches one exact or wildcard name."""

    normalized = str(name or "").strip()
    if not normalized:
        return False
    if normalized.endswith("*"):
        return tool.name.startswith(normalized[:-1])
    return tool.name == normalized


def find_tool_by_name(tools: Iterable[ToolDef], name: str) -> ToolDef | None:
    """Return the first tool that matches the provided name."""

    for tool in tools:
        if tool_matches_name(tool, name):
            return tool
    return None
