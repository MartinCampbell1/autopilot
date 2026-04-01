"""Conservative path validation helpers for runtime-managed worktree paths."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


WORKTREE_NAME_PATTERN = re.compile(r"^(?P<name>.+)-story-(?P<story_id>\d+)$")
SHELL_EXPANSION_PATTERN = re.compile(r"(?P<dynamic>~|\$\(|\$\{|\$[A-Za-z_][A-Za-z0-9_]*|%[A-Za-z_][A-Za-z0-9_]*%|`)")


@dataclass(frozen=True)
class PathValidationResult:
    """Result of validating one runtime-managed filesystem path."""

    allowed: bool
    normalized_path: Path
    reason: str = ""


def validate_story_worktree_path(
    project_path: Path,
    candidate_path: Path | str,
    *,
    expected_story_id: int | None = None,
) -> PathValidationResult:
    """Validate one story worktree path against the owning project path."""

    raw_value = str(candidate_path).strip()
    if not raw_value:
        return PathValidationResult(False, Path(project_path).expanduser().resolve(), "Worktree path is empty.")
    if SHELL_EXPANSION_PATTERN.search(raw_value):
        return PathValidationResult(
            False,
            Path(raw_value),
            "Worktree path contains shell expansion syntax and is not trusted.",
        )

    resolved_project = Path(project_path).expanduser().resolve()
    resolved_candidate = Path(raw_value).expanduser().resolve(strict=False)
    if resolved_candidate == resolved_project:
        return PathValidationResult(False, resolved_candidate, "Worktree path cannot equal the primary project path.")
    if resolved_candidate.parent != resolved_project.parent:
        return PathValidationResult(
            False,
            resolved_candidate,
            "Worktree path must stay in the primary project parent directory.",
        )

    match = WORKTREE_NAME_PATTERN.match(resolved_candidate.name)
    if not match or match.group("name") != resolved_project.name:
        return PathValidationResult(
            False,
            resolved_candidate,
            "Worktree path must match the `<project>-story-<id>` naming contract.",
        )

    if expected_story_id is not None and int(match.group("story_id")) != int(expected_story_id):
        return PathValidationResult(
            False,
            resolved_candidate,
            f"Worktree path story id does not match expected story #{expected_story_id}.",
        )

    return PathValidationResult(True, resolved_candidate)


def assert_story_worktree_path(
    project_path: Path,
    candidate_path: Path | str,
    *,
    expected_story_id: int | None = None,
) -> Path:
    """Return the normalized worktree path or raise when unsafe."""

    result = validate_story_worktree_path(project_path, candidate_path, expected_story_id=expected_story_id)
    if not result.allowed:
        raise ValueError(result.reason)
    return result.normalized_path
