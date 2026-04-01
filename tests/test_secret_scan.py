"""Tests for secret-scan heuristics used by safe-edit writes."""

from pathlib import Path

from autopilot.core.secret_scan import SecretScanError, assert_no_obvious_secrets, scan_text_for_secrets


def test_scan_text_for_secrets_detects_obvious_key_material() -> None:
    findings = scan_text_for_secrets('OPENAI_API_KEY="sk-test1234567890abcdefghijk"')

    assert findings
    assert findings[0].kind in {"openai_key", "generic_secret_assignment"}


def test_scan_text_for_secrets_ignores_placeholder_values() -> None:
    findings = scan_text_for_secrets('API_KEY="changeme"\nCLIENT_SECRET="<your-secret>"\n')

    assert findings == []


def test_assert_no_obvious_secrets_raises_with_path_context(tmp_path: Path) -> None:
    path = tmp_path / "config.env"

    try:
        assert_no_obvious_secrets('GITHUB_TOKEN="ghp_1234567890abcdefghijKLMN"', path=path)
    except SecretScanError as exc:
        assert "config.env" in str(exc)
        assert "github_token" in str(exc)
        return
    raise AssertionError("Expected secret scan rejection.")
