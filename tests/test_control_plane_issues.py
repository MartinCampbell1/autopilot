"""Tests for execution control-plane issue records."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.control_plane_issues import create_issue, list_issues, resolve_issue
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import emit_project_event
from autopilot.core.project_store import register_project


def test_create_issue_reuses_open_dedupe_key(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "issue-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Issue Project", project_path=project_dir)

    first = create_issue(
        config,
        project=project,
        title="Approval required for `launch`",
        category="policy_approval",
        dedupe_key="policy:launch",
    )
    second = create_issue(
        config,
        project=project,
        title="Approval required for `launch`",
        category="policy_approval",
        dedupe_key="policy:launch",
    )

    assert first.id == second.id

    resolve_issue(config, first.id, actor="martin", note="Handled.")
    third = create_issue(
        config,
        project=project,
        title="Approval required for `launch`",
        category="policy_approval",
        dedupe_key="policy:launch",
    )

    assert third.id != first.id


def test_runtime_event_sync_creates_and_resolves_story_issue(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "Runtime Issue Project",
            "description": "Project for runtime issue sync",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "runtime-issue-project"),
        launch=False,
    )

    emit_project_event(
        config,
        created.project_id,
        event="worker_failed",
        status="error",
        message="Build command crashed.",
        story_id=1,
    )

    issues = list_issues(config, project_id=created.project_id, status="open")
    assert len(issues) == 1
    assert issues[0].category == "runtime_worker_failure"
    assert issues[0].story_id == 1
    assert issues[0].source_event == "worker_failed"
    assert issues[0].root_cause == "Build command crashed."
    assert issues[0].context["story"]["title"] == "Bootstrap"
    assert issues[0].context["story"]["id"] == 1

    emit_project_event(
        config,
        created.project_id,
        event="story_done",
        status="done",
        message="Story completed.",
        story_id=1,
    )

    resolved = list_issues(config, project_id=created.project_id)
    assert len(resolved) == 1
    assert resolved[0].status == "resolved"


def test_runtime_event_sync_creates_and_resolves_budget_issue(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "Budget Issue Project",
            "description": "Project for budget issue sync",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "budget-issue-project"),
        launch=False,
    )

    emit_project_event(
        config,
        created.project_id,
        event="budget_paused",
        status="paused",
        message="Budget exhausted.",
    )

    issues = list_issues(config, project_id=created.project_id, status="open")
    assert len(issues) == 1
    assert issues[0].category == "runtime_budget_paused"
    assert issues[0].story_id is None
    assert issues[0].root_cause == "Budget exhausted."
    assert "budget" in issues[0].context
    assert "policy" in issues[0].context["budget"]
    assert "usage" in issues[0].context["budget"]

    emit_project_event(
        config,
        created.project_id,
        event="resumed",
        status="running",
        message="Project resumed.",
    )

    resolved = list_issues(config, project_id=created.project_id)
    assert len(resolved) == 1
    assert resolved[0].status == "resolved"


def test_runtime_event_sync_uses_structured_gate_failure_payload(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "Gate Failure Project",
            "description": "Project for gate failure sync",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "gate-failure-project"),
        launch=False,
    )

    emit_project_event(
        config,
        created.project_id,
        event="story_gate_failed",
        status="error",
        message="Quality gates failed.",
        story_id=1,
        extra={
            "iteration": 2,
            "gate_failures": [
                {
                    "name": "pytest",
                    "cmd": "pytest",
                    "passed": False,
                    "output": "2 tests failed",
                    "required": True,
                    "elapsed_sec": 1.2,
                }
            ],
            "critic_feedback": "- pytest: 2 tests failed",
        },
    )

    issues = list_issues(config, project_id=created.project_id, status="open")
    assert len(issues) == 1
    assert issues[0].category == "runtime_gate_failure"
    assert issues[0].source_event == "story_gate_failed"
    assert issues[0].root_cause == "pytest: 2 tests failed"
    assert issues[0].runtime_agent_id == ""
    assert issues[0].context["event"]["extra"]["iteration"] == 2
    assert issues[0].context["event"]["extra"]["gate_failures"][0]["name"] == "pytest"


def test_runtime_event_sync_preserves_explicit_runtime_agent_id(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "Runtime Agent Project",
            "description": "Project for runtime agent issue sync",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "runtime-agent-project"),
        launch=False,
    )

    emit_project_event(
        config,
        created.project_id,
        event="worker_failed",
        status="error",
        message="Build command crashed.",
        story_id=1,
        extra={"runtime_agent_id": f"{created.project_id}:1:worker:primary"},
    )

    issues = list_issues(config, project_id=created.project_id, status="open")
    assert len(issues) == 1
    assert issues[0].runtime_agent_id == f"{created.project_id}:1:worker:primary"

    filtered = list_issues(
        config,
        project_id=created.project_id,
        status="open",
        runtime_agent_id=f"{created.project_id}:1:worker:primary",
    )
    assert len(filtered) == 1
    assert filtered[0].id == issues[0].id


def test_issue_filter_matches_runtime_agent_ids_scope(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "issue-project"
    project_dir.mkdir(parents=True)
    project = register_project(config, name="Issue Project", project_path=project_dir)

    issue = create_issue(
        config,
        project=project,
        title="Approval required for `pause`",
        category="policy_approval",
        runtime_agent_ids=["agent:1", "agent:2"],
        dedupe_key="policy:pause",
    )

    filtered = list_issues(config, project_id=project["id"], runtime_agent_id="agent:2")
    assert len(filtered) == 1
    assert filtered[0].id == issue.id


def test_github_reaction_events_create_and_resolve_story_issues(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    created = create_project_from_prd(
        config=config,
        prd={
            "title": "GitHub Issue Project",
            "description": "Project for GitHub issue sync",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        },
        project_path=str(tmp_path / "github-issue-project"),
        launch=False,
    )

    emit_project_event(
        config,
        created.project_id,
        event="github_ci_failed",
        status="error",
        message="GitHub CI failed for PR #12.",
        story_id=1,
        extra={"check_summary": "pytest failed", "github_pr_number": 12},
    )
    emit_project_event(
        config,
        created.project_id,
        event="github_changes_requested",
        status="warning",
        message="GitHub changes requested for PR #12.",
        story_id=1,
        extra={"review_comment": "Please fix the regression."},
    )

    issues = list_issues(config, project_id=created.project_id, status="open")
    categories = {issue.category for issue in issues}
    assert "github_ci_failure" in categories
    assert "github_changes_requested" in categories

    emit_project_event(
        config,
        created.project_id,
        event="github_approved_and_green",
        status="ok",
        message="GitHub PR #12 is approved and green.",
        story_id=1,
    )

    resolved = list_issues(config, project_id=created.project_id)
    assert resolved
    assert all(issue.status == "resolved" for issue in resolved)
