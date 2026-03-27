"""Shared dependencies for API routes."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import AutopilotConfig, load_config


def get_config() -> AutopilotConfig:
    return load_config(Path.home() / ".autopilot" / "config.yaml")


def get_account_manager() -> AccountManager:
    config = get_config()
    manager = AccountManager(profiles_dir=config.profiles_dir)
    manager.discover()
    return manager
