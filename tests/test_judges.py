"""Tests for swappable judge packs."""

from autopilot.core.evals.judges import JudgePack, JudgePackResult, available_judge_packs, evaluate_judge_pack


def test_available_judge_packs_includes_execution_claims() -> None:
    packs = available_judge_packs()

    assert any(pack["pack_id"] == "execution_claims" for pack in packs)


def test_evaluate_judge_pack_allows_custom_registry_override() -> None:
    custom = JudgePack(
        pack_id="custom",
        label="Custom",
        description="Custom override for testing.",
        evaluator=lambda context: JudgePackResult(
            pack_id="custom",
            verdict="FAIL",
            approved=False,
            summary="Custom registry override fired.",
            findings=["custom_override"],
        ),
    )

    result = evaluate_judge_pack(
        "custom",
        context=type(
            "JudgeContextStub",
            (),
            {
                "subject": "stub",
                "approved": True,
                "verdict": "PASS",
                "feedback": "",
                "raw_output": "",
                "review_phases": [],
                "review_results": [],
                "verification_checks": [],
                "findings": [],
                "gates": [],
                "checks": [],
                "summary": {},
                "metadata": {},
            },
        )(),
        registry={"custom": custom},
    )

    assert result.pack_id == "custom"
    assert result.verdict == "FAIL"
    assert result.findings == ["custom_override"]
