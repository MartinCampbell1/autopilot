"""Guardrail policy decisions for plugin and plugin-defined MCP surfaces."""

from __future__ import annotations

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_models import LoadedPlugin, PluginMcpServerDescriptor


class PluginSurfacePolicyDecision(BaseModel):
    """Guardrail decision for one plugin or MCP runtime surface."""

    action: str = "allow"
    status: str = "ok"
    summary: str = ""
    issues: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    wrapper_mode: str = ""
    runtime_profile: str = ""


def _pick_runtime_profile(config: AutopilotConfig, preferred: str) -> str:
    available = {str(profile.id).strip() for profile in config.runtime_profiles}
    if preferred in available:
        return preferred
    resolved = config.resolve_runtime_profile(None)
    return str(resolved.id).strip()


def evaluate_loaded_plugin_policy(
    config: AutopilotConfig,
    plugin: LoadedPlugin,
) -> PluginSurfacePolicyDecision:
    """Classify one discovered plugin before exposing it to runtime surfaces."""

    del config
    issues = list(plugin.validation_errors)
    flags: list[str] = []
    if plugin.validation_status != "valid":
        flags.append("manifest_invalid")
        return PluginSurfacePolicyDecision(
            action="block",
            status="blocked",
            summary="Plugin is blocked until manifest validation issues are resolved.",
            issues=issues,
            flags=flags,
        )
    if not plugin.enabled:
        flags.append("disabled")
        return PluginSurfacePolicyDecision(
            action="allow",
            status="inactive",
            summary="Plugin is disabled and will not be projected into runtime surfaces.",
            issues=issues,
            flags=flags,
        )
    return PluginSurfacePolicyDecision(
        action="allow",
        status="ok",
        summary="Plugin manifest validated successfully.",
        issues=issues,
        flags=flags,
    )


def evaluate_plugin_mcp_policy(
    config: AutopilotConfig,
    plugin: LoadedPlugin,
    descriptor: PluginMcpServerDescriptor,
) -> PluginSurfacePolicyDecision:
    """Classify one plugin-defined MCP surface into allow, wrap, sandbox, or block."""

    issues: list[str] = []
    flags: list[str] = []
    if plugin.validation_status != "valid":
        issues.extend(plugin.validation_errors)
        flags.append("plugin_invalid")
    if descriptor.validation_status != "valid":
        issues.extend(descriptor.validation_errors)
        flags.append("descriptor_invalid")
    if descriptor.missing_option_keys:
        flags.append("missing_options")
    if descriptor.missing_env_vars:
        flags.append("missing_env")
    if issues:
        return PluginSurfacePolicyDecision(
            action="block",
            status="blocked",
            summary="Plugin MCP surface is blocked until validation issues are resolved.",
            issues=issues,
            flags=sorted(set(flags)),
        )
    if descriptor.transport == "stdio":
        return PluginSurfacePolicyDecision(
            action="sandbox",
            status="guarded",
            summary="Plugin stdio MCP surface should run under a local isolation profile.",
            flags=["local_exec"],
            wrapper_mode="sandbox-runner",
            runtime_profile=_pick_runtime_profile(config, "local"),
        )
    return PluginSurfacePolicyDecision(
        action="wrap",
        status="guarded",
        summary="Remote plugin MCP surface must run through the MCP wrapper path.",
        flags=["remote_mcp"],
        wrapper_mode="audit-proxy",
        runtime_profile=_pick_runtime_profile(config, "hybrid"),
    )
