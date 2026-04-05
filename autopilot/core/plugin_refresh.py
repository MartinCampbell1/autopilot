"""Refresh helpers for plugin discovery and preflight scans."""

from __future__ import annotations

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_loader import clear_plugin_cache
from autopilot.core.plugin_scan import PluginRuntimeScan, build_plugin_runtime_scan


def refresh_plugin_runtime_scan(config: AutopilotConfig) -> PluginRuntimeScan:
    """Force a plugin rescan and rebuild the runtime inventory."""

    clear_plugin_cache()
    return build_plugin_runtime_scan(config)
