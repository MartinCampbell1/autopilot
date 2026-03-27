"""Stuck detector for repeated failure patterns."""

from __future__ import annotations

from enum import StrEnum

from autopilot.core.models import IterationRecord


class StuckReason(StrEnum):
    NOT_STUCK = "not_stuck"
    SAME_FEEDBACK = "same_feedback"
    EMPTY_DIFF = "empty_diff"
    SAME_GATE_FAIL = "same_gate_fail"
    TIMEOUT = "timeout"


class StuckDetector:
    """Track iteration history and detect when an agent is spinning."""

    def __init__(
        self,
        max_same_feedback: int = 3,
        max_empty_diffs: int = 3,
        max_same_gate_fail: int = 3,
    ):
        self.max_same_feedback = max_same_feedback
        self.max_empty_diffs = max_empty_diffs
        self.max_same_gate_fail = max_same_gate_fail
        self.iterations: list[IterationRecord] = []
        self.stuck_reason: StuckReason = StuckReason.NOT_STUCK

    def record_iteration(self, record: IterationRecord) -> None:
        """Append one iteration to history."""
        self.iterations.append(record)

    def is_stuck(self) -> bool:
        """Return whether any configured stuck pattern is currently active."""
        if not self.iterations:
            self.stuck_reason = StuckReason.NOT_STUCK
            return False

        if self._check_same_feedback():
            self.stuck_reason = StuckReason.SAME_FEEDBACK
            return True

        if self._check_empty_diffs():
            self.stuck_reason = StuckReason.EMPTY_DIFF
            return True

        if self._check_same_gate_fail():
            self.stuck_reason = StuckReason.SAME_GATE_FAIL
            return True

        self.stuck_reason = StuckReason.NOT_STUCK
        return False

    def _check_same_feedback(self) -> bool:
        """Detect identical critic feedback N times in a row."""
        recent = self.iterations[-self.max_same_feedback :]
        if len(recent) < self.max_same_feedback:
            return False

        critic_rejections = [
            record
            for record in recent
            if record.gates_passed and record.critic_approved is False and record.critic_feedback
        ]
        if len(critic_rejections) < self.max_same_feedback:
            return False

        feedbacks = [record.critic_feedback.strip().lower() for record in critic_rejections]
        return len(set(feedbacks)) == 1

    def _check_empty_diffs(self) -> bool:
        """Detect no changes N times in a row."""
        recent = self.iterations[-self.max_empty_diffs :]
        if len(recent) < self.max_empty_diffs:
            return False

        return all(record.git_diff_empty for record in recent)

    def _check_same_gate_fail(self) -> bool:
        """Detect repeated identical gate failure text N times in a row."""
        recent = self.iterations[-self.max_same_gate_fail :]
        if len(recent) < self.max_same_gate_fail:
            return False

        failed = [record for record in recent if not record.gates_passed and record.critic_feedback.strip()]
        if len(failed) < self.max_same_gate_fail:
            return False

        feedbacks = [record.critic_feedback.strip().lower() for record in failed]
        return len(set(feedbacks)) == 1

    def reset(self) -> None:
        """Clear history and reset current stuck state."""
        self.iterations.clear()
        self.stuck_reason = StuckReason.NOT_STUCK

    def summary(self) -> str:
        """Return a human-readable description of the current stuck state."""
        if not self.is_stuck():
            return "Not stuck"

        reason_messages = {
            StuckReason.SAME_FEEDBACK: f"Critic gave same feedback {self.max_same_feedback} times",
            StuckReason.EMPTY_DIFF: f"No code changes for {self.max_empty_diffs} iterations",
            StuckReason.SAME_GATE_FAIL: f"Same failure for {self.max_same_gate_fail} iterations",
            StuckReason.TIMEOUT: "Agent timed out",
        }
        return reason_messages.get(self.stuck_reason, str(self.stuck_reason))
