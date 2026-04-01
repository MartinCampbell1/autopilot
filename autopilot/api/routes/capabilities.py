"""Routes for MCP connectors, skill packs, and role templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autopilot.api.deps import get_config
from autopilot.core.capability_store import (
    DEFAULT_LAUNCH_PRESETS,
    MCPConnector,
    RoutingPolicy,
    SkillPack,
    build_tool_catalog,
    delete_connector,
    delete_skill_pack,
    get_connector_type_schema,
    load_connector_type_catalog,
    load_connectors_registry,
    load_role_templates,
    load_routing_policies_registry,
    load_skill_packs_registry,
    upsert_routing_policy,
    upsert_connector,
    upsert_skill_pack,
    validate_connector_config,
)
from autopilot.core.plugins import (
    list_agent_providers,
    list_runtimes,
    resolve_notifier_plugins,
    resolve_loaded_plugins,
    resolve_tracker_plugins,
)
from autopilot.core.plugin_commands import list_plugin_commands, render_plugin_command_content
from autopilot.core.plugin_loader import build_plugin_id, clear_plugin_cache
from autopilot.core.plugin_mcp import list_plugin_mcp_servers
from autopilot.core.plugin_skills import list_plugin_skills
from autopilot.core.plugin_storage import get_plugin_option_state, save_plugin_options
from autopilot.core.plugin_state import set_plugin_enabled

router = APIRouter()
EXTENSION_LIFECYCLE = ["discover", "validate", "enable", "expose", "audit"]


def _build_extension_registry(config) -> dict[str, object]:
    loaded_plugins = resolve_loaded_plugins(config)
    plugin_skills = list_plugin_skills(config)
    plugin_commands = list_plugin_commands(config)
    plugin_mcp_servers = list_plugin_mcp_servers(config)
    skill_counts: dict[str, int] = {}
    command_counts: dict[str, int] = {}
    mcp_counts: dict[str, int] = {}
    invalid_mcp_counts: dict[str, int] = {}
    for skill in plugin_skills:
        skill_counts[skill.plugin_id] = skill_counts.get(skill.plugin_id, 0) + 1
    for command in plugin_commands:
        command_counts[command.plugin_id] = command_counts.get(command.plugin_id, 0) + 1
    for server in plugin_mcp_servers:
        mcp_counts[server.plugin_id] = mcp_counts.get(server.plugin_id, 0) + 1
        if server.validation_status != "valid":
            invalid_mcp_counts[server.plugin_id] = invalid_mcp_counts.get(server.plugin_id, 0) + 1
    option_states = {
        plugin.plugin_id: get_plugin_option_state(config, plugin)
        for plugin in loaded_plugins
    }
    return {
        "lifecycle": list(EXTENSION_LIFECYCLE),
        "plugins": [
            {
                "extension_id": plugin.plugin_id,
                "display_name": plugin.display_name or plugin.name,
                "kind": "plugin",
                "transport": "plugin",
                "metadata": {
                    "source": plugin.source,
                    "version": plugin.version,
                    "description": plugin.description,
                    "enabled": plugin.enabled,
                    "manifest_path": plugin.manifest_path,
                    "root_path": plugin.root_path,
                    "data_dir": plugin.data_dir,
                    "commands_path": plugin.commands_path,
                    "commands_paths": list(plugin.commands_paths),
                    "command_count": command_counts.get(plugin.plugin_id, 0),
                    "mcp_paths": list(plugin.mcp_paths),
                    "mcp_server_count": mcp_counts.get(plugin.plugin_id, 0),
                    "invalid_mcp_server_count": invalid_mcp_counts.get(plugin.plugin_id, 0),
                    "skills_path": plugin.skills_path,
                    "skills_present": plugin.skills_present,
                    "skill_count": skill_counts.get(plugin.plugin_id, 0),
                    "apps_path": plugin.apps_path,
                    "apps_present": plugin.apps_present,
                    "configurable": bool(plugin.user_config),
                    "option_count": len(plugin.user_config),
                    "configured_option_keys": option_states[plugin.plugin_id].configured_keys,
                    "unconfigured_option_keys": option_states[plugin.plugin_id].unconfigured_keys,
                    "validation_option_errors": option_states[plugin.plugin_id].validation_errors,
                    "validation_status": plugin.validation_status,
                    "validation_errors": list(plugin.validation_errors),
                    "homepage": plugin.homepage,
                    "repository": plugin.repository,
                    "license": plugin.license,
                    "keywords": list(plugin.keywords),
                    "category": plugin.interface.category,
                    "developer_name": plugin.interface.developerName
                    or (plugin.author.name if plugin.author is not None else ""),
                    "capabilities": list(plugin.interface.capabilities),
                    "default_prompts": plugin.interface.normalized_default_prompts(),
                },
            }
            for plugin in loaded_plugins
        ],
        "agent_providers": [
            {
                "extension_id": plugin.provider_family,
                "display_name": plugin.display_name,
                "kind": "provider",
                "provider_family": plugin.provider_family,
                "adapter_id": plugin.adapter_id,
                "runtime_id": plugin.runtime_id,
                "metadata": plugin.metadata,
            }
            for plugin in list_agent_providers()
        ],
        "runtimes": [
            {
                "extension_id": plugin.runtime_id,
                "display_name": plugin.display_name,
                "kind": "runtime",
                "runtime_id": plugin.runtime_id,
                "provider_family": plugin.provider_family,
                "adapter_id": plugin.adapter_id,
                "transport": plugin.kind,
                "metadata": plugin.metadata,
            }
            for plugin in list_runtimes()
        ],
        "trackers": [
            {
                "extension_id": plugin.tracker_id,
                "display_name": plugin.display_name,
                "kind": "tracker",
                "transport": plugin.kind,
                "metadata": plugin.metadata,
            }
            for plugin in resolve_tracker_plugins(config)
        ],
        "notifiers": [
            {
                "extension_id": plugin.notifier_id,
                "display_name": plugin.display_name,
                "kind": "notifier",
                "transport": plugin.kind,
                "metadata": plugin.metadata,
            }
            for plugin in resolve_notifier_plugins(config)
        ],
    }


class ConnectorRequest(BaseModel):
    id: str
    name: str
    connector_type: str
    description: str = ""
    transport: str = "builtin"
    tags: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=lambda: ["codex", "claude", "gemini", "ollama"])
    risk_level: str = "medium"
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class SkillPackRequest(BaseModel):
    id: str
    name: str
    description: str
    prompt: str
    tags: list[str] = Field(default_factory=list)
    default_roles: list[str] = Field(default_factory=list)
    preferred_connectors: list[str] = Field(default_factory=list)
    enabled: bool = True


class RoutingPolicyRequest(BaseModel):
    role_id: str
    preferred_skill_packs: list[str] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    preferred_connectors: list[str] = Field(default_factory=list)
    forbidden_connectors: list[str] = Field(default_factory=list)


class PluginEnablementRequest(BaseModel):
    enabled: bool = True


class PluginOptionsRequest(BaseModel):
    values: dict[str, object] = Field(default_factory=dict)


def _require_plugin(config, plugin_id: str):
    normalized = build_plugin_id(plugin_id)
    discovered = {plugin.plugin_id: plugin for plugin in resolve_loaded_plugins(config)}
    plugin = discovered.get(normalized)
    if plugin is None:
        raise HTTPException(404, f"Plugin {plugin_id} not found")
    return normalized, plugin


@router.get("/catalog")
async def get_capabilities_catalog() -> dict:
    config = get_config()
    connectors = load_connectors_registry(config)
    return {
        "connectors": [connector.model_dump() for connector in connectors],
        "tools": [tool.model_dump() for tool in build_tool_catalog(connectors)],
        "skill_packs": [skill_pack.model_dump() for skill_pack in load_skill_packs_registry(config)],
        "roles": [role.model_dump() for role in load_role_templates()],
        "connector_types": [connector_type.model_dump() for connector_type in load_connector_type_catalog()],
        "routing_policies": [policy.model_dump() for policy in load_routing_policies_registry(config)],
        "launch_presets": [preset.model_dump() for preset in DEFAULT_LAUNCH_PRESETS],
        "provider_configs": config.resolved_provider_config_payloads(),
        "runtime_profiles": config.runtime_profile_payloads(),
        "extensions": _build_extension_registry(config),
    }


@router.get("/providers")
async def list_provider_configs() -> dict[str, list[dict]]:
    config = get_config()
    return {"provider_configs": config.resolved_provider_config_payloads()}


@router.get("/runtime-profiles")
async def list_runtime_profiles() -> dict[str, list[dict]]:
    config = get_config()
    return {"runtime_profiles": config.runtime_profile_payloads()}


@router.get("/connector-types")
async def list_connector_types() -> dict:
    return {"connector_types": [connector_type.model_dump() for connector_type in load_connector_type_catalog()]}


@router.get("/connectors")
async def list_connectors() -> dict[str, list[dict]]:
    config = get_config()
    return {"connectors": [connector.model_dump() for connector in load_connectors_registry(config)]}


@router.get("/tools")
async def list_tools() -> dict[str, list[dict]]:
    config = get_config()
    connectors = load_connectors_registry(config)
    return {"tools": [tool.model_dump() for tool in build_tool_catalog(connectors)]}


@router.get("/extensions")
async def list_extensions() -> dict[str, object]:
    return _build_extension_registry(get_config())


@router.get("/plugins")
async def list_plugins() -> dict[str, list[dict]]:
    return {"plugins": [plugin.model_dump() for plugin in resolve_loaded_plugins(get_config())]}


@router.get("/plugins/{plugin_id}/options")
async def get_plugin_options(plugin_id: str) -> dict[str, object]:
    config = get_config()
    _, plugin = _require_plugin(config, plugin_id)
    return {
        "plugin": plugin.model_dump(),
        "options": get_plugin_option_state(config, plugin).model_dump(),
    }


@router.put("/plugins/{plugin_id}/options")
async def update_plugin_options(plugin_id: str, request: PluginOptionsRequest) -> dict[str, object]:
    config = get_config()
    normalized, plugin = _require_plugin(config, plugin_id)
    if not plugin.user_config:
        raise HTTPException(400, f"Plugin {plugin_id} has no configurable options")
    validation = save_plugin_options(config, normalized, request.values, plugin.user_config)
    if not validation.valid:
        raise HTTPException(400, {"errors": validation.errors})
    _, refreshed = _require_plugin(config, normalized)
    return {
        "status": "ok",
        "plugin": refreshed.model_dump(),
        "options": get_plugin_option_state(config, refreshed).model_dump(),
    }


@router.get("/plugins/{plugin_id}/commands")
async def list_plugin_command_descriptors(plugin_id: str) -> dict[str, list[dict]]:
    config = get_config()
    normalized, _ = _require_plugin(config, plugin_id)
    return {
        "commands": [command.model_dump() for command in list_plugin_commands(config, plugin_id=normalized)]
    }


@router.get("/plugins/{plugin_id}/commands/{command_id}")
async def get_plugin_command_descriptor(plugin_id: str, command_id: str) -> dict[str, object]:
    config = get_config()
    normalized, _ = _require_plugin(config, plugin_id)
    command = next(
        (
            item
            for item in list_plugin_commands(config, plugin_id=normalized)
            if item.command_id == command_id
        ),
        None,
    )
    if command is None:
        raise HTTPException(404, f"Plugin command {command_id} not found")
    return {
        "command": command.model_dump(),
        "content": render_plugin_command_content(config, command),
    }


@router.get("/plugins/{plugin_id}/mcp")
async def list_plugin_mcp_descriptors(plugin_id: str) -> dict[str, list[dict]]:
    config = get_config()
    normalized, _ = _require_plugin(config, plugin_id)
    return {
        "mcp_servers": [
            server.model_dump()
            for server in list_plugin_mcp_servers(config, plugin_id=normalized)
        ]
    }


@router.get("/plugins/{plugin_id}/skills")
async def list_plugin_skill_descriptors(plugin_id: str) -> dict[str, list[dict]]:
    config = get_config()
    normalized, _ = _require_plugin(config, plugin_id)
    return {
        "skills": [skill.model_dump() for skill in list_plugin_skills(config, plugin_id=normalized)]
    }


@router.patch("/plugins/{plugin_id}")
async def update_plugin_enablement(plugin_id: str, request: PluginEnablementRequest) -> dict[str, object]:
    config = get_config()
    normalized, _ = _require_plugin(config, plugin_id)
    record = set_plugin_enabled(config, normalized, enabled=request.enabled)
    clear_plugin_cache()
    refreshed = {item.plugin_id: item for item in resolve_loaded_plugins(config)}[normalized]
    return {
        "status": "ok",
        "plugin": refreshed.model_dump(),
        "enablement": record.model_dump(),
    }


@router.post("/connectors")
async def create_connector(request: ConnectorRequest) -> dict:
    config = get_config()
    existing = {connector.id: connector for connector in load_connectors_registry(config)}
    current = existing.get(request.id)
    if current is not None and (current.built_in or current.managed):
        raise HTTPException(400, f"Connector {request.id} is managed and cannot be overwritten")
    if get_connector_type_schema(request.connector_type) is None:
        raise HTTPException(400, f"Unknown connector type: {request.connector_type}")
    connector = MCPConnector.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_connector(config, connector)
    return {"status": "ok", "connector": stored.model_dump()}


@router.patch("/connectors/{connector_id}")
async def update_connector(connector_id: str, request: ConnectorRequest) -> dict:
    if connector_id != request.id:
        raise HTTPException(400, "Connector id mismatch")
    config = get_config()
    existing = {connector.id: connector for connector in load_connectors_registry(config)}
    current = existing.get(connector_id)
    if current is None:
        raise HTTPException(404, f"Connector {connector_id} not found")
    if current.built_in or current.managed:
        raise HTTPException(400, f"Connector {connector_id} is managed and cannot be edited")
    if get_connector_type_schema(request.connector_type) is None:
        raise HTTPException(400, f"Unknown connector type: {request.connector_type}")
    connector = MCPConnector.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_connector(config, connector)
    return {"status": "ok", "connector": stored.model_dump()}


@router.post("/connectors/validate")
async def validate_connector(request: ConnectorRequest) -> dict:
    if get_connector_type_schema(request.connector_type) is None:
        raise HTTPException(400, f"Unknown connector type: {request.connector_type}")
    connector = MCPConnector.model_validate({**request.model_dump(), "built_in": False})
    result = validate_connector_config(connector)
    return {"status": "ok", "result": result.model_dump()}


@router.post("/connectors/{connector_id}/validate")
async def validate_saved_connector(connector_id: str) -> dict:
    config = get_config()
    existing = {connector.id: connector for connector in load_connectors_registry(config)}
    connector = existing.get(connector_id)
    if connector is None:
        raise HTTPException(404, f"Connector {connector_id} not found")
    result = validate_connector_config(connector)
    if connector.managed:
        return {
            "status": "ok",
            "connector": connector.model_dump(),
            "result": result.model_dump(),
        }
    stored = upsert_connector(
        config,
        connector.model_copy(
            update={
                "validation_status": result.status,
                "last_validation_result": result.model_dump(),
            }
        ),
    )
    return {
        "status": "ok",
        "connector": stored.model_dump(),
        "result": result.model_dump(),
    }


@router.delete("/connectors/{connector_id}")
async def remove_connector(connector_id: str) -> dict[str, str]:
    config = get_config()
    existing = {connector.id: connector for connector in load_connectors_registry(config)}
    connector = existing.get(connector_id)
    if connector is None:
        raise HTTPException(404, f"Connector {connector_id} not found")
    if connector.built_in or connector.managed:
        raise HTTPException(400, f"Connector {connector_id} is built in and cannot be deleted")
    delete_connector(config, connector_id)
    return {"status": "ok", "message": f"Connector {connector_id} deleted."}


@router.get("/skill-packs")
async def list_skill_packs() -> dict[str, list[dict]]:
    config = get_config()
    return {"skill_packs": [skill_pack.model_dump() for skill_pack in load_skill_packs_registry(config)]}


@router.post("/skill-packs")
async def create_skill_pack(request: SkillPackRequest) -> dict:
    config = get_config()
    skill_pack = SkillPack.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_skill_pack(config, skill_pack)
    return {"status": "ok", "skill_pack": stored.model_dump()}


@router.patch("/skill-packs/{skill_pack_id}")
async def update_skill_pack(skill_pack_id: str, request: SkillPackRequest) -> dict:
    if skill_pack_id != request.id:
        raise HTTPException(400, "Skill pack id mismatch")
    config = get_config()
    existing = {skill_pack.id for skill_pack in load_skill_packs_registry(config)}
    if skill_pack_id not in existing:
        raise HTTPException(404, f"Skill pack {skill_pack_id} not found")
    skill_pack = SkillPack.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_skill_pack(config, skill_pack)
    return {"status": "ok", "skill_pack": stored.model_dump()}


@router.delete("/skill-packs/{skill_pack_id}")
async def remove_skill_pack(skill_pack_id: str) -> dict[str, str]:
    config = get_config()
    existing = {skill_pack.id: skill_pack for skill_pack in load_skill_packs_registry(config)}
    skill_pack = existing.get(skill_pack_id)
    if skill_pack is None:
        raise HTTPException(404, f"Skill pack {skill_pack_id} not found")
    if skill_pack.built_in:
        raise HTTPException(400, f"Skill pack {skill_pack_id} is built in and cannot be deleted")
    delete_skill_pack(config, skill_pack_id)
    return {"status": "ok", "message": f"Skill pack {skill_pack_id} deleted."}


@router.get("/routing-policies")
async def list_routing_policies() -> dict[str, list[dict]]:
    config = get_config()
    return {"routing_policies": [policy.model_dump() for policy in load_routing_policies_registry(config)]}


@router.patch("/routing-policies/{role_id}")
async def update_routing_policy(role_id: str, request: RoutingPolicyRequest) -> dict:
    if role_id != request.role_id:
        raise HTTPException(400, "Routing policy role_id mismatch")
    known_roles = {role.id for role in load_role_templates()}
    if role_id not in known_roles:
        raise HTTPException(404, f"Role {role_id} not found")
    config = get_config()
    stored = upsert_routing_policy(config, RoutingPolicy.model_validate(request.model_dump()))
    return {"status": "ok", "routing_policy": stored.model_dump()}


@router.get("/launch-presets")
async def list_launch_presets() -> dict[str, list[dict]]:
    return {"launch_presets": [preset.model_dump() for preset in DEFAULT_LAUNCH_PRESETS]}
