"""Global structured runtime registry without CLI dependencies."""

from __future__ import annotations

from contextvars import ContextVar

from autopilot.core.structured_io import StructuredIO

_ACTIVE_STRUCTURED_IO: ContextVar[StructuredIO | None] = ContextVar(
    "autopilot_active_structured_io",
    default=None,
)


def get_active_structured_io() -> StructuredIO | None:
    """Return the active structured runtime for the current execution context."""

    return _ACTIVE_STRUCTURED_IO.get()


def activate_structured_io(io: StructuredIO | None) -> None:
    """Register or clear the structured runtime for the current execution context."""

    _ACTIVE_STRUCTURED_IO.set(io)
