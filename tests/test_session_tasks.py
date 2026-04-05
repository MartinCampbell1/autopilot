"""Tests for runtime task-close helpers."""

from autopilot.core.models import CriticResult, ReviewPhaseResult, VerificationCheck
from autopilot.core.session_tasks import VERIFICATION_NUDGE_FEEDBACK, verification_nudge_needed


def test_verification_nudge_needed_rejects_approved_result_without_evidence() -> None:
    result = CriticResult(approved=True, feedback="", raw_output="APPROVED")

    assert verification_nudge_needed(result) is True


def test_verification_nudge_needed_accepts_pass_with_evidence() -> None:
    result = CriticResult(
        approved=True,
        feedback="",
        raw_output="VERDICT: PASS",
        verdict="PASS",
        verification_checks=[
            VerificationCheck(
                name="adversarial probe - invalid token",
                command="pytest -q",
                output="3 passed",
                status="PASS",
            )
        ],
    )

    assert verification_nudge_needed(result) is False


def test_verification_nudge_needed_rejects_pass_without_adversarial_probe() -> None:
    result = CriticResult(
        approved=True,
        feedback="",
        raw_output="VERDICT: PASS",
        verdict="PASS",
        verification_checks=[
            VerificationCheck(
                name="unit tests",
                command="pytest -q",
                output="3 passed",
                status="PASS",
            )
        ],
    )

    assert verification_nudge_needed(result) is True


def test_verification_nudge_needed_requires_evidence_for_approved_review_phases() -> None:
    result = CriticResult(
        approved=True,
        feedback="",
        raw_output="VERDICT: PASS",
        verdict="PASS",
        review_results=[
            ReviewPhaseResult(
                phase="security",
                approved=True,
                feedback="",
                raw_output="VERDICT: PASS",
                verdict="PASS",
                verification_checks=[],
            )
        ],
    )

    assert verification_nudge_needed(result) is True
    assert "Verification evidence is missing" in VERIFICATION_NUDGE_FEEDBACK
