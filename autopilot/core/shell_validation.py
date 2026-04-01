"""Lightweight shell-safety checks for command strings."""

from __future__ import annotations

from pathlib import Path
import re
import shlex
from dataclasses import dataclass


SHELL_REDIRECT_TOKENS = {">", ">>", "<"}
SHELL_HEREDOC_TOKENS = {"<<", "<<<"}
SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")
SHELL_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
UNC_PATH_PATTERNS = (
    re.compile(
        r"(?ix)"
        r"(?:^|[\s'\"=])"
        r"(?:\\\\\\\\[^\\/\s]+[\\/][^\\/\s]+)"
    ),
    re.compile(
        r"(?ix)"
        r"(?:^|[\s'\"=])"
        r"(?://(?:[^/\s]+|\[[0-9a-f:]+\])/[^\s/]+)"
    ),
    re.compile(
        r"(?ix)"
        r"(?:^|[\s'\"=])"
        r"(?:\\\\\\\\[^\\/\s]+@SSL[\\/]+DavWWWRoot(?:[\\/][^\\/\s]+)*)"
    ),
    re.compile(
        r"(?ix)"
        r"(?:^|[\s'\"=])"
        r"(?://[^/\s]+@SSL/DavWWWRoot(?:/[^\s/]+)*)"
    ),
)
SUSPICIOUS_WHITESPACE_PATTERN = re.compile(
    r"[\u00a0\u1680\u180e\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]"
)
JQ_SYSTEM_PATTERN = re.compile(r"\bsystem\s*\(", re.IGNORECASE)


@dataclass(frozen=True)
class SecurityViolation:
    """One shell-safety violation detected before execution."""

    kind: str
    reason: str


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _contains_unc_or_network_path(value: str) -> bool:
    return any(pattern.search(value) for pattern in UNC_PATH_PATTERNS)


def _resolved_command_name(argv: list[str]) -> str:
    index = 0
    while index < len(argv) and SHELL_ASSIGNMENT_PATTERN.match(argv[index]):
        index += 1

    if index >= len(argv):
        return ""

    token = Path(argv[index]).name
    if token in {"env", "/usr/bin/env"}:
        index += 1
        while index < len(argv) and SHELL_ASSIGNMENT_PATTERN.match(argv[index]):
            index += 1
        if index >= len(argv):
            return ""
        token = Path(argv[index]).name
    return token


def _has_newline_hash_injection(value: str) -> bool:
    for index, char in enumerate(value):
        if char != "\n":
            continue
        comment = value[index + 1 :].lstrip(" \t")
        if not comment.startswith("#"):
            continue

        backslash_count = 0
        probe = index - 1
        while probe >= 0 and value[probe] == "\\":
            backslash_count += 1
            probe -= 1
        if backslash_count % 2 == 0:
            return True
    return False


def validate_shell_security(command: str) -> list[SecurityViolation]:
    """Return shell-safety violations for one command string."""

    raw_value = str(command)
    violations: list[SecurityViolation] = []

    if SUSPICIOUS_WHITESPACE_PATTERN.search(raw_value):
        violations.append(
            SecurityViolation(
                kind="suspicious_whitespace",
                reason="Gate command contains suspicious Unicode whitespace and is not trusted.",
            )
        )

    if _contains_unc_or_network_path(raw_value):
        violations.append(
            SecurityViolation(
                kind="unc_path",
                reason="Gate command contains a UNC or network path and is not trusted.",
            )
        )

    if _has_newline_hash_injection(raw_value):
        violations.append(
            SecurityViolation(
                kind="newline_hash_injection",
                reason="Gate command uses newline-comment injection syntax and is not trusted.",
            )
        )

    try:
        punctuated_tokens = _shell_tokens(raw_value)
        argv = shlex.split(raw_value, posix=True)
    except ValueError:
        return violations

    if _resolved_command_name(argv) == "jq" and any(JQ_SYSTEM_PATTERN.search(arg) for arg in argv[1:]):
        violations.append(
            SecurityViolation(
                kind="jq_system",
                reason="Gate command uses jq system() execution and is not trusted.",
            )
        )

    for index, token in enumerate(punctuated_tokens):
        if token in SHELL_HEREDOC_TOKENS:
            violations.append(
                SecurityViolation(
                    kind="heredoc",
                    reason="Gate command uses heredoc syntax and is not trusted.",
                )
            )
            continue
        if token not in SHELL_REDIRECT_TOKENS or index + 1 >= len(punctuated_tokens):
            continue
        target = punctuated_tokens[index + 1].strip()
        if SHELL_EXPANSION_PATTERN.search(target) or target.startswith(("*", "?", "{", "!", "~")):
            violations.append(
                SecurityViolation(
                    kind="dynamic_redirect",
                    reason="Gate command uses a dynamic redirect target and is not trusted.",
                )
            )
        elif _contains_unc_or_network_path(target):
            violations.append(
                SecurityViolation(
                    kind="redirect_unc_path",
                    reason="Gate command redirects to a UNC or network path and is not trusted.",
                )
            )

    return violations
