"""Tests for lightweight shell-safety validation helpers."""

from autopilot.core.shell_validation import validate_shell_security


def test_validate_shell_security_rejects_unc_path() -> None:
    violations = validate_shell_security(r"pytest //server/share/tests")

    assert violations
    assert violations[0].kind == "unc_path"


def test_validate_shell_security_rejects_webdav_unc_path() -> None:
    violations = validate_shell_security(r"pytest //files.example.com@SSL/DavWWWRoot/shared/tests")

    assert any(violation.kind == "unc_path" for violation in violations)


def test_validate_shell_security_rejects_ipv6_unc_path() -> None:
    violations = validate_shell_security(r"pytest //[2001:db8::1]/share/tests")

    assert any(violation.kind == "unc_path" for violation in violations)


def test_validate_shell_security_rejects_dynamic_redirect() -> None:
    violations = validate_shell_security("pytest -q > $TMPDIR/out.txt")

    assert any(violation.kind == "dynamic_redirect" for violation in violations)


def test_validate_shell_security_rejects_heredoc() -> None:
    violations = validate_shell_security("cat <<EOF")

    assert any(violation.kind == "heredoc" for violation in violations)


def test_validate_shell_security_rejects_unicode_whitespace() -> None:
    violations = validate_shell_security("pytest\u00a0-q")

    assert any(violation.kind == "suspicious_whitespace" for violation in violations)


def test_validate_shell_security_rejects_newline_hash_injection() -> None:
    violations = validate_shell_security("printf foo\\\\\n# hidden")

    assert any(violation.kind == "newline_hash_injection" for violation in violations)


def test_validate_shell_security_rejects_jq_system_execution() -> None:
    violations = validate_shell_security("jq 'map(system(\"touch /tmp/pwned\"))' data.json")

    assert any(violation.kind == "jq_system" for violation in violations)
