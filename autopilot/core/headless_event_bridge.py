"""Event-log bridge for background headless runtime control requests."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.control_messages import (
    BoundedMessageIdSet,
    ControlRequestEnvelope,
    ControlResponseEnvelope,
    parse_control_request_message,
)
from autopilot.core.headless_control import HeadlessControlSession


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_event_log_message(config: AutopilotConfig, payload: dict[str, Any]) -> dict[str, Any]:
    """Append one raw structured message to the shared event log."""

    path = config.events_log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return payload


@dataclass(slots=True)
class HeadlessEventLogControlBridge:
    """Watch the shared event log for targeted control requests and emit responses."""

    config: AutopilotConfig
    session: HeadlessControlSession
    poll_interval_sec: float = 0.2
    _stop: threading.Event = field(default_factory=threading.Event)
    _ready: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _seen_request_ids: BoundedMessageIdSet = field(default_factory=lambda: BoundedMessageIdSet(1024))

    def _event_log_path(self) -> Path:
        return self.config.events_log_path

    def _read_matching_request(self, line: str) -> ControlRequestEnvelope | None:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        request = parse_control_request_message(payload)
        if request is None:
            return None
        if str(request.session_id or "").strip() != self.session.session_id:
            return None
        if self._seen_request_ids.has(request.request_id):
            return None
        self._seen_request_ids.add(request.request_id)
        return request

    def _emit_response(self, response: ControlResponseEnvelope) -> None:
        append_event_log_message(
            self.config,
            {
                **response.model_dump(exclude_none=True),
                "timestamp": _utcnow_iso(),
                "project_id": self.session.project_id,
                "runtime_session_id": self.session.session_id,
                "source": "headless_event_log_control_bridge",
            },
        )

    def _loop(self) -> None:
        path = self._event_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)

        with path.open("r", encoding="utf-8") as handle:
            handle.seek(0, 2)
            self._ready.set()
            while not self._stop.is_set():
                line = handle.readline()
                if not line:
                    self._stop.wait(self.poll_interval_sec)
                    continue
                request = self._read_matching_request(line)
                if request is None:
                    continue
                response = self.session.handle_request(request)
                self._emit_response(response)

    def start(self) -> threading.Thread:
        """Start the background bridge thread if it is not already running."""

        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._stop.clear()
        self._ready.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"headless-event-bridge-{self.session.session_id}",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=max(self.poll_interval_sec * 4, 0.5))
        return self._thread

    def close(self) -> None:
        """Stop the bridge loop and wait briefly for shutdown."""

        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=max(self.poll_interval_sec * 4, 0.5))


__all__ = [
    "HeadlessEventLogControlBridge",
    "append_event_log_message",
]
