"""Tests for story-scoped GitHub PR metadata helpers."""

from autopilot.core.github_prs import normalize_story_github_pr, stable_story_branch_name


def test_stable_story_branch_name_uses_project_and_story_slug() -> None:
    branch = stable_story_branch_name("Leased Project", 3, "Bootstrap dashboard shell")

    assert branch == "autopilot/leased-project/story-3-bootstrap-dashboard-shell"


def test_normalize_story_github_pr_infers_review_ready_state() -> None:
    payload = normalize_story_github_pr(
        "FounderOS Copilot",
        {"id": 1, "title": "Bootstrap shell"},
        incoming={
            "number": 12,
            "url": "https://github.com/example/repo/pull/12",
            "review_status": "approved",
            "ci_status": "green",
        },
    )

    assert payload["state"] == "open"
    assert payload["handoff_status"] == "approved_and_green"
    assert payload["merge_state"] == "ready"
