"""Compatibility facade over the typed local adapter registry."""

from __future__ import annotations

from collections.abc import Mapping

from autopilot.core.adapters import AdapterMode, get_adapter, list_provider_families


def _provider_commands_snapshot() -> dict[str, dict[str, object]]:
    return {
        provider: {
            "exec": get_adapter(provider).prepare_cli_command("__PROMPT__", model=None, mode=AdapterMode.EXEC)[:-1],
            "review": get_adapter(provider).prepare_cli_command("__PROMPT__", model=None, mode=AdapterMode.REVIEW)[:-1],
            "check_installed": get_adapter(provider).check_installed_command(),
            "install_hint": get_adapter(provider).install_hint,
            "adapter_id": get_adapter(provider).adapter_id,
        }
        for provider in list_provider_families()
    }


class _ProviderCommandsProxy(Mapping[str, dict[str, object]]):
    def __getitem__(self, key: str) -> dict[str, object]:
        return _provider_commands_snapshot()[key]

    def __iter__(self):
        return iter(_provider_commands_snapshot())

    def __len__(self) -> int:
        return len(_provider_commands_snapshot())


PROVIDER_COMMANDS: Mapping[str, dict[str, object]] = _ProviderCommandsProxy()


def build_cli_command(
    provider: str,
    prompt: str,
    model: str | None = None,
    mode: str = "exec",
) -> list[str]:
    """Build a CLI command for the requested provider or adapter."""
    return get_adapter(provider).build_cli_command(prompt, model=model, mode=AdapterMode(mode))
