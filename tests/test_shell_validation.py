"""Tests for lightweight shell-safety validation helpers."""

from autopilot.core.shell_validation import validate_shell_security


def test_validate_shell_security_rejects_unc_path() -> None:
    violations = validate_shell_security(r"pytest //server/share/tests")

    assert violations
    assert violations[0].kind == "unc_path"


def test_validate_shell_security_rejects_dynamic_redirect() -> None:
    violations = validate_shell_security("pytest -q > $TMPDIR/out.txt")

    assert any(violation.kind == "dynamic_redirect" for violation in violations)


def test_validate_shell_security_rejects_heredoc() -> None:
    violations = validate_shell_security("cat <<EOF")

    assert any(violation.kind == "heredoc" for violation in violations)


def test_validate_shell_security_rejects_unicode_whitespace() -> None:
    violations = validate_shell_security("pytest\u00a0-q")

    assert any(violation.kind == "suspicious_whitespace" for violation in violations)
