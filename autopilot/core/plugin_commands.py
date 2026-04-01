"""Plugin command discovery from markdown bundles."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import LoadedPlugin, PluginCommandDescriptor
from autopilot.core.plugin_storage import (
    load_plugin_options,
    substitute_plugin_variables,
    substitute_user_config_in_content,
)
from autopilot.core.plugins import resolve_loaded_plugins


def _parse_markdown_bundle(markdown_path: Path) -> tuple[dict[str, object], str]:
    text = markdown_path.read_text()
    if not text.startswith("---\n"):
        return {}, text
    remainder = text[4:]
    try:
        frontmatter_text, body = remainder.split("\n---\n", 1)
    except ValueError:
        return {}, text
    payload = yaml.safe_load(frontmatter_text) or {}
    return (payload if isinstance(payload, dict) else {}), body


def _parse_bool(value: object, *, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _parse_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        normalized = value.strip()
        return [normalized] if normalized else []
    return []


def _normalize_segment(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return normalized or "item"


def _extract_description(content: str) -> str:
    lines = [line.strip() for line in content.splitlines()]
    bucket: list[str] = []
    for line in lines:
        if not line:
            if bucket:
                break
            continue
        if line.startswith("#"):
            continue
        bucket.append(line)
    return " ".join(bucket).strip()


def _walk_command_markdown(root: Path) -> list[Path]:
    if root.is_file() and root.suffix.lower() == ".md":
        return [root]
    if not root.exists() or not root.is_dir():
        return []

    discovered: list[Path] = []

    def scan(directory: Path) -> None:
        entries = sorted(directory.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
        skill_file = next(
            (
                item
                for item in entries
                if item.is_file() and item.name.lower() == "skill.md"
            ),
            None,
        )
        if skill_file is not None:
            discovered.append(skill_file)
            return
        for entry in entries:
            if entry.is_dir():
                scan(entry)
            elif entry.is_file() and entry.suffix.lower() == ".md":
                discovered.append(entry)

    scan(root)
    return discovered


def _command_id_for_markdown(plugin: LoadedPlugin, base_dir: Path, markdown_path: Path) -> str:
    is_skill = markdown_path.name.lower() == "skill.md"
    if is_skill:
        if markdown_path.parent == base_dir:
            namespace_parts: tuple[str, ...] = ()
            leaf = markdown_path.parent.name
        else:
            rel_parent = markdown_path.parent.relative_to(base_dir)
            namespace_parts = rel_parent.parts[:-1]
            leaf = rel_parent.parts[-1]
    else:
        relative = markdown_path.relative_to(base_dir)
        namespace_parts = relative.parts[:-1]
        leaf = Path(relative.name).stem
    parts = [plugin.plugin_id] + [_normalize_segment(part) for part in namespace_parts] + [_normalize_segment(leaf)]
    return ":".join(parts)


def load_plugin_commands(plugin: LoadedPlugin) -> list[PluginCommandDescriptor]:
    """Discover markdown-backed command bundles declared by one plugin."""

    roots: list[Path] = []
    if plugin.commands_paths:
        roots.extend(Path(path) for path in plugin.commands_paths)
    elif plugin.commands_path:
        roots.append(Path(plugin.commands_path))

    if not roots:
        return []

    discovered: list[PluginCommandDescriptor] = []
    seen_paths: set[str] = set()
    for root in roots:
        base_dir = root if root.is_dir() else root.parent
        for markdown_path in _walk_command_markdown(root):
            resolved_path = str(markdown_path.resolve())
            if resolved_path in seen_paths:
                continue
            seen_paths.add(resolved_path)
            frontmatter, content = _parse_markdown_bundle(markdown_path)
            command_id = _command_id_for_markdown(plugin, base_dir, markdown_path)
            description = str(frontmatter.get("description") or "").strip() or _extract_description(content)
            display_name = str(frontmatter.get("name") or "").strip() or command_id
            discovered.append(
                PluginCommandDescriptor(
                    plugin_id=plugin.plugin_id,
                    command_id=command_id,
                    name=command_id,
                    display_name=display_name,
                    description=description,
                    path=resolved_path,
                    relative_path=str(markdown_path.resolve().relative_to(Path(plugin.root_path))),
                    source_kind="skill" if markdown_path.name.lower() == "skill.md" else "command",
                    user_invocable=_parse_bool(frontmatter.get("user-invocable"), default=True),
                    argument_hint=str(frontmatter.get("argument-hint") or "").strip(),
                    arguments=_parse_string_list(frontmatter.get("arguments")),
                    allowed_tools=_parse_string_list(frontmatter.get("allowed-tools")),
                    when_to_use=str(frontmatter.get("when_to_use") or "").strip(),
                    metadata={
                        key: value
                        for key, value in frontmatter.items()
                        if key
                        not in {
                            "name",
                            "description",
                            "user-invocable",
                            "argument-hint",
                            "arguments",
                            "allowed-tools",
                            "when_to_use",
                        }
                    },
                )
            )
    discovered.sort(key=lambda item: (item.plugin_id, item.command_id, item.path))
    return discovered


def list_plugin_commands(
    config: AutopilotConfig,
    *,
    plugin_id: str | None = None,
    enabled_only: bool = False,
) -> list[PluginCommandDescriptor]:
    """Discover commands across all loaded plugins."""

    plugin_filter = str(plugin_id or "").strip().lower()
    discovered: list[PluginCommandDescriptor] = []
    for plugin in resolve_loaded_plugins(config):
        if plugin_filter and plugin.plugin_id != plugin_filter:
            continue
        if enabled_only and not plugin.enabled:
            continue
        discovered.extend(load_plugin_commands(plugin))
    discovered.sort(key=lambda item: (item.plugin_id, item.command_id, item.path))
    return discovered


def render_plugin_command_content(
    config: AutopilotConfig,
    descriptor: PluginCommandDescriptor,
) -> str:
    """Resolve one command markdown body with plugin/user substitutions applied."""

    plugins = {plugin.plugin_id: plugin for plugin in resolve_loaded_plugins(config)}
    plugin = plugins.get(descriptor.plugin_id)
    if plugin is None:
        raise KeyError(f"Plugin {descriptor.plugin_id} not found")
    markdown_path = Path(descriptor.path)
    _, content = _parse_markdown_bundle(markdown_path)
    rendered = substitute_plugin_variables(content, plugin)
    if plugin.user_config:
        rendered = substitute_user_config_in_content(
            rendered,
            load_plugin_options(config, plugin.plugin_id),
            plugin.user_config,
        )
    if descriptor.source_kind == "skill":
        skill_dir = str(markdown_path.parent.resolve()).replace("\\", "/")
        rendered = rendered.replace("${CLAUDE_SKILL_DIR}", skill_dir)
        rendered = rendered.replace("${AUTOPILOT_SKILL_DIR}", skill_dir)
    return rendered
