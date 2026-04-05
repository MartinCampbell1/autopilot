"""Tests for higher-level command safety validation."""

from autopilot.core.bash_ast import parse_bash_command
from autopilot.core.command_safety import validate_command_safety


def test_validate_command_safety_rejects_nested_shell() -> None:
    ast = parse_bash_command("bash -lc 'pytest -q'")

    violations = validate_command_safety("bash -lc 'pytest -q'", ast=ast)

    assert any(item.kind == "nested_shell" for item in violations)


def test_validate_command_safety_rejects_env_assignment_expansion() -> None:
    ast = parse_bash_command("FOO=$BAR pytest -q")

    violations = validate_command_safety("FOO=$BAR pytest -q", ast=ast)

    assert any(item.kind == "env_assignment_expansion" for item in violations)


def test_validate_command_safety_rejects_protected_internal_path() -> None:
    ast = parse_bash_command("rg token .git/config")

    violations = validate_command_safety("rg token .git/config", ast=ast)

    assert any(item.kind == "protected_internal_path" for item in violations)
