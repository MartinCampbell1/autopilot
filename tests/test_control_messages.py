"""Unit tests for structured control-message helpers."""

from __future__ import annotations

from autopilot.core.control_messages import (
    BoundedMessageIdSet,
    build_structured_event_envelope,
    make_control_error_response,
    make_control_success_response,
    normalize_control_message_keys,
    parse_control_message,
)


def test_parse_control_message_normalizes_camel_case_request_payload() -> None:
    payload = {
        "type": "control_request",
        "requestId": "req_123",
        "request": {
            "subtype": "can_use_tool",
            "toolName": "execution.launch",
            "toolUseId": "toolu_123",
            "agentId": "agent_1",
            "displayName": "Launch",
            "decisionReason": "Need explicit approval",
            "input": {"command": "launch"},
        },
    }

    parsed = parse_control_message(payload)

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request_id == "req_123"
    assert parsed.request.subtype == "can_use_tool"
    assert parsed.request.tool_name == "execution.launch"
    assert parsed.request.tool_use_id == "toolu_123"
    assert parsed.request.agent_id == "agent_1"
    assert parsed.request.display_name == "Launch"
    assert parsed.request.decision_reason == "Need explicit approval"


def test_control_response_builders_preserve_request_ids() -> None:
    success = make_control_success_response("req_success", response={"accepted": True}, session_id="sess_1")
    error = make_control_error_response("req_error", error="Denied", session_id="sess_2")

    assert success.response.request_id == "req_success"
    assert success.response.response == {"accepted": True}
    assert success.session_id == "sess_1"
    assert error.response.request_id == "req_error"
    assert error.response.error == "Denied"
    assert error.session_id == "sess_2"


def test_parse_control_message_supports_reload_plugins_request() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "request_id": "req_reload",
            "request": {"subtype": "reload_plugins"},
            "session_id": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "reload_plugins"
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_tool_permission_runtime_resolution_request() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_tool_perm_runtime",
            "request": {
                "subtype": "resolve_tool_permission_runtime",
                "approvalRuntimeId": "apprt_123",
                "outcome": "allow",
                "actor": "founderos",
                "source": "user",
                "note": "Proceed.",
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "resolve_tool_permission_runtime"
    assert parsed.request.approval_runtime_id == "apprt_123"
    assert parsed.request.outcome == "allow"
    assert parsed.request.actor == "founderos"
    assert parsed.session_id == "sess_1"


def test_build_structured_event_envelope_uses_sequence_when_no_explicit_id() -> None:
    event = {
        "event": "project_created",
        "project_id": "proj_1",
        "timestamp": "2026-04-01T00:00:00+00:00",
    }

    envelope = build_structured_event_envelope(event, sequence=7)

    assert envelope.event == "project_created"
    assert envelope.event_id == "evt_7"
    assert envelope.sequence == 7
    assert envelope.data["project_id"] == "proj_1"


def test_normalize_control_message_keys_handles_nested_lists() -> None:
    normalized = normalize_control_message_keys(
        {
            "requestId": "req_nested",
            "request": {
                "subtype": "initialize",
                "sdkMcpServers": ["github"],
                "jsonSchema": {"projectId": {"type": "string"}},
            },
        }
    )

    assert normalized["request_id"] == "req_nested"
    assert normalized["request"]["sdk_mcp_servers"] == ["github"]
    assert "json_schema" in normalized["request"]
    assert normalized["request"]["json_schema"]["project_id"]["type"] == "string"


def test_bounded_message_id_set_evicts_oldest_values() -> None:
    ids = BoundedMessageIdSet(2)

    ids.add("first")
    ids.add("second")
    ids.add("third")

    assert ids.has("first") is False
    assert ids.has("second") is True
    assert ids.has("third") is True
