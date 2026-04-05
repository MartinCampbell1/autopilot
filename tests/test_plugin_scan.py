"""Tests for plugin runtime preflight scan and policy summaries."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_scan import build_plugin_runtime_scan
from autopilot.core.plugins import resolve_loaded_plugins
from autopilot.core.plugin_state import set_plugin_enabled
from autopilot.core.plugin_storage import save_plugin_options


def _write_plugin_with_inline_mcp(root: Path) -> None:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".app.json").write_text("{}")
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "ops",
                "version": "0.1.0",
                "description": "Ops plugin",
                "apps": "./.app.json",
                "mcpServers": {
                    "review": {
                        "type": "stdio",
                        "command": "node ${CLAUDE_PLUGIN_ROOT}/mcp/review.js",
                        "args": ["--project", "${user_config.projectId}"],
                    },
                    "remote": {
                        "type": "http",
                        "url": "https://mcp.example.com/${user_config.projectId}",
                    },
                },
                "userConfig": {
                    "projectId": {"type": "string", "required": True},
                    "apiToken": {"type": "string", "required": True, "sensitive": True},
                },
                "interface": {"displayName": "Ops"},
            },
            indent=2,
        )
    )


def test_plugin_runtime_scan_summarizes_guardrail_actions(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_inline_mcp(config.plugins_dir / "ops")
    plugin = next(plugin for plugin in resolve_loaded_plugins(config) if plugin.plugin_id == "ops")
    save_plugin_options(
        config,
        "ops",
        {"projectId": "proj-123", "apiToken": "secret-token"},
        plugin.user_config,
    )

    scan = build_plugin_runtime_scan(config)

    assert scan.summary.plugin_count == 1
    assert scan.summary.active_mcp_server_count == 2
    assert scan.summary.blocked_mcp_server_count == 0
    assert scan.summary.wrapped_surface_count == 1
    assert scan.summary.sandboxed_surface_count == 1
    assert scan.summary.recommended_runtime_profile == "hybrid"
    assert any("wrapper mode" in item for item in scan.recommendations)
    plugin_record = scan.plugins[0]
    assert plugin_record.policy_action == "allow"
    assert plugin_record.wrapped_surface_count == 1
    assert plugin_record.sandboxed_surface_count == 1
    assert plugin_record.recommended_runtime_profile == "hybrid"


def test_plugin_runtime_scan_treats_disabled_plugins_as_inactive(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_inline_mcp(config.plugins_dir / "ops")
    set_plugin_enabled(config, "ops", enabled=False)

    scan = build_plugin_runtime_scan(config)

    assert scan.summary.plugin_count == 1
    assert scan.summary.enabled_plugin_count == 0
    assert scan.summary.active_mcp_server_count == 0
    assert scan.summary.blocked_mcp_server_count == 0
    assert scan.summary.wrapped_surface_count == 0
    assert scan.summary.sandboxed_surface_count == 0
    assert scan.plugins[0].policy_status == "inactive"
