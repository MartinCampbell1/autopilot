"""Tests for core data models."""

import time

from autopilot.core.models import (
    CriticResult,
    GateResult,
    IterationRecord,
    Profile,
    StoryStatus,
)


class TestProfile:
    def test_create_profile(self) -> None:
        profile = Profile(name="acc1", provider="codex", path="/home/.autopilot/profiles/codex/acc1")
        assert profile.name == "acc1"
        assert profile.provider == "codex"
        assert profile.is_available is True
        assert profile.requests_made == 0

    def test_mark_rate_limited(self) -> None:
        profile = Profile(name="acc1", provider="codex", path="/tmp")
        profile.mark_rate_limited(cooldown_base=300)
        assert profile.is_available is False
        assert profile.consecutive_errors == 1
        assert profile.cooldown_until > time.time()

    def test_cooldown_recovery(self) -> None:
        profile = Profile(name="acc1", provider="codex", path="/tmp")
        profile.cooldown_until = time.time() - 1
        profile.is_available = False
        assert profile.check_available() is True
        assert profile.is_available is True

    def test_mark_success_resets_errors(self) -> None:
        profile = Profile(name="acc1", provider="codex", path="/tmp")
        profile.consecutive_errors = 3
        profile.mark_success()
        assert profile.consecutive_errors == 0


class TestGateResult:
    def test_gate_passed(self) -> None:
        result = GateResult(name="build", cmd="npm run build", passed=True, output="ok", required=True)
        assert result.passed is True

    def test_gate_failed_required(self) -> None:
        result = GateResult(name="test", cmd="npm test", passed=False, output="1 failed", required=True)
        assert result.passed is False
        assert result.required is True


class TestCriticResult:
    def test_approved(self) -> None:
        result = CriticResult(approved=True, feedback="", raw_output="APPROVED\nAll looks good.")
        assert result.approved is True

    def test_needs_work(self) -> None:
        result = CriticResult(
            approved=False,
            feedback="- callback URL is hardcoded\n- no error handling",
            raw_output="NEEDS_WORK\n- callback URL is hardcoded\n- no error handling",
        )
        assert result.approved is False
        assert "hardcoded" in result.feedback


class TestStoryStatus:
    def test_values(self) -> None:
        assert StoryStatus.OPEN == "open"
        assert StoryStatus.IN_PROGRESS == "in_progress"
        assert StoryStatus.DONE == "done"
        assert StoryStatus.STUCK == "stuck"


class TestIterationRecord:
    def test_create(self) -> None:
        record = IterationRecord(
            story_id=1,
            iteration=1,
            profile_used="acc3",
            provider="codex",
            gates_passed=True,
            critic_approved=False,
            critic_feedback="missing tests",
            elapsed_sec=120.5,
        )
        assert record.story_id == 1
        assert record.critic_approved is False
