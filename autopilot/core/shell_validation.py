"""Lightweight shell-safety checks for command strings."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass


SHELL_REDIRECT_TOKENS = {">", ">>", "<"}
SHELL_HEREDOC_TOKENS = {"<<", "<<<"}
SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")
UNC_PATH_PATTERN = re.compile(
    r"(?ix)"
    r"(?:^|[\s'\"=])"
    r"("
    r"(?:\\\\\\\\[^\\/\s]+[\\/][^\\/\s]+)"
    r"|"
    r"(?://[^/\s]+/[^/\s]+)"
    r")"
)
SUSPICIOUS_WHITESPACE_PATTERN = re.compile(
    r"[\u00a0\u1680\u180e\u2000-\u200f\u2028\u2029\u202f\u205f\u3000]"
)


@dataclass(frozen=True)
class SecurityViolation:
    """One shell-safety violation detected before execution."""

    kind: str
    reason: str


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


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

    if UNC_PATH_PATTERN.search(raw_value):
        violations.append(
            SecurityViolation(
                kind="unc_path",
                reason="Gate command contains a UNC or network path and is not trusted.",
            )
        )

    try:
        punctuated_tokens = _shell_tokens(raw_value)
    except ValueError:
        return violations

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
        elif UNC_PATH_PATTERN.search(target):
            violations.append(
                SecurityViolation(
                    kind="redirect_unc_path",
                    reason="Gate command redirects to a UNC or network path and is not trusted.",
                )
            )

    return violations
