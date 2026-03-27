"""Tests for main orchestrator loop."""

from pathlib import Path
from unittest.mock import patch

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import CriticResult, GateResult, Profile
from autopilot.core.orchestrator import Orchestrator, StoryOutcome


class TestOrchestrator:
    def _make_orchestrator(self, tmp_path: Path) -> Orchestrator:
        return Orchestrator(
            project_path=tmp_path,
            config=AutopilotConfig(),
            profiles_dir=tmp_path / "profiles",
        )

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_critic")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_successful_iteration(
        self,
        mock_ralph,
        mock_gates,
        mock_critic,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (
            True,
            [GateResult(name="build", cmd="x", passed=True, output="ok")],
        )
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_critic.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[{"name": "build", "cmd": "npm run build"}],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.APPROVED

    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_gate_failure(self, mock_ralph, mock_gates, tmp_path: Path) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (
            False,
            [GateResult(name="test", cmd="x", passed=False, output="1 failed")],
        )

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[{"name": "test", "cmd": "npm test"}],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.GATE_FAILED

    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_rate_limited(self, mock_ralph, tmp_path: Path) -> None:
        mock_ralph.return_value = (False, "429 Too Many Requests", True)

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="desc",
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.RATE_LIMITED
