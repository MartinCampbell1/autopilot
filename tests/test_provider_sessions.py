"""Tests for provider session import helpers."""

import json
from pathlib import Path

import pytest

from autopilot.core.provider_sessions import import_current_session, provider_login_command


class TestProviderSessions:
    def test_import_current_codex_session(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        source = home / ".codex"
        source.mkdir(parents=True)
        (source / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}))
        (source / "config.toml").write_text('model = "gpt-5.4"')

        profiles_dir = tmp_path / "profiles"
        name = import_current_session("codex", profiles_dir=profiles_dir, home=home)

        assert name == "acc1"
        assert (profiles_dir / "codex" / "acc1" / "auth.json").exists()

    def test_import_current_claude_session(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        source = home / ".claude"
        source.mkdir(parents=True)
        (source / "settings.json").write_text("{}")

        profiles_dir = tmp_path / "profiles"
        name = import_current_session("claude", profiles_dir=profiles_dir, home=home)

        assert name == "acc1"
        assert (profiles_dir / "claude" / "acc1" / "home" / ".claude" / "settings.json").exists()

    def test_import_current_gemini_session(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        source = home / ".config" / "gemini"
        source.mkdir(parents=True)
        (source / "config.json").write_text("{}")

        profiles_dir = tmp_path / "profiles"
        name = import_current_session("gemini", profiles_dir=profiles_dir, home=home)

        assert name == "acc1"
        assert (profiles_dir / "gemini" / "acc1" / "home" / ".config" / "gemini" / "config.json").exists()

    def test_provider_login_command(self) -> None:
        assert provider_login_command("codex") == ["codex", "login"]
        assert provider_login_command("claude") == ["claude", "auth", "login"]
        assert provider_login_command("gemini") == ["gemini"]
        assert provider_login_command("ollama") == []
        assert provider_login_command("openai_compatible") == []
        assert provider_login_command("local_command") == []

    def test_import_current_session_rejects_stateless_provider(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="stateless local execution"):
            import_current_session("ollama", profiles_dir=tmp_path / "profiles", home=tmp_path / "home")
        with pytest.raises(ValueError, match="stateless local execution"):
            import_current_session("openai_compatible", profiles_dir=tmp_path / "profiles", home=tmp_path / "home")
