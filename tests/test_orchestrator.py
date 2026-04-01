"""Tests for main orchestrator loop."""

from pathlib import Path
from unittest.mock import patch

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import CriticResult, GateResult, Profile, ReviewPhaseResult
from autopilot.core.orchestrator import Orchestrator, StoryOutcome


class TestOrchestrator:
    def _make_orchestrator(
        self,
        tmp_path: Path,
        *,
        quality_regression_mode: str = "retry",
        max_task_attempts: int = 1,
    ) -> Orchestrator:
        return Orchestrator(
            project_path=tmp_path,
            config=AutopilotConfig(),
            profiles_dir=tmp_path / "profiles",
            quality_regression_mode=quality_regression_mode,
            max_task_attempts=max_task_attempts,
        )

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_prompt_iteration")
    @patch("autopilot.core.orchestrator.get_adapter")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_stateless_provider_primary_iteration_uses_prompt_runtime(
        self,
        mock_ralph,
        mock_get_adapter,
        mock_prompt_iteration,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_get_adapter.return_value = type("Adapter", (), {"requires_managed_profile": False})()
        mock_prompt_iteration.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (
            True,
            [GateResult(name="build", cmd="x", passed=True, output="ok")],
        )
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_review_plan.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(
            name="local-openai",
            provider="openai_compatible",
            adapter_id="openai_compatible_local",
            path=str(tmp_path),
        )
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
            progress_callback=lambda *_: None,
        )

        assert outcome == StoryOutcome.APPROVED
        mock_prompt_iteration.assert_called_once()
        mock_ralph.assert_not_called()
        assert "Selected story #1: Setup" in mock_prompt_iteration.call_args.args[3]
        assert callable(mock_prompt_iteration.call_args.kwargs["on_progress"])

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.get_adapter")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_successful_iteration(
        self,
        mock_ralph,
        mock_get_adapter,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_get_adapter.return_value = type("Adapter", (), {"requires_managed_profile": True})()
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (
            True,
            [GateResult(name="build", cmd="x", passed=True, output="ok")],
        )
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_review_plan.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

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
            progress_callback=lambda *_: None,
        )

        assert outcome == StoryOutcome.APPROVED
        assert callable(mock_ralph.call_args.kwargs["on_progress"])

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_retry_iteration")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_retry_iteration_uses_targeted_retry_prompt(
        self,
        mock_ralph,
        mock_retry,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "unused", False)
        mock_retry.return_value = (True, "fixed", False)
        mock_gates.return_value = (True, [])
        mock_get_diff.return_value = "+notes.txt"
        mock_diff_empty.return_value = False
        mock_review_plan.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
            retry_only=True,
            progress_callback=lambda *_: None,
        )

        assert outcome == StoryOutcome.APPROVED
        mock_retry.assert_called_once()
        mock_ralph.assert_not_called()
        assert callable(mock_retry.call_args.kwargs["on_progress"])

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_retry_iteration")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_alternate_attempt_can_win_same_task(
        self,
        mock_ralph,
        mock_retry,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "primary failed gates", False)
        mock_retry.return_value = (True, "retry fixed it", False)
        mock_gates.side_effect = [
            (False, [GateResult(name="test", cmd="npm test", passed=False, output="1 failed")]),
            (True, []),
        ]
        mock_review_plan.return_value = CriticResult(
            approved=True,
            feedback="",
            raw_output="APPROVED",
            usage={
                "provider": "codex",
                "role": "critic",
                "invocations": 1,
                "tracked_invocations": 0,
                "priced_invocations": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "pricing_source": "unconfigured",
            },
        )
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.side_effect = [False, False]

        orchestrator = self._make_orchestrator(tmp_path, max_task_attempts=2)
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

        assert outcome == StoryOutcome.APPROVED
        assert len(orchestrator.iteration_history) == 1
        assert orchestrator.iteration_history[-1].worker_usage["invocations"] == 2
        assert orchestrator.iteration_history[-1].critic_usage["invocations"] == 1
        mock_retry.assert_called_once()

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_retry_iteration")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_last_attempt_wins_when_no_valid_outcome_exists(
        self,
        mock_ralph,
        mock_retry,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (False, "primary crashed", False)
        mock_retry.return_value = (True, "retry changed files", False)
        mock_gates.return_value = (True, [])
        mock_review_plan.return_value = CriticResult(
            approved=False,
            feedback="needs tests",
            raw_output="NEEDS_WORK\nneeds tests",
            usage={
                "provider": "codex",
                "role": "critic",
                "invocations": 1,
                "tracked_invocations": 0,
                "priced_invocations": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
                "pricing_source": "unconfigured",
            },
        )
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.side_effect = [True, False]

        orchestrator = self._make_orchestrator(tmp_path, max_task_attempts=2)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
        )

        assert outcome == StoryOutcome.CRITIC_REJECTED
        assert len(orchestrator.iteration_history) == 1
        assert orchestrator.iteration_history[-1].critic_feedback == "needs tests"
        assert orchestrator.iteration_history[-1].worker_usage["invocations"] == 2
        assert orchestrator.iteration_history[-1].critic_usage["invocations"] == 1

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

    @patch("autopilot.core.orchestrator.update_quality_ratchet")
    @patch("autopilot.core.orchestrator.read_quality_ratchet")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_gate_regression_is_recorded_and_retried(
        self,
        mock_ralph,
        mock_gates,
        mock_read_quality_ratchet,
        mock_update_quality_ratchet,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_read_quality_ratchet.return_value = {"test": True}
        mock_gates.return_value = (
            False,
            [
                GateResult(
                    name="test",
                    cmd="npm test",
                    passed=False,
                    output="1 failed",
                    required=True,
                    baseline_passed=True,
                    regression=True,
                )
            ],
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
        assert orchestrator.iteration_history[-1].quality_regression is True
        assert "regressed after previously passing" in orchestrator.iteration_history[-1].regression_summary
        mock_update_quality_ratchet.assert_called_once()

    @patch("autopilot.core.orchestrator.update_quality_ratchet")
    @patch("autopilot.core.orchestrator.read_quality_ratchet")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_gate_regression_can_quarantine_for_manual_attention(
        self,
        mock_ralph,
        mock_gates,
        mock_read_quality_ratchet,
        mock_update_quality_ratchet,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_read_quality_ratchet.return_value = {"test": True}
        mock_gates.return_value = (
            False,
            [
                GateResult(
                    name="test",
                    cmd="npm test",
                    passed=False,
                    output="1 failed",
                    required=True,
                    baseline_passed=True,
                    regression=True,
                )
            ],
        )

        orchestrator = self._make_orchestrator(tmp_path, quality_regression_mode="quarantine")
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

        assert outcome == StoryOutcome.QUALITY_REGRESSION

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

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_iteration_passes_review_phases_to_review_plan(
        self,
        mock_ralph,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (True, [])
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_review_plan.return_value = CriticResult(approved=True, feedback="", raw_output="APPROVED")

        orchestrator = self._make_orchestrator(tmp_path)
        profile = Profile(name="acc1", provider="codex", path=str(tmp_path))
        env = {"PATH": "/usr/bin"}

        outcome = orchestrator.run_single_iteration(
            profile=profile,
            env=env,
            story_id=1,
            story_title="Setup",
            story_description="Project setup",
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
            review_phases=["security", "tests"],
        )

        assert outcome == StoryOutcome.APPROVED
        assert mock_review_plan.call_args.kwargs["review_phases"] == ["security", "tests"]

    @patch("autopilot.core.orchestrator.check_git_diff_empty")
    @patch("autopilot.core.orchestrator.get_last_commit_diff")
    @patch("autopilot.core.orchestrator.run_review_plan")
    @patch("autopilot.core.orchestrator.run_gates")
    @patch("autopilot.core.orchestrator.run_ralph_iteration")
    def test_iteration_record_keeps_review_results(
        self,
        mock_ralph,
        mock_gates,
        mock_review_plan,
        mock_get_diff,
        mock_diff_empty,
        tmp_path: Path,
    ) -> None:
        mock_ralph.return_value = (True, "Story 1 done", False)
        mock_gates.return_value = (True, [])
        mock_get_diff.return_value = "+new code"
        mock_diff_empty.return_value = False
        mock_review_plan.return_value = CriticResult(
            approved=False,
            feedback="- [security] secret is committed",
            raw_output="NEEDS_WORK\n- secret is committed",
            review_phases=["security"],
            review_results=[
                ReviewPhaseResult(
                    phase="security",
                    approved=False,
                    feedback="- secret is committed",
                    raw_output="NEEDS_WORK\n- secret is committed",
                )
            ],
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
            gates_config=[],
            critic_profile=profile,
            critic_env=env,
            review_phases=["security"],
        )

        assert outcome == StoryOutcome.CRITIC_REJECTED
        assert orchestrator.iteration_history[-1].review_phases == ["security"]
        assert orchestrator.iteration_history[-1].review_results[0].phase == "security"
