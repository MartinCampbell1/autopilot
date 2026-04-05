"""Tests for pre-handoff shadow audit helpers."""

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import VerificationCheck
from autopilot.core.shadow_audit import (
    audit_verifier_output,
    compose_shadow_audit_decision,
    create_shadow_audit_record,
    list_shadow_audit_records,
    resolve_shadow_audit_record,
)


def test_shadow_audit_quarantines_pass_without_command_evidence() -> None:
    verdict, decision = audit_verifier_output("VERDICT: PASS", [])

    assert verdict == "PASS"
    assert decision.action == "quarantine"
    assert decision.findings == ("missing_command_evidence",)


def test_shadow_audit_retries_invalid_verdict_contract() -> None:
    raw_output = "VERDICT: PASS\nextra trailing line\n"
    verdict, decision = audit_verifier_output(raw_output, [])

    assert verdict == ""
    assert decision.action == "retry"
    assert decision.findings == ("invalid_verdict_contract",)


def test_shadow_audit_passes_valid_verifier_output() -> None:
    raw_output = """### Check: unit tests
**Command run:**
  pytest -q
**Output observed:**
  3 passed in 0.12s
**Result: PASS**

### Check: adversarial probe - invalid OAuth state
**Command run:**
  python -m pytest tests/test_auth.py -k invalid_state
**Output observed:**
  1 passed in 0.05s
**Result: PASS**

VERDICT: PASS
"""
    verdict, decision = audit_verifier_output(
        raw_output,
        [
            VerificationCheck(name="unit tests", command="pytest -q", output="3 passed in 0.12s", status="PASS"),
            VerificationCheck(
                name="adversarial probe - invalid OAuth state",
                command="python -m pytest tests/test_auth.py -k invalid_state",
                output="1 passed in 0.05s",
                status="PASS",
            ),
        ],
    )

    assert verdict == "PASS"
    assert decision.action == "pass"
    assert decision.findings == ("verdict:pass",)


def test_shadow_audit_composes_rule_based_generated_patch_quarantine() -> None:
    decision, content, metadata = compose_shadow_audit_decision(
        {},
        payload={"patch": "diff --git a/app.py b/app.py\n+print('hi')"},
        content="diff --git a/app.py b/app.py\n+print('hi')",
    )

    assert decision is not None
    assert decision.action == "quarantine"
    assert decision.findings == ("unverified_generated_patch",)
    assert "Generated patch output requires explicit review" in decision.summary
    assert "diff --git" in content
    assert metadata["decision_sources"] == ["generated_patch_rule"]


def test_shadow_audit_prefers_explicit_escalate_over_rule_based_quarantine() -> None:
    decision, _, metadata = compose_shadow_audit_decision(
        {
            "shadow_audit": {
                "action": "escalate",
                "summary": "Generated patch requires operator escalation.",
                "findings": ["manual_operator_attention"],
            }
        },
        payload={"patch": "diff --git a/app.py b/app.py\n+print('hi')"},
        content="diff --git a/app.py b/app.py\n+print('hi')",
    )

    assert decision is not None
    assert decision.action == "escalate"
    assert decision.findings == ("manual_operator_attention", "unverified_generated_patch")
    assert metadata["decision_sources"] == ["metadata", "generated_patch_rule"]


def test_shadow_audit_can_resolve_blocked_artifact_record(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))

    record = create_shadow_audit_record(
        config,
        project_id="proj_shadow",
        source_kind="runtime_agent_task_output",
        source_name="launch",
        source_id="rat_shadow_1",
        action="quarantine",
        summary="Background task output requires explicit review.",
        blocked_artifact_id="tout_shadow_1",
        blocked_artifact_owner_kind="runtime_agent_task",
        blocked_artifact_owner_id="rat_shadow_1",
    )
    resolved = resolve_shadow_audit_record(
        config,
        record.id,
        actor="founderos",
        note="Reviewed and accepted.",
    )

    open_records = list_shadow_audit_records(config, blocked_artifact_id="tout_shadow_1", status="open")
    all_records = list_shadow_audit_records(config, blocked_artifact_id="tout_shadow_1")

    assert resolved.status == "resolved"
    assert resolved.resolution["actor"] == "founderos"
    assert resolved.resolution["note"] == "Reviewed and accepted."
    assert open_records == []
    assert len(all_records) == 1
    assert all_records[0].blocked_artifact_owner_id == "rat_shadow_1"
