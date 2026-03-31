"""Helpers for importing provider sessions and opening login flows."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from autopilot.core.adapters import get_adapter, list_provider_families

VALID_PROVIDERS = tuple(list_provider_families())


def is_valid_provider(provider: str) -> bool:
    return provider in set(list_provider_families())


def provider_source_dir(provider: str, home: Path | None = None) -> Path:
    """Return the default source directory for a provider's logged-in session."""
    adapter = get_adapter(provider)
    return adapter.session_source_dir(home or Path.home())


def provider_has_logged_in_session(provider: str, home: Path | None = None) -> bool:
    """Return whether a logged-in session exists for the given provider."""
    adapter = get_adapter(provider)
    return adapter.has_logged_in_session(home)


def provider_login_command(provider: str) -> list[str]:
    """Return the interactive CLI command used to log into a provider."""
    return get_adapter(provider).login_command()


def import_current_session(provider: str, profiles_dir: Path, home: Path | None = None) -> str:
    """Copy the currently logged-in provider session into the managed profile pool."""
    if not is_valid_provider(provider):
        raise ValueError(f"Unsupported provider: {provider}")

    adapter = get_adapter(provider)
    return adapter.import_session(profiles_dir, home or Path.home())


def open_login_terminal(provider: str, cwd: Path | None = None) -> str:
    """Open an interactive provider login flow in a separate terminal window."""
    command = provider_login_command(provider)
    command_str = shlex.join(command)

    if sys.platform == "darwin":
        working_dir = shlex.quote(str((cwd or Path.home()).expanduser()))
        osa_command = (
            'tell application "Terminal" to activate\n'
            f'tell application "Terminal" to do script "cd {working_dir}; {command_str}"'
        )
        subprocess.Popen(["osascript", "-e", osa_command])
        return command_str

    subprocess.Popen(command, cwd=str((cwd or Path.home()).expanduser()))
    return command_str
