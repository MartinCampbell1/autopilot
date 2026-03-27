"""Tests for provider-specific environment building and CLI commands."""

from autopilot.core.providers import PROVIDER_COMMANDS, build_cli_command


class TestProviders:
    def test_codex_command(self) -> None:
        cmd = build_cli_command("codex", "do the thing", model=None)
        assert cmd[0] == "codex"
        assert "exec" in cmd
        assert "--full-auto" in cmd

    def test_claude_command(self) -> None:
        cmd = build_cli_command("claude", "do the thing", model=None)
        assert cmd[0] == "claude"
        assert "-p" in cmd

    def test_gemini_command(self) -> None:
        cmd = build_cli_command("gemini", "do the thing", model=None)
        assert cmd[0] == "gemini"

    def test_provider_registry(self) -> None:
        assert "codex" in PROVIDER_COMMANDS
        assert "claude" in PROVIDER_COMMANDS
        assert "gemini" in PROVIDER_COMMANDS
