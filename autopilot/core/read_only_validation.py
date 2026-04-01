"""Conservative verification-safe command matrix for gate shell commands."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


SHELL_ASSIGNMENT_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
SAFE_PACKAGE_SCRIPT_PATTERN = re.compile(r"^(build|test|lint|check|typecheck|verify|smoke)(:[A-Za-z0-9._-]+)?$")
PACKAGE_MANAGERS = {"npm", "pnpm", "yarn", "bun"}
PYTHON_INTERPRETERS = {"python", "python3"}
GO_SUBCOMMANDS = {"build", "test", "vet"}
CARGO_SUBCOMMANDS = {"build", "test", "check", "clippy"}
READ_ONLY_GIT_SUBCOMMANDS = {"diff", "status", "show", "log", "rev-parse", "ls-files"}
FORBIDDEN_GIT_FLAGS = {"--exec-path", "--output", "--ext-diff"}


@dataclass(frozen=True)
class GateCommandPolicyResult:
    """Classification result for one parsed gate command."""

    allowed: bool
    classification: str = ""
    reason: str = ""


def _basename(token: str) -> str:
    return Path(token).name


def _deny(reason: str, classification: str = "unsafe") -> GateCommandPolicyResult:
    return GateCommandPolicyResult(False, classification=classification, reason=reason)


def _allow(classification: str) -> GateCommandPolicyResult:
    return GateCommandPolicyResult(True, classification=classification)


def _strip_env_wrapper(argv: Sequence[str]) -> list[str]:
    tokens = list(argv)
    if not tokens or _basename(tokens[0]) not in {"env"}:
        return tokens

    index = 1
    while index < len(tokens) and SHELL_ASSIGNMENT_PATTERN.match(tokens[index]):
        index += 1
    return tokens[index:]


def _validate_package_manager(command_name: str, args: Sequence[str]) -> GateCommandPolicyResult:
    if not args:
        return _deny(f"Gate command `{command_name}` must run a specific verification script.", "too_complex")

    subcommand = args[0]
    if subcommand == "test":
        return _allow("verification_safe")
    if subcommand != "run" or len(args) < 2:
        return _deny(
            f"Gate command `{command_name}` only allows `test` or `run <verification-script>`.",
            "too_complex",
        )

    script_name = args[1]
    if not SAFE_PACKAGE_SCRIPT_PATTERN.match(script_name):
        return _deny(
            f"Gate script `{script_name}` is not in the verification-safe allowlist.",
            "unsafe",
        )
    return _allow("verification_safe")


def _validate_python(command_name: str, args: Sequence[str]) -> GateCommandPolicyResult:
    if len(args) >= 2 and args[0] == "-m" and args[1] == "pytest":
        return _allow("verification_safe")
    return _deny(
        f"Gate command `{command_name}` only allows `-m pytest` execution, not arbitrary inline Python.",
        "unsafe",
    )


def _validate_ruff(args: Sequence[str]) -> GateCommandPolicyResult:
    if args and args[0] == "check":
        return _allow("verification_safe")
    return _deny("Gate command `ruff` only allows the read-only `check` subcommand.", "unsafe")


def _validate_cargo(args: Sequence[str]) -> GateCommandPolicyResult:
    if not args:
        return _deny("Gate command `cargo` must specify a verification subcommand.", "too_complex")
    if args[0] in CARGO_SUBCOMMANDS:
        return _allow("verification_safe")
    return _deny(f"Gate command `cargo {args[0]}` is not in the verification-safe allowlist.", "unsafe")


def _validate_go(args: Sequence[str]) -> GateCommandPolicyResult:
    if not args:
        return _deny("Gate command `go` must specify a verification subcommand.", "too_complex")
    if args[0] in GO_SUBCOMMANDS:
        return _allow("verification_safe")
    return _deny(f"Gate command `go {args[0]}` is not in the verification-safe allowlist.", "unsafe")


def _validate_git(args: Sequence[str]) -> GateCommandPolicyResult:
    if not args:
        return _deny("Gate command `git` must specify a read-only subcommand.", "too_complex")

    subcommand = args[0]
    if subcommand not in READ_ONLY_GIT_SUBCOMMANDS:
        return _deny(f"Gate command `git {subcommand}` is not in the read-only allowlist.", "unsafe")

    for token in args[1:]:
        if token in FORBIDDEN_GIT_FLAGS or any(token.startswith(f"{flag}=") for flag in FORBIDDEN_GIT_FLAGS):
            return _deny(f"Gate command `git {subcommand}` uses the unsafe flag `{token}`.", "unsafe")

    return _allow("read_only")


def validate_gate_command_policy(argv: Sequence[str]) -> GateCommandPolicyResult:
    """Classify one parsed gate command as verification-safe, read-only, or denied."""

    normalized_argv = _strip_env_wrapper(argv)
    if not normalized_argv:
        return _deny("Gate command is empty after removing `env` wrapper.", "too_complex")

    command_name = _basename(normalized_argv[0])
    args = normalized_argv[1:]

    if command_name in PACKAGE_MANAGERS:
        return _validate_package_manager(command_name, args)
    if command_name in PYTHON_INTERPRETERS:
        return _validate_python(command_name, args)
    if command_name == "pytest":
        return _allow("verification_safe")
    if command_name == "ruff":
        return _validate_ruff(args)
    if command_name == "cargo":
        return _validate_cargo(args)
    if command_name == "go":
        return _validate_go(args)
    if command_name == "git":
        return _validate_git(args)
    if command_name in {"grep", "diff", "find"}:
        return _allow("read_only")

    return _deny(
        f"Gate command `{command_name}` is not in the verification-safe allowlist.",
        "too_complex",
    )
