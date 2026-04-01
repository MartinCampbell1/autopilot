"""Tests for persisted account diagnostics and probe snapshots."""

from pathlib import Path

from autopilot.core.account_diagnostics import (
    build_account_diagnostics_snapshot,
    build_provider_setup_snapshot,
    load_account_probe_state,
)
from autopilot.core.adapters import (
    AdapterProbeResult,
    AdapterResumeState,
    AdapterRuntimeMetadata,
    ProbeStatus,
)
from autopilot.core.config import AutopilotConfig, ProviderConfig
from autopilot.core.models import Profile


class _FakeManager:
    def __init__(self, profile: Profile):
        self.pools = {"codex": [profile], "claude": [], "gemini": []}

    def build_env(self, profile: Profile) -> dict[str, str]:
        return {"CODEX_HOME": profile.path}


class _FakeAdapter:
    adapter_id = "codex_local"
    install_hint = "npm i -g @openai/codex"
    provider_mode = "cloud"
    transport = "command"
    auth_strategy = "managed_session"
    capabilities = ["exec", "review", "critic"]

    def runtime_metadata(self, profile: Profile) -> AdapterRuntimeMetadata:
        return AdapterRuntimeMetadata(
            adapter_id="codex_local",
            provider_family="codex",
            profile_name=profile.name,
            profile_path=profile.path,
            runtime_home=profile.path,
            session_strategy="managed_runtime_home",
            env_overrides={"CODEX_HOME": profile.path},
        )

    def resume_state(self, profile: Profile) -> AdapterResumeState:
        return AdapterResumeState(
            strategy="managed_runtime_home",
            state_path=profile.path,
            available=True,
            session_files=["auth.json"],
        )

    def test_environment(self, profile: Profile | None = None, *, env=None, timeout: int) -> AdapterProbeResult:
        return AdapterProbeResult(status=ProbeStatus.READY, summary="Environment ok", output="codex 1.0")

    def quota_probe(self, profile: Profile, *, env, timeout: int) -> AdapterProbeResult:
        return AdapterProbeResult(status=ProbeStatus.READY, summary="Quota ok", output="no rate limit")


class _FakeLocalManager:
    def __init__(self, profile: Profile):
        self.pools = {"ollama": [profile]}

    def build_env(self, profile: Profile) -> dict[str, str]:
        return {}


class _FakeLocalAdapter:
    adapter_id = "ollama_local"
    install_hint = "brew install ollama"
    provider_mode = "local"
    transport = "command"
    auth_strategy = "none"
    capabilities = ["exec", "review"]

    def runtime_metadata(self, profile: Profile) -> AdapterRuntimeMetadata:
        return AdapterRuntimeMetadata(
            adapter_id="ollama_local",
            provider_family="ollama",
            profile_name=profile.name,
            profile_path=profile.path,
            runtime_home=profile.path,
            session_strategy="stateless",
            provider_mode="local",
            transport="command",
            auth_strategy="none",
            capabilities=["exec", "review"],
        )

    def resume_state(self, profile: Profile) -> AdapterResumeState:
        return AdapterResumeState(
            strategy="stateless",
            state_path="",
            available=True,
        )

    def test_environment(self, profile: Profile | None = None, *, env=None, timeout: int) -> AdapterProbeResult:
        return AdapterProbeResult(status=ProbeStatus.READY, summary="Environment ok", output="ollama 1.0")

    def quota_probe(self, profile: Profile, *, env, timeout: int) -> AdapterProbeResult:
        return AdapterProbeResult(status=ProbeStatus.READY, summary="Local runtime ok", output="local runtime")


def test_refresh_account_probe_snapshot_persists_results(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    profile_dir = tmp_path / "profiles" / "codex" / "acc1"
    profile_dir.mkdir(parents=True)
    profile = Profile(name="acc1", provider="codex", adapter_id="codex_local", path=str(profile_dir))
    manager = _FakeManager(profile)

    monkeypatch.setattr("autopilot.core.account_diagnostics.get_adapter", lambda _: _FakeAdapter())

    snapshot = build_account_diagnostics_snapshot(config, manager, refresh=True)

    assert snapshot["recorded_at"] is not None
    entry = snapshot["providers"]["codex"][0]
    assert entry["environment_probe"]["status"] == "ready"
    assert entry["quota_probe"]["status"] == "ready"
    persisted = load_account_probe_state(config)
    assert persisted["providers"]["codex"][0]["name"] == "acc1"


def test_account_probe_snapshot_uses_cached_results_without_refresh(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    profile_dir = tmp_path / "profiles" / "codex" / "acc1"
    profile_dir.mkdir(parents=True)
    profile = Profile(name="acc1", provider="codex", adapter_id="codex_local", path=str(profile_dir))
    manager = _FakeManager(profile)

    monkeypatch.setattr("autopilot.core.account_diagnostics.get_adapter", lambda _: _FakeAdapter())
    build_account_diagnostics_snapshot(config, manager, refresh=True)

    snapshot = build_account_diagnostics_snapshot(config, manager, refresh=False)

    entry = snapshot["providers"]["codex"][0]
    assert entry["environment_probe"]["summary"] == "Environment ok"
    assert entry["quota_probe"]["summary"] == "Quota ok"


def test_provider_setup_snapshot_includes_cli_and_source_session_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    profile_dir = tmp_path / "profiles" / "codex" / "acc1"
    profile_dir.mkdir(parents=True)
    profile = Profile(name="acc1", provider="codex", adapter_id="codex_local", path=str(profile_dir))
    manager = _FakeManager(profile)

    monkeypatch.setattr("autopilot.core.account_diagnostics.get_adapter", lambda _: _FakeAdapter())
    monkeypatch.setattr(
        "autopilot.core.account_diagnostics.provider_source_dir",
        lambda provider, home=None: Path("/tmp/source") / provider,
    )
    monkeypatch.setattr(
        "autopilot.core.account_diagnostics.provider_has_logged_in_session",
        lambda provider, home=None: provider == "codex",
    )
    monkeypatch.setattr(
        "autopilot.core.account_diagnostics.provider_login_command",
        lambda provider: [provider, "login"],
    )

    snapshot = build_provider_setup_snapshot(config, manager, refresh=True)

    codex = snapshot["providers"]["codex"]
    assert codex["managed_profile_count"] == 1
    assert codex["source_session_available"] is True
    assert codex["login_command"] == ["codex", "login"]
    assert codex["cli_probe"]["status"] == "ready"


def test_provider_setup_snapshot_marks_stateless_local_provider_as_session_free(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        providers_order=[],
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
    profile = Profile(
        name="ollama-local",
        provider="ollama",
        adapter_id="ollama_local",
        path=str(tmp_path / "providers" / "ollama-local"),
    )
    manager = _FakeLocalManager(profile)

    monkeypatch.setattr("autopilot.core.account_diagnostics.get_adapter", lambda _: _FakeLocalAdapter())
    monkeypatch.setattr("autopilot.core.account_diagnostics.provider_source_dir", lambda provider, home=None: None)
    monkeypatch.setattr(
        "autopilot.core.account_diagnostics.provider_has_logged_in_session",
        lambda provider, home=None: False,
    )
    monkeypatch.setattr("autopilot.core.account_diagnostics.provider_login_command", lambda provider: [])

    snapshot = build_provider_setup_snapshot(config, manager, refresh=True)

    ollama = snapshot["providers"]["ollama"]
    assert ollama["auth_strategy"] == "none"
    assert ollama["source_session_required"] is False
    assert ollama["session_source_dir"] is None
    assert ollama["login_command"] == []
    assert ollama["provider_config"]["id"] == "ollama-local"
    assert any(profile["id"] == "cloud" for profile in snapshot["runtime_profiles"])
