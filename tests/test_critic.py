"""Tests for critic runner."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from autopilot.core.critic import (
    NON_ACTIONABLE_FEEDBACK,
    NON_ACTIONABLE_VERIFICATION_FEEDBACK,
    build_critic_prompt,
    feedback_is_actionable,
    parse_critic_output,
    run_critic,
    run_review_plan,
)


class TestParseCriticOutput:
    def test_approved(self) -> None:
        output = "APPROVED\n\nAll looks good. Code is clean and well-tested."
        result = parse_critic_output(output)
        assert result.approved is True
        assert result.feedback == ""

    def test_needs_work(self) -> None:
        output = "NEEDS_WORK\n- callback URL is hardcoded\n- no error handling for OAuth"
        result = parse_critic_output(output)
        assert result.approved is False
        assert "hardcoded" in result.feedback
        assert "error handling" in result.feedback

    def test_approved_with_notes(self) -> None:
        output = "APPROVED\n\nMinor: could add more comments, but not blocking."
        result = parse_critic_output(output)
        assert result.approved is True

    def test_needs_work_takes_priority(self) -> None:
        output = "NEEDS_WORK\n- serious issue\nBut otherwise APPROVED"
        result = parse_critic_output(output)
        assert result.approved is False

    def test_empty_output(self) -> None:
        result = parse_critic_output("")
        assert result.approved is False
        assert "empty" in result.feedback.lower()

    def test_needs_work_extracts_issue_lines_from_noisy_output(self) -> None:
        output = """If there are issues:
NEEDS_WORK
- Issue 1: specific description
- Issue 2: specific description

NEEDS_WORK
- Issue 1: latest change is missing tests
- Issue 2: handler does not validate input
OpenAI Codex v0.116.0
exec /bin/zsh -lc 'git show'
"""
        result = parse_critic_output(output)
        assert result.approved is False
        assert result.feedback == (
            "- Issue 1: latest change is missing tests\n"
            "- Issue 2: handler does not validate input"
        )

    def test_needs_work_placeholder_only_becomes_actionable_fallback(self) -> None:
        output = """NEEDS_WORK
- Issue 1: specific description
- Issue 2: specific description
"""
        result = parse_critic_output(output)
        assert result.approved is False
        assert result.feedback == NON_ACTIONABLE_FEEDBACK

    def test_needs_work_instruction_echo_becomes_non_actionable(self) -> None:
        output = """NEEDS_WORK
Then list one or more bullet points with concrete blocking issues.
"""
        result = parse_critic_output(output)
        assert result.approved is False
        assert result.feedback == NON_ACTIONABLE_FEEDBACK

    def test_verdict_pass_with_command_backed_evidence(self) -> None:
        output = """### Check: unit tests
**Command run:**
  pytest -q
**Output observed:**
  3 passed in 0.12s
**Result: PASS**

VERDICT: PASS
"""
        result = parse_critic_output(output)
        assert result.approved is True
        assert result.verdict == "PASS"
        assert len(result.verification_checks) == 1
        assert result.verification_checks[0].command == "pytest -q"

    def test_verdict_pass_without_command_backed_evidence_is_rejected(self) -> None:
        result = parse_critic_output("VERDICT: PASS")
        assert result.approved is False
        assert result.feedback == NON_ACTIONABLE_VERIFICATION_FEEDBACK

    def test_verdict_partial_extracts_actionable_feedback(self) -> None:
        output = """### Check: CLI import
**Command run:**
  python3 -m pytest tests/test_execution_approval_cli.py
**Output observed:**
  ModuleNotFoundError: No module named 'typer'
**Result: PARTIAL**
**Expected vs Actual:**
  Expected the CLI test module to import successfully. Actual import failed because `typer` is unavailable.

VERDICT: PARTIAL
"""
        result = parse_critic_output(output)
        assert result.approved is False
        assert result.verdict == "PARTIAL"
        assert "typer" in result.feedback
        assert feedback_is_actionable(result.feedback)

    def test_feedback_is_actionable(self) -> None:
        assert feedback_is_actionable("- Issue 1: missing test")
        assert not feedback_is_actionable(NON_ACTIONABLE_FEEDBACK)
        assert not feedback_is_actionable(NON_ACTIONABLE_VERIFICATION_FEEDBACK)
        assert not feedback_is_actionable("- Issue 1: specific description")
        assert not feedback_is_actionable("- <concrete issue tied to code, tests, files, or behavior>")
        assert not feedback_is_actionable("Then list one or more bullet points with concrete blocking issues.")


class TestBuildCriticPrompt:
    def test_builds_prompt_with_diff(self) -> None:
        prompt = build_critic_prompt(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            template_path=None,
        )
        assert "OAuth login" in prompt
        assert "oauth_callback" in prompt
        assert "latest relevant code changes in the workspace" in prompt
        assert "**Command run:**" in prompt
        assert "VERDICT: PASS" in prompt
        assert "Do not modify project files" in prompt

    def test_builds_strict_prompt_without_placeholder_language(self) -> None:
        prompt = build_critic_prompt(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            strict=True,
        )
        assert "If you cannot identify at least one concrete blocking issue, respond with APPROVED." in prompt
        assert "<concrete issue" not in prompt
        assert "Do not return PASS unless at least one check block includes both a concrete command and observed output." in prompt

    def test_builds_phase_focused_prompt(self) -> None:
        prompt = build_critic_prompt(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            phase="security",
        )
        assert "focused security review" in prompt.lower()
        assert "ignore non-security concerns" in prompt.lower()


class TestRunCritic:
    @patch("autopilot.core.critic.get_adapter")
    def test_run_critic_uses_adapter_execution(self, mock_get_adapter: MagicMock, tmp_path: Path) -> None:
        mock_adapter = MagicMock()
        mock_adapter.provider_family = "codex"
        mock_adapter.adapter_id = "codex_local"
        mock_adapter.execute.return_value = SimpleNamespace(
            timed_out=False,
            stderr="",
            diagnostics=None,
        )
        mock_adapter.parse_output.return_value = SimpleNamespace(text="APPROVED", rate_limited=False)
        mock_get_adapter.return_value = mock_adapter

        result = run_critic(
            prompt="Review this change",
            provider="codex",
            env={"CODEX_HOME": str(tmp_path / ".codex")},
            workdir=Path(tmp_path),
        )

        assert result.approved is True
        request = mock_adapter.execute.call_args.args[0]
        assert request.mode.value == "critic"


class TestRunReviewPlan:
    @patch("autopilot.core.critic.run_critic")
    def test_run_review_plan_aggregates_multi_phase_failures(self, mock_run_critic: MagicMock, tmp_path: Path) -> None:
        mock_run_critic.side_effect = [
            SimpleNamespace(
                approved=False,
                feedback="- secret is committed",
                raw_output="NEEDS_WORK\n- secret is committed",
                usage={"provider": "codex", "role": "critic", "invocations": 1, "tracked_invocations": 0, "priced_invocations": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_source": "unconfigured"},
                elapsed_sec=1.2,
                profile_used="critic",
                review_results=[],
            ),
            SimpleNamespace(
                approved=True,
                feedback="",
                raw_output="APPROVED",
                usage={"provider": "codex", "role": "critic", "invocations": 1, "tracked_invocations": 0, "priced_invocations": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_source": "unconfigured"},
                elapsed_sec=0.8,
                profile_used="critic",
                review_results=[],
            ),
            SimpleNamespace(
                approved=False,
                feedback="- missing regression test",
                raw_output="NEEDS_WORK\n- missing regression test",
                usage={"provider": "codex", "role": "critic", "invocations": 1, "tracked_invocations": 0, "priced_invocations": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_source": "unconfigured"},
                elapsed_sec=0.5,
                profile_used="critic",
                review_results=[],
            ),
        ]

        result = run_review_plan(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            provider="codex",
            env={"CODEX_HOME": str(tmp_path / ".codex")},
            workdir=tmp_path,
            review_phases=["security", "architecture", "tests"],
        )

        assert result.approved is False
        assert "- [security] secret is committed" in result.feedback
        assert "- [tests] missing regression test" in result.feedback
        assert result.review_phases == ["security", "architecture", "tests"]
        assert len(result.review_results) == 3
        assert result.usage["invocations"] == 3

    @patch("autopilot.core.critic.run_critic")
    def test_run_review_plan_keeps_single_review_path_when_no_phases(self, mock_run_critic: MagicMock, tmp_path: Path) -> None:
        mock_run_critic.return_value = SimpleNamespace(
            approved=True,
            feedback="",
            raw_output="APPROVED",
            usage={"provider": "codex", "role": "critic", "invocations": 1, "tracked_invocations": 0, "priced_invocations": 0, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_source": "unconfigured"},
            elapsed_sec=0.5,
            profile_used="critic",
            review_results=[],
        )

        result = run_review_plan(
            story_title="OAuth login",
            story_description="Add Google OAuth",
            diff="+ def oauth_callback():\n+     pass",
            provider="codex",
            env={"CODEX_HOME": str(tmp_path / ".codex")},
            workdir=tmp_path,
            review_phases=[],
        )

        assert result.approved is True
        assert result.review_results == []
        assert mock_run_critic.call_count == 1
