"""Provider-specific CLI command builders and configurations."""

from __future__ import annotations

PROVIDER_COMMANDS: dict[str, dict] = {
    "codex": {
        "exec": ["codex", "exec", "--full-auto"],
        "review": ["codex", "review"],
        "check_installed": ["codex", "--version"],
        "install_hint": "npm i -g @openai/codex",
    },
    "claude": {
        "exec": ["claude", "-p"],
        "review": ["claude", "-p"],
        "check_installed": ["claude", "--version"],
        "install_hint": "curl -fsSL https://claude.ai/install.sh | bash",
    },
    "gemini": {
        "exec": ["gemini", "-p"],
        "review": ["gemini", "-p"],
        "check_installed": ["gemini", "--version"],
        "install_hint": "npm i -g @anthropic-ai/gemini",
    },
}


def build_cli_command(
    provider: str,
    prompt: str,
    model: str | None = None,
    mode: str = "exec",
) -> list[str]:
    """Build a CLI command for the requested provider."""
    config = PROVIDER_COMMANDS.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}")

    cmd = list(config[mode])

    if provider == "codex":
        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
    elif provider in ("claude", "gemini"):
        cmd.append(prompt)

    return cmd
