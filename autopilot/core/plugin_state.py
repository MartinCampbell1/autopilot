"""File-backed plugin enablement state."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class PluginEnablementRecord(BaseModel):
    """Persisted enablement preference for one installed plugin."""

    plugin_id: str
    enabled: bool = True
    updated_at: str


def load_plugin_enablement_registry(
    config: AutopilotConfig,
) -> dict[str, PluginEnablementRecord]:
    """Load all persisted plugin enablement preferences."""

    path = config.plugin_enablement_json_path
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}

    records: dict[str, PluginEnablementRecord] = {}
    for raw_item in payload.get("plugins", []):
        try:
            record = PluginEnablementRecord.model_validate(raw_item)
        except Exception:
            continue
        records[record.plugin_id] = record
    return records


def save_plugin_enablement_registry(
    config: AutopilotConfig,
    records: dict[str, PluginEnablementRecord],
) -> dict[str, PluginEnablementRecord]:
    """Persist plugin enablement preferences deterministically."""

    ordered = [records[key].model_dump() for key in sorted(records)]
    _atomic_write_json(config.plugin_enablement_json_path, {"plugins": ordered})
    return records


def plugin_enabled(
    config: AutopilotConfig,
    plugin_id: str,
    *,
    default: bool = True,
) -> bool:
    """Return the persisted enablement for one plugin, defaulting to enabled."""

    record = load_plugin_enablement_registry(config).get(str(plugin_id or "").strip().lower())
    if record is None:
        return default
    return bool(record.enabled)


def set_plugin_enabled(
    config: AutopilotConfig,
    plugin_id: str,
    *,
    enabled: bool,
) -> PluginEnablementRecord:
    """Persist one plugin enablement preference."""

    normalized = str(plugin_id or "").strip().lower()
    if not normalized:
        raise ValueError("plugin_id is required")
    records = load_plugin_enablement_registry(config)
    record = PluginEnablementRecord(
        plugin_id=normalized,
        enabled=bool(enabled),
        updated_at=_utcnow_iso(),
    )
    records[normalized] = record
    save_plugin_enablement_registry(config, records)
    return record
