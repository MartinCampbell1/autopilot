"""Plugin skill discovery from loaded plugin bundles."""

from __future__ import annotations

from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import LoadedPlugin, PluginSkillDescriptor
from autopilot.core.plugins import resolve_loaded_plugins


def _frontmatter_payload(skill_path: Path) -> dict[str, object]:
    text = skill_path.read_text()
    if not text.startswith("---\n"):
        return {}
    remainder = text[4:]
    try:
        frontmatter_text, _ = remainder.split("\n---\n", 1)
    except ValueError:
        return {}
    payload = yaml.safe_load(frontmatter_text) or {}
    return payload if isinstance(payload, dict) else {}


def load_plugin_skills(plugin: LoadedPlugin) -> list[PluginSkillDescriptor]:
    """Discover `SKILL.md` bundles under one plugin's declared skills directory."""

    skills_root = Path(plugin.skills_path) if plugin.skills_path else None
    if skills_root is None or not skills_root.exists() or not skills_root.is_dir():
        return []

    discovered: list[PluginSkillDescriptor] = []
    for skill_path in sorted(skills_root.glob("*/SKILL.md"), key=lambda item: str(item)):
        frontmatter = _frontmatter_payload(skill_path)
        skill_name = str(frontmatter.get("name") or skill_path.parent.name).strip() or skill_path.parent.name
        license_path = skill_path.parent / "LICENSE.txt"
        discovered.append(
            PluginSkillDescriptor(
                plugin_id=plugin.plugin_id,
                skill_id=f"{plugin.plugin_id}:{skill_name}",
                name=skill_name,
                description=str(frontmatter.get("description") or "").strip(),
                path=str(skill_path.resolve()),
                relative_path=str(skill_path.relative_to(skills_root.parent)),
                license_path=str(license_path.resolve()) if license_path.exists() else "",
                metadata={
                    key: value
                    for key, value in frontmatter.items()
                    if key not in {"name", "description"}
                },
            )
        )
    return discovered


def list_plugin_skills(
    config: AutopilotConfig,
    *,
    plugin_id: str | None = None,
    enabled_only: bool = False,
) -> list[PluginSkillDescriptor]:
    """Discover skills across loaded plugins."""

    plugin_filter = str(plugin_id or "").strip().lower()
    discovered: list[PluginSkillDescriptor] = []
    for plugin in resolve_loaded_plugins(config):
        if plugin_filter and plugin.plugin_id != plugin_filter:
            continue
        if enabled_only and not plugin.enabled:
            continue
        discovered.extend(load_plugin_skills(plugin))
    discovered.sort(key=lambda item: (item.plugin_id, item.name, item.path))
    return discovered
