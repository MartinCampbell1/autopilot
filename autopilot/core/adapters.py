"""Typed adapter layer for local provider CLIs."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable, Mapping

from autopilot.core.models import Profile, is_rate_limited
from autopilot.core.plugins import (
    AgentProviderPlugin,
    RuntimePlugin,
    register_agent_provider,
    register_runtime,
    unregister_agent_provider,
    unregister_runtime,
)

DEFAULT_PATH_PREFIXES = (
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
)
USER_BIN_DIRS = (".npm-global/bin", ".local/bin", ".cargo/bin", ".bun/bin")
SUPPORTED_PROVIDER_FAMILIES = ("codex", "claude", "gemini")


class AdapterMode(StrEnum):
    EXEC = "exec"
    REVIEW = "review"
    CRITIC = "critic"


class ProbeStatus(StrEnum):
    READY = "ready"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    RATE_LIMITED = "rate_limited"


@dataclass(slots=True)
class AdapterResumeState:
    """Persisted state that lets an adapter resume authenticated work."""

    strategy: str
    state_path: str
    available: bool
    session_files: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class AdapterRuntimeMetadata:
    """Static runtime metadata for one adapter/profile combination."""

    adapter_id: str
    provider_family: str
    profile_name: str | None
    profile_path: str | None
    runtime_home: str | None
    session_strategy: str
    provider_mode: str = "cloud"
    transport: str = "command"
    auth_strategy: str = "managed_session"
    env_overrides: dict[str, str] = field(default_factory=dict)
    supports_model_override: bool = False
    supports_quota_probe: bool = True
    capabilities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AdapterDiagnostics:
    """Execution diagnostics emitted by probes and command invocations."""

    metadata: AdapterRuntimeMetadata
    command: list[str] = field(default_factory=list)
    cli_path: str | None = None
    elapsed_sec: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AdapterProbeResult:
    """Result of an adapter environment or quota probe."""

    status: ProbeStatus
    summary: str
    output: str = ""
    diagnostics: AdapterDiagnostics | None = None

    @property
    def ok(self) -> bool:
        return self.status == ProbeStatus.READY


@dataclass(slots=True)
class AdapterParsedOutput:
    """Normalized provider output."""

    text: str
    rate_limited: bool
    diagnostics: AdapterDiagnostics | None = None


@dataclass(slots=True)
class AdapterExecutionRequest:
    """Inputs for one adapter command execution."""

    profile: Profile
    prompt: str
    workdir: Path
    env: Mapping[str, str] | None = None
    timeout: int = 1800
    model: str | None = None
    mode: AdapterMode = AdapterMode.EXEC
    on_progress: Callable[[int, str], None] | None = None
    progress_interval: int = 15
    progress_message: Callable[[], str] | None = None


@dataclass(slots=True)
class AdapterExecutionResult:
    """Low-level result of running a provider CLI."""

    success: bool
    returncode: int | None
    stdout: str
    stderr: str
    output: str
    timed_out: bool
    rate_limited: bool
    diagnostics: AdapterDiagnostics


@dataclass(slots=True)
class _PreparedInvocation:
    command: list[str]
    env: dict[str, str]
    input_text: str | None = None
    output_file: Path | None = None
    cleanup_paths: list[Path] = field(default_factory=list)


class LocalProviderAdapter(ABC):
    """Base contract for local CLI adapters."""

    adapter_id: str
    provider_family: str
    cli_name: str
    install_hint: str
    session_strategy = "managed_runtime_home"
    provider_mode = "cloud"
    transport = "command"
    auth_strategy = "managed_session"
    requires_managed_profile = True
    supports_model_override = False
    supported_modes: tuple[AdapterMode, ...] = (AdapterMode.EXEC, AdapterMode.REVIEW)

    @property
    def canonical_provider(self) -> str:
        return self.provider_family

    def runtime_home(self, profile: Profile) -> Path:
        return Path(profile.path)

    @property
    def capabilities(self) -> list[str]:
        return [mode.value for mode in self.supported_modes]

    def default_command(self) -> list[str]:
        return [self.cli_name]

    def runtime_env_overrides(self, profile: Profile) -> dict[str, str]:
        return {}

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = dict(base_env) if base_env is not None else os.environ.copy()
        env.update(self.runtime_env_overrides(profile))
        return env

    def runtime_metadata(self, profile: Profile | None = None) -> AdapterRuntimeMetadata:
        env_overrides: dict[str, str] = {}
        runtime_home: str | None = None
        profile_name: str | None = None
        profile_path: str | None = None

        if profile is not None:
            env_overrides = self.runtime_env_overrides(profile)
            runtime_home = str(self.runtime_home(profile))
            profile_name = profile.name
            profile_path = profile.path

        return AdapterRuntimeMetadata(
            adapter_id=self.adapter_id,
            provider_family=self.provider_family,
            profile_name=profile_name,
            profile_path=profile_path,
            runtime_home=runtime_home,
            session_strategy=self.session_strategy,
            provider_mode=self.provider_mode,
            transport=self.transport,
            auth_strategy=self.auth_strategy,
            env_overrides=env_overrides,
            supports_model_override=self.supports_model_override,
            capabilities=self.capabilities,
        )

    def diagnostics(
        self,
        profile: Profile | None = None,
        *,
        command: list[str] | None = None,
        elapsed_sec: float = 0.0,
        notes: list[str] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> AdapterDiagnostics:
        resolved_env = self.build_env(profile, env) if profile is not None else dict(env or os.environ.copy())
        cli_path = shutil.which(self.cli_name, path=resolved_env.get("PATH"))
        return AdapterDiagnostics(
            metadata=self.runtime_metadata(profile),
            command=list(command or []),
            cli_path=cli_path,
            elapsed_sec=round(elapsed_sec, 2),
            notes=list(notes or []),
        )

    def parse_output(self, result: AdapterExecutionResult) -> AdapterParsedOutput:
        text = result.output.strip()
        return AdapterParsedOutput(
            text=text,
            rate_limited=is_rate_limited(text),
            diagnostics=result.diagnostics,
        )

    def test_environment(
        self,
        profile: Profile | None = None,
        *,
        env: Mapping[str, str] | None = None,
        timeout: int = 15,
    ) -> AdapterProbeResult:
        started_at = time.monotonic()
        diagnostics = self.diagnostics(profile, env=env)
        notes = list(diagnostics.notes)

        if diagnostics.cli_path is None:
            notes.append("CLI binary not found on PATH.")
            diagnostics.notes = notes
            diagnostics.elapsed_sec = round(time.monotonic() - started_at, 2)
            return AdapterProbeResult(
                status=ProbeStatus.UNAVAILABLE,
                summary=f"{self.cli_name} is not installed.",
                diagnostics=diagnostics,
            )

        resume_state = self.resume_state(profile) if profile is not None else None
        if profile is not None and self.requires_managed_profile and not resume_state.available:
            notes.append("Managed runtime home exists but no resumable session files were found.")
            diagnostics.notes = notes
            diagnostics.elapsed_sec = round(time.monotonic() - started_at, 2)
            return AdapterProbeResult(
                status=ProbeStatus.DEGRADED,
                summary="Managed runtime home is missing provider session state.",
                diagnostics=diagnostics,
            )

        try:
            result = subprocess.run(
                self.check_installed_command(),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self.build_env(profile, env) if profile is not None else dict(env or os.environ.copy()),
            )
        except subprocess.TimeoutExpired:
            notes.append("CLI version probe timed out.")
            diagnostics.notes = notes
            diagnostics.elapsed_sec = round(time.monotonic() - started_at, 2)
            return AdapterProbeResult(
                status=ProbeStatus.DEGRADED,
                summary=f"{self.cli_name} did not respond to the environment probe in time.",
                diagnostics=diagnostics,
            )
        except Exception as exc:
            notes.append(f"CLI probe failed: {exc}")
            diagnostics.notes = notes
            diagnostics.elapsed_sec = round(time.monotonic() - started_at, 2)
            return AdapterProbeResult(
                status=ProbeStatus.UNAVAILABLE,
                summary=f"{self.cli_name} probe failed.",
                output=str(exc),
                diagnostics=diagnostics,
            )

        output = f"{result.stdout}\n{result.stderr}".strip()
        diagnostics.notes = notes
        diagnostics.elapsed_sec = round(time.monotonic() - started_at, 2)
        status = ProbeStatus.READY if result.returncode == 0 else ProbeStatus.DEGRADED
        summary = "CLI and managed runtime home look healthy." if result.returncode == 0 else "CLI responded with a non-zero status."
        return AdapterProbeResult(
            status=status,
            summary=summary,
            output=output,
            diagnostics=diagnostics,
        )

    def quota_probe(
        self,
        profile: Profile | None = None,
        *,
        env: Mapping[str, str] | None = None,
        timeout: int = 15,
    ) -> AdapterProbeResult:
        probe = self.test_environment(profile, env=env, timeout=timeout)
        if probe.status != ProbeStatus.READY:
            return probe

        output = probe.output.strip()
        status = ProbeStatus.RATE_LIMITED if is_rate_limited(output) else ProbeStatus.READY
        summary = (
            "Quota probe saw a rate-limit signal from the provider environment."
            if status == ProbeStatus.RATE_LIMITED
            else "CLI and managed runtime home are ready; no quota issue detected by the non-invasive probe."
        )
        return AdapterProbeResult(
            status=status,
            summary=summary,
            output=output,
            diagnostics=probe.diagnostics,
        )

    def execute(self, request: AdapterExecutionRequest) -> AdapterExecutionResult:
        started_at = time.monotonic()
        invocation = self.prepare_invocation(request)

        try:
            if request.on_progress is not None:
                success, returncode, stdout, stderr, timed_out = self._run_with_progress(
                    invocation,
                    request=request,
                )
            else:
                result = subprocess.run(
                    invocation.command,
                    cwd=str(request.workdir),
                    input=invocation.input_text,
                    capture_output=True,
                    text=True,
                    timeout=request.timeout,
                    env=invocation.env,
                )
                success = result.returncode == 0
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
                timed_out = False
        except subprocess.TimeoutExpired:
            success = False
            returncode = None
            stdout = ""
            stderr = f"Timeout after {request.timeout}s"
            timed_out = True
        except Exception as exc:
            success = False
            returncode = None
            stdout = ""
            stderr = f"ERROR: {exc}"
            timed_out = False

        output = self._collect_output(invocation, stdout, stderr)
        elapsed_sec = time.monotonic() - started_at
        diagnostics = self.diagnostics(
            request.profile,
            command=invocation.command,
            elapsed_sec=elapsed_sec,
            env=request.env,
        )

        for cleanup_path in invocation.cleanup_paths:
            cleanup_path.unlink(missing_ok=True)

        return AdapterExecutionResult(
            success=success,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            output=output,
            timed_out=timed_out,
            rate_limited=is_rate_limited(output),
            diagnostics=diagnostics,
        )

    def build_cli_command(
        self,
        prompt: str,
        *,
        model: str | None = None,
        mode: AdapterMode = AdapterMode.EXEC,
    ) -> list[str]:
        return self.prepare_cli_command(prompt, model=model, mode=mode)

    def profile_is_valid(self, profile_dir: Path) -> bool:
        return self.runtime_home_from_profile_dir(profile_dir).exists()

    def resume_state(self, profile: Profile | None) -> AdapterResumeState:
        runtime_home = self.runtime_home(profile) if profile is not None else self.session_source_dir(Path.home())
        if runtime_home is None:
            return AdapterResumeState(
                strategy=self.session_strategy,
                state_path="",
                available=not self.requires_managed_profile,
                metadata={"adapter_id": self.adapter_id, "provider_family": self.provider_family},
            )
        session_files = [str(path.relative_to(runtime_home)) for path in self.resume_state_paths(runtime_home)]
        return AdapterResumeState(
            strategy=self.session_strategy,
            state_path=str(runtime_home),
            available=bool(session_files),
            session_files=session_files,
            metadata={"adapter_id": self.adapter_id, "provider_family": self.provider_family},
        )

    def has_logged_in_session(self, home: Path | None = None) -> bool:
        source_dir = self.session_source_dir(home or Path.home())
        if source_dir is None:
            return False
        return bool(self.resume_state_paths(source_dir))

    def login_command(self) -> list[str]:
        return list(self.provider_login_command())

    def import_session(self, profiles_dir: Path, home: Path | None = None) -> str:
        if not self.requires_managed_profile:
            raise ValueError(f"{self.provider_family} uses stateless local execution and does not support session import.")
        source_home = self.session_source_dir(home or Path.home())
        if source_home is None or not self.has_logged_in_session(home):
            raise FileNotFoundError(f"No active {self.provider_family} session found at {source_home}")

        destination = self._next_profile_destination(profiles_dir)
        self.copy_session_to_profile(source_home, destination)
        return destination.name

    def _next_profile_destination(self, profiles_dir: Path) -> Path:
        provider_dir = profiles_dir / self.provider_family
        provider_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(
            account_dir.name
            for account_dir in provider_dir.iterdir()
            if account_dir.is_dir() and account_dir.name.startswith("acc")
        )
        destination = provider_dir / f"acc{len(existing) + 1}"
        destination.mkdir(parents=True, exist_ok=False)
        return destination

    def _collect_output(self, invocation: _PreparedInvocation, stdout: str, stderr: str) -> str:
        if invocation.output_file and invocation.output_file.exists():
            file_output = invocation.output_file.read_text(encoding="utf-8").strip()
            if file_output:
                return file_output
        return f"{stdout}\n{stderr}".strip()

    def _run_with_progress(
        self,
        invocation: _PreparedInvocation,
        *,
        request: AdapterExecutionRequest,
    ) -> tuple[bool, int | None, str, str, bool]:
        tmp_dir = request.workdir / ".ralph" / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        progress_log_path = tmp_dir / f"autopilot-adapter-{self.adapter_id}-{time.time_ns()}.log"
        invocation.cleanup_paths.append(progress_log_path)

        started_at = time.monotonic()
        next_progress_at = started_at + max(1, request.progress_interval)

        with progress_log_path.open("w", encoding="utf-8") as output_file:
            process = subprocess.Popen(
                invocation.command,
                cwd=str(request.workdir),
                stdout=output_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if invocation.input_text is not None else None,
                text=True,
                env=invocation.env,
            )

            if process.stdin is not None and invocation.input_text is not None:
                process.stdin.write(invocation.input_text)
                process.stdin.close()

            timed_out = False
            while True:
                returncode = process.poll()
                if returncode is not None:
                    break

                elapsed = int(time.monotonic() - started_at)
                if elapsed >= request.timeout:
                    timed_out = True
                    process.kill()
                    process.wait(timeout=5)
                    return False, None, "", f"Timeout after {request.timeout}s", True

                now = time.monotonic()
                if now >= next_progress_at:
                    try:
                        message = (
                            request.progress_message()
                            if request.progress_message is not None
                            else f"{self.adapter_id} is still running."
                        )
                        request.on_progress(elapsed, message)
                    except Exception:
                        pass
                    next_progress_at = now + max(1, request.progress_interval)
                time.sleep(1)

        output = progress_log_path.read_text(encoding="utf-8") if progress_log_path.exists() else ""
        return returncode == 0, returncode, output, "", timed_out

    @abstractmethod
    def check_installed_command(self) -> list[str]:
        """Return a command that validates the local CLI is available."""

    @abstractmethod
    def provider_login_command(self) -> list[str]:
        """Return the interactive CLI login command."""

    @abstractmethod
    def session_source_dir(self, home: Path) -> Path | None:
        """Return the root directory containing the provider session state."""

    @abstractmethod
    def runtime_home_from_profile_dir(self, profile_dir: Path) -> Path:
        """Resolve the managed runtime home from a stored profile directory."""

    @abstractmethod
    def resume_state_paths(self, runtime_home: Path) -> list[Path]:
        """Return the session files/directories used for resume semantics."""

    @abstractmethod
    def copy_session_to_profile(self, source_home: Path, destination: Path) -> None:
        """Copy the current logged-in session into a managed profile."""

    @abstractmethod
    def prepare_cli_command(self, prompt: str, *, model: str | None, mode: AdapterMode) -> list[str]:
        """Build the provider CLI command for a prompt-driven execution."""

    def prepare_invocation(self, request: AdapterExecutionRequest) -> _PreparedInvocation:
        env = self.build_env(request.profile, request.env)
        command = self.prepare_cli_command(request.prompt, model=request.model, mode=request.mode)
        return _PreparedInvocation(command=command, env=env)


class CodexLocalAdapter(LocalProviderAdapter):
    adapter_id = "codex_local"
    provider_family = "codex"
    cli_name = "codex"
    install_hint = "npm i -g @openai/codex"
    supports_model_override = True
    supported_modes = (AdapterMode.EXEC, AdapterMode.REVIEW, AdapterMode.CRITIC)

    def check_installed_command(self) -> list[str]:
        return ["codex", "--version"]

    def provider_login_command(self) -> list[str]:
        return ["codex", "login"]

    def session_source_dir(self, home: Path) -> Path | None:
        return home / ".codex"

    def runtime_home_from_profile_dir(self, profile_dir: Path) -> Path:
        return profile_dir

    def runtime_env_overrides(self, profile: Profile) -> dict[str, str]:
        return {"CODEX_HOME": str(self.runtime_home(profile))}

    def resume_state_paths(self, runtime_home: Path) -> list[Path]:
        return [path for path in (runtime_home / "auth.json", runtime_home / "config.toml") if path.exists()]

    def copy_session_to_profile(self, source_home: Path, destination: Path) -> None:
        shutil.rmtree(destination)
        shutil.copytree(source_home, destination)

    def profile_is_valid(self, profile_dir: Path) -> bool:
        return bool(self.resume_state_paths(self.runtime_home_from_profile_dir(profile_dir)))

    def prepare_cli_command(self, prompt: str, *, model: str | None, mode: AdapterMode) -> list[str]:
        cmd: list[str]
        if mode in (AdapterMode.EXEC, AdapterMode.CRITIC):
            cmd = ["codex", "exec", "--full-auto"]
        elif mode == AdapterMode.REVIEW:
            cmd = ["codex", "review"]
        else:
            raise ValueError(f"Unsupported mode: {mode}")

        if model:
            cmd.extend(["-m", model])
        cmd.append(prompt)
        return cmd

    def prepare_invocation(self, request: AdapterExecutionRequest) -> _PreparedInvocation:
        env = self.build_env(request.profile, request.env)

        if request.mode != AdapterMode.CRITIC:
            return _PreparedInvocation(
                command=self.prepare_cli_command(request.prompt, model=request.model, mode=request.mode),
                env=env,
            )

        handle = tempfile.NamedTemporaryFile(prefix="autopilot-critic-", suffix=".txt", delete=False)
        output_path = Path(handle.name)
        handle.close()
        command = [
            "codex",
            "exec",
            "--full-auto",
            "--skip-git-repo-check",
            "--ephemeral",
            "-o",
            str(output_path),
            "-",
        ]
        return _PreparedInvocation(
            command=command,
            env=env,
            input_text=request.prompt,
            output_file=output_path,
            cleanup_paths=[output_path],
        )


class _ManagedHomeCliAdapter(LocalProviderAdapter):
    runtime_subdir = "home"
    session_copy_targets: tuple[tuple[str, str], ...]

    def runtime_home_from_profile_dir(self, profile_dir: Path) -> Path:
        return profile_dir / self.runtime_subdir

    def runtime_home(self, profile: Profile) -> Path:
        return self.runtime_home_from_profile_dir(Path(profile.path))

    def build_env(self, profile: Profile, base_env: Mapping[str, str] | None = None) -> dict[str, str]:
        env = dict(base_env) if base_env is not None else os.environ.copy()
        env["HOME"] = str(self.runtime_home(profile))
        env["PATH"] = self._managed_home_path(real_home=Path.home(), existing_path=env.get("PATH", ""))
        return env

    def runtime_env_overrides(self, profile: Profile) -> dict[str, str]:
        return {"HOME": str(self.runtime_home(profile))}

    def _managed_home_path(self, *, real_home: Path, existing_path: str) -> str:
        user_paths = [str(real_home / suffix) for suffix in USER_BIN_DIRS]
        return ":".join([*DEFAULT_PATH_PREFIXES, *user_paths, existing_path])

    def profile_is_valid(self, profile_dir: Path) -> bool:
        return bool(self.resume_state_paths(self.runtime_home_from_profile_dir(profile_dir)))

    def copy_session_to_profile(self, source_home: Path, destination: Path) -> None:
        runtime_home = self.runtime_home_from_profile_dir(destination)
        runtime_home.mkdir(parents=True, exist_ok=True)

        copied_any = False
        for source_rel, destination_rel in self.session_copy_targets:
            source_path = source_home / source_rel
            if not source_path.exists():
                continue
            destination_path = runtime_home / destination_rel
            destination_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_path, destination_path)
            copied_any = True

        if not copied_any:
            raise FileNotFoundError(f"No active {self.provider_family} session found at {source_home}")


class ClaudeLocalAdapter(_ManagedHomeCliAdapter):
    adapter_id = "claude_local"
    provider_family = "claude"
    cli_name = "claude"
    install_hint = "curl -fsSL https://claude.ai/install.sh | bash"
    session_copy_targets = ((".claude", ".claude"),)

    def check_installed_command(self) -> list[str]:
        return ["claude", "--version"]

    def provider_login_command(self) -> list[str]:
        return ["claude", "auth", "login"]

    def session_source_dir(self, home: Path) -> Path | None:
        return home

    def resume_state_paths(self, runtime_home: Path) -> list[Path]:
        session_dir = runtime_home / ".claude"
        return [session_dir] if session_dir.exists() else []

    def prepare_cli_command(self, prompt: str, *, model: str | None, mode: AdapterMode) -> list[str]:
        return ["claude", "-p", prompt]


class GeminiLocalAdapter(_ManagedHomeCliAdapter):
    adapter_id = "gemini_local"
    provider_family = "gemini"
    cli_name = "gemini"
    install_hint = "npm i -g @anthropic-ai/gemini"
    session_copy_targets = ((".config/gemini", ".config/gemini"), (".gemini", ".gemini"))

    def check_installed_command(self) -> list[str]:
        return ["gemini", "--version"]

    def provider_login_command(self) -> list[str]:
        return ["gemini"]

    def session_source_dir(self, home: Path) -> Path | None:
        return home

    def resume_state_paths(self, runtime_home: Path) -> list[Path]:
        return [path for path in (runtime_home / ".config" / "gemini", runtime_home / ".gemini") if path.exists()]

    def prepare_cli_command(self, prompt: str, *, model: str | None, mode: AdapterMode) -> list[str]:
        return ["gemini", "-p", prompt]


class OllamaLocalAdapter(LocalProviderAdapter):
    adapter_id = "ollama_local"
    provider_family = "ollama"
    cli_name = "ollama"
    install_hint = "brew install ollama"
    provider_mode = "local"
    auth_strategy = "none"
    session_strategy = "stateless"
    requires_managed_profile = False
    supports_model_override = True
    supported_modes = (AdapterMode.EXEC, AdapterMode.REVIEW)

    def check_installed_command(self) -> list[str]:
        return ["ollama", "--version"]

    def provider_login_command(self) -> list[str]:
        return []

    def session_source_dir(self, home: Path) -> Path | None:
        return None

    def runtime_home_from_profile_dir(self, profile_dir: Path) -> Path:
        return profile_dir

    def resume_state_paths(self, runtime_home: Path) -> list[Path]:
        return []

    def copy_session_to_profile(self, source_home: Path, destination: Path) -> None:
        raise ValueError("ollama uses stateless local execution and does not support session import.")

    def prepare_cli_command(self, prompt: str, *, model: str | None, mode: AdapterMode) -> list[str]:
        return ["ollama", "run", model or "llama3.2", prompt]


_LOCAL_ADAPTERS: tuple[LocalProviderAdapter, ...] = (
    CodexLocalAdapter(),
    ClaudeLocalAdapter(),
    GeminiLocalAdapter(),
    OllamaLocalAdapter(),
)
SUPPORTED_PROVIDER_FAMILIES = tuple(adapter.provider_family for adapter in _LOCAL_ADAPTERS)
_ADAPTERS_BY_ID: dict[str, LocalProviderAdapter] = {}
_DEFAULT_ADAPTER_BY_PROVIDER: dict[str, LocalProviderAdapter] = {}


def _runtime_id_for_adapter(adapter: LocalProviderAdapter) -> str:
    return f"{adapter.adapter_id}:runtime"


def register_adapter(adapter: LocalProviderAdapter, *, default: bool = True) -> LocalProviderAdapter:
    """Register one adapter and expose it through the minimal plugin slots."""
    _ADAPTERS_BY_ID[adapter.adapter_id] = adapter
    if default or adapter.provider_family not in _DEFAULT_ADAPTER_BY_PROVIDER:
        _DEFAULT_ADAPTER_BY_PROVIDER[adapter.provider_family] = adapter
    runtime_id = _runtime_id_for_adapter(adapter)
    register_runtime(
        RuntimePlugin(
            runtime_id=runtime_id,
            display_name=f"{adapter.provider_family} local runtime",
            kind="local_cli",
            provider_family=adapter.provider_family,
            adapter_id=adapter.adapter_id,
            metadata={"cli_name": adapter.cli_name, "install_hint": adapter.install_hint},
        )
    )
    register_agent_provider(
        AgentProviderPlugin(
            provider_family=adapter.provider_family,
            adapter_id=adapter.adapter_id,
            runtime_id=runtime_id,
            display_name=adapter.provider_family,
            metadata={
                "cli_name": adapter.cli_name,
                "install_hint": adapter.install_hint,
                "mode": adapter.provider_mode,
                "transport": adapter.transport,
                "auth_strategy": adapter.auth_strategy,
                "capabilities": adapter.capabilities,
            },
        )
    )
    return adapter


def unregister_adapter(adapter_id: str) -> None:
    """Remove an adapter from the registry and free its plugin slots."""
    adapter = _ADAPTERS_BY_ID.pop(adapter_id, None)
    if adapter is None:
        return
    current_default = _DEFAULT_ADAPTER_BY_PROVIDER.get(adapter.provider_family)
    if current_default is adapter:
        del _DEFAULT_ADAPTER_BY_PROVIDER[adapter.provider_family]
    unregister_runtime(_runtime_id_for_adapter(adapter))
    unregister_agent_provider(adapter.provider_family)


for _adapter in _LOCAL_ADAPTERS:
    register_adapter(_adapter)


def adapter_id_for_provider(provider: str) -> str:
    """Resolve a provider family or adapter id to a concrete adapter id."""
    if provider in _ADAPTERS_BY_ID:
        return provider
    if provider in _DEFAULT_ADAPTER_BY_PROVIDER:
        return _DEFAULT_ADAPTER_BY_PROVIDER[provider].adapter_id
    raise ValueError(f"Unknown provider adapter: {provider}")


def get_adapter(provider: str) -> LocalProviderAdapter:
    """Return the adapter for a provider family or adapter id."""
    adapter_id = adapter_id_for_provider(provider)
    return _ADAPTERS_BY_ID[adapter_id]


def list_adapters() -> list[LocalProviderAdapter]:
    """Return the registered local adapters."""
    return list(_ADAPTERS_BY_ID.values())


def list_provider_families() -> list[str]:
    """Return the canonical provider family names."""
    return list(_DEFAULT_ADAPTER_BY_PROVIDER)
