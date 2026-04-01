"""Tests for plugin skill discovery."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_skills import list_plugin_skills
from autopilot.core.plugin_state import set_plugin_enabled


def _write_plugin_with_skill(root: Path, *, plugin_name: str, skill_name: str, description: str) -> None:
    (root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    (root / "skills" / skill_name).mkdir(parents=True, exist_ok=True)
    (root / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(
            {
                "name": plugin_name,
                "version": "0.1.0",
                "description": f"{plugin_name} plugin",
                "skills": "./skills/",
                "interface": {"displayName": plugin_name.title()},
            },
            indent=2,
        )
    )
    (root / "skills" / skill_name / "SKILL.md").write_text(
        "---\n"
        f"name: {skill_name}\n"
        f"description: {description}\n"
        "metadata:\n"
        "  short-description: demo\n"
        "---\n\n"
        "# Demo\n"
    )
    (root / "skills" / skill_name / "LICENSE.txt").write_text("demo")


def test_list_plugin_skills_discovers_frontmatter_metadata(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_skill(
        config.plugins_dir / "github",
        plugin_name="github",
        skill_name="github",
        description="Triage GitHub work.",
    )

    skills = list_plugin_skills(config)

    assert len(skills) == 1
    assert skills[0].plugin_id == "github"
    assert skills[0].skill_id == "github:github"
    assert skills[0].description == "Triage GitHub work."
    assert skills[0].license_path.endswith("LICENSE.txt")
    assert skills[0].metadata["metadata"] == {"short-description": "demo"}


def test_list_plugin_skills_can_filter_enabled_plugins(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    _write_plugin_with_skill(
        config.plugins_dir / "github",
        plugin_name="github",
        skill_name="github",
        description="Triage GitHub work.",
    )
    set_plugin_enabled(config, "github", enabled=False)

    assert len(list_plugin_skills(config, enabled_only=False)) == 1
    assert list_plugin_skills(config, enabled_only=True) == []
