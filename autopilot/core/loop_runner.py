"""Loop runner that wraps Ralph for one worker iteration."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from autopilot.core.models import is_rate_limited

IGNORED_PREFIXES = (".agents/", ".ralph/")


def check_ralph_installed() -> bool:
    """Return whether the Ralph CLI is available."""
    return shutil.which("ralph") is not None


def init_ralph_project(project_path: Path) -> bool:
    """Run `ralph install` in the project directory."""
    agents_dir = project_path / ".agents" / "ralph"
    try:
        result = subprocess.run(
            ["ralph", "install", "--force"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return True
        return agents_dir.exists()
    except Exception:
        return agents_dir.exists()


def run_ralph_iteration(
    project_path: Path,
    env: dict[str, str],
    timeout: int = 1800,
    prd_path: str | None = None,
) -> tuple[bool, str, bool]:
    """Run one Ralph build iteration and report success/output/rate-limit state."""
    cmd = ["ralph", "build", "1"]
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


def _run_capture(project_path: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip()
    except Exception:
        return 1, ""


def _git_has_revision(project_path: Path, revision: str) -> bool:
    code, _ = _run_capture(project_path, ["git", "rev-parse", "--verify", revision], timeout=10)
    return code == 0


def _pathspec() -> list[str]:
    return ["--", ".", ":(exclude).agents", ":(exclude).ralph"]


def _committed_diff(project_path: Path) -> str:
    if not _git_has_revision(project_path, "HEAD"):
        return ""

    if _git_has_revision(project_path, "HEAD~1"):
        _, output = _run_capture(
            project_path,
            ["git", "diff", "HEAD~1", "HEAD", *_pathspec()],
        )
        return output

    _, output = _run_capture(
        project_path,
        ["git", "show", "--format=", "HEAD", *_pathspec()],
    )
    return output


def _working_tree_diff(project_path: Path) -> str:
    chunks: list[str] = []

    _, staged = _run_capture(project_path, ["git", "diff", "--cached", *_pathspec()])
    if staged:
        chunks.append(staged)

    _, unstaged = _run_capture(project_path, ["git", "diff", *_pathspec()])
    if unstaged:
        chunks.append(unstaged)

    _, untracked_raw = _run_capture(
        project_path,
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    for relative_path in untracked_raw.splitlines():
        relative_path = relative_path.strip()
        if not relative_path or relative_path.startswith(IGNORED_PREFIXES):
            continue
        file_path = project_path / relative_path
        if not file_path.is_file():
            continue
        _, file_diff = _run_capture(
            project_path,
            ["git", "diff", "--no-index", "--", "/dev/null", relative_path],
        )
        if file_diff:
            chunks.append(file_diff)

    return "\n".join(chunk for chunk in chunks if chunk).strip()


def check_git_diff_empty(project_path: Path) -> bool:
    """Return whether the latest relevant workspace changes are empty."""
    return get_last_commit_diff(project_path).strip() == ""


def get_last_commit_diff(project_path: Path) -> str:
    """Return the latest relevant changes for critic review.

    Prefer the current working tree if Ralph left changes uncommitted.
    Fall back to the latest commit diff when the tree is clean.
    """
    worktree_diff = _working_tree_diff(project_path)
    if worktree_diff:
        return worktree_diff
    return _committed_diff(project_path)
