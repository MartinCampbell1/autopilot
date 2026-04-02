"""Runtime and context diagnostics for doctor flows."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.github_repo_setup import GITHUB_BOOTSTRAP_WORKFLOW_RELPATH
from autopilot.core.project_store import load_project_state, load_projects_registry
from autopilot.core.repo_registry import (
    build_repo_registry_key,
    find_canonical_git_root,
    get_github_repo,
    get_git_remote_url,
    get_known_paths_for_repo,
)
from autopilot.core.shipping import ShippingError, get_current_branch, get_default_branch
from autopilot.core.worktree import resolve_story_worktree_owner

EVENT_LOG_WARN_BYTES = 10 * 1024 * 1024


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _ps_output(*args: str) -> str:
    try:
        result = subprocess.run(
            ["ps", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def _is_pid_running(pid: int | None) -> bool:
    if not pid:
        return False
    stat = _ps_output("-o", "stat=", "-p", str(pid))
    if not stat:
        return False
    return "Z" not in stat.upper()


def _diagnostic(
    *,
    code: str,
    severity: str,
    scope: str,
    message: str,
    fix: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "scope": scope,
        "message": message,
        "fix": fix,
        "metadata": dict(metadata or {}),
    }


def _git_output(cwd: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, PermissionError, subprocess.TimeoutExpired, NotADirectoryError):
        return ""
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def _git_ref_exists(cwd: Path, ref_name: str) -> bool:
    return bool(_git_output(cwd, "rev-parse", "--verify", ref_name))


def _resolve_base_ref(cwd: Path, base_branch: str) -> str:
    remote_ref = f"refs/remotes/origin/{base_branch}"
    local_ref = f"refs/heads/{base_branch}"
    if _git_ref_exists(cwd, remote_ref):
        return f"origin/{base_branch}"
    if _git_ref_exists(cwd, local_ref):
        return base_branch
    return ""


def _working_tree_dirty(cwd: Path) -> bool:
    return bool(_git_output(cwd, "status", "--porcelain"))


def _changed_file_count(cwd: Path, base_ref: str) -> int | None:
    if not base_ref:
        return None
    output = _git_output(cwd, "diff", "--name-only", f"{base_ref}...HEAD", "--")
    if output == "":
        return 0
    return len([line for line in output.splitlines() if line.strip()])


def build_runtime_diagnostics(
    *,
    config: AutopilotConfig,
    config_path: Path,
    project_path: Path,
) -> dict[str, Any]:
    """Build concrete runtime/context diagnostics for one doctor invocation."""

    normalized_project_path = _normalize_path(project_path)
    diagnostics: list[dict[str, Any]] = []
    if not config_path.exists():
        diagnostics.append(
            _diagnostic(
                code="config_missing",
                severity="warning",
                scope="config",
                message="Autopilot config file does not exist yet.",
                fix="Create ~/.autopilot/config.yaml or run an Autopilot command that writes initial config.",
            )
        )

    worktree_owner = resolve_story_worktree_owner(normalized_project_path)
    current_checkout_root = worktree_owner[1] if worktree_owner is not None else (find_canonical_git_root(normalized_project_path) or normalized_project_path)
    effective_project_root = worktree_owner[0] if worktree_owner is not None else normalized_project_path
    current_repo_key = build_repo_registry_key(effective_project_root)
    same_repo_paths = sorted(get_known_paths_for_repo(config, repo_key=current_repo_key)) if current_repo_key else []
    related_projects: list[dict[str, Any]] = []
    for project in load_projects_registry(config, include_archived=True):
        project_repo_key = build_repo_registry_key(Path(project["path"]))
        if current_repo_key and current_repo_key == project_repo_key:
            related_projects.append(project)

    if (
        effective_project_root.exists()
        and (effective_project_root / ".git").exists()
        and not str(get_git_remote_url(effective_project_root) or "").strip()
    ):
        diagnostics.append(
            _diagnostic(
                code="repo_identity_missing",
                severity="warning",
                scope="project",
                message="Git repository has no stable repo identity yet.",
                fix="Add an origin remote so resume and ship flows can map this repo across clones and worktrees.",
                metadata={"path": str(effective_project_root)},
            )
        )

    if len(same_repo_paths) > 1:
        diagnostics.append(
            _diagnostic(
                code="same_repo_multiple_paths",
                severity="info",
                scope="resume",
                message=f"Same repo has been observed in {len(same_repo_paths)} local paths.",
                fix="Use `autopilot resume` or `autopilot run --project-id ...` to disambiguate the intended clone/worktree.",
                metadata={"paths": same_repo_paths},
            )
        )

    current_branch = ""
    default_branch = ""
    changed_file_count: int | None = None
    github_cli_available = bool(shutil.which("gh"))
    checkout_repo_root = find_canonical_git_root(current_checkout_root)
    if checkout_repo_root is not None:
        github_repo = str(get_github_repo(checkout_repo_root) or "").strip()
        if not github_cli_available:
            diagnostics.append(
                _diagnostic(
                    code="github_cli_missing",
                    severity="warning",
                    scope="ship",
                    message="GitHub CLI `gh` is not installed, so local ship cannot create pull requests.",
                    fix="Install GitHub CLI and run `gh auth login` before relying on `autopilot ship`.",
                    metadata={"path": str(checkout_repo_root)},
                )
            )
        if github_repo and not (checkout_repo_root / GITHUB_BOOTSTRAP_WORKFLOW_RELPATH).exists():
            diagnostics.append(
                _diagnostic(
                    code="github_actions_workflow_missing",
                    severity="info",
                    scope="ship",
                    message="Managed GitHub Actions bootstrap workflow is not installed yet.",
                    fix="Run `autopilot github` from a feature branch to install the managed GitHub Actions workflow.",
                    metadata={
                        "path": str(checkout_repo_root),
                        "workflow_relpath": GITHUB_BOOTSTRAP_WORKFLOW_RELPATH,
                        "github_repo": github_repo,
                    },
                )
            )

        try:
            current_branch = get_current_branch(checkout_repo_root)
        except ShippingError as exc:
            diagnostics.append(
                _diagnostic(
                    code="checkout_detached",
                    severity="warning",
                    scope="ship",
                    message=str(exc),
                    fix="Check out a named branch before using review and ship flows.",
                    metadata={"path": str(checkout_repo_root)},
                )
            )
        try:
            default_branch = get_default_branch(checkout_repo_root)
        except ShippingError as exc:
            diagnostics.append(
                _diagnostic(
                    code="default_branch_unknown",
                    severity="warning",
                    scope="ship",
                    message=str(exc),
                    fix="Fetch the repo's default branch or pass an explicit base branch to review/ship commands.",
                    metadata={"path": str(checkout_repo_root)},
                )
            )

        if current_branch and default_branch and current_branch == default_branch:
            diagnostics.append(
                _diagnostic(
                    code="protected_branch_checked_out",
                    severity="warning",
                    scope="ship",
                    message=f"Current checkout is on the default branch `{current_branch}`.",
                    fix="Create or switch to a feature branch before using `autopilot ship`.",
                    metadata={"branch": current_branch, "base_branch": default_branch},
                )
            )

        if _working_tree_dirty(checkout_repo_root):
            diagnostics.append(
                _diagnostic(
                    code="working_tree_dirty",
                    severity="info",
                    scope="review",
                    message="Working tree has uncommitted changes.",
                    fix="Commit or stash local edits before treating review or ship results as durable handoff state.",
                    metadata={"path": str(checkout_repo_root)},
                )
            )

        base_ref = _resolve_base_ref(checkout_repo_root, default_branch) if default_branch else ""
        changed_file_count = _changed_file_count(checkout_repo_root, base_ref)
        if changed_file_count == 0 and current_branch and default_branch and current_branch != default_branch:
            diagnostics.append(
                _diagnostic(
                    code="no_diff_against_base",
                    severity="info",
                    scope="ship",
                    message=f"Current branch `{current_branch}` has no changes against `{default_branch}`.",
                    fix="Make or commit changes before expecting review or ship to produce a meaningful PR.",
                    metadata={"branch": current_branch, "base_branch": default_branch},
                )
            )

    if worktree_owner is not None:
        diagnostics.append(
            _diagnostic(
                code="story_worktree_detected",
                severity="info",
                scope="resume",
                message="Current path is inside an Autopilot story worktree.",
                fix="Run resume or run commands from this checkout safely; Autopilot can map it back to the owning project.",
                metadata={
                    "owner_project_path": str(worktree_owner[0]),
                    "worktree_root": str(worktree_owner[1]),
                },
            )
        )

    for project in related_projects:
        state = load_project_state(config, str(project["id"]))
        pid = state.get("pid")
        if str(state.get("status") or "") != "running":
            continue
        if _is_pid_running(pid if isinstance(pid, int) else None):
            continue
        diagnostics.append(
            _diagnostic(
                code="stale_runtime_pid",
                severity="warning",
                scope="runtime",
                message=f"Registered project '{project['name']}' still says running, but its PID is no longer alive.",
                fix="Resume or pause this project to reconcile state before relying on its runtime status.",
                metadata={
                    "project_id": str(project["id"]),
                    "project_path": str(project["path"]),
                    "pid": pid,
                    "runtime_session_id": str(state.get("runtime_session_id") or ""),
                },
            )
        )

    if config.events_log_path.exists():
        try:
            events_log_size = config.events_log_path.stat().st_size
        except OSError:
            events_log_size = 0
        if events_log_size >= EVENT_LOG_WARN_BYTES:
            diagnostics.append(
                _diagnostic(
                    code="events_log_large",
                    severity="info",
                    scope="context",
                    message="Structured event log has grown large enough to be worth pruning.",
                    fix="Archive or rotate ~/.autopilot/events/events.jsonl if live diagnostics or local disk usage start to degrade.",
                    metadata={"bytes": events_log_size},
                )
            )

    return {
        "project_path": str(normalized_project_path),
        "current_checkout_root": str(current_checkout_root),
        "effective_project_root": str(effective_project_root),
        "current_repo_key": current_repo_key,
        "current_branch": current_branch,
        "default_branch": default_branch,
        "github_cli_available": github_cli_available,
        "changed_file_count": changed_file_count,
        "same_repo_known_paths": same_repo_paths,
        "related_project_ids": [str(project["id"]) for project in related_projects],
        "diagnostics": diagnostics,
        "summary": {
            "error_count": sum(1 for item in diagnostics if item["severity"] == "error"),
            "warning_count": sum(1 for item in diagnostics if item["severity"] == "warning"),
            "info_count": sum(1 for item in diagnostics if item["severity"] == "info"),
        },
    }
