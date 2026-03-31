"""Configuration management for Autopilot."""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass, field
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
class AutopilotConfig:
    accounts: AccountAllocation = field(default_factory=AccountAllocation)
    codex_timeout_sec: int = 1800
    cooldown_base_sec: int = 300
    max_retries_per_provider: int = 3
    providers_order: list[str] = field(default_factory=lambda: ["codex", "claude", "gemini"])
    autopilot_home_override: str | None = None
    profiles_dir_override: str | None = None
    notifications: list[NotificationChannelConfig] = field(default_factory=list)

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
    }
    path.write_text(yaml.dump(data, default_flow_style=False))


def load_config(path: Path) -> AutopilotConfig:
    """Load config from YAML or return defaults when it doesn't exist."""
    if not path.exists():
        return AutopilotConfig()

    data = yaml.safe_load(path.read_text()) or {}
    accounts_data = data.get("accounts", {})
    notifications_data = data.get("notifications", [])
    notifications: list[NotificationChannelConfig] = []
    if isinstance(notifications_data, list):
        for raw_channel in notifications_data:
            channel = _load_notification_channel(raw_channel)
            if channel is not None:
                notifications.append(channel)

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
    )
