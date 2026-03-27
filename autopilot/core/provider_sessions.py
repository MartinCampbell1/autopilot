"""Helpers for importing provider sessions and opening login flows."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path


VALID_PROVIDERS = ("codex", "claude", "gemini")


def provider_source_dir(provider: str, home: Path | None = None) -> Path:
    """Return the default source directory for a provider's logged-in session."""
    home = home or Path.home()
    if provider == "codex":
        return home / ".codex"
    return home


def provider_has_logged_in_session(provider: str, home: Path | None = None) -> bool:
    """Return whether a logged-in session exists for the given provider."""
    source = provider_source_dir(provider, home)

    if provider == "codex":
        return (source / "auth.json").exists() or (source / "config.toml").exists()
    if provider == "claude":
        return (source / ".claude").exists()
    if provider == "gemini":
        return (source / ".config" / "gemini").exists() or (source / ".gemini").exists()
    raise ValueError(f"Unsupported provider: {provider}")


def provider_login_command(provider: str) -> list[str]:
    """Return the interactive CLI command used to log into a provider."""
    if provider == "codex":
        return ["codex", "login"]
    if provider == "claude":
        return ["claude", "auth", "login"]
    if provider == "gemini":
        return ["gemini"]
    raise ValueError(f"Unsupported provider: {provider}")


def import_current_session(provider: str, profiles_dir: Path, home: Path | None = None) -> str:
    """Copy the currently logged-in provider session into the managed profile pool."""
    if provider not in VALID_PROVIDERS:
        raise ValueError(f"Unsupported provider: {provider}")

    home = home or Path.home()
    source = provider_source_dir(provider, home)

    if not provider_has_logged_in_session(provider, home):
        raise FileNotFoundError(f"No active {provider} session found at {source}")

    provider_dir = profiles_dir / provider
    provider_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(
        account_dir.name
        for account_dir in provider_dir.iterdir()
        if account_dir.is_dir() and account_dir.name.startswith("acc")
    )
    name = f"acc{len(existing) + 1}"
    destination = provider_dir / name

    if provider == "codex":
        shutil.copytree(source, destination)
        return name

    home_dir = destination / "home"
    home_dir.mkdir(parents=True, exist_ok=True)

    if provider == "claude":
        shutil.copytree(source / ".claude", home_dir / ".claude")
        return name

    for candidate in (".config/gemini", ".gemini"):
        source_path = source / candidate
        if source_path.exists():
            destination_path = home_dir / candidate
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_path, destination_path)
            return name

    raise FileNotFoundError(f"No active {provider} session found at {source}")


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
