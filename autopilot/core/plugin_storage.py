"""File-backed plugin option storage and variable substitution helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json
from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import (
    LoadedPlugin,
    PluginOptionState,
    PluginOptionValidationResult,
    PluginUserConfigOption,
)


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    _shared_atomic_write_json(path, payload)


def _read_plugin_value_registry(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    raw_plugins = payload.get("plugins", {})
    if not isinstance(raw_plugins, dict):
        return {}
    registry: dict[str, dict[str, object]] = {}
    for plugin_id, raw_values in raw_plugins.items():
        if not isinstance(raw_values, dict):
            continue
        registry[str(plugin_id).strip().lower()] = dict(raw_values)
    return registry


def _normalize_plugin_id(plugin_id: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(plugin_id or "").strip().lower()).strip("-")
    if not normalized:
        raise ValueError("plugin_id is required")
    return normalized


def plugin_storage_id(plugin: LoadedPlugin | str) -> str:
    """Return the canonical storage key for persisted plugin options."""

    return _normalize_plugin_id(plugin.plugin_id if isinstance(plugin, LoadedPlugin) else plugin)


def load_plugin_options_registry(config: AutopilotConfig) -> dict[str, dict[str, object]]:
    """Load non-sensitive plugin option values."""

    return _read_plugin_value_registry(config.plugin_options_json_path)


def load_plugin_secrets_registry(config: AutopilotConfig) -> dict[str, dict[str, object]]:
    """Load sensitive plugin option values."""

    return _read_plugin_value_registry(config.plugin_secrets_json_path)


def _save_plugin_value_registry(path: Path, registry: dict[str, dict[str, object]]) -> None:
    ordered = {
        plugin_id: registry[plugin_id]
        for plugin_id in sorted(registry)
        if registry[plugin_id]
    }
    _atomic_write_json(path, {"plugins": ordered})


def load_plugin_options(
    config: AutopilotConfig,
    plugin_id: str,
) -> dict[str, object]:
    """Load merged plugin option values, with secrets overlaying plain config."""

    normalized = plugin_storage_id(plugin_id)
    regular = load_plugin_options_registry(config).get(normalized, {})
    sensitive = load_plugin_secrets_registry(config).get(normalized, {})
    return {**regular, **sensitive}


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def _coerce_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError("Expected a boolean value.")


def _coerce_number(value: object) -> int | float:
    if isinstance(value, bool):
        raise ValueError("Expected a number, received a boolean.")
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            raise ValueError("Expected a number value.")
        try:
            return int(normalized) if "." not in normalized else float(normalized)
        except ValueError as exc:
            raise ValueError("Expected a number value.") from exc
    raise ValueError("Expected a number value.")


def _coerce_array(value: object, option: PluginUserConfigOption) -> list[str | int | float | bool]:
    item_type = option.items or "string"
    raw_items = value
    if isinstance(raw_items, str):
        raw_items = [item.strip() for item in raw_items.split(",") if item.strip()]
    if not isinstance(raw_items, list):
        raise ValueError("Expected an array value.")
    coerced: list[str | int | float | bool] = []
    for item in raw_items:
        if item_type == "number":
            coerced.append(_coerce_number(item))
        elif item_type == "boolean":
            coerced.append(_coerce_bool(item))
        else:
            text = str(item).strip()
            if not text:
                continue
            coerced.append(text)
    return coerced


def _coerce_option_value(value: object, option: PluginUserConfigOption) -> object:
    if option.type == "boolean":
        normalized = _coerce_bool(value)
    elif option.type == "number":
        normalized = _coerce_number(value)
    elif option.type == "array":
        normalized = _coerce_array(value, option)
    else:
        normalized = str(value).strip()

    if option.enum:
        enum_values = [str(item) for item in option.enum]
        candidate = str(normalized)
        if candidate not in enum_values:
            raise ValueError(f"Expected one of: {', '.join(enum_values)}.")
    if option.pattern and isinstance(normalized, str):
        if re.fullmatch(option.pattern, normalized) is None:
            raise ValueError("Value does not match the required pattern.")
    return normalized


def validate_user_config(
    values: dict[str, object] | None,
    schema: dict[str, PluginUserConfigOption],
) -> PluginOptionValidationResult:
    """Validate and normalize a plugin option payload against manifest schema."""

    payload = dict(values or {})
    normalized: dict[str, object] = {}
    errors: dict[str, str] = {}

    for key in payload:
        if key not in schema:
            errors[key] = "Unknown plugin option."

    for key, option in schema.items():
        raw_value = payload.get(key, option.default)
        if _is_missing_value(raw_value):
            if option.default is not None:
                normalized[key] = option.default
            elif option.required:
                errors[key] = f"{option.title or key} is required."
            continue
        try:
            normalized[key] = _coerce_option_value(raw_value, option)
        except ValueError as exc:
            errors[key] = str(exc)

    return PluginOptionValidationResult(valid=not errors, values=normalized, errors=errors)


def save_plugin_options(
    config: AutopilotConfig,
    plugin_id: str,
    values: dict[str, object],
    schema: dict[str, PluginUserConfigOption],
) -> PluginOptionValidationResult:
    """Persist plugin option values, splitting sensitive keys into a separate store."""

    normalized_plugin_id = plugin_storage_id(plugin_id)
    merged = load_plugin_options(config, normalized_plugin_id)
    merged.update(values)
    validation = validate_user_config(merged, schema)
    if not validation.valid:
        return validation

    regular_registry = load_plugin_options_registry(config)
    secrets_registry = load_plugin_secrets_registry(config)
    regular_values: dict[str, object] = {}
    sensitive_values: dict[str, object] = {}

    for key, value in validation.values.items():
        if schema[key].sensitive:
            sensitive_values[key] = value
        else:
            regular_values[key] = value

    if regular_values:
        regular_registry[normalized_plugin_id] = regular_values
    else:
        regular_registry.pop(normalized_plugin_id, None)
    if sensitive_values:
        secrets_registry[normalized_plugin_id] = sensitive_values
    else:
        secrets_registry.pop(normalized_plugin_id, None)

    _save_plugin_value_registry(config.plugin_options_json_path, regular_registry)
    _save_plugin_value_registry(config.plugin_secrets_json_path, secrets_registry)
    return validation


def get_unconfigured_options(
    config: AutopilotConfig,
    plugin: LoadedPlugin,
) -> dict[str, PluginUserConfigOption]:
    """Return the schema slice that still needs valid user-provided values."""

    if not plugin.user_config:
        return {}
    saved = load_plugin_options(config, plugin.plugin_id)
    validation = validate_user_config(saved, plugin.user_config)
    if validation.valid:
        return {}

    unconfigured: dict[str, PluginUserConfigOption] = {}
    for key, field_schema in plugin.user_config.items():
        single = validate_user_config({key: saved.get(key)}, {key: field_schema})
        if not single.valid:
            unconfigured[key] = field_schema
    return unconfigured


def redact_plugin_options(
    values: dict[str, object],
    schema: dict[str, PluginUserConfigOption],
) -> dict[str, object]:
    """Redact sensitive option values before surfacing them through APIs."""

    redacted: dict[str, object] = {}
    for key, value in values.items():
        if key in schema and schema[key].sensitive:
            redacted[key] = "[configured]" if not _is_missing_value(value) else ""
        else:
            redacted[key] = value
    return redacted


def get_plugin_option_state(
    config: AutopilotConfig,
    plugin: LoadedPlugin,
) -> PluginOptionState:
    """Resolve the current persisted option status for one plugin."""

    schema = dict(plugin.user_config)
    values = load_plugin_options(config, plugin.plugin_id)
    validation = validate_user_config(values, schema)
    configured_keys = sorted(key for key, value in values.items() if not _is_missing_value(value))
    sensitive_keys = sorted(key for key, option in schema.items() if option.sensitive and key in values)
    unconfigured = get_unconfigured_options(config, plugin)
    return PluginOptionState(
        plugin_id=plugin.plugin_id,
        option_schema=schema,
        configured_values=redact_plugin_options(values, schema),
        configured_keys=configured_keys,
        sensitive_keys=sensitive_keys,
        unconfigured_keys=sorted(unconfigured),
        validation_errors=validation.errors,
    )


def substitute_plugin_variables(value: str, plugin: LoadedPlugin) -> str:
    """Substitute plugin-root and plugin-data variables in markdown content."""

    def normalize(path: str) -> str:
        return path.replace("\\", "/")

    plugin_data_dir = Path(plugin.data_dir)
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    substitutions = {
        "${CLAUDE_PLUGIN_ROOT}": normalize(plugin.root_path),
        "${CLAUDE_PLUGIN_DATA}": normalize(str(plugin_data_dir.resolve())),
        "${AUTOPILOT_PLUGIN_ROOT}": normalize(plugin.root_path),
        "${AUTOPILOT_PLUGIN_DATA}": normalize(str(plugin_data_dir.resolve())),
    }
    output = value
    for needle, replacement in substitutions.items():
        output = output.replace(needle, replacement)
    return output


def substitute_user_config_variables(
    value: str,
    user_config: dict[str, object],
) -> str:
    """Strictly substitute saved user-config variables, failing on missing keys."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        config_value = user_config.get(key)
        if config_value is None:
            raise ValueError(
                f"Missing required user configuration value: {key}. "
                "This should have been validated before variable substitution."
            )
        return str(config_value)

    return re.sub(r"\$\{user_config\.([^}]+)\}", replace, value)


def substitute_user_config_in_content(
    content: str,
    options: dict[str, object],
    schema: dict[str, PluginUserConfigOption],
) -> str:
    """Substitute non-sensitive option values while redacting sensitive content."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in schema and schema[key].sensitive:
            return f"[sensitive option '{key}' not available in prompt content]"
        value = options.get(key)
        if value is None:
            return match.group(0)
        return str(value)

    return re.sub(r"\$\{user_config\.([^}]+)\}", replace, content)
