"""Structured NDJSON I/O for headless/runtime control channels."""

from __future__ import annotations

import json
import os
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, IO

from autopilot.core.control_messages import (
    BoundedMessageIdSet,
    ControlRequestEnvelope,
    ControlRequestPayload,
    ControlResponseEnvelope,
    build_structured_event_envelope,
    format_sse_frame,
    make_result_message,
    normalize_control_message_keys,
    parse_control_message,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_structured_session_id(prefix: str = "headless") -> str:
    """Build one opaque session id for a structured runtime stream."""

    normalized = prefix.strip().replace(" ", "_") or "headless"
    return f"{normalized}_{uuid.uuid4().hex[:12]}"


@dataclass
class PendingStructuredRequest:
    """One open control request waiting for a correlated control_response."""

    request: ControlRequestEnvelope
    _ready: threading.Event = field(default_factory=threading.Event)
    _response: dict[str, Any] | None = None
    _error: str | None = None

    def resolve(self, response: dict[str, Any]) -> None:
        self._response = dict(response)
        self._ready.set()

    def reject(self, error: str) -> None:
        self._error = str(error)
        self._ready.set()

    def result(self, timeout: float | None = None) -> dict[str, Any]:
        """Block until the request resolves or times out."""

        if not self._ready.wait(timeout):
            raise TimeoutError(f"Timed out waiting for control response `{self.request.request_id}`.")
        if self._error is not None:
            raise RuntimeError(self._error)
        return dict(self._response or {})


class StructuredIO:
    """Thin NDJSON runtime for control requests, events, and result envelopes."""

    def __init__(
        self,
        *,
        session_id: str | None = None,
        input_stream: IO[str] | None = None,
        output_stream: IO[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.session_id = session_id or build_structured_session_id()
        self.input_stream = input_stream if input_stream is not None else sys.stdin
        self.output_stream = output_stream if output_stream is not None else sys.stdout
        self.metadata = dict(metadata or {})
        self._pending_requests: dict[str, PendingStructuredRequest] = {}
        self._pending_lock = threading.RLock()
        self._output_lock = threading.RLock()
        self._sequence_lock = threading.Lock()
        self._sequence = 0
        self._closed = False
        self._reader_thread: threading.Thread | None = None
        self._seen_response_ids = BoundedMessageIdSet(1024)
        self._unexpected_response_callback: Callable[[ControlResponseEnvelope], None] | None = None
        self._on_control_request_sent: Callable[[ControlRequestEnvelope], None] | None = None
        self._on_control_request_resolved: Callable[[str], None] | None = None
        self._on_control_request_received: Callable[[ControlRequestEnvelope], None] | None = None

    @property
    def pending_requests(self) -> list[ControlRequestEnvelope]:
        """Return the current open control requests."""

        with self._pending_lock:
            return [pending.request for pending in self._pending_requests.values()]

    def set_unexpected_response_callback(
        self,
        callback: Callable[[ControlResponseEnvelope], None] | None,
    ) -> None:
        self._unexpected_response_callback = callback

    def set_on_control_request_sent(
        self,
        callback: Callable[[ControlRequestEnvelope], None] | None,
    ) -> None:
        self._on_control_request_sent = callback

    def set_on_control_request_resolved(
        self,
        callback: Callable[[str], None] | None,
    ) -> None:
        self._on_control_request_resolved = callback

    def set_on_control_request_received(
        self,
        callback: Callable[[ControlRequestEnvelope], None] | None,
    ) -> None:
        self._on_control_request_received = callback

    def _next_sequence(self) -> int:
        with self._sequence_lock:
            self._sequence += 1
            return self._sequence

    def _write_message(self, payload: dict[str, Any]) -> None:
        with self._output_lock:
            self.output_stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self.output_stream.flush()

    def emit_event(
        self,
        event: str,
        *,
        data: dict[str, Any],
        source: str = "headless",
    ) -> dict[str, Any]:
        """Emit one structured event envelope."""

        sequence = self._next_sequence()
        envelope = build_structured_event_envelope(
            {
                "event": event,
                **data,
                "session_id": self.session_id,
            },
            sequence=sequence,
            source=source,
        )
        payload = envelope.model_dump(exclude_none=True)
        self._write_message(payload)
        return payload

    def emit_result(
        self,
        summary: dict[str, Any],
        *,
        is_error: bool = False,
    ) -> dict[str, Any]:
        """Emit one structured result envelope."""

        message = make_result_message(
            self.session_id,
            result=str(summary.get("kind") or summary.get("status") or ""),
            is_error=is_error,
            summary=dict(summary),
            timestamp=str(summary.get("timestamp") or _utcnow_iso()),
        )
        payload = message.model_dump(exclude_none=True)
        self._write_message(payload)
        return payload

    def emit_control_response(
        self,
        response: ControlResponseEnvelope | dict[str, Any],
    ) -> dict[str, Any]:
        """Emit one canonical control_response envelope."""

        parsed = response if isinstance(response, ControlResponseEnvelope) else parse_control_message(response)
        if not isinstance(parsed, ControlResponseEnvelope):
            raise ValueError("Structured IO expected a control_response envelope.")
        payload = parsed.model_dump(exclude_none=True)
        self._write_message(payload)
        return payload

    def open_request(
        self,
        request: ControlRequestPayload | dict[str, Any],
        *,
        request_id: str | None = None,
    ) -> PendingStructuredRequest:
        """Create and emit one correlated control_request without waiting."""

        if self._closed:
            raise RuntimeError("Structured IO stream is closed.")
        payload = (
            request.model_dump(exclude_none=True)
            if hasattr(request, "model_dump")
            else normalize_control_message_keys(dict(request))
        )
        envelope = ControlRequestEnvelope(
            type="control_request",
            request_id=request_id or str(uuid.uuid4()),
            request=payload,
            session_id=self.session_id,
        )
        pending = PendingStructuredRequest(request=envelope)
        with self._pending_lock:
            if envelope.request_id in self._pending_requests:
                raise ValueError(f"Duplicate control request id: {envelope.request_id}")
            self._pending_requests[envelope.request_id] = pending
        self._write_message(envelope.model_dump(exclude_none=True))
        if self._on_control_request_sent is not None:
            self._on_control_request_sent(envelope)
        return pending

    def send_request(
        self,
        request: ControlRequestPayload | dict[str, Any],
        *,
        timeout: float | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Emit one correlated control_request and wait for its response."""

        pending = self.open_request(request, request_id=request_id)
        return pending.result(timeout=timeout)

    def cancel_request(self, request_id: str, *, error: str = "Request cancelled.") -> None:
        """Cancel one open request locally and notify the peer."""

        normalized = str(request_id or "").strip()
        if not normalized:
            return
        with self._pending_lock:
            pending = self._pending_requests.pop(normalized, None)
        if pending is None:
            return
        pending.reject(error)
        self._write_message(
            {
                "type": "control_cancel_request",
                "request_id": normalized,
            }
        )

    def inject_control_response(self, response: ControlResponseEnvelope | dict[str, Any]) -> bool:
        """Resolve one pending request from an explicit control_response payload."""

        parsed = response if isinstance(response, ControlResponseEnvelope) else parse_control_message(response)
        if not isinstance(parsed, ControlResponseEnvelope):
            return False
        request_id = parsed.response.request_id
        self._seen_response_ids.add(request_id)
        with self._pending_lock:
            pending = self._pending_requests.pop(request_id, None)
        if pending is None:
            if self._unexpected_response_callback is not None:
                self._unexpected_response_callback(parsed)
            return False
        if parsed.response.subtype == "error":
            pending.reject(parsed.response.error)
        else:
            pending.resolve(dict(parsed.response.response))
        if self._on_control_request_resolved is not None:
            self._on_control_request_resolved(request_id)
        return True

    def process_input_line(self, line: str) -> ControlRequestEnvelope | ControlResponseEnvelope | dict[str, Any] | None:
        """Parse and route one inbound NDJSON line."""

        raw = str(line or "").strip()
        if not raw:
            return None
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return None
        normalized = normalize_control_message_keys(payload)
        parsed = parse_control_message(normalized)
        if isinstance(parsed, ControlResponseEnvelope):
            self.inject_control_response(parsed)
            return parsed
        if isinstance(parsed, ControlRequestEnvelope):
            if self._on_control_request_received is not None:
                self._on_control_request_received(parsed)
            return parsed
        message_type = str(normalized.get("type") or "").strip()
        if message_type == "keep_alive":
            return None
        if message_type == "update_environment_variables":
            for key, value in dict(normalized.get("variables") or {}).items():
                os.environ[str(key)] = str(value)
            return normalized
        return normalized

    def _reader_loop(self) -> None:
        try:
            while not self._closed:
                try:
                    line = self.input_stream.readline()
                except Exception:
                    break
                if line == "":
                    break
                self.process_input_line(line)
        finally:
            self._closed = True
            with self._pending_lock:
                pending = list(self._pending_requests.values())
                self._pending_requests.clear()
            for request in pending:
                request.reject("Structured IO input stream closed before response was received.")

    def start_reader_thread(self) -> threading.Thread:
        """Start a daemon thread that consumes inbound NDJSON control messages."""

        if self._reader_thread is not None and self._reader_thread.is_alive():
            return self._reader_thread
        thread = threading.Thread(
            target=self._reader_loop,
            name=f"structured-io-{self.session_id}",
            daemon=True,
        )
        thread.start()
        self._reader_thread = thread
        return thread

    def close(self) -> None:
        """Close the structured stream and reject any pending requests."""

        self._closed = True
        with self._pending_lock:
            pending = list(self._pending_requests.values())
            self._pending_requests.clear()
        for request in pending:
            request.reject("Structured IO stream closed.")


__all__ = [
    "PendingStructuredRequest",
    "StructuredIO",
    "build_structured_session_id",
    "format_sse_frame",
]
