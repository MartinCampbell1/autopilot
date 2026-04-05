"""Shared atomic file writes for durable Autopilot state."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml


def atomic_write_text(path: Path, contents: str, *, encoding: str = "utf-8") -> None:
    """Persist one text payload via a unique temp file and atomic replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def atomic_write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    """Persist one JSON payload with stable formatting."""

    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def atomic_write_yaml(path: Path, payload: dict[str, Any]) -> None:
    """Persist one YAML payload with stable formatting."""

    atomic_write_text(path, yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
