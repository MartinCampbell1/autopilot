"""Tests for config loading and saving."""

from pathlib import Path

from autopilot.core.config import DEFAULT_CONFIG, AutopilotConfig, load_config, save_config


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
