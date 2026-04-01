"""Hook pipeline for runtime tool execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from autopilot.core.tool_contracts import ToolDef, ToolResult, ToolUseContext
from autopilot.core.tool_permissions import PermissionDecision

ToolHookEventName = Literal["pre_tool_use", "permission_request", "post_tool_use", "post_tool_use_failure"]


class ToolHookOutput(BaseModel):
    """Normalized hook output consumed by the tool runner."""

    continue_execution: bool = True
    message: str = ""
    permission_behavior: Literal["allow", "deny", "ask"] | None = None
    updated_input: dict[str, Any] = Field(default_factory=dict)
    result_updates: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class HookExecutionRecord(BaseModel):
    """Stable audit record for one executed hook."""

    event: ToolHookEventName
    hook_name: str
    continue_execution: bool = True
    message: str = ""
    permission_behavior: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class HookPipelineResult(BaseModel):
    """Result of executing a hook pipeline for one event."""

    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_result: ToolResult | None = None
    permission_decision: PermissionDecision | None = None
    records: list[HookExecutionRecord] = Field(default_factory=list)
    blocked: bool = False
    message: str = ""


@dataclass(slots=True)
class ToolHookContext:
    """Context passed to one hook handler."""

    event: ToolHookEventName
    tool: ToolDef
    tool_input: dict[str, Any]
    use_context: ToolUseContext
    permission_decision: PermissionDecision | None = None
    tool_result: ToolResult | None = None
    error: Exception | None = None


ToolHookHandler = Callable[[ToolHookContext], ToolHookOutput | dict[str, Any] | None]


@dataclass(slots=True)
class ToolHookDefinition:
    """One registered tool hook."""

    name: str
    event: ToolHookEventName
    handler: ToolHookHandler
    tool_names: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_hook_output(raw_output: ToolHookOutput | dict[str, Any] | None) -> ToolHookOutput:
    """Normalize one raw hook output."""

    if raw_output is None:
        return ToolHookOutput()
    if isinstance(raw_output, ToolHookOutput):
        return raw_output
    if isinstance(raw_output, dict):
        return ToolHookOutput.model_validate(raw_output)
    raise TypeError(f"Unsupported hook output type: {type(raw_output).__name__}")


def process_hook_json_output(raw_output: ToolHookOutput | dict[str, Any] | None) -> ToolHookOutput:
    """Parse and validate one hook output."""

    return parse_hook_output(raw_output)


def _hook_matches_tool(tool: ToolDef, hook: ToolHookDefinition) -> bool:
    if not hook.tool_names:
        return True
    for item in hook.tool_names:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        if normalized.endswith("*") and tool.name.startswith(normalized[:-1]):
            return True
        if tool.name == normalized:
            return True
    return False


def resolve_hook_permission_decision(
    decision: PermissionDecision,
    hook_output: ToolHookOutput,
    *,
    tool_name: str,
) -> PermissionDecision:
    """Apply one permission-specific hook output to the current decision."""

    behavior = hook_output.permission_behavior
    if behavior is None:
        return decision
    if behavior == "allow":
        return PermissionDecision(behavior="allow", reasons=list(decision.reasons))
    if behavior == "deny":
        message = hook_output.message or decision.message or f"Tool `{tool_name}` denied by hook."
        return PermissionDecision(behavior="deny", message=message, reasons=list(decision.reasons) or [message])
    message = hook_output.message or decision.message or f"Tool `{tool_name}` requires approval."
    return PermissionDecision(behavior="ask", message=message, reasons=list(decision.reasons))


def execute_hooks(
    *,
    event: ToolHookEventName,
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
    hooks: list[ToolHookDefinition] | None = None,
    permission_decision: PermissionDecision | None = None,
    tool_result: ToolResult | None = None,
    error: Exception | None = None,
) -> tuple[list[HookExecutionRecord], list[ToolHookOutput]]:
    """Execute all hooks that match one event/tool pair."""

    records: list[HookExecutionRecord] = []
    outputs: list[ToolHookOutput] = []
    for hook in hooks or []:
        if hook.event != event or not _hook_matches_tool(tool, hook):
            continue
        context = ToolHookContext(
            event=event,
            tool=tool,
            tool_input=dict(tool_input),
            use_context=use_context,
            permission_decision=permission_decision,
            tool_result=tool_result,
            error=error,
        )
        output = process_hook_json_output(hook.handler(context))
        outputs.append(output)
        records.append(
            HookExecutionRecord(
                event=event,
                hook_name=hook.name,
                continue_execution=output.continue_execution,
                message=output.message,
                permission_behavior=output.permission_behavior,
                metadata=output.metadata,
            )
        )
    return records, outputs


def execute_pre_tool_hooks(
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
    hooks: list[ToolHookDefinition] | None = None,
) -> HookPipelineResult:
    """Execute pre-tool hooks and return the updated input."""

    updated_input = dict(tool_input)
    records, outputs = execute_hooks(
        event="pre_tool_use",
        tool=tool,
        tool_input=updated_input,
        use_context=use_context,
        hooks=hooks,
    )
    blocked = False
    message = ""
    for output in outputs:
        if output.updated_input:
            updated_input.update(output.updated_input)
        if not output.continue_execution and not blocked:
            blocked = True
            message = output.message or f"Tool `{tool.name}` blocked by pre-tool hook."
    return HookPipelineResult(tool_input=updated_input, records=records, blocked=blocked, message=message)


def run_pre_tool_use_hooks(
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
    hooks: list[ToolHookDefinition] | None = None,
) -> HookPipelineResult:
    """Alias for the pre-tool hook pipeline."""

    return execute_pre_tool_hooks(tool, tool_input, use_context, hooks)


def execute_permission_request_hooks(
    tool: ToolDef,
    tool_input: dict[str, Any],
    use_context: ToolUseContext,
    permission_decision: PermissionDecision,
    hooks: list[ToolHookDefinition] | None = None,
) -> HookPipelineResult:
    """Execute hooks that can rewrite a pending permission request."""

    records, outputs = execute_hooks(
        event="permission_request",
        tool=tool,
        tool_input=tool_input,
        use_context=use_context,
        hooks=hooks,
        permission_decision=permission_decision,
    )
    resolved = permission_decision
    updated_input = dict(tool_input)
    blocked = False
    message = ""
    for output in outputs:
        if output.updated_input:
            updated_input.update(output.updated_input)
        resolved = resolve_hook_permission_decision(resolved, output, tool_name=tool.name)
        if not output.continue_execution and not blocked:
            blocked = True
            message = output.message or f"Tool `{tool.name}` blocked by permission hook."
    return HookPipelineResult(
        tool_input=updated_input,
        permission_decision=resolved,
        records=records,
        blocked=blocked,
        message=message,
    )
