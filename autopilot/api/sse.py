"""Server-Sent Events broadcaster for live dashboard updates."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import AsyncGenerator


@dataclass
class SSEEvent:
    event: str
    data: dict


class SSEBroadcaster:
    """Manage SSE subscribers and broadcast events to them."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield f"event: {event.event}\ndata: {json.dumps(event.data)}\n\n"
        finally:
            self._queues.remove(queue)

    async def broadcast(self, event: str, data: dict) -> None:
        """Broadcast one event to all subscribers."""
        sse_event = SSEEvent(event=event, data=data)
        for queue in self._queues:
            await queue.put(sse_event)


broadcaster = SSEBroadcaster()
