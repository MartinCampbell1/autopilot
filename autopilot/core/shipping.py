"""Safe branch -> commit -> push -> PR helpers for `autopilot ship`."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from autopilot.core.repo_registry import find_canonical_git_root, get_github_repo


class ShippingError(RuntimeError):
    """Raised when the ship flow cannot continue safely."""


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError, subprocess.TimeoutExpired) as exc:
        raise ShippingError("Git is unavailable or the repository path is inaccessible.") from exc


def _run_gh(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["gh", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError, subprocess.TimeoutExpired) as exc:
        raise ShippingError("GitHub CLI `gh` is unavailable or the repository path is inaccessible.") from exc


def _command_failure(command_label: str, result: subprocess.CompletedProcess[str]) -> ShippingError:
    detail = str(result.stderr or result.stdout or "").strip() or "unknown error"
    return ShippingError(f"{command_label} failed: {detail}")


def _git_stdout(cwd: Path, args: list[str], *, command_label: str) -> str:
    result = _run_git(cwd, args)
    if result.returncode != 0:
        raise _command_failure(command_label, result)
    return str(result.stdout or "").strip()


def _git_ref_exists(cwd: Path, ref_name: str) -> bool:
    result = _run_git(cwd, ["rev-parse", "--verify", ref_name])
    return result.returncode == 0


def get_current_branch(project_path: Path | str = ".") -> str:
    """Return the current checked out branch name."""

    repo_root = find_canonical_git_root(project_path)
    if repo_root is None:
        raise ShippingError("Path is not inside a git repository.")
    branch_name = _git_stdout(repo_root, ["branch", "--show-current"], command_label="git branch --show-current")
    if not branch_name:
        raise ShippingError("Current checkout is detached; ship requires a named branch.")
    return branch_name


def get_default_branch(project_path: Path | str = ".", *, explicit_base_branch: str | None = None) -> str:
    """Return the default base branch used for pull requests."""

    explicit_value = str(explicit_base_branch or "").strip()
    if explicit_value:
        return explicit_value

    repo_root = find_canonical_git_root(project_path)
    if repo_root is None:
        raise ShippingError("Path is not inside a git repository.")

    result = _run_git(repo_root, ["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if result.returncode == 0:
        stdout = str(result.stdout or "").strip()
        prefix = "refs/remotes/origin/"
        if stdout.startswith(prefix):
            branch_name = stdout.removeprefix(prefix).strip()
            if branch_name:
                return branch_name

    for candidate in ("main", "master"):
        if _git_ref_exists(repo_root, f"refs/remotes/origin/{candidate}") or _git_ref_exists(repo_root, f"refs/heads/{candidate}"):
            return candidate

    raise ShippingError("Could not determine the default branch. Pass --base-branch explicitly.")


def _working_tree_dirty(cwd: Path) -> bool:
    return bool(_git_stdout(cwd, ["status", "--porcelain"], command_label="git status --porcelain"))


def _last_commit_subject(cwd: Path) -> str:
    return _git_stdout(cwd, ["log", "-1", "--pretty=%s"], command_label="git log -1 --pretty=%s")


def _last_commit_body(cwd: Path) -> str:
    return _git_stdout(cwd, ["log", "-1", "--pretty=%b"], command_label="git log -1 --pretty=%b")


def _resolve_base_ref(cwd: Path, base_branch: str) -> str:
    remote_ref = f"refs/remotes/origin/{base_branch}"
    local_ref = f"refs/heads/{base_branch}"
    if _git_ref_exists(cwd, remote_ref):
        return f"origin/{base_branch}"
    if _git_ref_exists(cwd, local_ref):
        return base_branch
    raise ShippingError(f"Base branch `{base_branch}` is not available locally. Fetch it or pass a valid --base-branch.")


def _branch_has_changes_against_base(cwd: Path, base_branch: str) -> bool:
    base_ref = _resolve_base_ref(cwd, base_branch)
    result = _run_git(cwd, ["diff", "--quiet", f"{base_ref}...HEAD", "--"])
    if result.returncode == 0:
        return False
    if result.returncode == 1:
        return True
    raise _command_failure(f"git diff {base_ref}...HEAD", result)


def _ensure_ship_readiness(repo_root: Path) -> dict[str, Any]:
    from autopilot.core.bootstrap_visibility import build_bootstrap_status

    status = build_bootstrap_status(project_path=repo_root)
    verification = dict(status.get("verification") or {})
    github = dict(status.get("github") or {})

    verification_path = str(verification.get("artifact_path") or "").strip()
    if not bool(verification.get("artifact_exists")):
        raise ShippingError(
            "Verifier bootstrap artifact is missing"
            + (f" at {verification_path}." if verification_path else ".")
            + f" Run `autopilot init-verifiers {repo_root}` before `autopilot ship`."
        )

    workflow_path = str(github.get("workflow_path") or "").strip()
    if str(github.get("github_repo") or "").strip() and not bool(github.get("workflow_exists")):
        raise ShippingError(
            "Managed GitHub workflow is missing"
            + (f" at {workflow_path}." if workflow_path else ".")
            + f" Run `autopilot github {repo_root}` from a feature branch before `autopilot ship`."
        )

    return status


def _normalize_pull_request(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": payload.get("number"),
        "url": str(payload.get("url") or "").strip(),
        "state": str(payload.get("state") or "").strip().lower() or "unknown",
        "draft": bool(payload.get("isDraft", payload.get("draft", False))),
        "title": str(payload.get("title") or "").strip(),
        "head_branch": str(payload.get("headRefName") or payload.get("head_branch") or "").strip(),
        "base_branch": str(payload.get("baseRefName") or payload.get("base_branch") or "").strip(),
    }


def _find_existing_pull_request(cwd: Path, *, github_repo: str, branch_name: str) -> dict[str, Any] | None:
    result = _run_gh(
        cwd,
        [
            "pr",
            "list",
            "--repo",
            github_repo,
            "--head",
            branch_name,
            "--json",
            "number,url,state,isDraft,title,headRefName,baseRefName",
            "--limit",
            "1",
        ],
    )
    if result.returncode != 0:
        raise _command_failure("gh pr list", result)
    try:
        payload = json.loads(str(result.stdout or "[]"))
    except json.JSONDecodeError as exc:
        raise ShippingError("gh pr list returned invalid JSON.") from exc
    if not isinstance(payload, list) or not payload:
        return None
    first = payload[0]
    if not isinstance(first, dict):
        return None
    return _normalize_pull_request(first)


def ship_repo(
    project_path: Path | str = ".",
    *,
    commit_message: str | None = None,
    title: str | None = None,
    body: str | None = None,
    draft: bool = False,
    base_branch: str | None = None,
) -> dict[str, Any]:
    """Safely ship the current branch by committing, pushing, and opening a PR."""

    repo_root = find_canonical_git_root(project_path)
    if repo_root is None:
        raise ShippingError("Path is not inside a git repository.")
    if shutil.which("gh") is None:
        raise ShippingError("GitHub CLI `gh` is required for `autopilot ship`.")

    github_repo = get_github_repo(repo_root)
    if not github_repo:
        raise ShippingError("Origin remote is not a GitHub repository. Ship is fail-closed without GitHub repo identity.")

    current_branch = get_current_branch(repo_root)
    resolved_base_branch = get_default_branch(repo_root, explicit_base_branch=base_branch)
    protected_branches = {resolved_base_branch, "main", "master", "trunk"}
    if current_branch in protected_branches:
        raise ShippingError(
            f"Refusing to ship from protected branch `{current_branch}`. Create or switch to a feature branch first."
        )

    bootstrap = _ensure_ship_readiness(repo_root)

    dirty_before_ship = _working_tree_dirty(repo_root)
    normalized_commit_message = str(commit_message or "").strip()
    if dirty_before_ship and not normalized_commit_message:
        raise ShippingError("Working tree has uncommitted changes. Pass --message to create a commit before shipping.")

    commit_created = False
    if dirty_before_ship:
        add_result = _run_git(repo_root, ["add", "-A"])
        if add_result.returncode != 0:
            raise _command_failure("git add -A", add_result)
        commit_result = _run_git(repo_root, ["commit", "-m", normalized_commit_message])
        if commit_result.returncode != 0:
            raise _command_failure("git commit", commit_result)
        commit_created = True

    push_result = _run_git(repo_root, ["push", "--set-upstream", "origin", current_branch])
    if push_result.returncode != 0:
        raise _command_failure("git push", push_result)

    pull_request = _find_existing_pull_request(repo_root, github_repo=github_repo, branch_name=current_branch)
    pr_created = False
    if pull_request is None:
        if not _branch_has_changes_against_base(repo_root, resolved_base_branch):
            raise ShippingError(
                f"Current branch `{current_branch}` has no changes compared with `{resolved_base_branch}`."
            )
        pr_title = str(title or "").strip() or _last_commit_subject(repo_root) or f"Ship {current_branch}"
        pr_body = str(body or "").strip() or _last_commit_body(repo_root) or f"Shipped from `{current_branch}` with `autopilot ship`."
        gh_args = [
            "pr",
            "create",
            "--repo",
            github_repo,
            "--head",
            current_branch,
            "--base",
            resolved_base_branch,
            "--title",
            pr_title,
            "--body",
            pr_body,
        ]
        if draft:
            gh_args.append("--draft")
        create_result = _run_gh(repo_root, gh_args)
        if create_result.returncode != 0:
            raise _command_failure("gh pr create", create_result)
        pr_created = True
        pull_request = _find_existing_pull_request(repo_root, github_repo=github_repo, branch_name=current_branch)
        if pull_request is None:
            raise ShippingError("Pull request creation succeeded, but the new PR could not be discovered afterwards.")

    return {
        "project_path": str(_normalize_path(project_path)),
        "repo_root": str(repo_root),
        "github_repo": github_repo,
        "branch": current_branch,
        "base_branch": resolved_base_branch,
        "dirty_before_ship": dirty_before_ship,
        "commit_created": commit_created,
        "push_performed": True,
        "pr_created": pr_created,
        "pull_request": pull_request,
        "bootstrap": bootstrap,
    }
