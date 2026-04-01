"""Filesystem plugin manifest discovery and validation."""

from __future__ import annotations

import json
import re
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import LoadedPlugin, PluginIdentifier, PluginManifest
from autopilot.core.plugin_state import plugin_enabled

PLUGIN_MANIFEST_RELPATH = Path(".codex-plugin") / "plugin.json"
_PLUGIN_CACHE: dict[tuple[str, int], list[LoadedPlugin]] = {}


def build_plugin_id(name: str) -> str:
    """Normalize a plugin name into a stable id."""

    normalized = re.sub(r"[^a-z0-9]+", "-", str(name or "").strip().lower()).strip("-")
    return normalized or "unknown-plugin"


def parse_plugin_identifier(value: str) -> PluginIdentifier:
    """Parse `name` or `name@version` plugin identifiers."""

    raw = str(value or "").strip()
    if "@" in raw[1:]:
        name, version = raw.rsplit("@", 1)
    else:
        name, version = raw, ""
    return PluginIdentifier(name=build_plugin_id(name), version=version.strip())


def get_plugins_directory(config: AutopilotConfig) -> Path:
    """Return the primary on-disk plugins directory."""

    return config.plugins_dir


def get_plugin_data_dir(config: AutopilotConfig, plugin_id: str) -> Path:
    """Return the scoped data directory for one plugin."""

    return config.plugin_data_dir(build_plugin_id(plugin_id))


def clear_plugin_cache() -> None:
    """Drop cached plugin discovery results."""

    _PLUGIN_CACHE.clear()


def _cache_key(config: AutopilotConfig) -> tuple[str, int]:
    state_mtime = -1
    if config.plugin_enablement_json_path.exists():
        state_mtime = config.plugin_enablement_json_path.stat().st_mtime_ns
    return (str(get_plugins_directory(config).expanduser().resolve()), state_mtime)


def _resolve_relative_path(root: Path, relpath: str) -> tuple[str, bool]:
    normalized = str(relpath or "").strip()
    if not normalized:
        return "", False
    resolved = (root / normalized).resolve()
    return str(resolved), resolved.exists()


def _normalized_manifest_paths(value: str | list[str]) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    paths: list[str] = []
    for item in value:
            normalized = str(item or "").strip()
            if normalized:
                paths.append(normalized)
    return paths


def _looks_like_remote_path(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized.startswith("http://") or normalized.startswith("https://")


def load_plugin_manifest(manifest_path: Path) -> PluginManifest:
    """Load and validate one plugin manifest file."""

    payload = json.loads(manifest_path.read_text())
    return PluginManifest.model_validate(payload)


def create_plugin_from_path(
    config: AutopilotConfig,
    plugin_root: Path,
) -> LoadedPlugin:
    """Resolve one plugin directory into a loaded plugin record."""

    manifest_path = plugin_root / PLUGIN_MANIFEST_RELPATH
    validation_errors: list[str] = []
    validation_status = "valid"
    manifest: PluginManifest | None = None

    try:
        manifest = load_plugin_manifest(manifest_path)
    except Exception as exc:
        validation_status = "invalid"
        validation_errors.append(f"Manifest load failed: {exc}")

    manifest_name = manifest.name if manifest is not None else plugin_root.name
    plugin_id = build_plugin_id(manifest_name)
    display_name = (
        manifest.interface.displayName
        if manifest is not None and manifest.interface.displayName.strip()
        else manifest_name
    )
    commands_path = ""
    commands_paths: list[str] = []
    mcp_paths: list[str] = []
    mcp_server_spec: str | dict[str, object] | list[object] | None = None
    skills_path, skills_present = _resolve_relative_path(
        plugin_root,
        manifest.skills if manifest is not None else "",
    )
    apps_path, apps_present = _resolve_relative_path(
        plugin_root,
        manifest.apps if manifest is not None else "",
    )

    if manifest is not None and manifest.skills and not skills_present:
        validation_status = "invalid"
        validation_errors.append(f"Declared skills path does not exist: {manifest.skills}")
    if manifest is not None and manifest.apps and not apps_present:
        validation_status = "invalid"
        validation_errors.append(f"Declared apps path does not exist: {manifest.apps}")
    if manifest is not None:
        command_paths = _normalized_manifest_paths(manifest.commands)
        if not command_paths:
            default_commands_dir = plugin_root / "commands"
            if default_commands_dir.exists():
                commands_path = str(default_commands_dir.resolve())
                commands_paths.append(commands_path)
        else:
            for raw_path in command_paths:
                resolved_path, present = _resolve_relative_path(plugin_root, raw_path)
                if not present:
                    validation_status = "invalid"
                    validation_errors.append(f"Declared commands path does not exist: {raw_path}")
                    continue
                if resolved_path not in commands_paths:
                    commands_paths.append(resolved_path)
                if not commands_path and Path(resolved_path).is_dir():
                    commands_path = resolved_path
        mcp_server_spec = manifest.mcpServers
        if manifest.mcpServers is None:
            default_mcp_path = plugin_root / ".mcp.json"
            if default_mcp_path.exists():
                mcp_paths.append(str(default_mcp_path.resolve()))
        elif isinstance(manifest.mcpServers, str):
            raw_path = manifest.mcpServers.strip()
            if raw_path.endswith(".mcpb") or raw_path.endswith(".dxt") or _looks_like_remote_path(raw_path):
                validation_status = "invalid"
                validation_errors.append(
                    "Plugin MCP bundles and remote MCP sources are not supported in this Autopilot slice."
                )
            else:
                resolved_path, present = _resolve_relative_path(plugin_root, raw_path)
                if not present:
                    validation_status = "invalid"
                    validation_errors.append(f"Declared MCP path does not exist: {raw_path}")
                else:
                    mcp_paths.append(resolved_path)
        elif isinstance(manifest.mcpServers, list):
            for item in manifest.mcpServers:
                if not isinstance(item, str):
                    continue
                raw_path = item.strip()
                if not raw_path:
                    continue
                if raw_path.endswith(".mcpb") or raw_path.endswith(".dxt") or _looks_like_remote_path(raw_path):
                    validation_status = "invalid"
                    validation_errors.append(
                        "Plugin MCP bundles and remote MCP sources are not supported in this Autopilot slice."
                    )
                    continue
                resolved_path, present = _resolve_relative_path(plugin_root, raw_path)
                if not present:
                    validation_status = "invalid"
                    validation_errors.append(f"Declared MCP path does not exist: {raw_path}")
                    continue
                if resolved_path not in mcp_paths:
                    mcp_paths.append(resolved_path)

    return LoadedPlugin(
        plugin_id=plugin_id,
        name=manifest_name,
        version=manifest.version if manifest is not None else "",
        display_name=display_name,
        description=manifest.description if manifest is not None else "",
        enabled=plugin_enabled(config, plugin_id, default=True),
        source="filesystem",
        root_path=str(plugin_root.resolve()),
        manifest_path=str(manifest_path.resolve()),
        data_dir=str(get_plugin_data_dir(config, plugin_id)),
        homepage=manifest.homepage if manifest is not None else "",
        repository=manifest.repository if manifest is not None else "",
        license=manifest.license if manifest is not None else "",
        keywords=list(manifest.keywords) if manifest is not None else [],
        author=manifest.author if manifest is not None else None,
        commands_path=commands_path,
        commands_paths=list(commands_paths),
        mcp_server_spec=mcp_server_spec,
        mcp_paths=list(mcp_paths),
        skills_path=skills_path,
        skills_present=skills_present,
        apps_path=apps_path,
        apps_present=apps_present,
        user_config=dict(manifest.userConfig) if manifest is not None else {},
        interface=manifest.interface if manifest is not None else {},
        validation_status=validation_status,
        validation_errors=validation_errors,
    )


def _discovered_plugin_roots(config: AutopilotConfig) -> list[Path]:
    plugins_dir = get_plugins_directory(config)
    if not plugins_dir.exists():
        return []
    roots = {
        manifest_path.parent.parent.resolve()
        for manifest_path in plugins_dir.rglob(str(PLUGIN_MANIFEST_RELPATH))
    }
    return sorted(roots, key=lambda item: str(item))


def load_all_plugins(
    config: AutopilotConfig,
    *,
    use_cache: bool = True,
) -> list[LoadedPlugin]:
    """Discover and validate all plugins under the configured plugins directory."""

    cache_key = _cache_key(config)
    if use_cache and cache_key in _PLUGIN_CACHE:
        return [plugin.model_copy(deep=True) for plugin in _PLUGIN_CACHE[cache_key]]

    discovered = [create_plugin_from_path(config, root) for root in _discovered_plugin_roots(config)]
    seen_ids: dict[str, str] = {}
    loaded: list[LoadedPlugin] = []
    for plugin in discovered:
        existing_root = seen_ids.get(plugin.plugin_id)
        if existing_root and existing_root != plugin.root_path:
            plugin.validation_status = "invalid"
            plugin.validation_errors.append(
                f"Duplicate plugin id `{plugin.plugin_id}` also discovered at {existing_root}."
            )
        else:
            seen_ids[plugin.plugin_id] = plugin.root_path
        loaded.append(plugin)

    loaded.sort(key=lambda item: (item.display_name.lower(), item.plugin_id, item.root_path))
    if use_cache:
        _PLUGIN_CACHE[cache_key] = [plugin.model_copy(deep=True) for plugin in loaded]
    return loaded
