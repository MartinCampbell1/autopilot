"""Compatibility facade over the typed local adapter registry."""

from __future__ import annotations

from autopilot.core.adapters import AdapterMode, get_adapter, list_provider_families

PROVIDER_COMMANDS: dict[str, dict[str, object]] = {
    provider: {
        "exec": get_adapter(provider).prepare_cli_command("__PROMPT__", model=None, mode=AdapterMode.EXEC)[:-1],
        "review": get_adapter(provider).prepare_cli_command("__PROMPT__", model=None, mode=AdapterMode.REVIEW)[:-1],
        "check_installed": get_adapter(provider).check_installed_command(),
        "install_hint": get_adapter(provider).install_hint,
        "adapter_id": get_adapter(provider).adapter_id,
    }
    for provider in list_provider_families()
}


def build_cli_command(
    provider: str,
    prompt: str,
    model: str | None = None,
    mode: str = "exec",
) -> list[str]:
    """Build a CLI command for the requested provider or adapter."""
    return get_adapter(provider).build_cli_command(prompt, model=model, mode=AdapterMode(mode))
