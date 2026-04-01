"""Tests for core data models."""

import time

import pytest

from autopilot.core.models import (
    CriticResult,
    GateResult,
    IterationRecord,
    Profile,
    ReviewPhaseResult,
    StoryDependencyError,
    StoryStatus,
    is_rate_limited,
    normalize_story_blocked_by,
    resolve_story_blocked_on,
    validate_story_dependencies,
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
        assert result.regression is False


class TestCriticResult:
    def test_approved(self) -> None:
        result = CriticResult(approved=True, feedback="", raw_output="APPROVED\nAll looks good.")
        assert result.approved is True
        assert result.review_phases == []
        assert result.review_results == []

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
        assert record.review_phases == []
        assert record.review_results == []
        assert record.quality_regression is False


class TestReviewPhaseResult:
    def test_create(self) -> None:
        result = ReviewPhaseResult(
            phase="security",
            approved=False,
            feedback="- secret is committed",
            raw_output="NEEDS_WORK\n- secret is committed",
        )

        assert result.phase == "security"
        assert result.approved is False


class TestRateLimitDetection:
    def test_detects_real_rate_limit_messages(self) -> None:
        assert is_rate_limited("HTTP 429 Too Many Requests")
        assert is_rate_limited("resource_exhausted: try again later")

    def test_ignores_timing_output_that_contains_429ms(self) -> None:
        assert not is_rate_limited("command succeeded in 429ms")

    def test_ignores_story_text_that_mentions_limited_scope(self) -> None:
        assert not is_rate_limited("The story is limited to creating README.md and notes.txt.")


class TestStoryDependencies:
    def test_normalize_story_blocked_by_deduplicates_ids(self) -> None:
        assert normalize_story_blocked_by(["1", 2, 2], story_id=3) == [1, 2]

    def test_validate_story_dependencies_rejects_unknown_reference(self) -> None:
        with pytest.raises(StoryDependencyError, match="depends on unknown stories"):
            validate_story_dependencies(
                [
                    {"id": 1, "blocked_by": []},
                    {"id": 2, "blocked_by": [99]},
                ]
            )

    def test_validate_story_dependencies_rejects_cycles(self) -> None:
        with pytest.raises(StoryDependencyError, match="cycle detected"):
            validate_story_dependencies(
                [
                    {"id": 1, "blocked_by": [2]},
                    {"id": 2, "blocked_by": [1]},
                ]
            )

    def test_resolve_story_blocked_on_only_returns_unfinished_dependencies(self) -> None:
        blocked_on = resolve_story_blocked_on(
            [1, 2, 3],
            {
                "1": {"status": "done"},
                "2": {"status": "skipped"},
                "3": {"status": "merge_blocked"},
            },
        )

        assert blocked_on == [3]
