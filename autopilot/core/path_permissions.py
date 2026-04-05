"""Conservative path validation helpers for runtime-managed paths and shell commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from autopilot.core.bash_ast import BashParseError, parse_bash_command
from autopilot.core.command_safety import validate_command_safety
from autopilot.core.read_only_validation import validate_gate_command_policy

WORKTREE_NAME_PATTERN = re.compile(r"^(?P<name>.+)-story-(?P<story_id>\d+)$")
SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")
PROTECTED_INTERNAL_PATH_SEGMENTS = {".git", ".hg", ".svn"}


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


def _touches_protected_internal_path(token: str) -> bool:
    normalized = token.replace("\\", "/")
    segments = [segment for segment in normalized.split("/") if segment not in {"", "."}]
    return any(segment in PROTECTED_INTERNAL_PATH_SEGMENTS for segment in segments)


def validate_gate_shell_command(command: str) -> ShellCommandValidationResult:
    """Validate one gate command before any shell expansion or mutation happens."""

    raw_value = str(command).strip()
    if not raw_value:
        return ShellCommandValidationResult(False, reason="Gate command is empty.")
    if any(marker in raw_value for marker in ("\r", "\n", "\x00")):
        return ShellCommandValidationResult(False, reason="Gate command contains newline or null-byte control characters.")

    try:
        ast = parse_bash_command(raw_value)
    except BashParseError as exc:
        return ShellCommandValidationResult(False, reason=str(exc))

    safety_violations = validate_command_safety(raw_value, ast=ast)
    if safety_violations:
        return ShellCommandValidationResult(False, reason=safety_violations[0].reason)

    policy_result = validate_gate_command_policy(ast.executable_argv)
    if not policy_result.allowed:
        return ShellCommandValidationResult(False, reason=policy_result.reason)

    for token in ast.executable_argv[1:]:
        if not _looks_like_path_token(token):
            continue
        if _touches_protected_internal_path(token):
            return ShellCommandValidationResult(
                False,
                reason="Gate command references protected VCS-internal paths and is not trusted.",
            )
        if SHELL_EXPANSION_PATTERN.search(token):
            return ShellCommandValidationResult(
                False,
                reason="Gate command contains path-like arguments with shell expansion syntax and is not trusted.",
            )

    return ShellCommandValidationResult(True, tuple(ast.executable_argv), env_updates=dict(ast.env_assignments))


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
