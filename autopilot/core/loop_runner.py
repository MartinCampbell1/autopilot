"""Loop runner that wraps Ralph for one worker iteration."""

from __future__ import annotations

import subprocess
from pathlib import Path

from autopilot.core.models import is_rate_limited


def check_ralph_installed() -> bool:
    """Return whether the Ralph CLI is available."""
    try:
        result = subprocess.run(["ralph", "--version"], capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def init_ralph_project(project_path: Path) -> bool:
    """Run `ralph install` in the project directory."""
    try:
        result = subprocess.run(
            ["ralph", "install"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def run_ralph_iteration(
    project_path: Path,
    env: dict[str, str],
    timeout: int = 1800,
    prd_path: str | None = None,
) -> tuple[bool, str, bool]:
    """Run one Ralph build iteration and report success/output/rate-limit state."""
    cmd = ["ralph", "build", "1", "--no-commit"]
    if prd_path:
        cmd.extend(["--prd", prd_path])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = f"{result.stdout}\n{result.stderr}".strip()
        success = result.returncode == 0
        rate_limited = is_rate_limited(output)
        return success, output, rate_limited
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s", False
    except Exception as exc:
        return False, str(exc), False


def read_progress(project_path: Path) -> str:
    """Read `.ralph/progress.md` if it exists."""
    progress_file = project_path / ".ralph" / "progress.md"
    if progress_file.exists():
        return progress_file.read_text()
    return ""


def write_critic_feedback(project_path: Path, feedback: str) -> None:
    """Write critic feedback to `.ralph/critic-feedback.md`."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    feedback_file = ralph_dir / "critic-feedback.md"
    feedback_file.write_text(feedback)


def append_guardrail(project_path: Path, guardrail: str) -> None:
    """Append one guardrail entry to `.ralph/guardrails.md`."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    guardrails_file = ralph_dir / "guardrails.md"
    existing = guardrails_file.read_text() if guardrails_file.exists() else ""
    guardrails_file.write_text(f"{existing}\n- {guardrail}\n")


def check_git_diff_empty(project_path: Path) -> bool:
    """Return whether the previous commit produced an empty diff stat."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1", "--stat"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == ""
    except Exception:
        return False


def get_last_commit_diff(project_path: Path) -> str:
    """Return the diff of the last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return ""
