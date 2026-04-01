"""Tests for shell command exit semantics."""

from autopilot.core.command_semantics import classify_command_exit


def test_classify_grep_exit_code_one_as_no_match() -> None:
    result = classify_command_exit("grep needle README.md", 1)

    assert result.status == "no_match"
    assert result.treat_as_error is False


def test_classify_diff_exit_code_one_as_difference() -> None:
    result = classify_command_exit(["diff", "before.txt", "after.txt"], 1)

    assert result.status == "difference"
    assert result.treat_as_error is False


def test_classify_find_exit_code_one_as_partial() -> None:
    result = classify_command_exit("find . -name '*.py'", 1)

    assert result.status == "partial"
    assert result.treat_as_error is False


def test_classify_unknown_non_zero_as_error() -> None:
    result = classify_command_exit("npm test", 1)

    assert result.status == "error"
    assert result.treat_as_error is True
