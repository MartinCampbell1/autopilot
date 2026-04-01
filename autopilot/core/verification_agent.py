"""Verifier-output validation helpers for critic evidence enforcement."""

from __future__ import annotations

import re
from collections.abc import Sequence

from autopilot.core.models import VerificationCheck

VERDICT_PATTERN = re.compile(r"^\s*VERDICT:\s*(PASS|FAIL|PARTIAL)\s*$", re.IGNORECASE | re.MULTILINE)
ADVERSARIAL_PROBE_PATTERN = re.compile(r"\badversarial probe\b", re.IGNORECASE)

NON_ACTIONABLE_VERIFICATION_FEEDBACK = "Critic returned VERDICT PASS without command-backed evidence."
NON_ACTIONABLE_VERDICT_FEEDBACK = (
    "Critic returned invalid VERDICT formatting; expected exactly one terminal `VERDICT: PASS|FAIL|PARTIAL` line."
)
NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK = (
    "Critic returned VERDICT PASS without an explicit adversarial probe check."
)


def extract_strict_verdict(raw_output: str) -> tuple[str, str]:
    """Return the single terminal verdict or an actionable formatting error."""

    matches = [match.group(1).upper() for match in VERDICT_PATTERN.finditer(raw_output)]
    if not matches:
        return "", ""
    if len(matches) != 1:
        return "", NON_ACTIONABLE_VERDICT_FEEDBACK

    final_nonempty_line = next((line.strip() for line in reversed(raw_output.splitlines()) if line.strip()), "")
    if not VERDICT_PATTERN.fullmatch(final_nonempty_line):
        return "", NON_ACTIONABLE_VERDICT_FEEDBACK
    return matches[0], ""


def require_adversarial_probe(checks: Sequence[VerificationCheck], raw_output: str = "") -> bool:
    """Return whether verifier output includes an explicitly labeled adversarial probe."""

    if any(ADVERSARIAL_PROBE_PATTERN.search(str(check.name or "")) for check in checks):
        return True
    return bool(ADVERSARIAL_PROBE_PATTERN.search(raw_output))


def validate_verifier_output(raw_output: str, checks: Sequence[VerificationCheck]) -> tuple[str, str]:
    """Validate strict verifier output rules before the critic trusts a verdict."""

    verdict, verdict_error = extract_strict_verdict(raw_output)
    if verdict_error:
        return verdict, verdict_error
    if not verdict:
        return "", ""

    if verdict == "PASS":
        has_command_backed_evidence = any(check.command.strip() and check.output.strip() for check in checks)
        if not has_command_backed_evidence:
            return verdict, NON_ACTIONABLE_VERIFICATION_FEEDBACK
        if not require_adversarial_probe(checks, raw_output):
            return verdict, NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK
    return verdict, ""
