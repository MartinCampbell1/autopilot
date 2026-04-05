"""Swappable judge packs for structured review and verifier outcomes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from autopilot.core.models import CriticResult, ReviewPhaseResult, VerificationCheck


@dataclass(frozen=True)
class JudgeContext:
    """Normalized input for one judge-pack evaluation."""

    subject: str
    approved: bool
    verdict: str
    feedback: str = ""
    raw_output: str = ""
    review_phases: list[str] = field(default_factory=list)
    review_results: list[ReviewPhaseResult] = field(default_factory=list)
    verification_checks: list[VerificationCheck] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    gates: list[dict[str, Any]] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class JudgePackResult:
    """One judge-pack decision."""

    pack_id: str
    verdict: str
    approved: bool
    summary: str
    findings: list[str] = field(default_factory=list)


JudgeEvaluator = Callable[[JudgeContext], JudgePackResult]


@dataclass(frozen=True)
class JudgePack:
    """Named judge pack with pluggable evaluation logic."""

    pack_id: str
    label: str
    description: str
    evaluator: JudgeEvaluator

    def evaluate(self, context: JudgeContext) -> JudgePackResult:
        return self.evaluator(context)


def _iter_verification_checks(context: JudgeContext) -> list[VerificationCheck]:
    checks = list(context.verification_checks or [])
    for review in context.review_results or []:
        checks.extend(list(review.verification_checks or []))
    return checks


def _local_check_rows(context: JudgeContext) -> list[dict[str, Any]]:
    rows = list(context.checks or [])
    rows.extend(list(context.gates or []))
    return rows


def _has_command_backed_evidence(context: JudgeContext) -> bool:
    if bool((context.summary or {}).get("command_backed_evidence")):
        return True

    for check in _iter_verification_checks(context):
        if str(check.command or "").strip() and str(check.output or "").strip():
            return True
    for item in _local_check_rows(context):
        command = str(item.get("command") or item.get("cmd") or "").strip()
        output = str(item.get("output") or "").strip()
        if command and output:
            return True
    return False


def _has_adversarial_probe(context: JudgeContext) -> bool:
    probe_status = str((context.summary or {}).get("adversarial_probe_status") or "").strip().upper()
    if probe_status == "PASS":
        return True

    for check in _iter_verification_checks(context):
        if "adversarial probe" in str(check.name or "").lower() and str(check.status or "").upper() == "PASS":
            return True
    for item in context.checks or []:
        if (
            "adversarial probe" in str(item.get("name") or "").lower()
            and str(item.get("status") or "").upper() == "PASS"
        ):
            return True
    return False


def _has_test_evidence(context: JudgeContext) -> bool:
    haystacks = []
    for check in _iter_verification_checks(context):
        haystacks.append(f"{check.name}\n{check.command}\n{check.output}")
    for item in _local_check_rows(context):
        haystacks.append(
            "\n".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("command") or item.get("cmd") or ""),
                    str(item.get("output") or ""),
                ]
            )
        )
    lowered = "\n".join(haystacks).lower()
    return any(token in lowered for token in ("pytest", "test", "vitest", "jest", "cargo test", "go test"))


def _blocking_findings(context: JudgeContext) -> list[str]:
    blocking: list[str] = []
    for finding in context.findings or []:
        if str(finding.get("severity") or "").lower() != "error":
            continue
        message = str(finding.get("message") or "").strip()
        if message:
            blocking.append(message)
    if blocking:
        return blocking
    for review in context.review_results or []:
        if review.approved:
            continue
        feedback = str(review.feedback or "").strip()
        if feedback:
            blocking.append(f"[{review.phase}] {feedback}")
    if blocking:
        return blocking
    feedback = str(context.feedback or "").strip()
    return [feedback] if feedback and not context.approved else []


def _preserve_existing_failure(context: JudgeContext, pack_id: str, fallback_summary: str) -> JudgePackResult:
    verdict = str(context.verdict or "").upper()
    findings = _blocking_findings(context)
    if verdict == "FAIL":
        return JudgePackResult(
            pack_id=pack_id,
            verdict="FAIL",
            approved=False,
            summary=findings[0] if findings else fallback_summary,
            findings=findings,
        )
    if verdict == "PARTIAL":
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PARTIAL",
            approved=False,
            summary=findings[0] if findings else fallback_summary,
            findings=findings,
        )
    return JudgePackResult(
        pack_id=pack_id,
        verdict="PARTIAL",
        approved=False,
        summary=fallback_summary,
        findings=findings,
    )


def _evaluate_execution_claims(context: JudgeContext) -> JudgePackResult:
    pack_id = "execution_claims"
    if not _has_command_backed_evidence(context):
        return JudgePackResult(
            pack_id=pack_id,
            verdict="FAIL" if context.approved else "PARTIAL",
            approved=False,
            summary="Execution-claims judge rejected the review because command-backed evidence is missing.",
            findings=["missing_command_backed_evidence"],
        )
    if not _has_adversarial_probe(context):
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PARTIAL",
            approved=False,
            summary="Execution-claims judge kept the review partial because no passing adversarial probe was recorded.",
            findings=["missing_adversarial_probe"],
        )
    if context.approved:
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PASS",
            approved=True,
            summary="Execution-claims judge confirmed evidence-backed PASS with an adversarial probe.",
        )
    return _preserve_existing_failure(
        context,
        pack_id=pack_id,
        fallback_summary="Execution-claims judge kept the existing non-pass review state.",
    )


def _evaluate_code_pack(context: JudgeContext) -> JudgePackResult:
    pack_id = "code"
    if context.approved and not _has_command_backed_evidence(context):
        return JudgePackResult(
            pack_id=pack_id,
            verdict="FAIL",
            approved=False,
            summary="Code judge rejected PASS without command-backed evidence.",
            findings=["missing_command_backed_evidence"],
        )
    if context.approved:
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PASS",
            approved=True,
            summary="Code judge confirmed the review outcome.",
        )
    return _preserve_existing_failure(
        context,
        pack_id=pack_id,
        fallback_summary="Code judge kept the current non-pass review state.",
    )


def _evaluate_docs_pack(context: JudgeContext) -> JudgePackResult:
    pack_id = "docs"
    if context.approved and not _has_command_backed_evidence(context):
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PARTIAL",
            approved=False,
            summary="Docs judge kept the review partial because documentation claims are not backed by a reproducible command trail.",
            findings=["missing_command_backed_evidence"],
        )
    if context.approved:
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PASS",
            approved=True,
            summary="Docs judge confirmed the review outcome.",
        )
    return _preserve_existing_failure(
        context,
        pack_id=pack_id,
        fallback_summary="Docs judge kept the current non-pass review state.",
    )


def _evaluate_tests_pack(context: JudgeContext) -> JudgePackResult:
    pack_id = "tests"
    if context.approved and not _has_test_evidence(context):
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PARTIAL",
            approved=False,
            summary="Tests judge kept the review partial because no concrete test evidence was found.",
            findings=["missing_test_evidence"],
        )
    if context.approved:
        return JudgePackResult(
            pack_id=pack_id,
            verdict="PASS",
            approved=True,
            summary="Tests judge confirmed the review outcome.",
        )
    return _preserve_existing_failure(
        context,
        pack_id=pack_id,
        fallback_summary="Tests judge kept the current non-pass review state.",
    )


BUILT_IN_JUDGE_PACKS: dict[str, JudgePack] = {
    "code": JudgePack(
        pack_id="code",
        label="Code",
        description="Generic code review judge with evidence-backed PASS enforcement.",
        evaluator=_evaluate_code_pack,
    ),
    "docs": JudgePack(
        pack_id="docs",
        label="Docs",
        description="Documentation-focused judge pack.",
        evaluator=_evaluate_docs_pack,
    ),
    "tests": JudgePack(
        pack_id="tests",
        label="Tests",
        description="Verification-quality judge pack focused on reproducible test evidence.",
        evaluator=_evaluate_tests_pack,
    ),
    "execution_claims": JudgePack(
        pack_id="execution_claims",
        label="Execution Claims",
        description="Strict execution-claims judge requiring command evidence and an adversarial probe.",
        evaluator=_evaluate_execution_claims,
    ),
}


def available_judge_packs(registry: Mapping[str, JudgePack] | None = None) -> list[dict[str, str]]:
    resolved = dict(BUILT_IN_JUDGE_PACKS)
    if registry:
        resolved.update(registry)
    return [
        {
            "pack_id": pack.pack_id,
            "label": pack.label,
            "description": pack.description,
        }
        for pack in resolved.values()
    ]


def evaluate_judge_pack(
    pack_id: str,
    context: JudgeContext,
    *,
    registry: Mapping[str, JudgePack] | None = None,
) -> JudgePackResult:
    resolved = dict(BUILT_IN_JUDGE_PACKS)
    if registry:
        resolved.update(registry)
    pack = resolved.get(str(pack_id or "").strip())
    if pack is None:
        available = ", ".join(sorted(resolved))
        raise ValueError(f"Unknown judge pack `{pack_id}`. Available packs: {available}")
    return pack.evaluate(context)


def build_critic_judge_context(
    result: CriticResult,
    *,
    subject: str = "critic_review",
    metadata: Mapping[str, Any] | None = None,
) -> JudgeContext:
    return JudgeContext(
        subject=subject,
        approved=bool(result.approved),
        verdict=str(result.verdict or "").upper(),
        feedback=str(result.feedback or ""),
        raw_output=str(result.raw_output or ""),
        review_phases=list(result.review_phases or []),
        review_results=list(result.review_results or []),
        verification_checks=list(result.verification_checks or []),
        metadata=dict(metadata or {}),
    )


def build_local_review_judge_context(
    payload: Mapping[str, Any],
    *,
    subject: str = "local_review",
    metadata: Mapping[str, Any] | None = None,
) -> JudgeContext:
    return JudgeContext(
        subject=subject,
        approved=str(payload.get("verdict") or "").upper() == "PASS",
        verdict=str(payload.get("verdict") or "").upper(),
        findings=[dict(item) for item in list(payload.get("findings") or [])],
        gates=[dict(item) for item in list(payload.get("gates") or [])],
        checks=[dict(item) for item in list(payload.get("checks") or [])],
        summary=dict(payload.get("summary") or {}),
        metadata={**dict(metadata or {}), "project_path": str(payload.get("project_path") or "")},
    )


def judge_result_to_dict(result: JudgePackResult) -> dict[str, Any]:
    return {
        "pack_id": result.pack_id,
        "verdict": result.verdict,
        "approved": bool(result.approved),
        "summary": result.summary,
        "findings": list(result.findings),
    }
