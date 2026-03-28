"""Autopilot - Autonomous AI Programmer Platform."""

from __future__ import annotations

import os

# Pydantic's entry-point plugin scan can stall startup on this Python/toolchain mix.
# Autopilot does not rely on third-party Pydantic plugins, so disable auto-loading.
os.environ.setdefault("PYDANTIC_DISABLE_PLUGINS", "__all__")

__version__ = "0.1.0"
