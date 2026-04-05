"""Plugin-defined MCP extraction and managed connector projection."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from autopilot.core.capability_store import MCPConnector, ConnectorValidationResult, validate_connector_config
from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import LoadedPlugin, PluginMcpServerDescriptor
from autopilot.core.plugin_policy import evaluate_plugin_mcp_policy
from autopilot.core.plugin_storage import (
    get_plugin_option_state,
    load_plugin_options,
    substitute_plugin_variables,
    substitute_user_config_in_content,
)
from autopilot.core.plugins import resolve_loaded_plugins

_ENV_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def build_plugin_connector_id(plugin_id: str, server_name: str) -> str:
    """Build a stable connector id for one plugin-provided MCP server."""

    normalized_server = re.sub(r"[^a-z0-9]+", "-", str(server_name or "").strip().lower()).strip("-")
    normalized_server = normalized_server or "server"
    return f"plugin-{plugin_id}-{normalized_server}"


def _read_json_file(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object payload in {path}")
    return payload


def _normalize_string_map(value: object, *, field_name: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object of string values.")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        text = str(item).strip()
        if text:
            normalized[str(key)] = text
    return normalized


def _normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("args must be a list of strings.")
    return [str(item).strip() for item in value if str(item).strip()]


def _normalize_server_config(raw: object) -> tuple[dict[str, object], list[str]]:
    if not isinstance(raw, dict):
        return {}, ["MCP server config must be an object."]
    payload = dict(raw)
    issues: list[str] = []
    server_type = str(payload.get("type") or "").strip().lower()
    if not server_type:
        server_type = "stdio" if "command" in payload else "http" if "url" in payload else ""
    if server_type not in {"stdio", "http", "sse", "ws"}:
        issues.append(f"Unsupported MCP server type: {server_type or 'unknown'}.")
        return {}, issues

    normalized: dict[str, object] = {"type": server_type}
    if server_type == "stdio":
        command = str(payload.get("command") or "").strip()
        if not command:
            issues.append("`command` is required for stdio MCP servers.")
        normalized["command"] = command
        normalized["args"] = _normalize_string_list(payload.get("args"))
        try:
            normalized["env"] = _normalize_string_map(payload.get("env"), field_name="env")
        except ValueError as exc:
            issues.append(str(exc))
    else:
        url = str(payload.get("url") or "").strip()
        if not url:
            issues.append("`url` is required for remote MCP servers.")
        normalized["url"] = url
        try:
            normalized["headers"] = _normalize_string_map(payload.get("headers"), field_name="headers")
        except ValueError as exc:
            issues.append(str(exc))
    return normalized, issues


def _expand_env_preview(value: str) -> tuple[str, list[str]]:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        env_name = match.group(1)
        if env_name in os.environ:
            return f"[env:{env_name}]"
        missing.append(env_name)
        return f"[missing env:{env_name}]"

    return _ENV_VAR_RE.sub(replace, value), missing


def _preview_resolve_value(
    config: AutopilotConfig,
    plugin: LoadedPlugin,
    value: str,
) -> tuple[str, list[str]]:
    substituted = substitute_plugin_variables(value, plugin)
    if plugin.user_config:
        substituted = substitute_user_config_in_content(
            substituted,
            load_plugin_options(config, plugin.plugin_id),
            plugin.user_config,
        )
    return _expand_env_preview(substituted)


def _preview_config(config: AutopilotConfig, plugin: LoadedPlugin, normalized: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    missing_envs: list[str] = []
    if normalized["type"] == "stdio":
        preview_env: dict[str, str] = {}
        preview_command, command_missing = _preview_resolve_value(config, plugin, str(normalized.get("command") or ""))
        missing_envs.extend(command_missing)
        preview_args: list[str] = []
        for arg in normalized.get("args", []):
            rendered, arg_missing = _preview_resolve_value(config, plugin, str(arg))
            preview_args.append(rendered)
            missing_envs.extend(arg_missing)
        base_env = dict(normalized.get("env") or {})
        for key, value in {
            "CLAUDE_PLUGIN_ROOT": plugin.root_path,
            "CLAUDE_PLUGIN_DATA": plugin.data_dir,
            "AUTOPILOT_PLUGIN_ROOT": plugin.root_path,
            "AUTOPILOT_PLUGIN_DATA": plugin.data_dir,
            **base_env,
        }.items():
            if key in {"CLAUDE_PLUGIN_ROOT", "CLAUDE_PLUGIN_DATA", "AUTOPILOT_PLUGIN_ROOT", "AUTOPILOT_PLUGIN_DATA"}:
                preview_env[key] = str(value).replace("\\", "/")
                continue
            rendered, env_missing = _preview_resolve_value(config, plugin, str(value))
            preview_env[key] = rendered
            missing_envs.extend(env_missing)
        return (
            {
                "type": "stdio",
                "command": preview_command,
                "args": preview_args,
                "env": preview_env,
            },
            sorted(set(missing_envs)),
        )

    preview_url, url_missing = _preview_resolve_value(config, plugin, str(normalized.get("url") or ""))
    missing_envs.extend(url_missing)
    preview_headers: dict[str, str] = {}
    for key, value in dict(normalized.get("headers") or {}).items():
        rendered, header_missing = _preview_resolve_value(config, plugin, str(value))
        preview_headers[key] = rendered
        missing_envs.extend(header_missing)
    return (
        {
            "type": normalized["type"],
            "url": preview_url,
            "headers": preview_headers,
        },
        sorted(set(missing_envs)),
    )


def _load_servers_from_file(path: Path) -> tuple[dict[str, object], list[str]]:
    try:
        payload = _read_json_file(path)
    except Exception as exc:
        return {}, [f"Failed to load MCP config file {path}: {exc}"]
    raw_servers = payload.get("mcpServers", payload)
    if not isinstance(raw_servers, dict):
        return {}, [f"MCP config file {path} must contain an object of servers."]
    return dict(raw_servers), []


def _manifest_specs(plugin: LoadedPlugin) -> list[tuple[str, object, str]]:
    specs: list[tuple[str, object, str]] = []
    if plugin.mcp_paths:
        explicit_paths = {str(item).strip() for item in plugin.mcp_paths}
        default_path = str((Path(plugin.root_path) / ".mcp.json").resolve())
        for path in plugin.mcp_paths:
            kind = "default_file" if str(path).strip() == default_path and plugin.mcp_server_spec is None else "file"
            specs.append((kind, path, path))
        if default_path not in explicit_paths and (Path(plugin.root_path) / ".mcp.json").exists():
            specs.insert(0, ("default_file", default_path, default_path))
    elif (Path(plugin.root_path) / ".mcp.json").exists():
        default_path = str((Path(plugin.root_path) / ".mcp.json").resolve())
        specs.append(("default_file", default_path, default_path))

    if isinstance(plugin.mcp_server_spec, dict):
        specs.append(("inline", plugin.mcp_server_spec, ""))
    elif isinstance(plugin.mcp_server_spec, list):
        for item in plugin.mcp_server_spec:
            if isinstance(item, dict):
                specs.append(("inline", item, ""))
    return specs


def list_plugin_mcp_servers(
    config: AutopilotConfig,
    *,
    plugin_id: str | None = None,
    enabled_only: bool = False,
) -> list[PluginMcpServerDescriptor]:
    """Resolve plugin-defined MCP servers into redacted descriptors."""

    descriptors: list[PluginMcpServerDescriptor] = []
    plugin_filter = str(plugin_id or "").strip().lower()
    for plugin in resolve_loaded_plugins(config):
        if plugin_filter and plugin.plugin_id != plugin_filter:
            continue
        if enabled_only and not plugin.enabled:
            continue

        option_state = get_plugin_option_state(config, plugin)
        merged_servers: dict[str, tuple[dict[str, object], str, str]] = {}
        source_errors: list[str] = []
        for source_kind, source_payload, source_path in _manifest_specs(plugin):
            if isinstance(source_payload, str):
                raw_servers, errors = _load_servers_from_file(Path(source_payload))
                source_errors.extend(errors)
            elif isinstance(source_payload, dict):
                raw_servers = dict(source_payload)
                errors = []
            else:
                continue
            if errors:
                source_errors.extend(errors)
                continue
            for server_name, raw_config in raw_servers.items():
                normalized, issues = _normalize_server_config(raw_config)
                merged_servers[str(server_name)] = (
                    normalized,
                    source_kind,
                    source_path,
                )
                if issues:
                    merged_servers[str(server_name)] = (
                        {"__issues__": issues, **normalized},
                        source_kind,
                        source_path,
                    )

        for server_name in sorted(merged_servers):
            normalized, source_kind, source_path = merged_servers[server_name]
            structural_issues = list(normalized.pop("__issues__", [])) if "__issues__" in normalized else []
            preview_config, missing_envs = _preview_config(config, plugin, normalized) if not structural_issues else ({}, [])
            validation_errors = list(source_errors) + structural_issues
            if option_state.unconfigured_keys:
                validation_errors.append(
                    "Plugin MCP server requires unresolved plugin options: "
                    + ", ".join(option_state.unconfigured_keys)
                )
            if missing_envs:
                validation_errors.append(
                    "Plugin MCP server references missing environment variables: "
                    + ", ".join(missing_envs)
                )
            transport = "stdio" if normalized.get("type") == "stdio" else "http"
            descriptor = PluginMcpServerDescriptor(
                plugin_id=plugin.plugin_id,
                server_name=server_name,
                connector_id=build_plugin_connector_id(plugin.plugin_id, server_name),
                display_name=f"{plugin.display_name or plugin.name}: {server_name}",
                transport=transport,
                source_kind=source_kind,
                source_path=source_path,
                config=preview_config,
                validation_status="invalid" if validation_errors else "valid",
                validation_errors=validation_errors,
                missing_env_vars=missing_envs,
                missing_option_keys=list(option_state.unconfigured_keys),
                sensitive_option_keys=list(option_state.sensitive_keys),
            )
            decision = evaluate_plugin_mcp_policy(config, plugin, descriptor)
            descriptors.append(
                descriptor.model_copy(
                    update={
                        "policy_action": decision.action,
                        "policy_status": decision.status,
                        "policy_summary": decision.summary,
                        "policy_flags": list(decision.flags),
                        "wrapper_mode": decision.wrapper_mode,
                        "recommended_runtime_profile": decision.runtime_profile,
                        "runtime_active": plugin.enabled and decision.action != "block",
                    }
                )
            )
    descriptors.sort(key=lambda item: (item.plugin_id, item.server_name, item.connector_id))
    return descriptors


def _descriptor_to_validation_result(descriptor: PluginMcpServerDescriptor, connector: MCPConnector) -> ConnectorValidationResult:
    structural = validate_connector_config(connector)
    issues: list[str] = []
    if not structural.ok:
        issues.extend(line[2:] if line.startswith("- ") else line for line in structural.log.splitlines() if line.strip())
    issues.extend(descriptor.validation_errors)
    if issues:
        return ConnectorValidationResult(
            ok=False,
            status="invalid",
            summary=f"{len(issues)} validation issue(s) found.",
            log="\n".join(f"- {issue}" for issue in issues),
            checked_fields=list(structural.checked_fields),
        )
    return ConnectorValidationResult(
        ok=True,
        status="valid",
        summary="Plugin MCP connector looks valid.",
        log="Validation completed successfully.",
        checked_fields=list(structural.checked_fields),
    )


def plugin_mcp_connectors(config: AutopilotConfig) -> list[MCPConnector]:
    """Project enabled plugin MCP servers into managed MCP connectors."""

    connectors: list[MCPConnector] = []
    plugins = {plugin.plugin_id: plugin for plugin in resolve_loaded_plugins(config)}
    for descriptor in list_plugin_mcp_servers(config, enabled_only=True):
        plugin = plugins.get(descriptor.plugin_id)
        if plugin is None:
            continue
        connector = MCPConnector(
            id=descriptor.connector_id,
            name=descriptor.display_name,
            connector_type="mcp_server",
            description=f"Plugin-provided MCP server `{descriptor.server_name}` from `{plugin.display_name or plugin.name}`.",
            transport=descriptor.transport,
            tags=["plugin", "mcp", descriptor.plugin_id, f"policy-{descriptor.policy_action}"],
            providers=["codex", "claude", "gemini", "ollama"],
            risk_level="high" if descriptor.policy_action == "wrap" else "medium",
            scopes=["workspace"] if descriptor.transport == "stdio" else ["network"],
            enabled=plugin.enabled and descriptor.policy_action != "block",
            built_in=False,
            config={
                **descriptor.config,
                "plugin_source_kind": descriptor.source_kind,
                "plugin_source_path": descriptor.source_path,
                "plugin_policy_action": descriptor.policy_action,
                "plugin_policy_status": descriptor.policy_status,
                "plugin_policy_summary": descriptor.policy_summary,
                "plugin_policy_flags": list(descriptor.policy_flags),
                "plugin_policy_wrapper_mode": descriptor.wrapper_mode,
                "plugin_policy_runtime_profile": descriptor.recommended_runtime_profile,
            },
            validation_status=descriptor.validation_status,
            source="plugin",
            managed=True,
            origin_plugin_id=descriptor.plugin_id,
            origin_server_name=descriptor.server_name,
        )
        validation = _descriptor_to_validation_result(descriptor, connector)
        connectors.append(
            connector.model_copy(
                update={
                    "validation_status": "blocked" if descriptor.policy_action == "block" else validation.status,
                    "last_validation_result": validation.model_copy(
                        update={
                            "ok": False if descriptor.policy_action == "block" else validation.ok,
                            "status": "blocked" if descriptor.policy_action == "block" else validation.status,
                            "summary": descriptor.policy_summary if descriptor.policy_action == "block" else validation.summary,
                            "log": (
                                (
                                    validation.log.rstrip()
                                    + ("\n" if validation.log.strip() and descriptor.validation_errors else "")
                                    + "\n".join(f"- {issue}" for issue in descriptor.validation_errors)
                                ).strip()
                                if descriptor.policy_action == "block"
                                else validation.log
                            ),
                        }
                    ).model_dump(),
                }
            )
        )
    connectors.sort(key=lambda item: (item.origin_plugin_id or "", item.origin_server_name or "", item.id))
    return connectors
