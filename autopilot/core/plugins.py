"""Minimal plugin slot registry for provider/runtime/tracker/notifier extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from autopilot.core.config import AutopilotConfig, NotificationChannelConfig, TrackerConfig
from autopilot.core.plugin_loader import load_all_plugins
from autopilot.core.plugin_models import LoadedPlugin
from autopilot.core.notifiers import channel_ready


@dataclass(slots=True)
class AgentProviderPlugin:
    provider_family: str
    adapter_id: str
    runtime_id: str
    display_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RuntimePlugin:
    runtime_id: str
    display_name: str
    kind: str
    provider_family: str | None = None
    adapter_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TrackerPlugin:
    tracker_id: str
    display_name: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class NotifierPlugin:
    notifier_id: str
    display_name: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


class PluginRegistry:
    """In-process registry for extension slots."""

    def __init__(self) -> None:
        self.agent_providers: dict[str, AgentProviderPlugin] = {}
        self.runtimes: dict[str, RuntimePlugin] = {}
        self.trackers: dict[str, TrackerPlugin] = {}
        self.notifiers: dict[str, NotifierPlugin] = {}

    def register_agent_provider(self, plugin: AgentProviderPlugin) -> AgentProviderPlugin:
        self.agent_providers[plugin.provider_family] = plugin
        return plugin

    def unregister_agent_provider(self, provider_family: str) -> AgentProviderPlugin | None:
        return self.agent_providers.pop(provider_family, None)

    def register_runtime(self, plugin: RuntimePlugin) -> RuntimePlugin:
        self.runtimes[plugin.runtime_id] = plugin
        return plugin

    def unregister_runtime(self, runtime_id: str) -> RuntimePlugin | None:
        return self.runtimes.pop(runtime_id, None)

    def register_tracker(self, plugin: TrackerPlugin) -> TrackerPlugin:
        self.trackers[plugin.tracker_id] = plugin
        return plugin

    def register_notifier(self, plugin: NotifierPlugin) -> NotifierPlugin:
        self.notifiers[plugin.notifier_id] = plugin
        return plugin


_REGISTRY = PluginRegistry()


def register_agent_provider(plugin: AgentProviderPlugin) -> AgentProviderPlugin:
    return _REGISTRY.register_agent_provider(plugin)


def unregister_agent_provider(provider_family: str) -> AgentProviderPlugin | None:
    return _REGISTRY.unregister_agent_provider(provider_family)


def get_agent_provider(provider_family: str) -> AgentProviderPlugin:
    return _REGISTRY.agent_providers[provider_family]


def list_agent_providers() -> list[AgentProviderPlugin]:
    return list(_REGISTRY.agent_providers.values())


def register_runtime(plugin: RuntimePlugin) -> RuntimePlugin:
    return _REGISTRY.register_runtime(plugin)


def unregister_runtime(runtime_id: str) -> RuntimePlugin | None:
    return _REGISTRY.unregister_runtime(runtime_id)


def get_runtime(runtime_id: str) -> RuntimePlugin:
    return _REGISTRY.runtimes[runtime_id]


def list_runtimes() -> list[RuntimePlugin]:
    return list(_REGISTRY.runtimes.values())


def register_tracker(plugin: TrackerPlugin) -> TrackerPlugin:
    return _REGISTRY.register_tracker(plugin)


def list_trackers() -> list[TrackerPlugin]:
    return list(_REGISTRY.trackers.values())


def register_notifier(plugin: NotifierPlugin) -> NotifierPlugin:
    return _REGISTRY.register_notifier(plugin)


def list_notifiers() -> list[NotifierPlugin]:
    return list(_REGISTRY.notifiers.values())


def tracker_plugin_from_config(tracker: TrackerConfig) -> TrackerPlugin:
    return TrackerPlugin(
        tracker_id=tracker.id,
        display_name=tracker.display_name,
        kind=tracker.transport,
        metadata={
            "source": "config",
            "tracker_kind": tracker.kind,
            "transport": tracker.transport,
            "endpoint": tracker.endpoint,
            "auth_strategy": tracker.auth_strategy,
            "event_kinds": list(tracker.event_kinds),
            "supports_ingest": True,
            **dict(tracker.metadata),
        },
    )


def notifier_plugin_from_channel(channel: NotificationChannelConfig) -> NotifierPlugin:
    target = channel.webhook_url or channel.webhook_url_env or ",".join(channel.email_to) or "configured-channel"
    return NotifierPlugin(
        notifier_id=channel.name,
        display_name=channel.name,
        kind=channel.kind,
        metadata={
            "source": "config",
            "transport": channel.kind,
            "events": list(channel.events),
            "target": target,
            "ready": channel_ready(channel),
        },
    )


def resolve_tracker_plugins(config: AutopilotConfig) -> list[TrackerPlugin]:
    trackers = {plugin.tracker_id: plugin for plugin in list_trackers()}
    for tracker in config.trackers:
        plugin = tracker_plugin_from_config(tracker)
        trackers[plugin.tracker_id] = plugin
    return list(trackers.values())


def resolve_notifier_plugins(config: AutopilotConfig) -> list[NotifierPlugin]:
    notifiers = {plugin.notifier_id: plugin for plugin in list_notifiers()}
    for channel in config.notifications:
        plugin = notifier_plugin_from_channel(channel)
        notifiers[plugin.notifier_id] = plugin
    return list(notifiers.values())


def resolve_loaded_plugins(config: AutopilotConfig) -> list[LoadedPlugin]:
    """Return discovered on-disk plugins with validation and enablement metadata."""

    return load_all_plugins(config, use_cache=False)


def _register_builtin_slots() -> None:
    register_tracker(
        TrackerPlugin(
            tracker_id="project_state",
            display_name="Project State Tracker",
            kind="filesystem",
            metadata={"module": "autopilot.core.project_store", "source": "builtin", "supports_ingest": False},
        )
    )
    register_notifier(
        NotifierPlugin(
            notifier_id="telegram",
            display_name="Telegram",
            kind="telegram",
            metadata={"source": "builtin"},
        )
    )
    register_notifier(
        NotifierPlugin(
            notifier_id="slack_webhook",
            display_name="Slack Webhook",
            kind="slack_webhook",
            metadata={"source": "builtin"},
        )
    )
    register_notifier(
        NotifierPlugin(
            notifier_id="webhook",
            display_name="Webhook",
            kind="webhook",
            metadata={"source": "builtin"},
        )
    )
    register_notifier(
        NotifierPlugin(
            notifier_id="email",
            display_name="Email",
            kind="email",
            metadata={"source": "builtin"},
        )
    )
    register_notifier(
        NotifierPlugin(
            notifier_id="script",
            display_name="Script",
            kind="script",
            metadata={"source": "builtin"},
        )
    )


_register_builtin_slots()
