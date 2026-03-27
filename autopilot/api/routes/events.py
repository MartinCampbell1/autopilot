"""SSE event stream route backed by the filesystem event log."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from autopilot.api.deps import get_config

router = APIRouter()


async def _event_generator(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)

    with path.open("r", encoding="utf-8") as handle:
        handle.seek(0, 2)
        while True:
            line = handle.readline()
            if not line:
                yield ": ping\n\n"
                await asyncio.sleep(1)
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_name = event.get("event", "project_event")
            yield f"event: {event_name}\ndata: {json.dumps(event)}\n\n"


@router.get("/")
async def event_stream() -> StreamingResponse:
    config = get_config()
    return StreamingResponse(
        _event_generator(config.events_log_path),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
