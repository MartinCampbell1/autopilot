"""Tests for account manager."""

import json
from pathlib import Path

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import AutopilotConfig, ProviderConfig


class TestAccountManager:
    def _create_codex_profile(self, base: Path, name: str) -> Path:
        """Create a fake codex profile directory."""
        profile_dir = base / "codex" / name
        profile_dir.mkdir(parents=True)
        (profile_dir / "auth.json").write_text(json.dumps({"auth_mode": "chatgpt"}))
        (profile_dir / "config.toml").write_text('model = "gpt-5.4"')
        return profile_dir

    def _create_claude_profile(self, base: Path, name: str) -> Path:
        """Create a fake claude profile directory."""
        profile_dir = base / "claude" / name / "home" / ".claude"
        profile_dir.mkdir(parents=True)
        (profile_dir / "settings.json").write_text("{}")
        return profile_dir.parent.parent

    def test_discover_codex_profiles(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        assert "codex" in manager.pools
        assert len(manager.pools["codex"]) == 2

    def test_discover_claude_profiles(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_claude_profile(profiles_dir, "acc1")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        assert "claude" in manager.pools
        assert len(manager.pools["claude"]) == 1

    def test_get_next_round_robin(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        profile_1 = manager.get_next("codex")
        profile_2 = manager.get_next("codex")
        profile_3 = manager.get_next("codex")

        assert profile_1 is not None
        assert profile_2 is not None
        assert profile_3 is not None
        assert profile_1.name == "acc1"
        assert profile_2.name == "acc2"
        assert profile_3.name == "acc1"

    def test_get_next_skips_unavailable(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        manager.mark_rate_limited("codex", "acc1")
        profile = manager.get_next("codex")
        assert profile is not None
        assert profile.name == "acc2"

    def test_get_next_returns_none_all_exhausted(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        manager.mark_rate_limited("codex", "acc1")
        profile = manager.get_next("codex")
        assert profile is None

    def test_pool_status(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        self._create_codex_profile(profiles_dir, "acc1")
        self._create_codex_profile(profiles_dir, "acc2")

        manager = AccountManager(profiles_dir=profiles_dir)
        manager.discover()

        status = manager.pool_status("codex")
        assert len(status) == 2
        assert all(item["available"] for item in status)

    def test_save_profile_from_source(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        source_dir = tmp_path / "source_codex"
        source_dir.mkdir()
        (source_dir / "auth.json").write_text('{"auth_mode": "chatgpt"}')
        (source_dir / "config.toml").write_text('model = "gpt-5.4"')

        manager = AccountManager(profiles_dir=profiles_dir)
        name = manager.save_profile("codex", source_dir)

        assert name == "acc1"
        assert (profiles_dir / "codex" / "acc1" / "auth.json").exists()
        assert (profiles_dir / "codex" / "acc1" / "config.toml").exists()

    def test_discover_stateless_provider_from_explicit_config(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        config = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            providers=[
                ProviderConfig(
                    id="ollama-local",
                    family="ollama",
                    mode="local",
                    transport="command",
                    command=["ollama"],
                    auth_strategy="none",
                    capabilities=["exec", "review"],
                )
            ],
        )

        manager = AccountManager(profiles_dir=profiles_dir, config=config)
        manager.discover()
        profile = manager.get_next("ollama")

        assert "ollama" in manager.pools
        assert profile is not None
        assert profile.name == "ollama-local"
        assert profile.adapter_id == "ollama_local"

    def test_discover_stateless_provider_from_providers_order(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        config = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            providers_order=["ollama"],
        )

        manager = AccountManager(profiles_dir=profiles_dir, config=config)
        manager.discover()
        profile = manager.get_next("ollama")

        assert "ollama" in manager.pools
        assert profile is not None
        assert profile.name == "ollama"

    def test_get_next_can_target_named_stateless_runtime(self, tmp_path: Path) -> None:
        profiles_dir = tmp_path / "profiles"
        config = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            providers=[
                ProviderConfig(
                    id="ollama-local-a",
                    family="ollama",
                    mode="local",
                    transport="command",
                    command=["ollama"],
                    auth_strategy="none",
                    capabilities=["exec", "review"],
                ),
                ProviderConfig(
                    id="ollama-local-b",
                    family="ollama",
                    mode="local",
                    transport="command",
                    command=["ollama"],
                    auth_strategy="none",
                    capabilities=["exec", "review"],
                ),
            ],
        )

        manager = AccountManager(profiles_dir=profiles_dir, config=config)
        manager.discover()
        profile = manager.get_next("ollama", preferred_name="ollama-local-b")

        assert profile is not None
        assert profile.name == "ollama-local-b"
