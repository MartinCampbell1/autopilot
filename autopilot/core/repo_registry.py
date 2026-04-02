"""Git repo identity and path mapping helpers for resume across clones and worktrees."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def _normalize_path(project_path: Path | str) -> Path:
    return Path(project_path).expanduser().resolve()


def _run_git(cwd: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=5,
    )


def _remote_url_to_github_repo(remote_url: str) -> str:
    normalized = str(remote_url or "").strip()
    if not normalized:
        return ""
    patterns = (
        r"^git@github\.com:(?P<repo>[^#\s]+?)(?:\.git)?$",
        r"^ssh://git@github\.com/(?P<repo>[^#\s]+?)(?:\.git)?$",
        r"^https://github\.com/(?P<repo>[^#\s]+?)(?:\.git)?$",
        r"^git://github\.com/(?P<repo>[^#\s]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.match(pattern, normalized, flags=re.IGNORECASE)
        if not match:
            continue
        repo = str(match.group("repo") or "").strip().strip("/")
        if repo:
            return repo.lower()
    return ""


def _load_repo_registry(config: AutopilotConfig) -> dict[str, Any]:
    path = config.repo_registry_json_path
    if not path.exists():
        return {"version": 1, "repos": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "repos": {}}
    repos = payload.get("repos")
    if not isinstance(repos, dict):
        repos = {}
    return {
        "version": int(payload.get("version") or 1),
        "repos": repos,
    }


def _persist_repo_registry(config: AutopilotConfig, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "version": int(payload.get("version") or 1),
        "repos": dict(payload.get("repos") or {}),
    }
    _atomic_write_json(config.repo_registry_json_path, normalized)
    return normalized


def find_canonical_git_root(project_path: Path | str) -> Path | None:
    """Return the canonical git root for one path, or None when outside git."""

    candidate = _normalize_path(project_path)
    cwd = candidate if candidate.is_dir() else candidate.parent
    try:
        result = _run_git(cwd, ["rev-parse", "--show-toplevel"])
    except (FileNotFoundError, NotADirectoryError, PermissionError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    stdout = str(result.stdout or "").strip()
    if not stdout:
        return None
    return _normalize_path(stdout)


def get_git_remote_url(project_path: Path | str, *, remote_name: str = "origin") -> str:
    """Return one configured git remote URL for the repo rooted at project_path."""

    canonical_root = find_canonical_git_root(project_path)
    if canonical_root is None:
        return ""
    try:
        result = _run_git(canonical_root, ["remote", "get-url", remote_name])
    except (FileNotFoundError, NotADirectoryError, PermissionError, subprocess.TimeoutExpired):
        return ""
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def get_github_repo(project_path: Path | str) -> str:
    """Return normalized GitHub owner/repo identity for one repo when available."""

    return _remote_url_to_github_repo(get_git_remote_url(project_path))


def build_repo_registry_key(project_path: Path | str) -> str:
    """Return a stable registry key for one git repo or empty string when unavailable."""

    canonical_root = find_canonical_git_root(project_path)
    if canonical_root is None:
        return ""
    github_repo = get_github_repo(canonical_root)
    if github_repo:
        return f"github:{github_repo}"
    remote_url = get_git_remote_url(canonical_root)
    if remote_url:
        return f"remote:{remote_url}"
    return f"git:{canonical_root}"


def update_repo_path_mapping(config: AutopilotConfig, project_path: Path | str) -> dict[str, Any] | None:
    """Persist one observed repo path under its stable repo identity."""

    observed_path = _normalize_path(project_path)
    canonical_root = find_canonical_git_root(observed_path)
    if canonical_root is None:
        return None
    repo_key = build_repo_registry_key(canonical_root)
    if not repo_key:
        return None

    registry = _load_repo_registry(config)
    repos = dict(registry.get("repos") or {})
    existing = dict(repos.get(repo_key) or {})
    known_paths = sorted(
        {
            str(observed_path),
            str(canonical_root),
            *[
                str(_normalize_path(path_value))
                for path_value in list(existing.get("known_paths") or [])
                if str(path_value).strip()
            ],
        }
    )
    updated_entry = {
        "repo_key": repo_key,
        "github_repo": get_github_repo(canonical_root),
        "remote_url": get_git_remote_url(canonical_root),
        "canonical_git_root": str(canonical_root),
        "known_paths": known_paths,
        "updated_at": _utcnow_iso(),
    }
    repos[repo_key] = updated_entry
    _persist_repo_registry(
        config,
        {
            "version": registry.get("version") or 1,
            "repos": repos,
        },
    )
    return updated_entry


def get_repo_registry_entry(
    config: AutopilotConfig,
    *,
    repo_key: str | None = None,
    project_path: Path | str | None = None,
) -> dict[str, Any] | None:
    """Load one repo registry entry by key or by inferring from a project path."""

    resolved_key = str(repo_key or "").strip()
    if not resolved_key and project_path is not None:
        resolved_key = build_repo_registry_key(project_path)
    if not resolved_key:
        return None
    registry = _load_repo_registry(config)
    entry = registry.get("repos", {}).get(resolved_key)
    return dict(entry) if isinstance(entry, dict) else None


def get_known_paths_for_repo(
    config: AutopilotConfig,
    *,
    repo_key: str | None = None,
    project_path: Path | str | None = None,
) -> list[str]:
    """Return all known paths recorded for one repo identity."""

    entry = get_repo_registry_entry(config, repo_key=repo_key, project_path=project_path)
    if entry is None:
        return []
    return [
        str(path_value).strip()
        for path_value in list(entry.get("known_paths") or [])
        if str(path_value).strip()
    ]
