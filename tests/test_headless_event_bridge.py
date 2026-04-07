"""Tests for background headless event-log control bridging."""

from __future__ import annotations

import json
import time
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.headless_control import create_headless_control_session
from autopilot.core.headless_event_bridge import HeadlessEventLogControlBridge, append_event_log_message
from autopilot.core.project_store import ensure_project_state, normalize_prd, register_project, save_project_prd, save_project_state
from autopilot.core.runtime_agent_tasks import create_or_reuse_runtime_agent_task, refresh_runtime_agent_task


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


def test_headless_event_log_control_bridge_processes_live_log_requests(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _create_project(config, tmp_path / "project_live_logs")
    log_path = config.autopilot_home / "logs" / "bridge-live.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line 1\nline 2\nline 3\n", encoding="utf-8")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="sess_bg_live",
        runtime_agent_ids=["proj_bridge_runtime:1:worker:a"],
        output_path=str(log_path),
    )
    save_project_prd(
        project,
        normalize_prd(
            {
                "title": "Bridge Live Project",
                "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
            }
        ),
    )
    save_project_state(
        config,
        str(project["id"]),
        {
            "status": "running",
            "paused": False,
            "runtime_session_id": "sess_bg_live",
            "log_path": str(log_path),
        },
    )
    refreshed = refresh_runtime_agent_task(config, task.id)
    session = create_headless_control_session(config, project_entry=project, session_id="sess_bg_live")
    bridge = HeadlessEventLogControlBridge(config=config, session=session, poll_interval_sec=0.05)
    bridge.start()
    try:
        append_event_log_message(
            config,
            {
                "type": "control_request",
                "request_id": "req_task_live",
                "request": {
                    "subtype": "get_runtime_agent_task_output_live",
                    "task_id": refreshed.id,
                    "tail_lines": 2,
                },
                "session_id": "sess_bg_live",
                "project_id": project["id"],
            },
        )
        append_event_log_message(
            config,
            {
                "type": "control_request",
                "request_id": "req_project_log",
                "request": {
                    "subtype": "get_project_runtime_log",
                    "offset": 7,
                    "max_bytes": 6,
                },
                "session_id": "sess_bg_live",
                "project_id": project["id"],
            },
        )

        deadline = time.time() + 2.0
        task_payload: dict[str, object] | None = None
        log_payload: dict[str, object] | None = None
        while time.time() < deadline:
            if config.events_log_path.exists():
                lines = [json.loads(line) for line in config.events_log_path.read_text().splitlines() if line.strip()]
                task_payload = next(
                    (
                        item
                        for item in lines
                        if item.get("type") == "control_response"
                        and ((item.get("response") or {}).get("request_id") == "req_task_live")
                    ),
                    None,
                )
                log_payload = next(
                    (
                        item
                        for item in lines
                        if item.get("type") == "control_response"
                        and ((item.get("response") or {}).get("request_id") == "req_project_log")
                    ),
                    None,
                )
                if task_payload is not None and log_payload is not None:
                    break
            time.sleep(0.05)

        assert task_payload is not None
        assert task_payload["response"]["subtype"] == "success"
        output = task_payload["response"]["response"]["output"]
        assert output["task_id"] == refreshed.id
        assert output["status"] == "live"
        assert output["source_path"] == str(log_path)
        assert "line 1" not in output["content"]
        assert "line 2" in output["content"]
        assert "line 3" in output["content"]

        assert log_payload is not None
        assert log_payload["response"]["subtype"] == "success"
        runtime_log = log_payload["response"]["response"]["runtime_log"]
        assert runtime_log["project_id"] == project["id"]
        assert runtime_log["status"] == "live"
        assert runtime_log["content"] == "line 2"
        assert runtime_log["content_offset"] == 7
        assert runtime_log["content_next_offset"] == 13
    finally:
        bridge.close()
