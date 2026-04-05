"""Compatibility exports for plugin manifest/discovery helpers."""

from __future__ import annotations

from autopilot.core.plugin_loader import (
    PLUGIN_MANIFEST_RELPATH,
    build_plugin_id,
    clear_plugin_cache,
    create_plugin_from_path,
    get_plugin_data_dir,
    get_plugins_directory,
    load_all_plugins,
    load_plugin_manifest,
    parse_plugin_identifier,
)

__all__ = [
    "PLUGIN_MANIFEST_RELPATH",
    "build_plugin_id",
    "clear_plugin_cache",
    "create_plugin_from_path",
    "get_plugin_data_dir",
    "get_plugins_directory",
    "load_all_plugins",
    "load_plugin_manifest",
    "parse_plugin_identifier",
]
