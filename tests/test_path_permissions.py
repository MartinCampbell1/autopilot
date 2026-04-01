"""Tests for runtime path validation helpers."""

from pathlib import Path

from autopilot.core.path_permissions import validate_gate_shell_command, validate_story_worktree_path


def test_validate_story_worktree_path_accepts_expected_layout(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"
    candidate = tmp_path / "demo-project-story-3"

    result = validate_story_worktree_path(project_path, candidate, expected_story_id=3)

    assert result.allowed is True
    assert result.normalized_path == candidate.resolve(strict=False)


def test_validate_story_worktree_path_rejects_shell_expansion_syntax(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"

    result = validate_story_worktree_path(project_path, "~/demo-project-story-3", expected_story_id=3)

    assert result.allowed is False
    assert "shell expansion" in result.reason.lower()


def test_validate_story_worktree_path_rejects_outside_parent_directory(tmp_path: Path) -> None:
    project_path = tmp_path / "demo-project"
    candidate = tmp_path / "nested" / "demo-project-story-3"

    result = validate_story_worktree_path(project_path, candidate, expected_story_id=3)

    assert result.allowed is False
    assert "parent directory" in result.reason.lower()


def test_validate_gate_shell_command_accepts_simple_gate_with_env_assignment() -> None:
    result = validate_gate_shell_command("PYTHONPATH=. python -m pytest -q")

    assert result.allowed is True
    assert result.argv == ("python", "-m", "pytest", "-q")
    assert result.env_updates == {"PYTHONPATH": "."}


def test_validate_gate_shell_command_rejects_shell_control_operator() -> None:
    result = validate_gate_shell_command("pytest && rm -rf dist")

    assert result.allowed is False
    assert "control operator" in result.reason.lower()


def test_validate_gate_shell_command_rejects_shell_expansion_in_path() -> None:
    result = validate_gate_shell_command("pytest ~/tests")

    assert result.allowed is False
    assert "shell expansion" in result.reason.lower()


def test_validate_gate_shell_command_rejects_destructive_find_operator() -> None:
    result = validate_gate_shell_command("find . -name '*.py' -delete")

    assert result.allowed is False
    assert "-delete" in result.reason


def test_validate_gate_shell_command_rejects_unc_network_path() -> None:
    result = validate_gate_shell_command(r"pytest //server/share/tests")

    assert result.allowed is False
    assert "unc" in result.reason.lower() or "network path" in result.reason.lower()


def test_validate_gate_shell_command_rejects_heredoc_syntax() -> None:
    result = validate_gate_shell_command("cat <<EOF")

    assert result.allowed is False
    assert "heredoc" in result.reason.lower()


def test_validate_gate_shell_command_rejects_dynamic_redirect_target() -> None:
    result = validate_gate_shell_command("pytest -q > $TMPDIR/out.txt")

    assert result.allowed is False
    assert "dynamic redirect" in result.reason.lower() or "shell expansion" in result.reason.lower()


def test_validate_gate_shell_command_rejects_suspicious_unicode_whitespace() -> None:
    result = validate_gate_shell_command("pytest\u00a0-q")

    assert result.allowed is False
    assert "unicode whitespace" in result.reason.lower()


def test_validate_gate_shell_command_accepts_git_diff_with_string_search_flag() -> None:
    result = validate_gate_shell_command("git diff -S needle -- README.md")

    assert result.allowed is True
    assert result.argv == ("git", "diff", "-S", "needle", "--", "README.md")


def test_validate_gate_shell_command_rejects_git_checkout_write_subcommand() -> None:
    result = validate_gate_shell_command("git checkout README.md")

    assert result.allowed is False
    assert "read-only allowlist" in result.reason.lower()


def test_validate_gate_shell_command_rejects_inline_python_eval() -> None:
    result = validate_gate_shell_command("python3 -c 'print(1)'")

    assert result.allowed is False
    assert "inline python" in result.reason.lower()


def test_validate_gate_shell_command_rejects_unknown_package_script() -> None:
    result = validate_gate_shell_command("npm run deploy")

    assert result.allowed is False
    assert "verification-safe allowlist" in result.reason.lower()


def test_validate_gate_shell_command_accepts_autodetected_gate_families() -> None:
    allowed_commands = [
        "pnpm run build",
        "ruff check autopilot tests",
        "cargo clippy --all-targets --all-features -- -D warnings",
        "go test ./...",
    ]

    for command in allowed_commands:
        result = validate_gate_shell_command(command)
        assert result.allowed is True, command
