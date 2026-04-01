"""Tests for filesystem plugin manifest discovery."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_loader import (
    build_plugin_id,
    create_plugin_from_path,
    load_all_plugins,
    parse_plugin_identifier,
)
from autopilot.core.plugin_state import set_plugin_enabled


def _write_plugin_manifest(
    root: Path,
    *,
    name: str = "github",
    version: str = "0.1.0",
    commands: str | list[str] | None = None,
    skills: str = "./skills/",
    apps: str = "./.app.json",
    user_config: dict[str, object] | None = None,
) -> Path:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / "skills").mkdir(parents=True, exist_ok=True)
    (root / ".app.json").write_text("{}")
    manifest: dict[str, object] = {
        "name": name,
        "version": version,
        "description": f"{name} plugin",
        "skills": skills,
        "apps": apps,
        "interface": {
            "displayName": name.title(),
            "category": "Coding",
            "capabilities": ["Interactive", "Write"],
            "defaultPrompt": "Inspect and act",
        },
    }
    if commands is not None:
        manifest["commands"] = commands
    if user_config is not None:
        manifest["userConfig"] = user_config
    manifest_path = root / ".codex-plugin" / "plugin.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2)
    )
    return manifest_path


def test_plugin_identifier_parsing_normalizes_name() -> None:
    parsed = parse_plugin_identifier("GitHub Reviews@0.2.0")

    assert parsed.name == "github-reviews"
    assert parsed.version == "0.2.0"
    assert build_plugin_id("GitHub Reviews") == "github-reviews"


def test_create_plugin_from_path_resolves_manifest_and_assets(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    plugin_root = config.plugins_dir / "github"
    _write_plugin_manifest(plugin_root, name="github")

    plugin = create_plugin_from_path(config, plugin_root)

    assert plugin.plugin_id == "github"
    assert plugin.display_name == "Github"
    assert plugin.skills_present is True
    assert plugin.apps_present is True
    assert plugin.validation_status == "valid"
    assert plugin.enabled is True
    assert plugin.data_dir.endswith("/plugins/data/github")


def test_create_plugin_from_path_resolves_default_commands_and_user_config(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    plugin_root = config.plugins_dir / "deploy"
    (plugin_root / "commands").mkdir(parents=True, exist_ok=True)
    _write_plugin_manifest(
        plugin_root,
        name="deploy",
        user_config={
            "projectId": {"type": "string", "required": True},
            "apiToken": {"type": "string", "required": True, "sensitive": True},
        },
    )

    plugin = create_plugin_from_path(config, plugin_root)

    assert plugin.commands_path.endswith("/deploy/commands")
    assert plugin.commands_paths == [plugin.commands_path]
    assert sorted(plugin.user_config) == ["apiToken", "projectId"]


def test_load_all_plugins_marks_disabled_and_invalid_plugins(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    good_root = config.plugins_dir / "github"
    bad_root = config.plugins_dir / "broken"
    _write_plugin_manifest(good_root, name="github")
    _write_plugin_manifest(bad_root, name="broken", skills="./missing-skills/")
    set_plugin_enabled(config, "github", enabled=False)

    plugins = load_all_plugins(config, use_cache=False)
    by_id = {plugin.plugin_id: plugin for plugin in plugins}

    assert sorted(by_id) == ["broken", "github"]
    assert by_id["github"].enabled is False
    assert by_id["broken"].validation_status == "invalid"
    assert any("Declared skills path does not exist" in item for item in by_id["broken"].validation_errors)


def test_load_all_plugins_marks_missing_command_paths_invalid(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    broken_root = config.plugins_dir / "deploy"
    _write_plugin_manifest(broken_root, name="deploy", commands="./commands/review.md")

    plugins = load_all_plugins(config, use_cache=False)

    assert plugins[0].validation_status == "invalid"
    assert any("Declared commands path does not exist" in item for item in plugins[0].validation_errors)
