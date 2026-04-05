"""Tests for plugin-defined MCP extraction and managed connector projection."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.capability_store import load_connectors_registry
from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_mcp import list_plugin_mcp_servers, plugin_mcp_connectors
from autopilot.core.plugins import resolve_loaded_plugins
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
                        "env": {
                            "API_TOKEN": "${user_config.apiToken}",
                            "HOME_REF": "${HOME}",
                        },
                    },
                    "remote": {
                        "type": "http",
                        "url": "https://mcp.example.com/${user_config.projectId}",
                        "headers": {
                            "Authorization": "Bearer ${user_config.apiToken}",
                        },
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


def _write_plugin_with_file_mcp(root: Path) -> None:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / ".app.json").write_text("{}")
    (root / "mcp").mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "deploy",
                "version": "0.1.0",
                "description": "Deploy plugin",
                "apps": "./.app.json",
                "mcpServers": "./mcp/servers.json",
                "interface": {"displayName": "Deploy"},
            },
            indent=2,
        )
    )
    (root / "mcp" / "servers.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "deployer": {
                        "type": "stdio",
                        "command": "node ./deployer.js",
                    }
                }
            },
            indent=2,
        )
    )


def test_list_plugin_mcp_servers_redacts_sensitive_values_and_tracks_missing_config(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    plugin_root = config.plugins_dir / "ops"
    _write_plugin_with_inline_mcp(plugin_root)

    initial = list_plugin_mcp_servers(config)
    assert len(initial) == 2
    assert all(item.validation_status == "invalid" for item in initial)
    assert initial[0].missing_option_keys == ["apiToken", "projectId"]
    assert all(item.policy_action == "block" for item in initial)
    assert all(item.runtime_active is False for item in initial)

    save_plugin_options(
        config,
        "ops",
        {"projectId": "proj-123", "apiToken": "secret-token"},
        next(
            plugin.user_config
            for plugin in resolve_loaded_plugins(config)
            if plugin.plugin_id == "ops"
        ),
    )

    servers = list_plugin_mcp_servers(config)
    review = next(item for item in servers if item.server_name == "review")
    remote = next(item for item in servers if item.server_name == "remote")

    assert review.validation_status == "valid"
    assert review.config["command"].endswith("/plugins/ops/mcp/review.js")
    assert review.config["args"] == ["--project", "proj-123"]
    assert review.config["env"]["API_TOKEN"] == "[sensitive option 'apiToken' not available in prompt content]"
    assert review.config["env"]["HOME_REF"].startswith("[env:") or review.config["env"]["HOME_REF"].startswith("[missing env:")
    assert review.policy_action == "sandbox"
    assert review.wrapper_mode == "sandbox-runner"
    assert review.recommended_runtime_profile == "local"
    assert review.runtime_active is True
    assert remote.policy_action == "wrap"
    assert remote.wrapper_mode == "audit-proxy"
    assert remote.recommended_runtime_profile == "hybrid"
    assert remote.runtime_active is True
    assert remote.config["headers"]["Authorization"] == "Bearer [sensitive option 'apiToken' not available in prompt content]"


def test_plugin_mcp_connectors_merge_into_registry_without_persisting(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_inline_mcp(config.plugins_dir / "ops")
    plugin = next(
        plugin
        for plugin in resolve_loaded_plugins(config)
        if plugin.plugin_id == "ops"
    )
    save_plugin_options(
        config,
        "ops",
        {"projectId": "proj-123", "apiToken": "secret-token"},
        plugin.user_config,
    )

    managed = plugin_mcp_connectors(config)
    registry = load_connectors_registry(config)

    assert {item.id for item in managed} == {"plugin-ops-remote", "plugin-ops-review"}
    review = next(item for item in registry if item.id == "plugin-ops-review")
    remote = next(item for item in registry if item.id == "plugin-ops-remote")
    assert review.managed is True
    assert review.source == "plugin"
    assert review.origin_plugin_id == "ops"
    assert review.last_validation_result["status"] == "valid"
    assert review.config["plugin_policy_action"] == "sandbox"
    assert review.config["plugin_policy_runtime_profile"] == "local"
    assert remote.config["plugin_policy_action"] == "wrap"
    assert remote.config["plugin_policy_wrapper_mode"] == "audit-proxy"
    assert remote.risk_level == "high"
    assert not config.connectors_json_path.exists()


def test_plugin_mcp_connectors_block_invalid_surfaces_before_runtime(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_inline_mcp(config.plugins_dir / "ops")

    connectors = {connector.id: connector for connector in plugin_mcp_connectors(config)}

    assert set(connectors) == {"plugin-ops-remote", "plugin-ops-review"}
    assert connectors["plugin-ops-review"].enabled is False
    assert connectors["plugin-ops-review"].validation_status == "blocked"
    assert connectors["plugin-ops-review"].config["plugin_policy_action"] == "block"
    assert connectors["plugin-ops-remote"].enabled is False
    assert connectors["plugin-ops-remote"].validation_status == "blocked"


def test_list_plugin_mcp_servers_loads_json_specs_from_manifest_paths(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_file_mcp(config.plugins_dir / "deploy")

    servers = list_plugin_mcp_servers(config)

    assert len(servers) == 1
    assert servers[0].server_name == "deployer"
    assert servers[0].source_kind == "file"
    assert servers[0].validation_status == "valid"
