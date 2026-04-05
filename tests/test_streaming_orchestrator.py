"""Tests for streaming execution orchestration."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autopilot.core.streaming_orchestrator import (
    StreamingExecutionSpec,
    infer_runtime_profile,
    run_streaming_execution,
)


def test_infer_runtime_profile_uses_codex_home(tmp_path: Path) -> None:
    env = {"CODEX_HOME": str(tmp_path / ".codex")}

    profile = infer_runtime_profile("codex", env)

    assert profile.provider == "codex"
    assert profile.path == str(tmp_path / ".codex")


@patch("autopilot.core.streaming_orchestrator.execute_with_context_recovery")
@patch("autopilot.core.streaming_orchestrator.get_adapter")
def test_run_streaming_execution_wraps_adapter_request(mock_get_adapter: MagicMock, mock_execute: MagicMock, tmp_path: Path) -> None:
    mock_adapter = MagicMock()
    mock_adapter.provider_family = "codex"
    mock_adapter.adapter_id = "codex_local"
    mock_get_adapter.return_value = mock_adapter
    mock_execute.return_value = (
        SimpleNamespace(success=True),
        SimpleNamespace(text="done", rate_limited=False),
    )

    outcome = run_streaming_execution(
        StreamingExecutionSpec(
            project_path=tmp_path,
            env={"CODEX_HOME": str(tmp_path / ".codex")},
            provider="codex",
            prompt="Selected story #1",
        )
    )

    assert outcome.success is True
    assert outcome.text == "done"
    assert outcome.rate_limited is False
    request = mock_execute.call_args.args[1]
    assert request.workdir == tmp_path
    assert request.prompt == "Selected story #1"
    assert request.profile.provider == "codex"
