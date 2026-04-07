"""Unit tests for structured control-message helpers."""

from __future__ import annotations

from autopilot.core.control_messages import (
    BoundedMessageIdSet,
    build_sse_replay_id,
    build_structured_event_envelope,
    make_control_error_response,
    make_control_success_response,
    normalize_control_message_keys,
    parse_control_message,
    parse_sse_replay_sequence,
    resolve_control_event_id,
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


def test_parse_control_message_supports_runtime_agent_task_artifact_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_task_output",
            "request": {
                "subtype": "get_runtime_agent_task_output",
                "taskId": "rat_123",
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "get_runtime_agent_task_output"
    assert parsed.request.task_id == "rat_123"
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_runtime_agent_task_live_output_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_task_output_live",
            "request": {
                "subtype": "get_runtime_agent_task_output_live",
                "taskId": "rat_123",
                "offset": 64,
                "maxBytes": 1024,
                "tailLines": 25,
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "get_runtime_agent_task_output_live"
    assert parsed.request.task_id == "rat_123"
    assert parsed.request.offset == 64
    assert parsed.request.max_bytes == 1024
    assert parsed.request.tail_lines == 25
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_project_runtime_log_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_project_runtime_log",
            "request": {
                "subtype": "get_project_runtime_log",
                "offset": 32,
                "maxBytes": 2048,
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "get_project_runtime_log"
    assert parsed.request.offset == 32
    assert parsed.request.max_bytes == 2048
    assert parsed.request.tail_lines is None
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_runtime_agent_task_wait_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_task_wait",
            "request": {
                "subtype": "get_runtime_agent_task",
                "taskId": "rat_123",
                "waitForAsyncSettlement": True,
                "runtimeAgentId": "runtime-agent-1",
                "waitTimeoutMs": 250,
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "get_runtime_agent_task"
    assert parsed.request.task_id == "rat_123"
    assert parsed.request.wait_for_async_settlement is True
    assert parsed.request.runtime_agent_id == "runtime-agent-1"
    assert parsed.request.wait_timeout_ms == 250
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_runtime_agent_action_run_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_run",
            "request": {
                "subtype": "get_runtime_agent_action_run",
                "runId": "aar_123",
                "waitForAsyncSettlement": True,
                "runtimeAgentId": "runtime-agent-1",
                "waitTimeoutMs": 250,
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "get_runtime_agent_action_run"
    assert parsed.request.run_id == "aar_123"
    assert parsed.request.wait_for_async_settlement is True
    assert parsed.request.runtime_agent_id == "runtime-agent-1"
    assert parsed.request.wait_timeout_ms == 250
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_runtime_agent_action_run_cancel_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_cancel_run",
            "request": {
                "subtype": "cancel_runtime_agent_action_run",
                "runId": "aar_123",
                "actor": "martin",
                "note": "Stop async follow-through.",
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "cancel_runtime_agent_action_run"
    assert parsed.request.run_id == "aar_123"
    assert parsed.request.actor == "martin"
    assert parsed.request.note == "Stop async follow-through."
    assert parsed.session_id == "sess_1"


def test_parse_control_message_supports_runtime_agent_listing_requests() -> None:
    parsed = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_list_runs",
            "request": {
                "subtype": "list_runtime_agent_action_runs",
                "orchestratorSessionId": "sess_1",
                "status": "ok",
                "dryRun": False,
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed is not None
    assert parsed.type == "control_request"
    assert parsed.request.subtype == "list_runtime_agent_action_runs"
    assert parsed.request.orchestrator_session_id == "sess_1"
    assert parsed.request.status == "ok"
    assert parsed.request.dry_run is False

    parsed_tasks = parse_control_message(
        {
            "type": "control_request",
            "requestId": "req_list_tasks",
            "request": {
                "subtype": "list_runtime_agent_tasks",
                "runtimeAgentId": "runtime-agent-1",
                "agentActionRunId": "aar_123",
            },
            "sessionId": "sess_1",
        }
    )

    assert parsed_tasks is not None
    assert parsed_tasks.type == "control_request"
    assert parsed_tasks.request.subtype == "list_runtime_agent_tasks"
    assert parsed_tasks.request.runtime_agent_id == "runtime-agent-1"
    assert parsed_tasks.request.agent_action_run_id == "aar_123"


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


def test_resolve_control_event_id_distinguishes_request_and_response() -> None:
    request_id = resolve_control_event_id(
        {
            "type": "control_request",
            "request_id": "req_control_1",
            "request": {"subtype": "interrupt"},
        },
        1,
    )
    response_id = resolve_control_event_id(
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "req_control_1",
                "response": {"accepted": True},
            },
        },
        2,
    )

    assert request_id == "req_control_1:request"
    assert response_id == "req_control_1:response"


def test_sse_replay_id_round_trips_sequence() -> None:
    replay_id = build_sse_replay_id(42)

    assert replay_id == "evt_42"
    assert parse_sse_replay_sequence(replay_id) == 42
    assert parse_sse_replay_sequence("42") == 42
    assert parse_sse_replay_sequence("req_control_1:response") is None


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
