"""Tests for verification-safe gate command classification."""

from autopilot.core.read_only_validation import validate_gate_command_policy


def test_validate_gate_command_policy_accepts_git_diff_string_search() -> None:
    result = validate_gate_command_policy(["git", "diff", "-S", "needle", "--", "README.md"])

    assert result.allowed is True
    assert result.classification == "read_only"


def test_validate_gate_command_policy_accepts_git_diff_regex_and_order_file_flags() -> None:
    commands = [
        ["git", "diff", "-G", "needle", "--", "README.md"],
        ["git", "diff", "-O", "orderfile.txt", "--", "README.md"],
    ]

    for argv in commands:
        result = validate_gate_command_policy(argv)
        assert result.allowed is True, argv


def test_validate_gate_command_policy_accepts_autodetected_gate_families() -> None:
    commands = [
        ["pnpm", "run", "build"],
        ["pytest", "-q"],
        ["python3", "-m", "pytest", "tests/test_models.py"],
        ["ruff", "check", "autopilot", "tests"],
        ["cargo", "clippy", "--all-targets", "--all-features", "--", "-D", "warnings"],
        ["go", "test", "./..."],
    ]

    for argv in commands:
        result = validate_gate_command_policy(argv)
        assert result.allowed is True, argv


def test_validate_gate_command_policy_rejects_mutating_ruff_fix_flags() -> None:
    result = validate_gate_command_policy(["ruff", "check", "--fix", "."])

    assert result.allowed is False
    assert "mutating fix flags" in result.reason.lower()


def test_validate_gate_command_policy_rejects_unknown_package_script() -> None:
    result = validate_gate_command_policy(["npm", "run", "deploy"])

    assert result.allowed is False
    assert "verification-safe allowlist" in result.reason.lower()


def test_validate_gate_command_policy_rejects_inline_python_module() -> None:
    result = validate_gate_command_policy(["python3", "-m", "pip", "install", "ruff"])

    assert result.allowed is False
    assert "-m pip" in result.reason.lower()


def test_validate_gate_command_policy_rejects_git_write_subcommand() -> None:
    result = validate_gate_command_policy(["git", "checkout", "README.md"])

    assert result.allowed is False
    assert "read-only allowlist" in result.reason.lower()


def test_validate_gate_command_policy_rejects_git_diff_string_flags_without_value() -> None:
    result = validate_gate_command_policy(["git", "diff", "-S", "--", "README.md"])

    assert result.allowed is False
    assert "explicit string argument" in result.reason.lower()


def test_validate_gate_command_policy_rejects_non_verification_toolchain_commands() -> None:
    commands = [
        ["cargo", "install", "ripgrep"],
        ["go", "env", "-w", "GOBIN=/tmp/bin"],
    ]

    for argv in commands:
        result = validate_gate_command_policy(argv)
        assert result.allowed is False, argv
        assert "allowlist" in result.reason.lower() or "verification-safe" in result.reason.lower()
