"""Compatibility exports for plugin option storage helpers."""

from __future__ import annotations

from autopilot.core.plugin_storage import (
    get_plugin_option_state,
    get_unconfigured_options,
    load_plugin_options,
    load_plugin_options_registry,
    load_plugin_secrets_registry,
    redact_plugin_options,
    save_plugin_options,
    substitute_plugin_variables,
    substitute_user_config_in_content,
    validate_user_config,
)

__all__ = [
    "get_plugin_option_state",
    "get_unconfigured_options",
    "load_plugin_options",
    "load_plugin_options_registry",
    "load_plugin_secrets_registry",
    "redact_plugin_options",
    "save_plugin_options",
    "substitute_plugin_variables",
    "substitute_user_config_in_content",
    "validate_user_config",
]
