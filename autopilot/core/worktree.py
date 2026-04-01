"""Git worktree helpers for parallel story execution."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from autopilot.core.path_permissions import assert_story_worktree_path

DEFAULT_WORKTREE_STALE_AFTER_SEC = 3600
WORKTREE_METADATA_FILENAME = ".autopilot-worktree.json"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _pid_is_running(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


class WorktreeMetadata(BaseModel):
    """Persisted metadata for one isolated worktree."""

    project_path: str
    story_id: int
    branch_name: str
    created_at: str
    runtime_pid: int | None = None


def worktree_path(project_path: Path, story_id: int) -> Path:
    """Return the filesystem path for a story worktree."""
    return project_path.parent / f"{project_path.name}-story-{story_id}"


def worktree_metadata_path(wt_path: Path) -> Path:
    """Return metadata path for one worktree."""

    return wt_path / WORKTREE_METADATA_FILENAME


def read_worktree_metadata(wt_path: Path) -> WorktreeMetadata | None:
    """Load metadata for one worktree if available."""

    path = worktree_metadata_path(wt_path)
    if not path.exists():
        return None
    try:
        return WorktreeMetadata.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return None


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


def _branch_exists(project_path: Path, branch_name: str) -> bool:
    result = _run_git(project_path, ["branch", "--list", branch_name])
    return result.returncode == 0 and bool(str(result.stdout or "").strip())


def _neutralize_worktree_hooks(wt_path: Path) -> None:
    _run_git(wt_path, ["config", "--local", "core.hooksPath", os.devnull], check=True)


def _write_worktree_metadata(project_path: Path, wt_path: Path, *, story_id: int, branch_name: str) -> None:
    _atomic_write_json(
        worktree_metadata_path(wt_path),
        WorktreeMetadata(
            project_path=str(project_path),
            story_id=story_id,
            branch_name=str(branch_name or "").strip(),
            created_at=_utcnow_iso(),
            runtime_pid=os.getpid(),
        ).model_dump(),
    )


def gc_stale_worktrees(
    project_path: Path,
    *,
    stale_after_sec: int = DEFAULT_WORKTREE_STALE_AFTER_SEC,
) -> list[Path]:
    """Remove stale sibling story worktrees based on metadata age and pid liveness."""

    removed: list[Path] = []
    parent = project_path.parent
    prefix = f"{project_path.name}-story-"
    for candidate in sorted(parent.iterdir()):
        if not candidate.is_dir() or not candidate.name.startswith(prefix):
            continue
        try:
            safe_candidate = assert_story_worktree_path(project_path, candidate)
        except ValueError:
            continue
        metadata = read_worktree_metadata(safe_candidate)
        if metadata is None:
            continue
        created_at = _parse_iso(metadata.created_at)
        if created_at is None:
            continue
        age_sec = max(0, int((datetime.now(timezone.utc) - created_at).total_seconds()))
        if age_sec < stale_after_sec or _pid_is_running(metadata.runtime_pid):
            continue
        remove_worktree(project_path, safe_candidate)
        removed.append(safe_candidate)
    return removed


def create_worktree(project_path: Path, story_id: int, *, branch_name: str | None = None) -> Path:
    """Create a git worktree for the given story and return its path."""
    wt_path = worktree_path(project_path, story_id)
    wt_path = assert_story_worktree_path(project_path, wt_path, expected_story_id=story_id)
    branch = str(branch_name or f"story-{story_id}").strip() or f"story-{story_id}"

    gc_stale_worktrees(project_path)
    _run_git(project_path, ["worktree", "prune"])
    if wt_path.exists():
        remove_worktree(project_path, wt_path)
    if _branch_exists(project_path, branch):
        _run_git(project_path, ["branch", "-D", branch])

    _run_git(project_path, ["worktree", "add", "--force", "-b", branch, str(wt_path), "HEAD"], check=True)
    wt_path.mkdir(parents=True, exist_ok=True)
    _neutralize_worktree_hooks(wt_path)
    _write_worktree_metadata(project_path, wt_path, story_id=story_id, branch_name=branch)
    return wt_path


def remove_worktree(project_path: Path, wt_path: Path) -> None:
    """Remove a git worktree."""
    wt_path = assert_story_worktree_path(project_path, wt_path)
    _run_git(project_path, ["worktree", "remove", str(wt_path), "--force"])
    _run_git(project_path, ["worktree", "prune"])
    if wt_path.exists():
        shutil.rmtree(wt_path, ignore_errors=True)


def merge_worktree(main_path: Path, worktree_path: Path, branch_name: str) -> bool:
    """Merge a worktree branch back into main and clean it up."""
    worktree_path = assert_story_worktree_path(main_path, worktree_path)
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
