"""Tests for the SSE event stream route helpers."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from autopilot.api.routes.events import _event_generator


def _write_event_log(path: Path, *records: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


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
    assert "id: req_2" in frames[1]
    assert "event: control_response" in frames[1]
    assert '"type": "control_response"' in frames[1]
    assert '"request_id": "req_2"' in frames[1]


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
