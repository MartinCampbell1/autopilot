"""Configuration management for Autopilot."""

from __future__ import annotations

import os
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml


@dataclass
class AccountAllocation:
    total: int = 20
    workers: int = 14
    critics: int = 5
    intake: int = 1


@dataclass
class NotificationChannelConfig:
    name: str
    kind: str
    enabled: bool = True
    events: list[str] = field(default_factory=list)
    token: str | None = None
    token_env: str | None = None
    chat_id: str | None = None
    chat_id_env: str | None = None
    webhook_url: str | None = None
    webhook_url_env: str | None = None
    email_to: list[str] = field(default_factory=list)
    email_from: str | None = None
    subject_prefix: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_password_env: str | None = None
    smtp_use_tls: bool = True
    command: list[str] = field(default_factory=list)


@dataclass
class TrackerConfig:
    id: str
    display_name: str
    kind: str
    transport: str
    endpoint: str | None = None
    auth_strategy: str = "none"
    event_kinds: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class ProviderConfig:
    id: str
    family: str
    mode: str
    transport: str
    endpoint: str | None = None
    command: list[str] = field(default_factory=list)
    auth_strategy: str = "managed_session"
    capabilities: list[str] = field(default_factory=list)


@dataclass
class RuntimeProfileConfig:
    id: str
    sandbox_mode: str
    network_policy: str
    filesystem_policy: str
    default_tools: list[str] = field(default_factory=list)


def _default_runtime_profiles() -> list[RuntimeProfileConfig]:
    return [
        RuntimeProfileConfig(
            id="cloud",
            sandbox_mode="host",
            network_policy="provider-default",
            filesystem_policy="workspace-write",
            default_tools=["shell", "git", "browser"],
        ),
        RuntimeProfileConfig(
            id="local",
            sandbox_mode="host",
            network_policy="local-only",
            filesystem_policy="workspace-write",
            default_tools=["shell", "git"],
        ),
        RuntimeProfileConfig(
            id="hybrid",
            sandbox_mode="host",
            network_policy="mixed",
            filesystem_policy="workspace-write",
            default_tools=["shell", "git", "browser"],
        ),
    ]


@dataclass
class AutopilotConfig:
    accounts: AccountAllocation = field(default_factory=AccountAllocation)
    codex_timeout_sec: int = 1800
    cooldown_base_sec: int = 300
    max_retries_per_provider: int = 3
    tool_result_inline_bytes_limit: int = 16384
    tool_result_preview_chars: int = 1200
    providers_order: list[str] = field(default_factory=lambda: ["codex", "claude", "gemini"])
    autopilot_home_override: str | None = None
    profiles_dir_override: str | None = None
    notifications: list[NotificationChannelConfig] = field(default_factory=list)
    trackers: list[TrackerConfig] = field(default_factory=list)
    providers: list[ProviderConfig] = field(default_factory=list)
    runtime_profiles: list[RuntimeProfileConfig] = field(default_factory=_default_runtime_profiles)

    @property
    def autopilot_home(self) -> Path:
        override = self.autopilot_home_override or os.getenv("AUTOPILOT_HOME")
        if override:
            return Path(override).expanduser()
        return Path.home() / ".autopilot"

    @property
    def profiles_dir(self) -> Path:
        override = self.profiles_dir_override or os.getenv("AUTOPILOT_PROFILES_DIR")
        if override:
            return Path(override).expanduser()
        return self.autopilot_home / "profiles"

    @property
    def state_db_path(self) -> Path:
        return self.autopilot_home / "state.db"

    @property
    def projects_yaml_path(self) -> Path:
        return self.autopilot_home / "projects.yaml"

    @property
    def runtime_state_dir(self) -> Path:
        return self.autopilot_home / "state"

    @property
    def account_probe_state_path(self) -> Path:
        return self.runtime_state_dir / "account-probes.json"

    @property
    def control_plane_state_dir(self) -> Path:
        return self.runtime_state_dir / "control-plane"

    @property
    def events_log_path(self) -> Path:
        return self.autopilot_home / "events" / "events.jsonl"

    @property
    def connectors_json_path(self) -> Path:
        return self.autopilot_home / "connectors.json"

    @property
    def skill_packs_json_path(self) -> Path:
        return self.autopilot_home / "skill-packs.json"

    @property
    def routing_policies_json_path(self) -> Path:
        return self.autopilot_home / "routing-policies.json"

    @property
    def plugins_dir(self) -> Path:
        return self.autopilot_home / "plugins"

    @property
    def plugin_state_dir(self) -> Path:
        return self.control_plane_state_dir / "plugins"

    @property
    def plugin_enablement_json_path(self) -> Path:
        return self.plugin_state_dir / "enablement.json"

    @property
    def plugin_data_root_dir(self) -> Path:
        return self.plugin_state_dir / "data"

    @property
    def plugin_options_json_path(self) -> Path:
        return self.plugin_state_dir / "options.json"

    @property
    def plugin_secrets_json_path(self) -> Path:
        return self.plugin_state_dir / "secrets.json"

    @property
    def tool_permissions_json_path(self) -> Path:
        return self.control_plane_state_dir / "tool-permissions.json"

    @property
    def tool_permission_denials_json_path(self) -> Path:
        return self.control_plane_state_dir / "tool-permission-denials.json"

    @property
    def tool_results_dir(self) -> Path:
        return self.control_plane_state_dir / "tool-results"

    def plugin_data_dir(self, plugin_id: str) -> Path:
        normalized = str(plugin_id or "").strip().lower() or "unknown-plugin"
        return self.plugin_data_root_dir / normalized

    def default_provider_config(self, provider: str) -> ProviderConfig:
        from autopilot.core.adapters import get_adapter

        adapter = get_adapter(provider)
        return ProviderConfig(
            id=adapter.provider_family,
            family=adapter.provider_family,
            mode=adapter.provider_mode,
            transport=adapter.transport,
            command=adapter.default_command(),
            auth_strategy=adapter.auth_strategy,
            capabilities=list(adapter.capabilities),
        )

    def resolved_provider_configs(self) -> list[ProviderConfig]:
        resolved: dict[str, ProviderConfig] = {}
        for provider in self.providers_order:
            try:
                resolved[provider] = self.default_provider_config(provider)
            except ValueError:
                continue
        for provider in self.providers:
            resolved[provider.id] = provider
        return list(resolved.values())

    def configured_provider_families(self) -> list[str]:
        families: list[str] = []
        for provider in self.resolved_provider_configs():
            if provider.family not in families:
                families.append(provider.family)
        return families

    def provider_configs_for_family(self, family: str) -> list[ProviderConfig]:
        return [provider for provider in self.resolved_provider_configs() if provider.family == family]

    def resolve_provider_config(self, family: str, provider_id: str | None = None) -> ProviderConfig:
        candidates = self.provider_configs_for_family(family)
        if provider_id:
            selected = next((provider for provider in candidates if provider.id == provider_id), None)
            if selected is not None:
                return selected
        if candidates:
            return candidates[0]
        return self.default_provider_config(family)

    def resolve_runtime_profile(self, profile_id: str | None = None) -> RuntimeProfileConfig:
        requested = str(profile_id or "").strip()
        if requested:
            selected = next((profile for profile in self.runtime_profiles if profile.id == requested), None)
            if selected is not None:
                return selected
        return self.runtime_profiles[0] if self.runtime_profiles else _default_runtime_profiles()[0]

    def resolved_provider_config_payloads(self) -> list[dict[str, object]]:
        return [asdict(provider) for provider in self.resolved_provider_configs()]

    def runtime_profile_payloads(self) -> list[dict[str, object]]:
        return [asdict(profile) for profile in self.runtime_profiles]


DEFAULT_CONFIG = AutopilotConfig()


def _serialize_notification_channel(channel: NotificationChannelConfig) -> dict[str, object]:
    return {
        "name": channel.name,
        "kind": channel.kind,
        "enabled": channel.enabled,
        "events": list(channel.events),
        "token": channel.token,
        "token_env": channel.token_env,
        "chat_id": channel.chat_id,
        "chat_id_env": channel.chat_id_env,
        "webhook_url": channel.webhook_url,
        "webhook_url_env": channel.webhook_url_env,
        "email_to": list(channel.email_to),
        "email_from": channel.email_from,
        "subject_prefix": channel.subject_prefix,
        "smtp_host": channel.smtp_host,
        "smtp_port": channel.smtp_port,
        "smtp_username": channel.smtp_username,
        "smtp_password": channel.smtp_password,
        "smtp_password_env": channel.smtp_password_env,
        "smtp_use_tls": channel.smtp_use_tls,
        "command": list(channel.command),
    }


def _serialize_tracker_config(tracker: TrackerConfig) -> dict[str, object]:
    return {
        "id": tracker.id,
        "display_name": tracker.display_name,
        "kind": tracker.kind,
        "transport": tracker.transport,
        "endpoint": tracker.endpoint,
        "auth_strategy": tracker.auth_strategy,
        "event_kinds": list(tracker.event_kinds),
        "metadata": dict(tracker.metadata),
    }


def _serialize_provider_config(provider: ProviderConfig) -> dict[str, object]:
    return {
        "id": provider.id,
        "family": provider.family,
        "mode": provider.mode,
        "transport": provider.transport,
        "endpoint": provider.endpoint,
        "command": list(provider.command),
        "auth_strategy": provider.auth_strategy,
        "capabilities": list(provider.capabilities),
    }


def _serialize_runtime_profile(profile: RuntimeProfileConfig) -> dict[str, object]:
    return {
        "id": profile.id,
        "sandbox_mode": profile.sandbox_mode,
        "network_policy": profile.network_policy,
        "filesystem_policy": profile.filesystem_policy,
        "default_tools": list(profile.default_tools),
    }


def _load_notification_channel(raw: object) -> NotificationChannelConfig | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()
    kind = str(raw.get("kind") or "").strip()
    if not name or not kind:
        return None
    command_value = raw.get("command")
    if isinstance(command_value, str):
        command = shlex.split(command_value)
    elif isinstance(command_value, list):
        command = [str(part) for part in command_value if str(part).strip()]
    else:
        command = []
    email_to_value = raw.get("email_to") or []
    if isinstance(email_to_value, str):
        email_to = [item.strip() for item in email_to_value.split(",") if item.strip()]
    elif isinstance(email_to_value, list):
        email_to = [str(item).strip() for item in email_to_value if str(item).strip()]
    else:
        email_to = []
    events_value = raw.get("events") or []
    if isinstance(events_value, str):
        events = [item.strip() for item in events_value.split(",") if item.strip()]
    elif isinstance(events_value, list):
        events = [str(item).strip() for item in events_value if str(item).strip()]
    else:
        events = []
    return NotificationChannelConfig(
        name=name,
        kind=kind,
        enabled=bool(raw.get("enabled", True)),
        events=events,
        token=raw.get("token"),
        token_env=raw.get("token_env"),
        chat_id=raw.get("chat_id"),
        chat_id_env=raw.get("chat_id_env"),
        webhook_url=raw.get("webhook_url"),
        webhook_url_env=raw.get("webhook_url_env"),
        email_to=email_to,
        email_from=raw.get("email_from"),
        subject_prefix=raw.get("subject_prefix"),
        smtp_host=raw.get("smtp_host"),
        smtp_port=int(raw.get("smtp_port", 587)),
        smtp_username=raw.get("smtp_username"),
        smtp_password=raw.get("smtp_password"),
        smtp_password_env=raw.get("smtp_password_env"),
        smtp_use_tls=bool(raw.get("smtp_use_tls", True)),
        command=command,
    )


def _load_provider_config(raw: object) -> ProviderConfig | None:
    if not isinstance(raw, dict):
        return None
    provider_id = str(raw.get("id") or "").strip()
    family = str(raw.get("family") or "").strip()
    mode = str(raw.get("mode") or "").strip()
    transport = str(raw.get("transport") or "").strip()
    if not provider_id or not family or not mode or not transport:
        return None
    command_value = raw.get("command")
    if isinstance(command_value, str):
        command = shlex.split(command_value)
    elif isinstance(command_value, list):
        command = [str(part) for part in command_value if str(part).strip()]
    else:
        command = []
    capabilities_value = raw.get("capabilities") or []
    if isinstance(capabilities_value, str):
        capabilities = [item.strip() for item in capabilities_value.split(",") if item.strip()]
    elif isinstance(capabilities_value, list):
        capabilities = [str(item).strip() for item in capabilities_value if str(item).strip()]
    else:
        capabilities = []
    return ProviderConfig(
        id=provider_id,
        family=family,
        mode=mode,
        transport=transport,
        endpoint=raw.get("endpoint"),
        command=command,
        auth_strategy=str(raw.get("auth_strategy") or "managed_session"),
        capabilities=capabilities,
    )


def _load_tracker_config(raw: object) -> TrackerConfig | None:
    if not isinstance(raw, dict):
        return None
    tracker_id = str(raw.get("id") or "").strip()
    display_name = str(raw.get("display_name") or raw.get("name") or tracker_id).strip()
    kind = str(raw.get("kind") or "").strip()
    transport = str(raw.get("transport") or "").strip()
    if not tracker_id or not display_name or not kind or not transport:
        return None
    event_kinds_value = raw.get("event_kinds") or []
    if isinstance(event_kinds_value, str):
        event_kinds = [item.strip() for item in event_kinds_value.split(",") if item.strip()]
    elif isinstance(event_kinds_value, list):
        event_kinds = [str(item).strip() for item in event_kinds_value if str(item).strip()]
    else:
        event_kinds = []
    metadata_value = raw.get("metadata")
    metadata = dict(metadata_value) if isinstance(metadata_value, dict) else {}
    return TrackerConfig(
        id=tracker_id,
        display_name=display_name,
        kind=kind,
        transport=transport,
        endpoint=raw.get("endpoint"),
        auth_strategy=str(raw.get("auth_strategy") or "none"),
        event_kinds=event_kinds,
        metadata=metadata,
    )


def _load_runtime_profile(raw: object) -> RuntimeProfileConfig | None:
    if not isinstance(raw, dict):
        return None
    profile_id = str(raw.get("id") or "").strip()
    sandbox_mode = str(raw.get("sandbox_mode") or "").strip()
    network_policy = str(raw.get("network_policy") or "").strip()
    filesystem_policy = str(raw.get("filesystem_policy") or "").strip()
    if not profile_id or not sandbox_mode or not network_policy or not filesystem_policy:
        return None
    default_tools_value = raw.get("default_tools") or []
    if isinstance(default_tools_value, str):
        default_tools = [item.strip() for item in default_tools_value.split(",") if item.strip()]
    elif isinstance(default_tools_value, list):
        default_tools = [str(item).strip() for item in default_tools_value if str(item).strip()]
    else:
        default_tools = []
    return RuntimeProfileConfig(
        id=profile_id,
        sandbox_mode=sandbox_mode,
        network_policy=network_policy,
        filesystem_policy=filesystem_policy,
        default_tools=default_tools,
    )


def save_config(config: AutopilotConfig, path: Path) -> None:
    """Save config to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "accounts": {
            "total": config.accounts.total,
            "workers": config.accounts.workers,
            "critics": config.accounts.critics,
            "intake": config.accounts.intake,
        },
        "codex_timeout_sec": config.codex_timeout_sec,
        "cooldown_base_sec": config.cooldown_base_sec,
        "max_retries_per_provider": config.max_retries_per_provider,
        "providers_order": config.providers_order,
        "autopilot_home": config.autopilot_home_override,
        "profiles_dir": config.profiles_dir_override,
        "notifications": [_serialize_notification_channel(channel) for channel in config.notifications],
        "trackers": [_serialize_tracker_config(tracker) for tracker in config.trackers],
        "providers": [_serialize_provider_config(provider) for provider in config.providers],
        "runtime_profiles": [_serialize_runtime_profile(profile) for profile in config.runtime_profiles],
    }
    path.write_text(yaml.dump(data, default_flow_style=False))


def load_config(path: Path) -> AutopilotConfig:
    """Load config from YAML or return defaults when it doesn't exist."""
    if not path.exists():
        return AutopilotConfig()

    data = yaml.safe_load(path.read_text()) or {}
    accounts_data = data.get("accounts", {})
    notifications_data = data.get("notifications", [])
    trackers_data = data.get("trackers", [])
    providers_data = data.get("providers", [])
    runtime_profiles_data = data.get("runtime_profiles", [])
    notifications: list[NotificationChannelConfig] = []
    trackers: list[TrackerConfig] = []
    providers: list[ProviderConfig] = []
    runtime_profiles: list[RuntimeProfileConfig] = []
    if isinstance(notifications_data, list):
        for raw_channel in notifications_data:
            channel = _load_notification_channel(raw_channel)
            if channel is not None:
                notifications.append(channel)
    if isinstance(providers_data, list):
        for raw_provider in providers_data:
            provider = _load_provider_config(raw_provider)
            if provider is not None:
                providers.append(provider)
    if isinstance(trackers_data, list):
        for raw_tracker in trackers_data:
            tracker = _load_tracker_config(raw_tracker)
            if tracker is not None:
                trackers.append(tracker)
    if isinstance(runtime_profiles_data, list):
        for raw_profile in runtime_profiles_data:
            runtime_profile = _load_runtime_profile(raw_profile)
            if runtime_profile is not None:
                runtime_profiles.append(runtime_profile)

    return AutopilotConfig(
        accounts=AccountAllocation(
            total=accounts_data.get("total", 20),
            workers=accounts_data.get("workers", 14),
            critics=accounts_data.get("critics", 5),
            intake=accounts_data.get("intake", 1),
        ),
        codex_timeout_sec=data.get("codex_timeout_sec", 1800),
        cooldown_base_sec=data.get("cooldown_base_sec", 300),
        max_retries_per_provider=data.get("max_retries_per_provider", 3),
        providers_order=data.get("providers_order", ["codex", "claude", "gemini"]),
        autopilot_home_override=data.get("autopilot_home"),
        profiles_dir_override=data.get("profiles_dir"),
        notifications=notifications,
        trackers=trackers,
        providers=providers,
        runtime_profiles=runtime_profiles or _default_runtime_profiles(),
    )
