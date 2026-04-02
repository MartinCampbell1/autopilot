"""Structured control-message and SSE framing helpers for runtime control."""

from __future__ import annotations

import json
import re
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter


_CAMEL_TO_SNAKE_OVERRIDES = {
    "requestId": "request_id",
    "sessionId": "session_id",
    "sdkMcpServers": "sdk_mcp_servers",
    "jsonSchema": "json_schema",
    "systemPrompt": "system_prompt",
    "appendSystemPrompt": "append_system_prompt",
    "promptSuggestions": "prompt_suggestions",
    "agentProgressSummaries": "agent_progress_summaries",
    "toolName": "tool_name",
    "permissionSuggestions": "permission_suggestions",
    "blockedPath": "blocked_path",
    "decisionReason": "decision_reason",
    "displayName": "display_name",
    "toolUseId": "tool_use_id",
    "agentId": "agent_id",
    "maxThinkingTokens": "max_thinking_tokens",
    "outputStyle": "output_style",
    "availableOutputStyles": "available_output_styles",
    "fastModeState": "fast_mode_state",
}


def _camel_to_snake(value: str) -> str:
    overridden = _CAMEL_TO_SNAKE_OVERRIDES.get(value)
    if overridden is not None:
        return overridden
    if not value or "_" in value:
        return value
    normalized = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", value)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    return normalized.lower()


def normalize_control_message_keys(value: Any) -> Any:
    """Recursively normalize control payload keys to snake_case."""

    if isinstance(value, dict):
        return {_camel_to_snake(str(key)): normalize_control_message_keys(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_control_message_keys(item) for item in value]
    return value


class ControlInitializeRequest(BaseModel):
    subtype: Literal["initialize"]
    hooks: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    sdk_mcp_servers: list[str] = Field(default_factory=list)
    json_schema: dict[str, Any] = Field(default_factory=dict)
    system_prompt: str | None = None
    append_system_prompt: str | None = None
    agents: dict[str, Any] = Field(default_factory=dict)
    prompt_suggestions: bool | None = None
    agent_progress_summaries: bool | None = None


class ControlInterruptRequest(BaseModel):
    subtype: Literal["interrupt"]


class ControlPermissionRequest(BaseModel):
    subtype: Literal["can_use_tool"]
    tool_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    permission_suggestions: list[dict[str, Any]] = Field(default_factory=list)
    blocked_path: str | None = None
    decision_reason: str | None = None
    title: str | None = None
    display_name: str | None = None
    tool_use_id: str
    agent_id: str | None = None
    description: str | None = None
    user_text: str | None = None
    classifier_enabled: bool | None = None
    classifier_mode: Literal["sync", "deferred"] | None = None
    classifier_fail_open: bool | None = None


class ControlSetPermissionModeRequest(BaseModel):
    subtype: Literal["set_permission_mode"]
    mode: str
    ultraplan: bool | None = None


class ControlSetModelRequest(BaseModel):
    subtype: Literal["set_model"]
    model: str | None = None


class ControlSetMaxThinkingTokensRequest(BaseModel):
    subtype: Literal["set_max_thinking_tokens"]
    max_thinking_tokens: int | None = None


class ControlMcpStatusRequest(BaseModel):
    subtype: Literal["mcp_status"]


class ControlReloadPluginsRequest(BaseModel):
    subtype: Literal["reload_plugins"]


class ControlGetContextUsageRequest(BaseModel):
    subtype: Literal["get_context_usage"]


class ControlGetRuntimeAgentTaskRequest(BaseModel):
    subtype: Literal["get_runtime_agent_task"]
    task_id: str
    wait_for_async_settlement: bool = False
    runtime_agent_id: str | None = None
    wait_timeout_ms: int | None = None


class ControlGetRuntimeAgentActionRunRequest(BaseModel):
    subtype: Literal["get_runtime_agent_action_run"]
    run_id: str
    wait_for_async_settlement: bool = False
    runtime_agent_id: str | None = None
    wait_timeout_ms: int | None = None


class ControlListRuntimeAgentActionRunsRequest(BaseModel):
    subtype: Literal["list_runtime_agent_action_runs"]
    orchestrator_session_id: str | None = None
    run_kind: str | None = None
    actor: str | None = None
    status: str | None = None
    dry_run: bool | None = None


class ControlGetRuntimeAgentTaskOutputRequest(BaseModel):
    subtype: Literal["get_runtime_agent_task_output"]
    task_id: str


class ControlListRuntimeAgentTasksRequest(BaseModel):
    subtype: Literal["list_runtime_agent_tasks"]
    orchestrator_session_id: str | None = None
    runtime_agent_id: str | None = None
    status: str | None = None
    command: str | None = None
    agent_action_run_id: str | None = None


class ControlGetRuntimeAgentTaskTranscriptRequest(BaseModel):
    subtype: Literal["get_runtime_agent_task_transcript"]
    task_id: str


class ControlCancelRuntimeAgentTaskRequest(BaseModel):
    subtype: Literal["cancel_runtime_agent_task"]
    task_id: str
    actor: str = "human"
    note: str = ""


class ControlListToolPermissionRuntimesRequest(BaseModel):
    subtype: Literal["list_tool_permission_runtimes"]
    runtime_agent_id: str | None = None
    status: str | None = None
    pending_stage: str | None = None


class ControlGetToolPermissionRuntimeRequest(BaseModel):
    subtype: Literal["get_tool_permission_runtime"]
    approval_runtime_id: str


class ControlResolveToolPermissionRuntimeRequest(BaseModel):
    subtype: Literal["resolve_tool_permission_runtime"]
    approval_runtime_id: str
    outcome: Literal["allow", "deny"]
    actor: str = "human"
    note: str = ""
    source: Literal["user", "channel"] = "user"


ControlRequestPayload = Annotated[
    ControlInitializeRequest
    | ControlInterruptRequest
    | ControlPermissionRequest
    | ControlSetPermissionModeRequest
    | ControlSetModelRequest
    | ControlSetMaxThinkingTokensRequest
    | ControlMcpStatusRequest
    | ControlReloadPluginsRequest
    | ControlGetContextUsageRequest
    | ControlGetRuntimeAgentTaskRequest
    | ControlGetRuntimeAgentActionRunRequest
    | ControlListRuntimeAgentActionRunsRequest
    | ControlListRuntimeAgentTasksRequest
    | ControlGetRuntimeAgentTaskOutputRequest
    | ControlGetRuntimeAgentTaskTranscriptRequest
    | ControlCancelRuntimeAgentTaskRequest
    | ControlListToolPermissionRuntimesRequest
    | ControlGetToolPermissionRuntimeRequest
    | ControlResolveToolPermissionRuntimeRequest,
    Field(discriminator="subtype"),
]
_CONTROL_REQUEST_ADAPTER = TypeAdapter(ControlRequestPayload)


class ControlRequestEnvelope(BaseModel):
    type: Literal["control_request"]
    request_id: str
    request: ControlRequestPayload
    session_id: str | None = None


class ControlSuccessResponse(BaseModel):
    subtype: Literal["success"]
    request_id: str
    response: dict[str, Any] = Field(default_factory=dict)


class ControlErrorResponse(BaseModel):
    subtype: Literal["error"]
    request_id: str
    error: str


ControlResponsePayload = Annotated[
    ControlSuccessResponse | ControlErrorResponse,
    Field(discriminator="subtype"),
]
_CONTROL_RESPONSE_ADAPTER = TypeAdapter(ControlResponsePayload)


class ControlResponseEnvelope(BaseModel):
    type: Literal["control_response"]
    response: ControlResponsePayload
    session_id: str | None = None


class SessionResultMessage(BaseModel):
    type: Literal["result"] = "result"
    subtype: Literal["success"] = "success"
    session_id: str
    uuid: str
    is_error: bool = False
    result: str = ""
    summary: dict[str, Any] | None = None
    timestamp: str | None = None


class StructuredEventEnvelope(BaseModel):
    type: Literal["event"] = "event"
    event: str
    event_id: str
    sequence: int
    data: dict[str, Any]
    source: str = "events_log"
    session_id: str | None = None
    timestamp: str | None = None


ParsedControlMessage = ControlRequestEnvelope | ControlResponseEnvelope


def parse_control_request_message(value: Any) -> ControlRequestEnvelope | None:
    """Parse one control_request payload after key normalization."""

    normalized = normalize_control_message_keys(value)
    if not isinstance(normalized, dict) or normalized.get("type") != "control_request":
        return None
    request = normalized.get("request")
    if not isinstance(request, dict):
        return None
    parsed_request = _CONTROL_REQUEST_ADAPTER.validate_python(request)
    return ControlRequestEnvelope(
        type="control_request",
        request_id=str(normalized.get("request_id") or "").strip(),
        request=parsed_request,
        session_id=str(normalized.get("session_id") or "").strip() or None,
    )


def parse_control_response_message(value: Any) -> ControlResponseEnvelope | None:
    """Parse one control_response payload after key normalization."""

    normalized = normalize_control_message_keys(value)
    if not isinstance(normalized, dict) or normalized.get("type") != "control_response":
        return None
    response = normalized.get("response")
    if not isinstance(response, dict):
        return None
    parsed_response = _CONTROL_RESPONSE_ADAPTER.validate_python(response)
    return ControlResponseEnvelope(
        type="control_response",
        response=parsed_response,
        session_id=str(normalized.get("session_id") or "").strip() or None,
    )


def parse_control_message(value: Any) -> ParsedControlMessage | None:
    """Parse a structured control message envelope, if present."""

    return parse_control_request_message(value) or parse_control_response_message(value)


def is_control_request_message(value: Any) -> bool:
    """Return True when the payload is a valid control_request envelope."""

    return parse_control_request_message(value) is not None


def is_control_response_message(value: Any) -> bool:
    """Return True when the payload is a valid control_response envelope."""

    return parse_control_response_message(value) is not None


def make_control_success_response(
    request_id: str,
    *,
    response: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> ControlResponseEnvelope:
    """Build a canonical success control_response envelope."""

    return ControlResponseEnvelope(
        type="control_response",
        response=ControlSuccessResponse(
            subtype="success",
            request_id=request_id,
            response=dict(response or {}),
        ),
        session_id=session_id,
    )


def make_control_error_response(
    request_id: str,
    *,
    error: str,
    session_id: str | None = None,
) -> ControlResponseEnvelope:
    """Build a canonical error control_response envelope."""

    return ControlResponseEnvelope(
        type="control_response",
        response=ControlErrorResponse(
            subtype="error",
            request_id=request_id,
            error=error,
        ),
        session_id=session_id,
    )


def make_result_message(
    session_id: str,
    *,
    result: str = "",
    is_error: bool = False,
    summary: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> SessionResultMessage:
    """Build a minimal session result message for future runtime transports."""

    return SessionResultMessage(
        session_id=session_id,
        uuid=str(uuid.uuid4()),
        result=result,
        is_error=is_error,
        summary=summary,
        timestamp=timestamp,
    )


def resolve_control_event_id(value: dict[str, Any], sequence: int) -> str:
    """Resolve a stable event id for one structured event/control payload."""

    parsed = parse_control_message(value)
    if isinstance(parsed, ControlRequestEnvelope):
        return parsed.request_id
    if isinstance(parsed, ControlResponseEnvelope):
        return parsed.response.request_id
    explicit = str(value.get("event_id") or value.get("id") or "").strip()
    if explicit:
        return explicit
    return f"evt_{sequence}"


def build_structured_event_envelope(
    value: dict[str, Any],
    *,
    sequence: int,
    source: str = "events_log",
) -> StructuredEventEnvelope:
    """Wrap one raw execution event in a stable structured envelope."""

    return StructuredEventEnvelope(
        event=str(value.get("event") or "project_event"),
        event_id=resolve_control_event_id(value, sequence),
        sequence=sequence,
        data=value,
        source=source,
        session_id=str(value.get("orchestrator_session_id") or value.get("session_id") or "").strip() or None,
        timestamp=str(value.get("timestamp") or "").strip() or None,
    )


def format_sse_frame(
    event: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
) -> str:
    """Encode one SSE frame with optional event id."""

    lines: list[str] = []
    if event_id:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


class BoundedMessageIdSet:
    """FIFO-bounded set for request/event id deduplication."""

    def __init__(self, capacity: int):
        self.capacity = max(1, int(capacity))
        self._ring: list[str | None] = [None] * self.capacity
        self._values: set[str] = set()
        self._write_index = 0

    def add(self, value: str) -> None:
        normalized = str(value or "").strip()
        if not normalized or normalized in self._values:
            return
        evicted = self._ring[self._write_index]
        if evicted is not None:
            self._values.discard(evicted)
        self._ring[self._write_index] = normalized
        self._values.add(normalized)
        self._write_index = (self._write_index + 1) % self.capacity

    def has(self, value: str) -> bool:
        return str(value or "").strip() in self._values

    def clear(self) -> None:
        self._ring = [None] * self.capacity
        self._values.clear()
        self._write_index = 0
