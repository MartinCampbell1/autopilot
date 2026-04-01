"""Git worktree helpers for parallel story execution."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def worktree_path(project_path: Path, story_id: int) -> Path:
    """Return the filesystem path for a story worktree."""
    return project_path.parent / f"{project_path.name}-story-{story_id}"


def _run_git(cwd: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
    )


def _worktree_has_changes(worktree_path: Path) -> bool:
    result = _run_git(worktree_path, ["status", "--porcelain"])
    return result.returncode == 0 and bool(result.stdout.strip())


def create_worktree(project_path: Path, story_id: int, *, branch_name: str | None = None) -> Path:
    """Create a git worktree for the given story and return its path."""
    wt_path = worktree_path(project_path, story_id)
    branch = str(branch_name or f"story-{story_id}").strip() or f"story-{story_id}"

    _run_git(project_path, ["worktree", "prune"])
    if wt_path.exists():
        remove_worktree(project_path, wt_path)
    _run_git(project_path, ["branch", "-D", branch])

    _run_git(project_path, ["worktree", "add", "--force", "-b", branch, str(wt_path), "HEAD"], check=True)

    return wt_path


def remove_worktree(project_path: Path, wt_path: Path) -> None:
    """Remove a git worktree."""
    _run_git(project_path, ["worktree", "remove", str(wt_path), "--force"])
    _run_git(project_path, ["worktree", "prune"])
    if wt_path.exists():
        shutil.rmtree(wt_path, ignore_errors=True)


def merge_worktree(main_path: Path, worktree_path: Path, branch_name: str) -> bool:
    """Merge a worktree branch back into main and clean it up."""
    if _worktree_has_changes(worktree_path):
        _run_git(worktree_path, ["add", "-A"])
        commit_result = _run_git(worktree_path, ["commit", "-m", f"Autopilot story merge: {branch_name}"])
        if commit_result.returncode != 0:
            return False
    result = _run_git(main_path, ["merge", branch_name, "--no-edit"])

    if result.returncode != 0:
        return False

    remove_worktree(main_path, worktree_path)
    _run_git(main_path, ["branch", "-d", branch_name])
    return True
