"""Higher-level shell command safety checks built on top of parsed commands."""

from __future__ import annotations

from dataclasses import dataclass
import re

from autopilot.core.bash_ast import BashCommandAst, parse_bash_command
from autopilot.core.shell_validation import validate_shell_security


SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "ksh", "fish", "cmd", "powershell", "pwsh"}
DESTRUCTIVE_COMMANDS = {"rm", "rmdir", "unlink", "shred", "srm"}
DESTRUCTIVE_GIT_SUBCOMMANDS = {"clean", "reset"}
DESTRUCTIVE_FIND_OPERATORS = {"-delete", "-exec", "-execdir", "-ok", "-okdir"}
PROTECTED_INTERNAL_PATH_SEGMENTS = {".git", ".hg", ".svn"}


@dataclass(frozen=True)
class CommandSafetyViolation:
    """One fail-closed shell safety violation."""

    kind: str
    reason: str


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


def validate_command_safety(command: str, *, ast: BashCommandAst | None = None) -> list[CommandSafetyViolation]:
    """Return fail-closed shell safety violations for one command."""

    raw_value = str(command or "").strip()
    resolved_ast = ast or parse_bash_command(raw_value)
    violations = [
        CommandSafetyViolation(kind=item.kind, reason=item.reason)
        for item in validate_shell_security(raw_value)
    ]

    if resolved_ast.control_operators:
        operator = resolved_ast.control_operators[0]
        violations.append(
            CommandSafetyViolation(
                kind="control_operator",
                reason=f"Gate command uses unsupported shell control operator `{operator}`.",
            )
        )

    for key, value in resolved_ast.env_assignments.items():
        if SHELL_EXPANSION_PATTERN.search(value):
            violations.append(
                CommandSafetyViolation(
                    kind="env_assignment_expansion",
                    reason=f"Gate command uses shell expansion inside environment assignment `{key}`.",
                )
            )
            break

    if not resolved_ast.executable_argv:
        violations.append(
            CommandSafetyViolation(
                kind="empty_command",
                reason="Gate command only contained environment assignments.",
            )
        )
        return violations

    command_name = resolved_ast.command_name
    executable_args = list(resolved_ast.executable_argv[1:])

    if command_name in SHELL_INTERPRETERS and any(arg in {"-c", "-lc", "/c"} for arg in executable_args):
        violations.append(
            CommandSafetyViolation(
                kind="nested_shell",
                reason="Gate command cannot delegate execution to a nested shell interpreter.",
            )
        )

    if command_name in DESTRUCTIVE_COMMANDS:
        violations.append(
            CommandSafetyViolation(
                kind="destructive_command",
                reason=f"Gate command `{command_name}` is destructive and is not allowed as a verification gate.",
            )
        )

    if command_name == "git":
        subcommand = executable_args[0] if executable_args else ""
        if subcommand in DESTRUCTIVE_GIT_SUBCOMMANDS:
            violations.append(
                CommandSafetyViolation(
                    kind="destructive_git",
                    reason=f"Gate command `git {subcommand}` is destructive and is not allowed as a verification gate.",
                )
            )

    if command_name == "find" and any(token in DESTRUCTIVE_FIND_OPERATORS for token in executable_args):
        violations.append(
            CommandSafetyViolation(
                kind="destructive_find",
                reason="Gate command `find` cannot use mutating operators such as `-delete` or `-exec`.",
            )
        )

    for token in executable_args:
        if not _looks_like_path_token(token):
            continue
        if _touches_protected_internal_path(token):
            violations.append(
                CommandSafetyViolation(
                    kind="protected_internal_path",
                    reason="Gate command references protected VCS-internal paths and is not trusted.",
                )
            )
            break
        if SHELL_EXPANSION_PATTERN.search(token):
            violations.append(
                CommandSafetyViolation(
                    kind="path_expansion",
                    reason="Gate command contains path-like arguments with shell expansion syntax and is not trusted.",
                )
            )
            break

    return violations


__all__ = [
    "CommandSafetyViolation",
    "validate_command_safety",
]
