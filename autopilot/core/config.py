"""Configuration management for Autopilot."""

from __future__ import annotations

import os
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
class AutopilotConfig:
    accounts: AccountAllocation = field(default_factory=AccountAllocation)
    codex_timeout_sec: int = 1800
    cooldown_base_sec: int = 300
    max_retries_per_provider: int = 3
    providers_order: list[str] = field(default_factory=lambda: ["codex", "claude", "gemini"])
    autopilot_home_override: str | None = None
    profiles_dir_override: str | None = None

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
    def events_log_path(self) -> Path:
        return self.autopilot_home / "events" / "events.jsonl"

    @property
    def connectors_json_path(self) -> Path:
        return self.autopilot_home / "connectors.json"

    @property
    def skill_packs_json_path(self) -> Path:
        return self.autopilot_home / "skill-packs.json"


DEFAULT_CONFIG = AutopilotConfig()


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
    }
    path.write_text(yaml.dump(data, default_flow_style=False))


def load_config(path: Path) -> AutopilotConfig:
    """Load config from YAML or return defaults when it doesn't exist."""
    if not path.exists():
        return AutopilotConfig()

    data = yaml.safe_load(path.read_text()) or {}
    accounts_data = data.get("accounts", {})

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
    )
