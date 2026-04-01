"""SSE event stream route backed by the filesystem event log."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from autopilot.api.deps import get_config
from autopilot.core.control_messages import (
    build_structured_event_envelope,
    format_sse_frame,
    parse_control_message,
    resolve_control_event_id,
)

router = APIRouter()


def _load_event_record(line: str) -> dict | None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _render_sse_event(payload: dict, *, sequence: int, structured: bool) -> str:
    parsed_control = parse_control_message(payload)
    event_name = str(payload.get("event") or getattr(parsed_control, "type", "project_event"))
    event_id = resolve_control_event_id(payload, sequence)
    if structured:
        data = (
            parsed_control.model_dump(exclude_none=True)
            if parsed_control is not None
            else build_structured_event_envelope(payload, sequence=sequence).model_dump(exclude_none=True)
        )
    else:
        data = payload
    return format_sse_frame(event_name, data, event_id=event_id)


async def _event_generator(path: Path, *, structured: bool = False, from_sequence: int | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    with path.open("r", encoding="utf-8") as handle:
        sequence = 0
        if from_sequence is None:
            handle.seek(0, 2)
        else:
            for line in handle:
                sequence += 1
                if sequence <= from_sequence:
                    continue
                payload = _load_event_record(line)
                if payload is None:
                    continue
                yield _render_sse_event(payload, sequence=sequence, structured=structured)
        while True:
            line = handle.readline()
            if not line:
                yield ": ping\n\n"
                await asyncio.sleep(1)
                continue

            sequence += 1
            payload = _load_event_record(line)
            if payload is None:
                continue
            yield _render_sse_event(payload, sequence=sequence, structured=structured)


@router.get("/")
async def event_stream(
    structured: bool = Query(default=False),
    from_sequence: int | None = Query(default=None, ge=0),
) -> StreamingResponse:
    config = get_config()
    return StreamingResponse(
        _event_generator(
            config.events_log_path,
            structured=structured,
            from_sequence=from_sequence,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
