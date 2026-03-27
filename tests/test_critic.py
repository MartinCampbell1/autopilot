"""Tests for critic runner."""

from autopilot.core.critic import build_critic_prompt, parse_critic_output


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
        assert result.feedback == "Critic returned NEEDS_WORK without actionable issues."


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
