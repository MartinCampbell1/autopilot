"""Fail-closed parsing helpers for simple shell command validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex


SHELL_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
SHELL_CONTROL_OPERATORS = {"&&", "||", "|", ";", "&"}
SHELL_REDIRECT_OPERATORS = {">", ">>", "<"}
SHELL_HEREDOC_OPERATORS = {"<<", "<<<"}


class BashParseError(ValueError):
    """Raised when a shell command cannot be parsed safely."""


@dataclass(frozen=True)
class BashRedirect:
    """One parsed shell redirect."""

    operator: str
    target: str = ""


@dataclass(frozen=True)
class BashCommandAst:
    """Normalized view of one shell command."""

    raw: str
    punctuated_tokens: tuple[str, ...]
    argv: tuple[str, ...]
    env_assignments: dict[str, str]
    executable_argv: tuple[str, ...]
    command_name: str
    control_operators: tuple[str, ...]
    redirects: tuple[BashRedirect, ...]


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _extract_env_assignments(argv: list[str]) -> tuple[dict[str, str], list[str]]:
    env_assignments: dict[str, str] = {}
    index = 0
    while index < len(argv) and SHELL_ASSIGNMENT_PATTERN.match(argv[index]):
        key, value = argv[index].split("=", 1)
        env_assignments[key] = value
        index += 1
    return env_assignments, argv[index:]


def _strip_env_wrapper(argv: list[str]) -> list[str]:
    env_assignments, remainder = _extract_env_assignments(argv)
    if not remainder:
        return []

    if Path(remainder[0]).name not in {"env", "/usr/bin/env"}:
        return [*env_assignments.keys()] and remainder or remainder

    _, remainder = _extract_env_assignments(remainder[1:])
    return remainder


def _resolved_command_name(executable_argv: list[str]) -> str:
    if not executable_argv:
        return ""
    return Path(executable_argv[0]).name


def _collect_redirects(tokens: list[str]) -> tuple[tuple[str, ...], tuple[BashRedirect, ...]]:
    control_operators: list[str] = []
    redirects: list[BashRedirect] = []

    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in SHELL_CONTROL_OPERATORS:
            control_operators.append(token)
            index += 1
            continue
        if token in SHELL_REDIRECT_OPERATORS or token in SHELL_HEREDOC_OPERATORS:
            target = tokens[index + 1] if index + 1 < len(tokens) else ""
            redirects.append(BashRedirect(operator=token, target=target))
            index += 2
            continue
        index += 1

    return tuple(control_operators), tuple(redirects)


def parse_bash_command(command: str) -> BashCommandAst:
    """Parse one shell command into a normalized, validation-friendly shape."""

    raw_value = str(command or "").strip()
    if not raw_value:
        raise BashParseError("Shell command is empty.")

    try:
        punctuated_tokens = _shell_tokens(raw_value)
        argv = shlex.split(raw_value, posix=True)
    except ValueError as exc:
        raise BashParseError(f"Shell command could not be parsed safely: {exc}") from exc

    if not argv:
        raise BashParseError("Shell command is empty after parsing.")

    env_assignments, _ = _extract_env_assignments(argv)
    executable_argv = _strip_env_wrapper(argv)
    control_operators, redirects = _collect_redirects(punctuated_tokens)
    command_name = _resolved_command_name(executable_argv)

    return BashCommandAst(
        raw=raw_value,
        punctuated_tokens=tuple(punctuated_tokens),
        argv=tuple(argv),
        env_assignments=env_assignments,
        executable_argv=tuple(executable_argv),
        command_name=command_name,
        control_operators=control_operators,
        redirects=redirects,
    )


__all__ = [
    "BashCommandAst",
    "BashParseError",
    "BashRedirect",
    "parse_bash_command",
]
