"""Git worktree helpers for parallel story execution."""

from __future__ import annotations

import subprocess
from pathlib import Path


def worktree_path(project_path: Path, story_id: int) -> Path:
    """Return the filesystem path for a story worktree."""
    return project_path.parent / f"{project_path.name}-story-{story_id}"


def create_worktree(project_path: Path, story_id: int) -> Path:
    """Create a git worktree for the given story and return its path."""
    wt_path = worktree_path(project_path, story_id)
    branch = f"story-{story_id}"

    if wt_path.exists():
        remove_worktree(project_path, wt_path)
    subprocess.run(
        ["git", "branch", "-D", branch],
        cwd=str(project_path),
        capture_output=True,
        text=True,
    )

    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_path)],
        cwd=str(project_path),
        capture_output=True,
        text=True,
        check=True,
    )

    return wt_path


def remove_worktree(project_path: Path, wt_path: Path) -> None:
    """Remove a git worktree."""
    subprocess.run(
        ["git", "worktree", "remove", str(wt_path), "--force"],
        cwd=str(project_path),
        capture_output=True,
        text=True,
    )


def merge_worktree(main_path: Path, worktree_path: Path, branch_name: str) -> bool:
    """Merge a worktree branch back into main and clean it up."""
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "commit", "-m", f"Autopilot story merge: {branch_name}"],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["git", "merge", branch_name, "--no-edit"],
        cwd=str(main_path),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return False

    remove_worktree(main_path, worktree_path)
    subprocess.run(
        ["git", "branch", "-d", branch_name],
        cwd=str(main_path),
        capture_output=True,
        text=True,
    )
    return True
