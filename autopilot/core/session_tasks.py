"""Runtime task-close helpers for honest completion enforcement."""

from __future__ import annotations

from collections.abc import Sequence

from autopilot.core.models import CriticResult, ReviewPhaseResult, VerificationCheck
from autopilot.core.verification_agent import require_adversarial_probe

VERIFICATION_NUDGE_FEEDBACK = (
    "Verification evidence is missing for task closure. Run concrete verification commands against the changed "
    "behavior, include observed output, include at least one adversarial probe, and end with "
    "`VERDICT: PASS|FAIL|PARTIAL`."
)


def _has_command_backed_evidence(checks: Sequence[VerificationCheck]) -> bool:
    return any(str(check.command).strip() and str(check.output).strip() for check in checks)


def _result_is_verification_backed(verdict: str, checks: Sequence[VerificationCheck]) -> bool:
    return (
        str(verdict).strip().upper() == "PASS"
        and _has_command_backed_evidence(checks)
        and require_adversarial_probe(checks)
    )


def verification_nudge_needed(result: CriticResult) -> bool:
    """Return whether an apparently approved task still lacks verification evidence."""

    if not bool(result.approved):
        return False

    review_results = list(getattr(result, "review_results", []) or [])
    if review_results:
        approved_reviews = [review for review in review_results if bool(getattr(review, "approved", False))]
        if not approved_reviews:
            return True
        return any(
            not _result_is_verification_backed(
                getattr(review, "verdict", ""),
                list(getattr(review, "verification_checks", []) or []),
            )
            for review in approved_reviews
        )

    return not _result_is_verification_backed(
        getattr(result, "verdict", ""),
        list(getattr(result, "verification_checks", []) or []),
    )
