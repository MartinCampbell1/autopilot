"""Lightweight secret heuristics for safe-edit write paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


PLACEHOLDER_VALUE_PATTERN = re.compile(
    r"^(?:example|sample|placeholder|dummy|test|fake|your[_-]?|replace[_-]?me|changeme|todo|none|null)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SecretScanFinding:
    """One obvious secret match detected in text that is about to be written."""

    kind: str
    preview: str


class SecretScanError(RuntimeError):
    """Raised when obvious secret material is detected before a file write."""


SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("pem_private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox(?:a|b|p|r|s)-[A-Za-z0-9-]{10,}\b")),
)

GENERIC_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"""(?imx)
    \b
    (?:
        api[_-]?key |
        access[_-]?token |
        refresh[_-]?token |
        auth[_-]?token |
        secret |
        client[_-]?secret |
        password
    )
    \b
    \s*
    (?::|=)
    \s*
    ["']?
    (?P<value>[^\s"'`]+)
    """,
)


def _is_placeholder_value(value: str) -> bool:
    cleaned = value.strip().strip("\"'`").strip()
    if not cleaned:
        return True
    if cleaned.startswith(("<", "${", "$(", "REDACTED")):
        return True
    return bool(PLACEHOLDER_VALUE_PATTERN.match(cleaned))


def scan_text_for_secrets(text: str) -> list[SecretScanFinding]:
    """Return obvious secret findings for one text payload."""

    findings: list[SecretScanFinding] = []
    for kind, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            findings.append(SecretScanFinding(kind=kind, preview=match.group(0)[:80]))

    for match in GENERIC_SECRET_ASSIGNMENT_PATTERN.finditer(text):
        value = match.group("value")
        if len(value) < 8 or _is_placeholder_value(value):
            continue
        findings.append(
            SecretScanFinding(
                kind="generic_secret_assignment",
                preview=match.group(0)[:120],
            )
        )
    return findings


def assert_no_obvious_secrets(text: str, *, path: Path | None = None) -> None:
    """Raise when text appears to contain obvious key or credential material."""

    findings = scan_text_for_secrets(text)
    if not findings:
        return

    location = f" in {path}" if path is not None else ""
    finding = findings[0]
    raise SecretScanError(
        f"Secret scan blocked write{location}: detected {finding.kind} (`{finding.preview}`)."
    )
