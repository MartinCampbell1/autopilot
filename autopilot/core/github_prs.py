"""Helpers for stable story branch names and persisted GitHub PR metadata."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

_NON_BRANCH_CHARS_RE = re.compile(r"[^a-z0-9._/-]+")
_SEPARATOR_RE = re.compile(r"[-/_.]{2,}")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(value: str, *, separator: str = "-") -> str:
    normalized = (
        unicodedata.normalize("NFKD", str(value or ""))
        .encode("ascii", "ignore")
        .decode("ascii")
        .strip()
        .lower()
    )
    normalized = normalized.replace("&", " and ")
    normalized = normalized.replace("'", "")
    normalized = re.sub(r"[^a-z0-9]+", separator, normalized)
    normalized = re.sub(rf"{re.escape(separator)}+", separator, normalized)
    return normalized.strip(separator)


class StoryGitHubPullRequest(BaseModel):
    """Stable story-scoped PR and handoff metadata."""

    provider: str = "github"
    head_branch: str = ""
    base_branch: str = "main"
    number: int | None = None
    url: str = ""
    title: str = ""
    state: str = "not_opened"
    ci_status: str = "unknown"
    review_status: str = "unreviewed"
    handoff_status: str = "not_requested"
    merge_state: str = "not_ready"
    draft: bool = False
    author: str = ""
    labels: list[str] = Field(default_factory=list)
    comment_count: int = 0
    review_comment_count: int = 0
    last_commit_sha: str = ""
    checks_url: str = ""
    latest_event: str = ""
    opened_at: str | None = None
    merged_at: str | None = None
    closed_at: str | None = None
    updated_at: str | None = None


def stable_story_branch_name(project_name: str, story_id: int, story_title: str) -> str:
    """Return the stable branch name reserved for one story."""

    project_slug = _slugify(project_name or "project") or "project"
    story_slug = _slugify(story_title or f"story-{story_id}") or f"story-{story_id}"
    branch = f"autopilot/{project_slug}/story-{int(story_id)}-{story_slug}"
    branch = _NON_BRANCH_CHARS_RE.sub("-", branch).strip("/.-")
    branch = _SEPARATOR_RE.sub(lambda match: match.group(0)[0], branch)
    if len(branch) <= 96:
        return branch

    head = f"autopilot/{project_slug}/story-{int(story_id)}-"
    remaining = max(8, 96 - len(head))
    branch = f"{head}{story_slug[:remaining]}".rstrip("/.-")
    return branch or f"autopilot/{project_slug}/story-{int(story_id)}"


def default_story_github_pr(
    project_name: str,
    *,
    story_id: int,
    story_title: str,
    base_branch: str = "main",
) -> dict[str, Any]:
    """Return the default GitHub PR payload for one story."""

    return StoryGitHubPullRequest(
        head_branch=stable_story_branch_name(project_name, story_id, story_title),
        base_branch=(str(base_branch or "main").strip() or "main"),
    ).model_dump()


def normalize_story_github_pr(
    project_name: str,
    story: dict[str, Any],
    *,
    existing: dict[str, Any] | None = None,
    incoming: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge existing and incoming PR metadata into the stable story schema."""

    payload: dict[str, Any] = default_story_github_pr(
        project_name,
        story_id=int(story["id"]),
        story_title=str(story.get("title") or ""),
    )
    if existing:
        payload.update({key: value for key, value in existing.items() if value is not None})
    if incoming:
        payload.update({key: value for key, value in incoming.items() if value is not None})

    payload["head_branch"] = str(payload.get("head_branch") or "").strip() or stable_story_branch_name(
        project_name,
        int(story["id"]),
        str(story.get("title") or ""),
    )
    payload["base_branch"] = str(payload.get("base_branch") or "main").strip() or "main"
    payload["url"] = str(payload.get("url") or "").strip()
    payload["title"] = str(payload.get("title") or "").strip()
    payload["state"] = str(payload.get("state") or "not_opened").strip().lower() or "not_opened"
    payload["ci_status"] = str(payload.get("ci_status") or "unknown").strip().lower() or "unknown"
    payload["review_status"] = str(payload.get("review_status") or "unreviewed").strip().lower() or "unreviewed"
    payload["handoff_status"] = str(payload.get("handoff_status") or "not_requested").strip().lower() or "not_requested"
    payload["merge_state"] = str(payload.get("merge_state") or "not_ready").strip().lower() or "not_ready"
    payload["draft"] = bool(payload.get("draft", False))
    payload["author"] = str(payload.get("author") or "").strip()
    payload["labels"] = sorted(
        {
            str(item).strip()
            for item in (payload.get("labels") or [])
            if str(item).strip()
        }
    )
    payload["comment_count"] = max(0, int(payload.get("comment_count") or 0))
    payload["review_comment_count"] = max(0, int(payload.get("review_comment_count") or 0))
    payload["last_commit_sha"] = str(payload.get("last_commit_sha") or "").strip()
    payload["checks_url"] = str(payload.get("checks_url") or "").strip()
    payload["latest_event"] = str(payload.get("latest_event") or "").strip()
    if payload.get("number") in {"", None}:
        payload["number"] = None
    else:
        payload["number"] = int(payload["number"])

    has_remote_pr = bool(payload["number"] or payload["url"])
    if payload["state"] == "not_opened" and has_remote_pr:
        payload["state"] = "draft" if payload["draft"] else "open"
    if payload["state"] == "open" and payload["draft"]:
        payload["state"] = "draft"
    if payload["state"] == "draft" and not payload["draft"]:
        payload["state"] = "open"

    if payload["state"] == "merged":
        payload["merge_state"] = "merged"
        if payload["handoff_status"] in {"", "not_requested", "in_review", "approved_and_green"}:
            payload["handoff_status"] = "merged"
        if not payload.get("merged_at"):
            payload["merged_at"] = payload.get("updated_at") or _utcnow_iso()
    elif payload["handoff_status"] == "merged_locally":
        payload["merge_state"] = "merged"
    elif payload["handoff_status"] == "manual_handoff":
        if payload["merge_state"] in {"", "not_ready", "ready"}:
            payload["merge_state"] = "blocked"
    elif payload["review_status"] == "changes_requested":
        payload["handoff_status"] = "changes_requested"
        payload["merge_state"] = "blocked"
    elif payload["ci_status"] == "red":
        if payload["handoff_status"] in {"", "not_requested", "in_review"}:
            payload["handoff_status"] = "ci_failed"
        payload["merge_state"] = "blocked"
    elif payload["review_status"] == "approved" and payload["ci_status"] == "green":
        payload["handoff_status"] = "approved_and_green"
        payload["merge_state"] = "ready"
    elif has_remote_pr or payload["state"] in {"open", "draft", "closed"}:
        if payload["handoff_status"] in {"", "not_requested"}:
            payload["handoff_status"] = "in_review"

    if payload["updated_at"] is not None:
        payload["updated_at"] = str(payload["updated_at"]).strip() or None
    for key in ("opened_at", "merged_at", "closed_at"):
        if payload.get(key) is not None:
            payload[key] = str(payload[key]).strip() or None

    return StoryGitHubPullRequest.model_validate(payload).model_dump()
