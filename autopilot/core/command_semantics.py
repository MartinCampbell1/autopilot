"""Semantic classification for shell exit codes."""

from __future__ import annotations

import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class CommandExitSemantics:
    """Normalized meaning of a shell command exit code."""

    command_name: str
    returncode: int | None
    status: str
    treat_as_error: bool
    summary: str = ""


def _normalize_argv(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, str):
        try:
            return shlex.split(command)
        except ValueError:
            return [command.strip()] if command.strip() else []
    return [str(part).strip() for part in command if str(part).strip()]


def _command_name(argv: list[str]) -> str:
    if not argv:
        return ""

    wrappers = {"sudo", "command", "builtin", "noglob", "nice", "time"}
    index = 0
    while index < len(argv):
        token = argv[index]
        if "=" in token and token.split("=", 1)[0] and not token.startswith((">", "<")):
            index += 1
            continue
        if token in wrappers:
            index += 1
            continue
        if token in {"env", "/usr/bin/env"}:
            index += 1
            while index < len(argv) and "=" in argv[index] and argv[index].split("=", 1)[0]:
                index += 1
            continue

        name = Path(token).name
        if name in {"bash", "sh", "zsh"} and index + 2 < len(argv) and argv[index + 1] in {"-c", "-lc"}:
            return _command_name(_normalize_argv(argv[index + 2]))
        if name == "git" and index + 1 < len(argv) and argv[index + 1] == "diff":
            return "git diff"
        return name
    return ""


def classify_command_exit(command: str | Sequence[str], returncode: int | None) -> CommandExitSemantics:
    """Classify whether a non-zero exit code is semantic or an actual shell error."""

    argv = _normalize_argv(command)
    name = _command_name(argv)

    if returncode is None:
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="error",
            treat_as_error=True,
            summary="Command exited without a return code.",
        )

    if returncode == 0:
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="success",
            treat_as_error=False,
            summary="Command completed successfully.",
        )

    if returncode < 0:
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="signal",
            treat_as_error=True,
            summary=f"Command terminated by signal {-returncode}.",
        )

    lowered = name.lower()
    if lowered in {"grep", "egrep", "fgrep", "rg", "ripgrep"}:
        if returncode == 1:
            return CommandExitSemantics(
                command_name=name,
                returncode=returncode,
                status="no_match",
                treat_as_error=False,
                summary=f"{name} returned 1 because no matches were found.",
            )
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="error",
            treat_as_error=True,
            summary=f"{name} returned {returncode}, which indicates a real error.",
        )

    if lowered in {"diff", "cmp"}:
        if returncode == 1:
            return CommandExitSemantics(
                command_name=name,
                returncode=returncode,
                status="difference",
                treat_as_error=False,
                summary=f"{name} returned 1 because differences were found.",
            )
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="error",
            treat_as_error=True,
            summary=f"{name} returned {returncode}, which indicates a real error.",
        )

    if lowered == "git diff" and returncode == 1:
        return CommandExitSemantics(
            command_name="git diff",
            returncode=returncode,
            status="difference",
            treat_as_error=False,
            summary="git diff returned 1 because changes were detected.",
        )

    if lowered == "find" and returncode == 1:
        return CommandExitSemantics(
            command_name=name,
            returncode=returncode,
            status="partial",
            treat_as_error=False,
            summary="find returned 1 after a partial traversal or permission-limited walk.",
        )

    return CommandExitSemantics(
        command_name=name,
        returncode=returncode,
        status="error",
        treat_as_error=True,
        summary=f"Command returned non-zero exit code {returncode}.",
    )
