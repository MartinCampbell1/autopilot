"""Tests for the SSE event stream route helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import events as events_routes
from autopilot.api.routes.events import (
    _event_generator,
    _event_matches_filters,
    _resolve_replay_sequence,
)
from autopilot.core.audit_chain import append_jsonl_audit_record
from autopilot.core.config import AutopilotConfig


def _write_event_log(path: Path, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(events_routes, "get_config", lambda: config)
    app = FastAPI()
    app.include_router(events_routes.router, prefix="/api/events")
    return TestClient(app)


def test_event_generator_replays_structured_frames_from_sequence_zero(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {
            "event": "project_created",
            "project_id": "proj_1",
            "timestamp": "2026-04-01T01:00:00+00:00",
        },
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "requestId": "req_2",
                "response": {"accepted": True},
            },
            "sessionId": "sess_2",
        },
    )

    async def _collect() -> list[str]:
        frames: list[str] = []
        generator = _event_generator(log_path, structured=True, from_sequence=0)
        try:
            frames.append(await generator.__anext__())
            frames.append(await generator.__anext__())
        finally:
            await generator.aclose()
        return frames

    frames = asyncio.run(_collect())

    assert "id: evt_1" in frames[0]
    assert 'event: project_created' in frames[0]
    assert '"type": "event"' in frames[0]
    assert '"sequence": 1' in frames[0]
    assert "id: req_2:response" in frames[1]
    assert "event: control_response" in frames[1]
    assert '"type": "control_response"' in frames[1]
    assert '"request_id": "req_2"' in frames[1]
    assert '"sequence": 2' in frames[1]
    assert '"event_id": "req_2:response"' in frames[1]


def test_event_generator_replays_only_frames_after_requested_sequence(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {"event": "project_created", "project_id": "proj_1"},
        {"event": "run_started", "project_id": "proj_1"},
    )

    async def _collect_one() -> str:
        generator = _event_generator(log_path, structured=False, from_sequence=1)
        try:
            return await generator.__anext__()
        finally:
            await generator.aclose()

    frame = asyncio.run(_collect_one())

    assert "event: run_started" in frame
    assert "project_created" not in frame


def test_event_generator_replays_only_frames_after_last_event_id(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {
            "type": "control_request",
            "request_id": "req_1",
            "request": {"subtype": "interrupt"},
            "session_id": "sess_1",
        },
        {
            "type": "control_response",
            "response": {
                "subtype": "success",
                "request_id": "req_1",
                "response": {"accepted": True},
            },
            "session_id": "sess_1",
        },
    )

    async def _collect_one() -> str:
        generator = _event_generator(log_path, structured=True, last_event_id="req_1:request")
        try:
            return await generator.__anext__()
        finally:
            await generator.aclose()

    frame = asyncio.run(_collect_one())

    assert "id: req_1:response" in frame
    assert "event: control_response" in frame
    assert '"accepted": true' in frame


def test_event_matches_filters_supports_execution_identifiers() -> None:
    payload = {
        "event": "execution_plane_agent_action_run_completed",
        "project_id": "proj_1",
        "runtime_agent_id": "agent_primary",
        "runtime_agent_ids": ["agent_primary", "agent_secondary"],
        "orchestrator_session_id": "sess_exec",
    }

    assert _event_matches_filters(payload, project_id="proj_1") is True
    assert _event_matches_filters(payload, runtime_agent_id="agent_secondary") is True
    assert _event_matches_filters(payload, orchestrator_session_id="sess_exec") is True
    assert _event_matches_filters(payload, project_id="proj_2") is False
    assert _event_matches_filters(payload, runtime_agent_id="agent_missing") is False
    assert _event_matches_filters(payload, orchestrator_session_id="sess_other") is False


def test_event_matches_filters_supports_initiative_and_orchestrator_snapshots() -> None:
    payload = {
        "event": "execution_plane_project_updated",
        "project_id": "proj_1",
    }
    snapshot_index = {
        "proj_1": {
            "initiative": {"id": "initiative_alpha"},
            "orchestration": {"orchestrator": "specialist"},
        }
    }

    assert _event_matches_filters(
        payload,
        initiative_id="initiative_alpha",
        snapshot_index=snapshot_index,
    ) is True
    assert _event_matches_filters(
        payload,
        orchestrator="specialist",
        snapshot_index=snapshot_index,
    ) is True
    assert _event_matches_filters(
        payload,
        initiative_id="initiative_beta",
        snapshot_index=snapshot_index,
    ) is False
    assert _event_matches_filters(
        payload,
        orchestrator="codex",
        snapshot_index=snapshot_index,
    ) is False


def test_event_generator_replays_only_matching_project_events(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {"event": "project_created", "project_id": "proj_1"},
        {"event": "run_started", "project_id": "proj_2"},
    )

    async def _collect_one() -> str:
        generator = _event_generator(log_path, structured=False, from_sequence=0, project_id="proj_2")
        try:
            return await generator.__anext__()
        finally:
            await generator.aclose()

    frame = asyncio.run(_collect_one())

    assert "event: run_started" in frame
    assert '"project_id": "proj_2"' in frame
    assert "project_created" not in frame


def test_event_generator_replays_only_matching_runtime_agent_events(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {
            "event": "execution_plane_issue_opened",
            "project_id": "proj_1",
            "runtime_agent_ids": ["agent_a"],
        },
        {
            "event": "execution_plane_issue_opened",
            "project_id": "proj_1",
            "runtime_agent_ids": ["agent_b"],
        },
    )

    async def _collect_one() -> str:
        generator = _event_generator(
            log_path,
            structured=False,
            from_sequence=0,
            runtime_agent_id="agent_b",
        )
        try:
            return await generator.__anext__()
        finally:
            await generator.aclose()

    frame = asyncio.run(_collect_one())

    assert '"runtime_agent_ids": ["agent_b"]' in frame
    assert "agent_a" not in frame


def test_event_generator_structured_frames_include_execution_context(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {
            "event": "run_started",
            "project_id": "proj_1",
            "timestamp": "2026-04-03T00:00:00+00:00",
        },
    )
    snapshot_index = {
        "proj_1": {
            "name": "Project One",
            "initiative": {"id": "initiative_alpha", "title": "Alpha"},
            "orchestration": {"orchestrator": "specialist", "project_ref": "proj-ref"},
        }
    }

    async def _collect_one() -> str:
        generator = _event_generator(
            log_path,
            structured=True,
            from_sequence=0,
            snapshot_index=snapshot_index,
        )
        try:
            return await generator.__anext__()
        finally:
            await generator.aclose()

    frame = asyncio.run(_collect_one())

    assert '"project_name": "Project One"' in frame
    assert '"initiative": {"id": "initiative_alpha", "title": "Alpha"}' in frame
    assert '"orchestration": {"orchestrator": "specialist", "project_ref": "proj-ref"}' in frame


def test_event_generator_dedupes_duplicate_event_ids_during_replay(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(
        log_path,
        {"event": "project_created", "event_id": "evt_dup", "project_id": "proj_1"},
        {"event": "project_created", "event_id": "evt_dup", "project_id": "proj_1"},
        {"event": "run_started", "event_id": "evt_next", "project_id": "proj_1"},
    )

    async def _collect_two() -> list[str]:
        frames: list[str] = []
        generator = _event_generator(log_path, structured=False, from_sequence=0)
        try:
            frames.append(await generator.__anext__())
            frames.append(await generator.__anext__())
        finally:
            await generator.aclose()
        return frames

    frames = asyncio.run(_collect_two())

    assert len(frames) == 2
    assert "id: evt_dup" in frames[0]
    assert "id: evt_next" in frames[1]


def test_resolve_replay_sequence_accepts_sequence_cursor_id(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    _write_event_log(log_path, {"event": "project_created", "project_id": "proj_1"})

    assert _resolve_replay_sequence(log_path, last_event_id="evt_7") == 7


def test_event_stream_audit_route_returns_packaged_bundle(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    append_jsonl_audit_record(
        config.events_log_path,
        {"event": "project_created", "project_id": "proj_1", "timestamp": "2026-04-02T00:00:00+00:00"},
        chain_kind="events",
        config=config,
    )
    append_jsonl_audit_record(
        config.events_log_path,
        {"event": "run_started", "project_id": "proj_1", "timestamp": "2026-04-02T00:01:00+00:00"},
        chain_kind="events",
        config=config,
    )

    response = client.get("/api/events/audit?limit=1")

    assert response.status_code == 200
    payload = response.json()["audit"]
    assert payload["audit_chain"]["verification"]["verified"] is True
    assert payload["audit_chain"]["source_verification"]["verified"] is True
    assert payload["audit_chain"]["entry_count"] == 1
    assert payload["audit_chain"]["source_entry_count"] == 2
    assert payload["entries"][0]["source_audit"]["chain_kind"] == "events"
