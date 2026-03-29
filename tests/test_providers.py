"""Tests for provider-specific environment building and CLI commands."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from autopilot.core.adapters import ProbeStatus, get_adapter
from autopilot.core.models import Profile
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
