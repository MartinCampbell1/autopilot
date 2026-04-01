"""Server-Sent Events broadcaster for live dashboard updates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator

from autopilot.core.control_messages import format_sse_frame

@dataclass
class SSEEvent:
    event: str
    data: dict
    event_id: str | None = None


class SSEBroadcaster:
    """Manage SSE subscribers and broadcast events to them."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []
        self._sequence = 0

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield format_sse_frame(
                    event.event,
                    event.data,
                    event_id=event.event_id,
                )
        finally:
            self._queues.remove(queue)

    async def broadcast(self, event: str, data: dict) -> None:
        """Broadcast one event to all subscribers."""
        self._sequence += 1
        sse_event = SSEEvent(
            event=event,
            data=data,
            event_id=str(data.get("event_id") or data.get("id") or f"evt_{self._sequence}"),
        )
        for queue in self._queues:
            await queue.put(sse_event)


broadcaster = SSEBroadcaster()
