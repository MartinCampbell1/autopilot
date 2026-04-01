"""Conservative path validation helpers for runtime-managed paths and shell commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
import shlex

from autopilot.core.shell_validation import validate_shell_security

WORKTREE_NAME_PATTERN = re.compile(r"^(?P<name>.+)-story-(?P<story_id>\d+)$")
SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")
SHELL_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
SHELL_CONTROL_TOKENS = {"&&", "||", "|", ";", "&", ">", ">>", "<", "<<", "<<<"}
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "ksh", "fish", "cmd", "powershell", "pwsh"}
DESTRUCTIVE_COMMANDS = {"rm", "rmdir", "unlink", "shred", "srm"}
DESTRUCTIVE_GIT_SUBCOMMANDS = {"clean", "reset"}
DESTRUCTIVE_FIND_OPERATORS = {"-delete", "-exec", "-execdir", "-ok", "-okdir"}


@dataclass(frozen=True)
class PathValidationResult:
    """Result of validating one runtime-managed filesystem path."""

    allowed: bool
    normalized_path: Path
    reason: str = ""


@dataclass(frozen=True)
class ShellCommandValidationResult:
    """Result of validating one shell-facing command string before execution."""

    allowed: bool
    argv: tuple[str, ...] = ()
    env_updates: dict[str, str] | None = None
    reason: str = ""


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def _extract_leading_env_assignments(argv: list[str]) -> tuple[dict[str, str], list[str]] | None:
    env_updates: dict[str, str] = {}
    index = 0
    while index < len(argv) and SHELL_ASSIGNMENT_PATTERN.match(argv[index]):
        key, value = argv[index].split("=", 1)
        if SHELL_EXPANSION_PATTERN.search(value):
            return None
        env_updates[key] = value
        index += 1
    return env_updates, argv[index:]


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


def _looks_like_path_token(token: str) -> bool:
    return (
        token in {".", ".."}
        or token.startswith(("./", "../", "/", "~"))
        or "/" in token
        or token.endswith(
            (
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".json",
                ".md",
                ".txt",
                ".toml",
                ".yaml",
                ".yml",
                ".ini",
                ".cfg",
                ".sh",
            )
        )
    )


def validate_gate_shell_command(command: str) -> ShellCommandValidationResult:
    """Validate one gate command before any shell expansion or mutation happens."""

    raw_value = str(command).strip()
    if not raw_value:
        return ShellCommandValidationResult(False, reason="Gate command is empty.")
    if any(marker in raw_value for marker in ("\r", "\n", "\x00")):
        return ShellCommandValidationResult(False, reason="Gate command contains newline or null-byte control characters.")
    shell_security_violations = validate_shell_security(raw_value)
    if shell_security_violations:
        return ShellCommandValidationResult(False, reason=shell_security_violations[0].reason)

    try:
        punctuated_tokens = _shell_tokens(raw_value)
        argv = shlex.split(raw_value, posix=True)
    except ValueError as exc:
        return ShellCommandValidationResult(False, reason=f"Gate command could not be parsed safely: {exc}")

    if not argv:
        return ShellCommandValidationResult(False, reason="Gate command is empty after parsing.")

    for token in punctuated_tokens:
        if token in SHELL_CONTROL_TOKENS:
            return ShellCommandValidationResult(
                False,
                reason=f"Gate command uses unsupported shell control operator `{token}`.",
            )

    if any(marker in raw_value for marker in ("$(", "${", "`")):
        return ShellCommandValidationResult(
            False,
            reason="Gate command uses shell expansion syntax and is not trusted.",
        )

    assignment_split = _extract_leading_env_assignments(argv)
    if assignment_split is None:
        return ShellCommandValidationResult(
            False,
            reason="Gate command uses shell expansion syntax inside an environment assignment.",
        )
    env_updates, executable_argv = assignment_split
    if not executable_argv:
        return ShellCommandValidationResult(False, reason="Gate command only contained environment assignments.")

    command_name = _resolved_command_name(argv)
    if command_name in SHELL_INTERPRETERS and any(arg in {"-c", "-lc", "/c"} for arg in executable_argv[1:]):
        return ShellCommandValidationResult(
            False,
            reason="Gate command cannot delegate execution to a nested shell interpreter.",
        )
    if command_name in DESTRUCTIVE_COMMANDS:
        return ShellCommandValidationResult(
            False,
            reason=f"Gate command `{command_name}` is destructive and is not allowed as a verification gate.",
        )
    if command_name == "git":
        subcommand = executable_argv[1] if len(executable_argv) > 1 else ""
        if subcommand in DESTRUCTIVE_GIT_SUBCOMMANDS:
            return ShellCommandValidationResult(
                False,
                reason=f"Gate command `git {subcommand}` is destructive and is not allowed as a verification gate.",
            )
    if command_name == "find" and any(token in DESTRUCTIVE_FIND_OPERATORS for token in executable_argv[1:]):
        return ShellCommandValidationResult(
            False,
            reason="Gate command `find` cannot use mutating operators such as `-delete` or `-exec`.",
        )

    for token in executable_argv[1:]:
        if not _looks_like_path_token(token):
            continue
        if SHELL_EXPANSION_PATTERN.search(token):
            return ShellCommandValidationResult(
                False,
                reason="Gate command contains path-like arguments with shell expansion syntax and is not trusted.",
            )

    return ShellCommandValidationResult(True, tuple(executable_argv), env_updates=env_updates)


def validate_story_worktree_path(
    project_path: Path,
    candidate_path: Path | str,
    *,
    expected_story_id: int | None = None,
) -> PathValidationResult:
    """Validate one story worktree path against the owning project path."""

    raw_value = str(candidate_path).strip()
    if not raw_value:
        return PathValidationResult(False, Path(project_path).expanduser().resolve(), "Worktree path is empty.")
    if SHELL_EXPANSION_PATTERN.search(raw_value):
        return PathValidationResult(
            False,
            Path(raw_value),
            "Worktree path contains shell expansion syntax and is not trusted.",
        )

    resolved_project = Path(project_path).expanduser().resolve()
    resolved_candidate = Path(raw_value).expanduser().resolve(strict=False)
    if resolved_candidate == resolved_project:
        return PathValidationResult(False, resolved_candidate, "Worktree path cannot equal the primary project path.")
    if resolved_candidate.parent != resolved_project.parent:
        return PathValidationResult(
            False,
            resolved_candidate,
            "Worktree path must stay in the primary project parent directory.",
        )

    match = WORKTREE_NAME_PATTERN.match(resolved_candidate.name)
    if not match or match.group("name") != resolved_project.name:
        return PathValidationResult(
            False,
            resolved_candidate,
            "Worktree path must match the `<project>-story-<id>` naming contract.",
        )

    if expected_story_id is not None and int(match.group("story_id")) != int(expected_story_id):
        return PathValidationResult(
            False,
            resolved_candidate,
            f"Worktree path story id does not match expected story #{expected_story_id}.",
        )

    return PathValidationResult(True, resolved_candidate)


def assert_story_worktree_path(
    project_path: Path,
    candidate_path: Path | str,
    *,
    expected_story_id: int | None = None,
) -> Path:
    """Return the normalized worktree path or raise when unsafe."""

    result = validate_story_worktree_path(project_path, candidate_path, expected_story_id=expected_story_id)
    if not result.allowed:
        raise ValueError(result.reason)
    return result.normalized_path
