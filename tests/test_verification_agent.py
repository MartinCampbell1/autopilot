"""Tests for verifier-output validation helpers."""

from autopilot.core.models import VerificationCheck
from autopilot.core.verification_agent import (
    NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK,
    NON_ACTIONABLE_VERDICT_FEEDBACK,
    extract_strict_verdict,
    require_adversarial_probe,
    validate_verifier_output,
)


def test_extract_strict_verdict_accepts_single_terminal_verdict() -> None:
    verdict, error = extract_strict_verdict("### Check: sample\nVERDICT: PASS\n")

    assert verdict == "PASS"
    assert error == ""


def test_extract_strict_verdict_rejects_non_terminal_verdict() -> None:
    verdict, error = extract_strict_verdict("VERDICT: PASS\nextra line\n")

    assert verdict == ""
    assert error == NON_ACTIONABLE_VERDICT_FEEDBACK


def test_require_adversarial_probe_matches_explicit_check_title() -> None:
    assert require_adversarial_probe([VerificationCheck(name="adversarial probe - invalid token")]) is True


def test_validate_verifier_output_rejects_pass_without_adversarial_probe() -> None:
    verdict, error = validate_verifier_output(
        """### Check: unit tests
**Command run:**
  pytest -q
**Output observed:**
  3 passed in 0.12s
**Result: PASS**

VERDICT: PASS
""",
        [VerificationCheck(name="unit tests", command="pytest -q", output="3 passed in 0.12s", status="PASS")],
    )

    assert verdict == "PASS"
    assert error == NON_ACTIONABLE_ADVERSARIAL_PROBE_FEEDBACK
