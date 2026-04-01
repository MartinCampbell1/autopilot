"""Global structured runtime registry without CLI dependencies."""

from __future__ import annotations

import threading

from autopilot.core.structured_io import StructuredIO

_STRUCTURED_IO_LOCK = threading.RLock()
_ACTIVE_STRUCTURED_IO: StructuredIO | None = None


def get_active_structured_io() -> StructuredIO | None:
    """Return the current global structured headless runtime, if any."""

    with _STRUCTURED_IO_LOCK:
        return _ACTIVE_STRUCTURED_IO


def activate_structured_io(io: StructuredIO | None) -> None:
    """Register or clear the global structured headless runtime."""

    global _ACTIVE_STRUCTURED_IO
    with _STRUCTURED_IO_LOCK:
        _ACTIVE_STRUCTURED_IO = io
