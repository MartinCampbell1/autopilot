"""Tests for stuck detector."""

from autopilot.core.models import IterationRecord
from autopilot.core.stuck_detector import StuckDetector, StuckReason


class TestStuckDetector:
    def test_not_stuck_initially(self) -> None:
        detector = StuckDetector(max_same_feedback=3, max_empty_diffs=3, max_same_gate_fail=3)
        assert detector.is_stuck() is False

    def test_stuck_same_feedback(self) -> None:
        detector = StuckDetector(max_same_feedback=3)
        for _ in range(3):
            detector.record_iteration(
                IterationRecord(
                    story_id=1,
                    iteration=1,
                    profile_used="acc1",
                    provider="codex",
                    gates_passed=True,
                    critic_approved=False,
                    critic_feedback="callback URL is hardcoded",
                )
            )
        result = detector.is_stuck()
        assert result is True
        assert detector.stuck_reason == StuckReason.SAME_FEEDBACK

    def test_not_stuck_different_feedback(self) -> None:
        detector = StuckDetector(max_same_feedback=3)
        for feedback in ["issue A", "issue B", "issue C"]:
            detector.record_iteration(
                IterationRecord(
                    story_id=1,
                    iteration=1,
                    profile_used="acc1",
                    provider="codex",
                    gates_passed=True,
                    critic_approved=False,
                    critic_feedback=feedback,
                )
            )
        assert detector.is_stuck() is False

    def test_stuck_empty_diffs(self) -> None:
        detector = StuckDetector(max_empty_diffs=3)
        for _ in range(3):
            detector.record_iteration(
                IterationRecord(
                    story_id=1,
                    iteration=1,
                    profile_used="acc1",
                    provider="codex",
                    gates_passed=True,
                    git_diff_empty=True,
                )
            )
        assert detector.is_stuck() is True
        assert detector.stuck_reason == StuckReason.EMPTY_DIFF

    def test_stuck_same_gate_failure(self) -> None:
        detector = StuckDetector(max_same_gate_fail=3)
        for _ in range(3):
            detector.record_iteration(
                IterationRecord(
                    story_id=1,
                    iteration=1,
                    profile_used="acc1",
                    provider="codex",
                    gates_passed=False,
                    critic_feedback="build: Error: cannot find module 'foo'",
                )
            )
        assert detector.is_stuck() is True
        assert detector.stuck_reason == StuckReason.SAME_GATE_FAIL

    def test_reset(self) -> None:
        detector = StuckDetector(max_same_feedback=2)
        for _ in range(2):
            detector.record_iteration(
                IterationRecord(
                    story_id=1,
                    iteration=1,
                    profile_used="acc1",
                    provider="codex",
                    gates_passed=True,
                    critic_approved=False,
                    critic_feedback="same",
                )
            )
        assert detector.is_stuck() is True
        detector.reset()
        assert detector.is_stuck() is False
