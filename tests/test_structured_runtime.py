"""Tests for structured runtime context isolation."""

from __future__ import annotations

import io
import threading

from autopilot.core.structured_io import StructuredIO
from autopilot.core.structured_runtime import activate_structured_io, get_active_structured_io


def test_structured_runtime_isolation_keeps_active_runtime_local_to_current_thread() -> None:
    runtime = StructuredIO(session_id="sess_main", input_stream=io.StringIO(""), output_stream=io.StringIO())
    observed: dict[str, str | None] = {"worker": "unset"}

    def inspect_other_thread() -> None:
        current = get_active_structured_io()
        observed["worker"] = None if current is None else current.session_id

    activate_structured_io(runtime)
    try:
        worker = threading.Thread(target=inspect_other_thread)
        worker.start()
        worker.join(timeout=1.0)
        current = get_active_structured_io()
    finally:
        activate_structured_io(None)
        runtime.close()

    assert current is runtime
    assert observed["worker"] is None
