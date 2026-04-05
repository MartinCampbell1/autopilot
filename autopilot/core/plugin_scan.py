"""Preflight scan and inventory helpers for plugin and MCP runtime surfaces."""

from __future__ import annotations

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.plugin_mcp import list_plugin_mcp_servers
from autopilot.core.plugin_policy import evaluate_loaded_plugin_policy
from autopilot.core.plugin_storage import get_plugin_option_state
from autopilot.core.plugins import resolve_loaded_plugins


class PluginRuntimeScanSummary(BaseModel):
    """Aggregate preflight scan counts for plugin runtime surfaces."""

    plugin_count: int = 0
    enabled_plugin_count: int = 0
    invalid_plugin_count: int = 0
    blocked_plugin_count: int = 0
    mcp_server_count: int = 0
    active_mcp_server_count: int = 0
    blocked_mcp_server_count: int = 0
    wrapped_surface_count: int = 0
    sandboxed_surface_count: int = 0
    recommended_runtime_profile: str = "cloud"


class PluginRuntimePluginRecord(BaseModel):
    """Per-plugin preflight scan result."""

    plugin_id: str
    display_name: str
    enabled: bool = True
    validation_status: str = "valid"
    policy_action: str = "allow"
    policy_status: str = "ok"
    policy_summary: str = ""
    policy_flags: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    configured_option_keys: list[str] = Field(default_factory=list)
    unconfigured_option_keys: list[str] = Field(default_factory=list)
    mcp_server_count: int = 0
    active_mcp_server_count: int = 0
    blocked_mcp_server_count: int = 0
    wrapped_surface_count: int = 0
    sandboxed_surface_count: int = 0
    recommended_runtime_profile: str = ""


class PluginRuntimeScan(BaseModel):
    """Full preflight inventory for plugin and MCP surfaces."""

    summary: PluginRuntimeScanSummary = Field(default_factory=PluginRuntimeScanSummary)
    plugins: list[PluginRuntimePluginRecord] = Field(default_factory=list)
    mcp_servers: list[dict[str, object]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


def _recommended_profile(actions: list[str]) -> str:
    if "wrap" in actions:
        return "hybrid"
    if "sandbox" in actions:
        return "local"
    return "cloud"


def build_plugin_runtime_scan(config: AutopilotConfig) -> PluginRuntimeScan:
    """Inventory plugin/MCP runtime surfaces and classify their guardrail posture."""

    plugins = resolve_loaded_plugins(config)
    mcp_servers = list_plugin_mcp_servers(config)
    option_states = {
        plugin.plugin_id: get_plugin_option_state(config, plugin)
        for plugin in plugins
    }
    enabled_plugins = {plugin.plugin_id for plugin in plugins if plugin.enabled}
    enabled_servers = [server for server in mcp_servers if server.plugin_id in enabled_plugins]
    active_servers = [server for server in enabled_servers if server.runtime_active]
    blocked_plugin_count = 0
    plugin_records: list[PluginRuntimePluginRecord] = []

    for plugin in plugins:
        decision = evaluate_loaded_plugin_policy(config, plugin)
        if decision.action == "block":
            blocked_plugin_count += 1
        related_servers = [server for server in mcp_servers if server.plugin_id == plugin.plugin_id]
        enabled_related = [server for server in related_servers if plugin.enabled]
        active_related = [server for server in enabled_related if server.runtime_active]
        active_actions = [server.policy_action for server in enabled_related if server.policy_action != "block"]
        option_state = option_states[plugin.plugin_id]
        plugin_records.append(
            PluginRuntimePluginRecord(
                plugin_id=plugin.plugin_id,
                display_name=plugin.display_name or plugin.name,
                enabled=plugin.enabled,
                validation_status=plugin.validation_status,
                policy_action=decision.action,
                policy_status=decision.status,
                policy_summary=decision.summary,
                policy_flags=list(decision.flags),
                issues=list(decision.issues),
                configured_option_keys=list(option_state.configured_keys),
                unconfigured_option_keys=list(option_state.unconfigured_keys),
                mcp_server_count=len(related_servers),
                active_mcp_server_count=len(active_related),
                blocked_mcp_server_count=sum(1 for server in enabled_related if server.policy_action == "block"),
                wrapped_surface_count=sum(1 for server in enabled_related if server.policy_action == "wrap"),
                sandboxed_surface_count=sum(1 for server in enabled_related if server.policy_action == "sandbox"),
                recommended_runtime_profile="" if not active_actions else _recommended_profile(active_actions),
            )
        )

    recommendations: list[str] = []
    if blocked_plugin_count or any(server.policy_action == "block" for server in enabled_servers):
        recommendations.append(
            "Fix or disable blocked plugin and MCP surfaces before relying on runtime integrations."
        )
    if any(server.policy_action == "wrap" for server in enabled_servers):
        recommendations.append(
            "Keep remote plugin MCP surfaces behind wrapper mode and review their headers/options before enabling them in production."
        )
    if any(server.policy_action == "sandbox" for server in enabled_servers):
        recommendations.append(
            "Prefer the local runtime profile when enabling stdio plugin MCP surfaces."
        )
    recommendations = list(dict.fromkeys(recommendations))

    summary = PluginRuntimeScanSummary(
        plugin_count=len(plugins),
        enabled_plugin_count=sum(1 for plugin in plugins if plugin.enabled),
        invalid_plugin_count=sum(1 for plugin in plugins if plugin.validation_status != "valid"),
        blocked_plugin_count=blocked_plugin_count,
        mcp_server_count=len(mcp_servers),
        active_mcp_server_count=len(active_servers),
        blocked_mcp_server_count=sum(1 for server in enabled_servers if server.policy_action == "block"),
        wrapped_surface_count=sum(1 for server in enabled_servers if server.policy_action == "wrap"),
        sandboxed_surface_count=sum(1 for server in enabled_servers if server.policy_action == "sandbox"),
        recommended_runtime_profile=_recommended_profile(
            [server.policy_action for server in enabled_servers if server.policy_action != "block"]
        ),
    )
    plugin_records.sort(key=lambda item: (item.display_name.lower(), item.plugin_id))
    server_payloads = [server.model_dump() for server in mcp_servers]
    server_payloads.sort(key=lambda item: (str(item.get("plugin_id") or ""), str(item.get("server_name") or "")))
    return PluginRuntimeScan(
        summary=summary,
        plugins=plugin_records,
        mcp_servers=server_payloads,
        recommendations=recommendations,
    )
