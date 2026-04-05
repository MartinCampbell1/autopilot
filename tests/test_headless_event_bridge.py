"""Tests for background headless event-log control bridging."""

from __future__ import annotations

import json
import time
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.headless_control import create_headless_control_session
from autopilot.core.headless_event_bridge import HeadlessEventLogControlBridge, append_event_log_message
from autopilot.core.project_store import ensure_project_state, normalize_prd, register_project, save_project_prd


def _create_project(config: AutopilotConfig, root: Path) -> dict:
    root.mkdir(parents=True, exist_ok=True)
    project = register_project(config, name="Bridge Project", project_path=root)
    save_project_prd(
        project,
        normalize_prd(
            {
                "title": "Bridge Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            }
        ),
    )
    ensure_project_state(config, project, seed_mode="new")
    return project


def test_headless_event_log_control_bridge_processes_targeted_requests(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project")
    session = create_headless_control_session(config, project_entry=project, session_id="sess_bg")
    bridge = HeadlessEventLogControlBridge(config=config, session=session, poll_interval_sec=0.05)
    bridge.start()
    try:
        append_event_log_message(
            config,
            {
                "type": "control_request",
                "request_id": "req_initialize",
                "request": {"subtype": "initialize"},
                "session_id": "sess_bg",
                "project_id": project["id"],
            },
        )

        deadline = time.time() + 2.0
        response_payload: dict[str, object] | None = None
        while time.time() < deadline:
            if config.events_log_path.exists():
                lines = [json.loads(line) for line in config.events_log_path.read_text().splitlines() if line.strip()]
                response_payload = next(
                    (
                        item
                        for item in lines
                        if item.get("type") == "control_response"
                        and ((item.get("response") or {}).get("request_id") == "req_initialize")
                    ),
                    None,
                )
                if response_payload is not None:
                    break
            time.sleep(0.05)

        assert response_payload is not None
        assert response_payload["runtime_session_id"] == "sess_bg"
        assert response_payload["response"]["subtype"] == "success"
        assert response_payload["response"]["response"]["session"]["project_id"] == project["id"]
    finally:
        bridge.close()


def test_headless_event_log_control_bridge_replays_pending_requests_queued_before_start(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project_replay")
    append_event_log_message(
        config,
        {
            "type": "control_request",
            "request_id": "req_prestart",
            "request": {"subtype": "initialize"},
            "session_id": "sess_bg_replay",
            "project_id": project["id"],
        },
    )

    session = create_headless_control_session(config, project_entry=project, session_id="sess_bg_replay")
    bridge = HeadlessEventLogControlBridge(config=config, session=session, poll_interval_sec=0.05)
    bridge.start()
    try:
        deadline = time.time() + 2.0
        response_payload: dict[str, object] | None = None
        while time.time() < deadline:
            if config.events_log_path.exists():
                lines = [json.loads(line) for line in config.events_log_path.read_text().splitlines() if line.strip()]
                response_payload = next(
                    (
                        item
                        for item in lines
                        if item.get("type") == "control_response"
                        and ((item.get("response") or {}).get("request_id") == "req_prestart")
                    ),
                    None,
                )
                if response_payload is not None:
                    break
            time.sleep(0.05)

        assert response_payload is not None
        assert response_payload["response"]["subtype"] == "success"
        assert response_payload["response"]["response"]["session"]["project_id"] == project["id"]
    finally:
        bridge.close()


def test_headless_event_log_control_bridge_skips_prestart_requests_that_already_have_response(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project_replay_resolved")
    append_event_log_message(
        config,
        {
            "type": "control_request",
            "request_id": "req_prestart_resolved",
            "request": {"subtype": "initialize"},
            "session_id": "sess_bg_replay_resolved",
            "project_id": project["id"],
        },
    )
    append_event_log_message(
        config,
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "req_prestart_resolved",
                "response": {"accepted": True},
            },
            "session_id": "sess_bg_replay_resolved",
            "project_id": project["id"],
        },
    )

    session = create_headless_control_session(config, project_entry=project, session_id="sess_bg_replay_resolved")
    bridge = HeadlessEventLogControlBridge(config=config, session=session, poll_interval_sec=0.05)
    bridge.start()
    try:
        time.sleep(0.2)
        lines = [json.loads(line) for line in config.events_log_path.read_text().splitlines() if line.strip()]
        matching_responses = [
            item
            for item in lines
            if item.get("type") == "control_response"
            and ((item.get("response") or {}).get("request_id") == "req_prestart_resolved")
        ]

        assert len(matching_responses) == 1
    finally:
        bridge.close()
