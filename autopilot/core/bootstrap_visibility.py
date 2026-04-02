"""Shared visibility helpers for verifier/GitHub bootstrap state."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autopilot.core.github_repo_setup import GITHUB_BOOTSTRAP_WORKFLOW_RELPATH
from autopilot.core.repo_registry import find_canonical_git_root, get_github_repo
from autopilot.core.verification_bootstrap import VERIFICATION_BOOTSTRAP_RELPATH


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def build_bootstrap_status(
    *,
    project_path: Path | str,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return operator-visible verifier and GitHub bootstrap state for one checkout."""

    normalized_path = _normalize_path(project_path)
    verification_record = dict((project or {}).get("verification_bootstrap") or {})
    github_record = dict((project or {}).get("github_bootstrap") or {})

    verification_relpath = str(verification_record.get("artifact_relpath") or VERIFICATION_BOOTSTRAP_RELPATH).strip()
    verification_path = normalized_path / verification_relpath

    workflow_relpath = str(github_record.get("workflow_relpath") or GITHUB_BOOTSTRAP_WORKFLOW_RELPATH).strip()
    workflow_path = normalized_path / workflow_relpath

    repo_root = find_canonical_git_root(normalized_path) or normalized_path
    github_repo = str(github_record.get("github_repo") or get_github_repo(repo_root) or "").strip()

    return {
        "verification": {
            "configured": bool(verification_record),
            "artifact_relpath": verification_relpath,
            "artifact_path": str(verification_path),
            "artifact_exists": verification_path.exists(),
            "updated_at": str(verification_record.get("updated_at") or "").strip(),
            "gate_count": int(verification_record.get("gate_count") or 0),
            "check_count": int(verification_record.get("check_count") or 0),
        },
        "github": {
            "configured": bool(github_record),
            "workflow_relpath": workflow_relpath,
            "workflow_path": str(workflow_path),
            "workflow_exists": workflow_path.exists(),
            "updated_at": str(github_record.get("updated_at") or "").strip(),
            "github_repo": github_repo,
            "current_branch": str(github_record.get("current_branch") or "").strip(),
            "default_branch": str(github_record.get("default_branch") or "").strip(),
            "compare_url": str(github_record.get("compare_url") or "").strip(),
            "gh_authenticated": bool(github_record.get("gh_authenticated", False)),
        },
    }
