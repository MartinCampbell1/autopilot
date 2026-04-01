"""Tests for plugin command discovery and rendering."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_commands import list_plugin_commands, render_plugin_command_content
from autopilot.core.plugins import resolve_loaded_plugins
from autopilot.core.plugin_storage import save_plugin_options
from autopilot.core.plugin_state import set_plugin_enabled


def _write_plugin_with_commands(root: Path) -> None:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / "commands" / "deploy").mkdir(parents=True, exist_ok=True)
    (root / ".app.json").write_text("{}")
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": "ops",
                "version": "0.1.0",
                "description": "Ops plugin",
                "apps": "./.app.json",
                "commands": "./commands/",
                "userConfig": {
                    "projectId": {"type": "string", "required": True},
                    "apiToken": {"type": "string", "required": True, "sensitive": True},
                },
                "interface": {"displayName": "Ops"},
            },
            indent=2,
        )
    )
    (root / "commands" / "review.md").write_text(
        "---\n"
        "name: Review PR\n"
        "description: Review the current pull request.\n"
        "allowed-tools:\n"
        "  - shell_exec\n"
        "  - github\n"
        "arguments:\n"
        "  - pr\n"
        "argument-hint: pull-request-number\n"
        "---\n\n"
        "Review ${user_config.projectId} from ${CLAUDE_PLUGIN_ROOT}\n"
    )
    (root / "commands" / "deploy" / "SKILL.md").write_text(
        "---\n"
        "name: Deploy release\n"
        "description: Deploy the release bundle.\n"
        "---\n\n"
        "Run deploy from ${CLAUDE_SKILL_DIR} with ${user_config.apiToken}\n"
    )


def test_list_plugin_commands_discovers_markdown_and_skill_dirs(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_commands(config.plugins_dir / "ops")

    commands = list_plugin_commands(config)

    assert [command.command_id for command in commands] == ["ops:deploy", "ops:review"]
    review = next(command for command in commands if command.command_id == "ops:review")
    deploy = next(command for command in commands if command.command_id == "ops:deploy")
    assert review.allowed_tools == ["shell_exec", "github"]
    assert review.arguments == ["pr"]
    assert deploy.source_kind == "skill"


def test_render_plugin_command_content_applies_plugin_and_user_substitutions(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    plugin_root = config.plugins_dir / "ops"
    _write_plugin_with_commands(plugin_root)
    plugin = next(plugin for plugin in resolve_loaded_plugins(config) if plugin.plugin_id == "ops")
    save_plugin_options(
        config,
        "ops",
        {"projectId": "proj-123", "apiToken": "secret-token"},
        plugin.user_config,
    )

    commands = list_plugin_commands(config)
    review = next(command for command in commands if command.command_id == "ops:review")
    deploy = next(command for command in commands if command.command_id == "ops:deploy")

    review_content = render_plugin_command_content(config, review)
    deploy_content = render_plugin_command_content(config, deploy)

    assert "proj-123" in review_content
    assert plugin_root.resolve().as_posix() in review_content
    assert "[sensitive option 'apiToken' not available in prompt content]" in deploy_content
    assert (plugin_root / "commands" / "deploy").resolve().as_posix() in deploy_content


def test_list_plugin_commands_can_filter_enabled_plugins(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_commands(config.plugins_dir / "ops")
    set_plugin_enabled(config, "ops", enabled=False)

    assert len(list_plugin_commands(config, enabled_only=False)) == 2
    assert list_plugin_commands(config, enabled_only=True) == []
