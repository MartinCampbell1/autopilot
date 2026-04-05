"""First-class wrapper for prompt execution with progress streaming and recovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from autopilot.core.adapters import AdapterExecutionRequest, AdapterMode, get_adapter
from autopilot.core.context_manager import execute_with_context_recovery
from autopilot.core.models import Profile


@dataclass(slots=True)
class StreamingExecutionSpec:
    """Inputs for one provider-backed prompt execution."""

    project_path: Path
    env: dict[str, str]
    provider: str
    prompt: str
    timeout: int = 1800
    mode: AdapterMode = AdapterMode.EXEC
    on_progress: Callable[[int, str], None] | None = None
    progress_interval: int = 15
    progress_message: Callable[[], str] | None = None
    profile: Profile | None = None


@dataclass(slots=True)
class StreamingExecutionOutcome:
    """Normalized result of one streaming prompt execution."""

    success: bool
    text: str
    rate_limited: bool


def infer_runtime_profile(provider: str, env: dict[str, str], profile: Profile | None = None) -> Profile:
    """Infer the concrete runtime profile for one provider-backed execution."""

    if profile is not None:
        return profile

    adapter = get_adapter(provider)
    if adapter.provider_family == "codex":
        runtime_path = env.get("CODEX_HOME", "")
    else:
        runtime_home = env.get("HOME", "")
        runtime_path = str(Path(runtime_home).parent) if runtime_home else ""

    return Profile(
        name="runtime",
        provider=adapter.provider_family,
        adapter_id=adapter.adapter_id,
        path=runtime_path or ".",
    )


def run_streaming_execution(spec: StreamingExecutionSpec) -> StreamingExecutionOutcome:
    """Execute a prompt with progress callbacks and compact retry recovery."""

    runtime_profile = infer_runtime_profile(spec.provider, spec.env, spec.profile)
    adapter = get_adapter(runtime_profile.resolved_adapter_id)
    result, parsed = execute_with_context_recovery(
        adapter,
        AdapterExecutionRequest(
            profile=runtime_profile,
            prompt=spec.prompt,
            workdir=spec.project_path,
            env=spec.env,
            timeout=spec.timeout,
            mode=spec.mode,
            on_progress=spec.on_progress,
            progress_interval=spec.progress_interval,
            progress_message=spec.progress_message,
        ),
    )
    return StreamingExecutionOutcome(
        success=result.success,
        text=parsed.text,
        rate_limited=parsed.rate_limited,
    )


__all__ = [
    "StreamingExecutionOutcome",
    "StreamingExecutionSpec",
    "infer_runtime_profile",
    "run_streaming_execution",
]
