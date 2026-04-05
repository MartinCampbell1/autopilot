"""Tests for structured evaluation feedback persistence."""

from __future__ import annotations

from autopilot.core.config import AutopilotConfig
from autopilot.core.evals.feedback import build_feedback_summary, read_feedback_records, record_iteration_feedback
from autopilot.core.models import IterationRecord, ReviewPhaseResult, VerificationCheck


def test_record_iteration_feedback_persists_critic_review_and_judge_outcomes(tmp_path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    record = IterationRecord(
        story_id=7,
        iteration=2,
        profile_used="acc1",
        provider="codex",
        gates_passed=True,
        critic_approved=False,
        critic_feedback="- missing regression test",
        review_results=[
            ReviewPhaseResult(
                phase="tests",
                approved=False,
                feedback="- add regression coverage",
                raw_output="FAIL",
                verification_checks=[VerificationCheck(name="pytest", command="pytest -q", status="FAIL")],
            )
        ],
        judge_pack="execution_claims",
        judge_verdict="PARTIAL",
        judge_summary="Need adversarial probe.",
        judge_findings=["missing_adversarial_probe"],
    )

    record_iteration_feedback(config, "proj-feedback", run_id="sess-1", iteration_record=record)
    payload = read_feedback_records(config, "proj-feedback")
    summary = build_feedback_summary(payload)

    assert len(payload) == 3
    assert summary["by_kind"]["critic_feedback"] == 1
    assert summary["by_kind"]["review_phase"] == 1
    assert summary["judge_outcomes"]["PARTIAL"] == 1
    assert summary["blocking_count"] >= 2
