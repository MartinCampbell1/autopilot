"""Structured company-goal builders for always-on project execution."""

from __future__ import annotations

from typing import Any

_DONE_STATUSES = {"done", "completed", "skipped"}
_ACTIVE_STATUSES = {"in_progress", "running"}
_BLOCKED_STATUSES = {"merge_blocked", "stuck", "failed"}


def _goal_status(stories: list[dict[str, Any]]) -> tuple[str, int, int, int, int]:
    total = len(stories)
    done = sum(1 for story in stories if str(story.get("status") or "").strip() in _DONE_STATUSES)
    active = sum(1 for story in stories if str(story.get("status") or "").strip() in _ACTIVE_STATUSES)
    blocked = sum(1 for story in stories if str(story.get("status") or "").strip() in _BLOCKED_STATUSES)
    queued = max(total - done - active - blocked, 0)

    if total > 0 and done >= total:
        return "completed", done, active, blocked, queued
    if active > 0:
        return "active", done, active, blocked, queued
    if blocked > 0:
        return "blocked", done, active, blocked, queued
    return "queued", done, active, blocked, queued


def _goal_item(
    *,
    goal_id: str,
    title: str,
    goal: str,
    stories: list[dict[str, Any]],
) -> dict[str, Any]:
    status, done, active, blocked, queued = _goal_status(stories)
    total = len(stories)
    current_story = next(
        (story for story in stories if str(story.get("status") or "").strip() in _ACTIVE_STATUSES),
        None,
    )
    completed_like = done
    progress_pct = int(round((completed_like / total) * 100)) if total > 0 else 0
    return {
        "id": goal_id,
        "title": str(title or "").strip() or "Execution goal",
        "goal": str(goal or "").strip(),
        "status": status,
        "progress_pct": progress_pct,
        "stories_total": total,
        "stories_done": done,
        "stories_active": active,
        "stories_blocked": blocked,
        "stories_queued": queued,
        "current_story_id": current_story.get("id") if current_story else None,
        "current_story_title": current_story.get("title") if current_story else None,
    }


def build_company_goals(
    *,
    project: dict[str, Any],
    prd: dict[str, Any],
    stories: list[dict[str, Any]],
    state: dict[str, Any],
) -> dict[str, Any]:
    """Build first-class goal objects from project phases and story state."""

    normalized_stories = list(stories or [])
    phases = [dict(phase or {}) for phase in list(prd.get("phases") or [])]
    items: list[dict[str, Any]] = []

    if phases:
        for index, phase in enumerate(phases, start=1):
            phase_id = str(phase.get("id") or f"phase-{index}").strip() or f"phase-{index}"
            phase_stories = [
                story
                for story in normalized_stories
                if str(story.get("phase_id") or "").strip() == phase_id
            ]
            items.append(
                _goal_item(
                    goal_id=phase_id,
                    title=str(phase.get("title") or f"Phase {index}").strip() or f"Phase {index}",
                    goal=str(phase.get("goal") or "").strip(),
                    stories=phase_stories,
                )
            )
    else:
        items.append(
            _goal_item(
                goal_id="project-goal",
                title=str(project.get("name") or prd.get("title") or "Project").strip() or "Project",
                goal=str(prd.get("description") or project.get("description") or "").strip(),
                stories=normalized_stories,
            )
        )

    status, done, active, blocked, queued = _goal_status(normalized_stories)
    current_story_id = state.get("current_story_id")
    current_story = next((story for story in normalized_stories if story.get("id") == current_story_id), None)
    return {
        "items": items,
        "summary": {
            "status": status,
            "goal_count": len(items),
            "stories_total": len(normalized_stories),
            "stories_done": done,
            "stories_active": active,
            "stories_blocked": blocked,
            "stories_queued": queued,
            "current_story_id": current_story_id,
            "current_story_title": current_story.get("title") if current_story else None,
        },
    }

