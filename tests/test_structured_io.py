"""Tests for structured NDJSON runtime I/O."""

from __future__ import annotations

import io
import json
import os
import threading

from autopilot.core.structured_io import StructuredIO


def test_structured_io_send_request_round_trips_control_response() -> None:
    output = io.StringIO()
    runtime = StructuredIO(session_id="sess_test", input_stream=io.StringIO(""), output_stream=output)

    result_holder: dict[str, object] = {}

    def _send_request() -> None:
        result_holder["result"] = runtime.send_request(
            {"subtype": "get_context_usage"},
            timeout=1.0,
            request_id="req_123",
        )

    thread = threading.Thread(target=_send_request)
    thread.start()
    while '"request_id": "req_123"' not in output.getvalue():
        pass
    injected = runtime.inject_control_response(
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "req_123",
                "response": {"totalTokens": 128},
            },
        }
    )
    thread.join(timeout=1.0)

    assert injected is True
    assert result_holder["result"] == {"total_tokens": 128}
    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert lines[0]["type"] == "control_request"
    assert lines[0]["request"]["subtype"] == "get_context_usage"
    assert runtime.pending_requests == []


def test_structured_io_process_input_line_applies_environment_updates() -> None:
    output = io.StringIO()
    runtime = StructuredIO(session_id="sess_test", input_stream=io.StringIO(""), output_stream=output)
    os.environ.pop("AUTOPILOT_TEST_STRUCTURED_IO", None)

    payload = runtime.process_input_line(
        json.dumps(
            {
                "type": "update_environment_variables",
                "variables": {"AUTOPILOT_TEST_STRUCTURED_IO": "enabled"},
            }
        )
    )

    assert payload is not None
    assert os.environ["AUTOPILOT_TEST_STRUCTURED_IO"] == "enabled"


def test_structured_io_emits_event_and_result_envelopes() -> None:
    output = io.StringIO()
    runtime = StructuredIO(session_id="sess_test", input_stream=io.StringIO(""), output_stream=output)

    event_payload = runtime.emit_event(
        "run_started",
        data={"project_id": "proj_1", "message": "Started."},
    )
    result_payload = runtime.emit_result(
        {"kind": "run_summary", "project_id": "proj_1", "exit_code": 0},
        is_error=False,
    )

    lines = [json.loads(line) for line in output.getvalue().splitlines()]
    assert event_payload["type"] == "event"
    assert event_payload["event"] == "run_started"
    assert event_payload["session_id"] == "sess_test"
    assert lines[1]["type"] == "result"
    assert result_payload["summary"]["project_id"] == "proj_1"
    assert result_payload["is_error"] is False
