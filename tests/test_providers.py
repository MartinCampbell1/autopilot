"""Tests for provider-specific environment building and CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.adapters import (
    LocalProviderAdapter,
    ProbeStatus,
    get_adapter,
    list_provider_families,
    register_adapter,
    unregister_adapter,
)
from autopilot.core.models import Profile
from autopilot.core.plugins import list_agent_providers, list_notifiers, list_runtimes, list_trackers
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

    def test_provider_alias_resolves_local_adapter(self) -> None:
        assert get_adapter("codex").adapter_id == "codex_local"
        assert get_adapter("claude_local").provider_family == "claude"

    def test_plugin_slots_expose_builtin_provider_runtime_tracker_and_notifier_entries(self) -> None:
        provider_families = {plugin.provider_family for plugin in list_agent_providers()}
        runtime_ids = {plugin.runtime_id for plugin in list_runtimes()}
        tracker_ids = {plugin.tracker_id for plugin in list_trackers()}
        notifier_ids = {plugin.notifier_id for plugin in list_notifiers()}

        assert {"codex", "claude", "gemini"}.issubset(provider_families)
        assert "codex_local:runtime" in runtime_ids
        assert "project_state" in tracker_ids
        assert {"telegram", "slack_webhook", "webhook", "email", "script"}.issubset(notifier_ids)

    def test_runtime_metadata_exposes_managed_home(self, tmp_path: Path) -> None:
        profile = Profile(
            name="acc1",
            provider="claude",
            adapter_id="claude_local",
            path=str(tmp_path / "profiles" / "claude" / "acc1"),
        )
        metadata = get_adapter("claude_local").runtime_metadata(profile)
        assert metadata.adapter_id == "claude_local"
        assert metadata.runtime_home == str(Path(profile.path) / "home")
        assert metadata.env_overrides["HOME"] == str(Path(profile.path) / "home")

    @patch("autopilot.core.adapters.subprocess.run")
    @patch("autopilot.core.adapters.shutil.which")
    def test_environment_probe_ready(self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "codex" / "acc1"
        profile_dir.mkdir(parents=True)
        (profile_dir / "auth.json").write_text("{}")

        mock_which.return_value = "/usr/bin/codex"
        mock_run.return_value = MagicMock(returncode=0, stdout="codex 1.0", stderr="")

        profile = Profile(name="acc1", provider="codex", adapter_id="codex_local", path=str(profile_dir))
        probe = get_adapter("codex_local").test_environment(profile)

        assert probe.status == ProbeStatus.READY
        assert probe.ok is True
        assert "healthy" in probe.summary.lower()

    @patch("autopilot.core.adapters.subprocess.run")
    @patch("autopilot.core.adapters.shutil.which")
    def test_quota_probe_reports_rate_limit_signal(self, mock_which: MagicMock, mock_run: MagicMock, tmp_path: Path) -> None:
        profile_dir = tmp_path / "profiles" / "codex" / "acc1"
        profile_dir.mkdir(parents=True)
        (profile_dir / "auth.json").write_text("{}")

        mock_which.return_value = "/usr/bin/codex"
        mock_run.return_value = MagicMock(returncode=0, stdout="429 Too Many Requests", stderr="")

        profile = Profile(name="acc1", provider="codex", adapter_id="codex_local", path=str(profile_dir))
        probe = get_adapter("codex").quota_probe(profile)

        assert probe.status == ProbeStatus.RATE_LIMITED

    def test_registering_non_core_provider_does_not_require_special_casing(self) -> None:
        class MockProviderAdapter(LocalProviderAdapter):
            adapter_id = "mock_provider_local"
            provider_family = "mock_provider"
            cli_name = "mock-provider"
            install_hint = "brew install mock-provider"

            def check_installed_command(self) -> list[str]:
                return ["mock-provider", "--version"]

            def provider_login_command(self) -> list[str]:
                return ["mock-provider", "login"]

            def session_source_dir(self, home: Path) -> Path:
                return home / ".mock-provider"

            def runtime_home_from_profile_dir(self, profile_dir: Path) -> Path:
                return profile_dir

            def resume_state_paths(self, runtime_home: Path) -> list[Path]:
                return [runtime_home / "session.json"] if (runtime_home / "session.json").exists() else []

            def copy_session_to_profile(self, source_home: Path, destination: Path) -> None:
                destination.mkdir(parents=True, exist_ok=True)

            def prepare_cli_command(self, prompt: str, *, model: str | None, mode) -> list[str]:
                command = ["mock-provider", "--prompt", prompt]
                if model:
                    command.extend(["--model", model])
                return command

        adapter = MockProviderAdapter()
        register_adapter(adapter)
        try:
            assert "mock_provider" in list_provider_families()
            assert get_adapter("mock_provider").adapter_id == "mock_provider_local"
            assert build_cli_command("mock_provider", "ship it")[:2] == ["mock-provider", "--prompt"]
            assert "mock_provider" in PROVIDER_COMMANDS
            assert any(plugin.provider_family == "mock_provider" for plugin in list_agent_providers())
            assert any(plugin.runtime_id == "mock_provider_local:runtime" for plugin in list_runtimes())
        finally:
            unregister_adapter("mock_provider_local")
