"""Tests for GitHub PR sync and reaction ingestion helpers."""

from pathlib import Path
from unittest.mock import patch

from autopilot.core.config import AutopilotConfig
from autopilot.core.execution_plane import update_project_command_policy
from autopilot.core.github_reactions import ingest_story_github_reaction, sync_story_github_pr
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import load_project_state, update_project_runtime, update_story_runtime


def test_sync_story_github_pr_persists_story_metadata(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "GitHub Sync Project",
            "description": "Project for sync tests",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "github-sync-project"),
        launch=False,
    )

    payload = sync_story_github_pr(
        config,
        project_id=created.project_id,
        story_id=1,
        payload={
            "number": 18,
            "url": "https://github.com/example/repo/pull/18",
            "state": "open",
        },
        emit_event_record=False,
    )

    state = load_project_state(config, created.project_id)
    assert payload["number"] == 18
    assert state["story_state"]["1"]["github_pr"]["url"] == "https://github.com/example/repo/pull/18"


@patch("autopilot.core.github_reactions.resume_project_run")
def test_ingest_story_github_reaction_auto_resumes_when_policy_allows(mock_resume_project_run, tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    mock_resume_project_run.return_value = (True, None, "Project resumed.")
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "GitHub Resume Project",
            "description": "Project for reaction tests",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "github-resume-project"),
        launch=False,
    )

    update_project_command_policy(config, created.project_id, github_approved_and_green_auto_resume=True)
    update_project_runtime(
        config,
        created.project_id,
        status="paused",
        paused=True,
        current_story_id=1,
        current_iteration=2,
    )
    update_story_runtime(
        config,
        created.project_id,
        1,
        status="in_progress",
        iteration=2,
        agent="codex/worker-a",
        github_pr={
            "provider": "github",
            "head_branch": "autopilot/github-resume-project/story-1-bootstrap",
            "base_branch": "main",
            "number": 44,
            "url": "https://github.com/example/repo/pull/44",
            "title": "Bootstrap",
            "state": "open",
            "ci_status": "pending",
            "review_status": "commented",
            "handoff_status": "in_review",
            "merge_state": "not_ready",
            "draft": False,
            "author": "",
            "labels": [],
            "comment_count": 0,
            "review_comment_count": 0,
            "last_commit_sha": "",
            "checks_url": "",
            "latest_event": "github_review_comment_received",
            "opened_at": None,
            "merged_at": None,
            "closed_at": None,
            "updated_at": "2026-03-31T00:00:00+00:00",
        },
    )

    payload = ingest_story_github_reaction(
        config,
        project_id=created.project_id,
        story_id=1,
        reaction_type="approved_and_green",
    )

    state = load_project_state(config, created.project_id)
    assert payload["auto_resumed"] is True
    mock_resume_project_run.assert_called_once()
    assert state["paused"] is True
    assert state["story_state"]["1"]["github_pr"]["handoff_status"] == "approved_and_green"
