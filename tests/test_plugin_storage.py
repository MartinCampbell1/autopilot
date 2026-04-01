"""Tests for plugin option storage and substitution helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_loader import create_plugin_from_path
from autopilot.core.plugin_storage import (
    get_plugin_option_state,
    load_plugin_options,
    save_plugin_options,
    substitute_plugin_variables,
    substitute_user_config_in_content,
)


def _write_configurable_plugin(root: Path) -> None:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / ".app.json").write_text("{}")
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "deploy",
                "version": "0.1.0",
                "description": "Deploy plugin",
                "skills": "./skills/",
                "apps": "./.app.json",
                "userConfig": {
                    "projectId": {"type": "string", "required": True},
                    "apiToken": {"type": "string", "required": True, "sensitive": True},
                    "mode": {"type": "string", "default": "safe", "enum": ["safe", "fast"]},
                },
                "interface": {"displayName": "Deploy"},
            },
            indent=2,
        )
    )


def test_plugin_option_state_tracks_unconfigured_and_redacted_values(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    root = config.plugins_dir / "deploy"
    _write_configurable_plugin(root)
    plugin = create_plugin_from_path(config, root)

    initial_state = get_plugin_option_state(config, plugin)
    assert initial_state.unconfigured_keys == ["apiToken", "projectId"]

    validation = save_plugin_options(
        config,
        plugin.plugin_id,
        {"projectId": "proj-123", "apiToken": "secret-token"},
        plugin.user_config,
    )
    assert validation.valid is True

    loaded = load_plugin_options(config, plugin.plugin_id)
    assert loaded["projectId"] == "proj-123"
    assert loaded["apiToken"] == "secret-token"
    assert loaded["mode"] == "safe"

    state = get_plugin_option_state(config, plugin)
    assert state.unconfigured_keys == []
    assert state.configured_values["projectId"] == "proj-123"
    assert state.configured_values["apiToken"] == "[configured]"

    plain_payload = json.loads(config.plugin_options_json_path.read_text())
    secret_payload = json.loads(config.plugin_secrets_json_path.read_text())
    assert plain_payload["plugins"]["deploy"]["projectId"] == "proj-123"
    assert "apiToken" not in plain_payload["plugins"]["deploy"]
    assert secret_payload["plugins"]["deploy"]["apiToken"] == "secret-token"


def test_plugin_option_validation_and_substitution_helpers(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    root = config.plugins_dir / "deploy"
    _write_configurable_plugin(root)
    plugin = create_plugin_from_path(config, root)

    invalid = save_plugin_options(
        config,
        plugin.plugin_id,
        {"projectId": "proj-123", "apiToken": "secret-token", "mode": "turbo"},
        plugin.user_config,
    )
    assert invalid.valid is False
    assert invalid.errors["mode"].startswith("Expected one of:")

    save_plugin_options(
        config,
        plugin.plugin_id,
        {"projectId": "proj-123", "apiToken": "secret-token", "mode": "fast"},
        plugin.user_config,
    )
    rendered = substitute_user_config_in_content(
        "Deploy ${user_config.projectId} with ${user_config.apiToken}",
        load_plugin_options(config, plugin.plugin_id),
        plugin.user_config,
    )
    assert rendered == "Deploy proj-123 with [sensitive option 'apiToken' not available in prompt content]"

    plugin_vars = substitute_plugin_variables(
        "root=${CLAUDE_PLUGIN_ROOT} data=${CLAUDE_PLUGIN_DATA}",
        plugin,
    )
    assert "root=" in plugin_vars and plugin.root_path.replace("\\", "/") in plugin_vars
    assert "data=" in plugin_vars and plugin.data_dir.replace("\\", "/") in plugin_vars
