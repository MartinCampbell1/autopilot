"""Tests for fail-closed shell command parsing helpers."""

from autopilot.core.bash_ast import BashParseError, parse_bash_command


def test_parse_bash_command_extracts_env_assignments_and_env_wrapper() -> None:
    ast = parse_bash_command("PYTHONPATH=. env FOO=1 python -m pytest -q")

    assert ast.env_assignments == {"PYTHONPATH": "."}
    assert ast.executable_argv == ("python", "-m", "pytest", "-q")
    assert ast.command_name == "python"


def test_parse_bash_command_collects_control_operators_and_redirects() -> None:
    ast = parse_bash_command("pytest -q > out.txt && echo done")

    assert ast.control_operators == ("&&",)
    assert ast.redirects[0].operator == ">"
    assert ast.redirects[0].target == "out.txt"


def test_parse_bash_command_rejects_empty_input() -> None:
    try:
        parse_bash_command("   ")
    except BashParseError as exc:
        assert "empty" in str(exc).lower()
        return
    raise AssertionError("Expected empty command to raise.")
