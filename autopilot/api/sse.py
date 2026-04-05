"""Server-Sent Events broadcaster for live dashboard updates."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import AsyncGenerator

from autopilot.core.control_messages import build_sse_replay_id, format_sse_frame, parse_sse_replay_sequence

@dataclass
class SSEEvent:
    event: str
    data: dict
    sequence: int
    event_id: str | None = None


class SSEBroadcaster:
    """Manage SSE subscribers and broadcast events to them."""

    def __init__(self, *, replay_capacity: int = 256):
        self._queues: list[asyncio.Queue] = []
        self._sequence = 0
        self._replay_capacity = max(1, int(replay_capacity))
        self._replay_buffer: list[SSEEvent] = []

    async def subscribe(
        self,
        *,
        from_sequence: int | None = None,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Subscribe to the event stream."""
        queue: asyncio.Queue = asyncio.Queue()
        replay_events = self._select_replay_events(from_sequence=from_sequence, last_event_id=last_event_id)
        self._queues.append(queue)
        try:
            for event in replay_events:
                yield format_sse_frame(
                    event.event,
                    event.data,
                    event_id=event.event_id,
                )
            while True:
                event = await queue.get()
                yield format_sse_frame(
                    event.event,
                    event.data,
                    event_id=event.event_id,
                )
        finally:
            self._queues.remove(queue)

    def _select_replay_events(
        self,
        *,
        from_sequence: int | None = None,
        last_event_id: str | None = None,
    ) -> list[SSEEvent]:
        if from_sequence is not None:
            return [event for event in self._replay_buffer if event.sequence > from_sequence]
        parsed_sequence = parse_sse_replay_sequence(last_event_id)
        if parsed_sequence is not None:
            return [event for event in self._replay_buffer if event.sequence > parsed_sequence]
        normalized_event_id = str(last_event_id or "").strip()
        if not normalized_event_id:
            return []
        start_index = -1
        for index, event in enumerate(self._replay_buffer):
            if event.event_id == normalized_event_id:
                start_index = index
        if start_index >= 0:
            return self._replay_buffer[start_index + 1 :]
        return list(self._replay_buffer)

    def _remember_event(self, event: SSEEvent) -> None:
        self._replay_buffer.append(event)
        overflow = len(self._replay_buffer) - self._replay_capacity
        if overflow > 0:
            del self._replay_buffer[:overflow]

    async def broadcast(self, event: str, data: dict) -> None:
        """Broadcast one event to all subscribers."""
        self._sequence += 1
        payload = dict(data)
        event_id = str(payload.get("event_id") or payload.get("id") or build_sse_replay_id(self._sequence))
        payload.setdefault("event_id", event_id)
        payload.setdefault("sequence", self._sequence)
        sse_event = SSEEvent(
            event=event,
            data=payload,
            sequence=self._sequence,
            event_id=event_id,
        )
        self._remember_event(sse_event)
        for queue in self._queues:
            await queue.put(sse_event)


broadcaster = SSEBroadcaster()
