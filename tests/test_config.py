"""Tests for config loading and saving."""

from pathlib import Path

from autopilot.core.config import (
    DEFAULT_CONFIG,
    AutopilotConfig,
    NotificationChannelConfig,
    ProviderConfig,
    RuntimeProfileConfig,
    TrackerConfig,
    load_config,
    save_config,
)


class TestConfig:
    def test_default_config(self) -> None:
        cfg = DEFAULT_CONFIG
        assert cfg.accounts.total == 20
        assert cfg.accounts.workers == 14
        assert cfg.accounts.critics == 5
        assert cfg.accounts.intake == 1

    def test_save_and_load(self, tmp_path: Path) -> None:
        cfg = DEFAULT_CONFIG
        cfg.autopilot_home_override = str(tmp_path / ".autopilot")
        cfg.profiles_dir_override = str(tmp_path / ".cli-profiles")
        config_path = tmp_path / "config.yaml"
        save_config(cfg, config_path)

        loaded = load_config(config_path)
        assert isinstance(loaded, AutopilotConfig)
        assert loaded.accounts.total == cfg.accounts.total
        assert loaded.accounts.workers == cfg.accounts.workers
        assert loaded.autopilot_home == tmp_path / ".autopilot"
        assert loaded.profiles_dir == tmp_path / ".cli-profiles"

    def test_load_missing_file_returns_default(self, tmp_path: Path) -> None:
        config_path = tmp_path / "nonexistent.yaml"
        loaded = load_config(config_path)
        assert loaded.accounts.total == 20

    def test_autopilot_home(self) -> None:
        cfg = DEFAULT_CONFIG
        home = cfg.autopilot_home
        assert home.name == ".autopilot"

    def test_save_and_load_notifications(self, tmp_path: Path) -> None:
        cfg = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            notifications=[
                NotificationChannelConfig(
                    name="ops-slack",
                    kind="slack_webhook",
                    events=["run_failed", "story_stuck"],
                    webhook_url="https://hooks.slack.test/123",
                ),
                NotificationChannelConfig(
                    name="script",
                    kind="script",
                    command=["/bin/echo", "notify"],
                ),
            ],
        )
        config_path = tmp_path / "config.yaml"

        save_config(cfg, config_path)
        loaded = load_config(config_path)

        assert len(loaded.notifications) == 2
        assert loaded.notifications[0].name == "ops-slack"
        assert loaded.notifications[0].events == ["run_failed", "story_stuck"]
        assert loaded.notifications[1].command == ["/bin/echo", "notify"]

    def test_save_and_load_provider_and_runtime_contracts(self, tmp_path: Path) -> None:
        cfg = AutopilotConfig(
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
            runtime_profiles=[
                RuntimeProfileConfig(
                    id="local",
                    sandbox_mode="host",
                    network_policy="local-only",
                    filesystem_policy="workspace-write",
                    default_tools=["shell", "git"],
                )
            ],
        )
        config_path = tmp_path / "config.yaml"

        save_config(cfg, config_path)
        loaded = load_config(config_path)

        assert loaded.providers[0].id == "ollama-local"
        assert loaded.providers[0].auth_strategy == "none"
        assert loaded.runtime_profiles[0].id == "local"
        assert loaded.runtime_profiles[0].default_tools == ["shell", "git"]

    def test_save_and_load_tracker_contracts(self, tmp_path: Path) -> None:
        cfg = AutopilotConfig(
            autopilot_home_override=str(tmp_path / ".autopilot"),
            trackers=[
                TrackerConfig(
                    id="linear",
                    display_name="Linear",
                    kind="issue_tracker",
                    transport="webhook",
                    endpoint="https://linear.example.com/webhooks/autopilot",
                    auth_strategy="bearer",
                    event_kinds=["issue.created", "issue.updated"],
                    metadata={"workspace": "founderos"},
                )
            ],
        )
        config_path = tmp_path / "config.yaml"

        save_config(cfg, config_path)
        loaded = load_config(config_path)

        assert len(loaded.trackers) == 1
        assert loaded.trackers[0].id == "linear"
        assert loaded.trackers[0].transport == "webhook"
        assert loaded.trackers[0].event_kinds == ["issue.created", "issue.updated"]
        assert loaded.trackers[0].metadata["workspace"] == "founderos"

    def test_resolved_provider_configs_merge_default_and_explicit_entries(self) -> None:
        cfg = AutopilotConfig(
            providers_order=["codex", "ollama"],
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

        resolved = cfg.resolved_provider_configs()
        ids = {provider.id for provider in resolved}
        families = {provider.family for provider in resolved}

        assert "codex" in ids
        assert "ollama-local" in ids
        assert {"codex", "ollama"}.issubset(families)

    def test_resolve_provider_and_runtime_profile_contracts(self) -> None:
        cfg = AutopilotConfig(
            providers_order=["codex"],
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
            runtime_profiles=[
                RuntimeProfileConfig(
                    id="local",
                    sandbox_mode="host",
                    network_policy="local-only",
                    filesystem_policy="workspace-write",
                    default_tools=["shell", "git"],
                )
            ],
        )

        provider = cfg.resolve_provider_config("ollama", "ollama-local")
        runtime_profile = cfg.resolve_runtime_profile("local")

        assert provider.id == "ollama-local"
        assert runtime_profile.network_policy == "local-only"
