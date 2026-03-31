"""Tests for project registry/runtime state helpers."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.models import StoryDependencyError
from autopilot.core.project_store import (
    auto_pause_project_run,
    build_project_detail,
    build_story_discovery_context,
    ensure_project_state,
    emit_project_event,
    extract_structured_discoveries,
    get_project_entry,
    launch_project_run,
    load_project_state,
    migrate_projects_registry,
    normalize_prd,
    record_discovery_markers,
    requeue_recoverable_stuck_stories,
    register_project,
    save_project_prd,
    save_project_state,
    update_project_budget_policy,
)


def test_migrate_projects_registry_adds_ids_and_archives_temp_paths(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    config.projects_yaml_path.parent.mkdir(parents=True, exist_ok=True)
    config.projects_yaml_path.write_text(
        yaml.safe_dump(
            {
                "projects": [
                    {"name": "Real Project", "path": str(tmp_path / "real-project")},
                    {"name": "Temp Project", "path": "/private/tmp/temp-project"},
                ]
            },
            sort_keys=False,
        )
    )

    projects = migrate_projects_registry(config)

    assert projects[0]["id"]
    assert projects[0]["archived"] is False
    assert projects[1]["id"]
    assert projects[1]["archived"] is True
    assert projects[0]["created_at"]


def test_ensure_project_state_normalizes_non_terminal_import_statuses(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="State Migration", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "State Migration",
            "stories": [
                {"id": 1, "title": "A", "status": "in_progress"},
                {"id": 2, "title": "B", "status": "stuck"},
                {"id": 3, "title": "C", "status": "done"},
            ],
        },
        seed_mode="migrate",
    )
    save_project_prd(project, prd)

    state = ensure_project_state(config, project, seed_mode="migrate")

    assert state["story_state"]["1"]["status"] == "open"
    assert state["story_state"]["2"]["status"] == "open"
    assert state["story_state"]["3"]["status"] == "done"


def test_load_project_state_after_register_and_save(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "loaded-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Loaded Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Loaded Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")

    loaded = load_project_state(config, project["id"])
    resolved = get_project_entry(config, project_id=project["id"])

    assert resolved is not None
    assert loaded["project_id"] == project["id"]
    assert json.loads((project_dir / ".agents" / "tasks" / "prd.json").read_text())["stories"][0]["status"] == "open"
    assert loaded["story_state"]["1"]["ownership"] is None
    assert loaded["story_state"]["1"]["checkout"] is None
    assert loaded["budget_policy"]["project_max_worker_iterations"] == 200
    assert loaded["budget_usage"]["project"]["worker_iterations"] == 0


def test_normalize_prd_enriches_story_routing_and_phases() -> None:
    prd = normalize_prd(
        {
            "title": "Solana Trader",
            "description": "Build a Solana trading system",
            "phases": [
                {"id": "phase-1", "title": "Data Foundation", "goal": "Collect and normalize inputs"},
            ],
            "stories": [
                {
                    "id": 1,
                    "phase_id": "phase-1",
                    "title": "Build market ingestion API",
                    "description": "Create FastAPI endpoints and normalize token data",
                }
            ],
        },
        seed_mode="new",
    )

    assert prd["phases"][0]["title"] == "Data Foundation"
    story = prd["stories"][0]
    assert story["phase_id"] == "phase-1"
    assert story["phase_title"] == "Data Foundation"
    assert "backend" in story["tags"]
    assert story["role"] == "backend_worker"
    assert "fastapi-backend" in story["skill_packs"]
    assert "shell_exec" in story["connectors"]


def test_normalize_prd_preserves_story_dependencies() -> None:
    prd = normalize_prd(
        {
            "title": "Dependency Project",
            "stories": [
                {"id": 1, "title": "Foundation", "description": "Start"},
                {
                    "id": 2,
                    "title": "UI",
                    "description": "Build shell",
                    "blocked_by": ["1", 1],
                },
            ],
        }
    )

    assert prd["stories"][0]["blocked_by"] == []
    assert prd["stories"][1]["blocked_by"] == [1]


def test_normalize_prd_rejects_invalid_story_dependencies() -> None:
    with pytest.raises(StoryDependencyError, match="cannot depend on itself"):
        normalize_prd(
            {
                "title": "Broken Project",
                "stories": [
                    {
                        "id": 1,
                        "title": "Impossible",
                        "description": "Broken dependency",
                        "blocked_by": [1],
                    }
                ],
            }
        )


def test_normalize_prd_rejects_dependency_cycles() -> None:
    with pytest.raises(StoryDependencyError, match="cycle detected"):
        normalize_prd(
            {
                "title": "Cyclic Project",
                "stories": [
                    {"id": 1, "title": "A", "description": "First", "blocked_by": [2]},
                    {"id": 2, "title": "B", "description": "Second", "blocked_by": [1]},
                ],
            }
        )


def test_ensure_project_state_requeues_interrupted_in_progress_story(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "failed-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Failed Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Failed Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state.update(
        {
            "status": "failed",
            "pid": None,
            "paused": False,
            "current_story_id": 1,
            "current_iteration": 4,
            "last_error": "Worker crashed.",
        }
    )
    story = state["story_state"]["1"]
    story.update(
        {
            "status": "in_progress",
            "started_at": "2026-03-27T11:00:00Z",
            "iteration": 4,
            "agent": "codex/acc1",
            "critic": "codex/acc2",
            "last_error": None,
        }
    )
    config.runtime_state_dir.mkdir(parents=True, exist_ok=True)
    (config.runtime_state_dir / f"{project['id']}.json").write_text(json.dumps(state))

    repaired = ensure_project_state(config, project, seed_mode="migrate")

    assert repaired["status"] == "failed"
    assert repaired["current_story_id"] is None
    assert repaired["current_iteration"] == 0
    assert repaired["story_state"]["1"]["status"] == "open"
    assert repaired["story_state"]["1"]["started_at"] is None
    assert repaired["story_state"]["1"]["agent"] is None
    assert repaired["story_state"]["1"]["critic"] is None
    assert repaired["story_state"]["1"]["last_error"] == "Worker crashed."


def test_ensure_project_state_tracks_blocked_dependencies_and_auto_unblocks(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "dependency-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Dependency Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Dependency Project",
            "stories": [
                {"id": 1, "title": "Foundation", "description": "Start"},
                {"id": 2, "title": "UI", "description": "Build shell", "blocked_by": [1]},
            ],
        }
    )
    save_project_prd(project, prd)

    state = ensure_project_state(config, project, seed_mode="new")

    assert state["story_state"]["1"]["blocked_by"] == []
    assert state["story_state"]["1"]["blocked_on"] == []
    assert state["story_state"]["2"]["blocked_by"] == [1]
    assert state["story_state"]["2"]["blocked_on"] == [1]

    state["story_state"]["1"].update(
        {
            "status": "done",
            "completed_at": "2026-03-31T12:00:00+00:00",
            "updated_at": "2026-03-31T12:00:00+00:00",
        }
    )
    save_project_state(config, project["id"], state)

    repaired = ensure_project_state(config, project, seed_mode="migrate")

    assert repaired["story_state"]["2"]["blocked_on"] == []


def test_ensure_project_state_keeps_paused_story_in_progress(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "paused-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Paused Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Paused Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state.update(
        {
            "status": "paused",
            "pid": None,
            "paused": True,
            "current_story_id": 1,
            "current_iteration": 2,
        }
    )
    story = state["story_state"]["1"]
    story.update(
        {
            "status": "in_progress",
            "started_at": "2026-03-27T11:00:00Z",
            "iteration": 2,
            "agent": "codex/acc1",
            "critic": "codex/acc2",
        }
    )
    (config.runtime_state_dir / f"{project['id']}.json").write_text(json.dumps(state))

    repaired = ensure_project_state(config, project, seed_mode="migrate")

    assert repaired["status"] == "paused"
    assert repaired["current_story_id"] == 1
    assert repaired["story_state"]["1"]["status"] == "in_progress"


def test_requeue_recoverable_stuck_stories_reopens_older_stuck_story(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "requeue-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Requeue Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Requeue Project",
            "stories": [
                {"id": 1, "title": "Foundation", "description": "Start"},
                {"id": 2, "title": "Scaffold", "description": "Finish"},
            ],
        }
    )
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state.update({"status": "failed", "last_error": "Run finished with stuck stories."})
    state["story_state"]["1"].update(
        {
            "status": "stuck",
            "updated_at": "2026-03-27T10:00:00+00:00",
            "completed_at": "2026-03-27T10:00:00+00:00",
            "last_error": "Missing scaffold.",
            "requeue_count": 0,
        }
    )
    state["story_state"]["2"].update(
        {
            "status": "done",
            "updated_at": "2026-03-27T10:05:00+00:00",
            "completed_at": "2026-03-27T10:05:00+00:00",
        }
    )
    save_project_state(config, project["id"], state)

    reopened = requeue_recoverable_stuck_stories(config, project["id"])
    repaired = load_project_state(config, project["id"])

    assert reopened == [1]
    assert repaired["status"] == "running"
    assert repaired["last_error"] is None
    assert repaired["story_state"]["1"]["status"] == "open"
    assert repaired["story_state"]["1"]["iteration"] == 0
    assert repaired["story_state"]["1"]["last_error"] is None
    assert repaired["story_state"]["1"]["requeue_count"] == 1


def test_build_project_detail_resolves_launch_profile_team_and_connectors(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "frontend-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Frontend Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Frontend Project",
            "stories": [
                {
                    "id": 1,
                    "title": "Build dashboard shell",
                    "description": "Create the main UI shell and verify in browser.",
                    "tags": ["frontend", "ui"],
                    "role": "frontend_worker",
                }
            ],
        }
    )
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state["launch_profile"] = {
        "preset": "team",
        "story_execution_mode": "team",
        "project_concurrency_mode": "sequential",
        "max_parallel_stories": 1,
    }
    save_project_state(config, project["id"], state)

    detail = build_project_detail(config, project["id"])

    assert detail["launch_profile"]["preset"] == "team"
    story = detail["stories"][0]
    assert story["team_mode"] == "team"
    assert story["story_pipeline"] == ["research", "implement", "review"]
    assert story["review_phases"] == ["security", "architecture", "tests"]
    assert [entry["stage"] for entry in story["pipeline_state"]] == ["research", "implement", "review"]
    assert any(member["execution_role"] == "specialist" for member in story["team_members"])
    assert any(connector["id"] == "browser_devtools" for connector in story["connector_activation"])


def test_discoveries_are_recorded_and_shared_in_story_context(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "discovery-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Discovery Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Discovery Project",
            "stories": [
                {"id": 1, "title": "Research", "description": "Study the API"},
                {"id": 2, "title": "Implement", "description": "Build the integration"},
            ],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")

    recorded = record_discovery_markers(
        config,
        project["id"],
        extract_structured_discoveries(
            """
            ## Warnings
            - API rate limit is aggressive under burst traffic

            ## Constraints
            - OAuth redirect URI must be pre-registered

            ## Intents
            - Reuse the existing provider session store
            """,
            story_id=1,
            source="specialist",
        ),
    )

    assert [marker["kind"] for marker in recorded] == ["warning", "constraint", "intent"]

    state = load_project_state(config, project["id"])
    shared_context = build_story_discovery_context(state, story_id=2)
    assert len(shared_context) == 3
    assert any(marker["kind"] == "constraint" for marker in shared_context)

    detail = build_project_detail(config, project["id"])
    implementation_story = next(story for story in detail["stories"] if story["id"] == 2)
    assert len(implementation_story["discoveries"]) == 3


def test_build_project_detail_includes_story_ownership_and_checkout(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "leased-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Leased Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Leased Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state["story_state"]["1"]["ownership"] = {"role": "coordinator", "owner": "run:123", "acquired_at": "2026-03-29T00:00:00+00:00"}
    state["story_state"]["1"]["checkout"] = {"mode": "worktree", "path": str(project_dir.parent / "leased-project-story-1"), "branch_name": "story-1"}
    save_project_state(config, project["id"], state)

    detail = build_project_detail(config, project["id"])

    assert detail["stories"][0]["ownership"]["owner"] == "run:123"
    assert detail["stories"][0]["checkout"]["branch_name"] == "story-1"
    assert detail["stories"][0]["github_pr"]["head_branch"].startswith("autopilot/leased-project/story-1-")
    assert "budget_policy" in detail
    assert "budget_usage" in detail
    assert "cost_usage" in detail
    assert detail["stories"][0]["cost"]["invocations"] == 0


def test_update_project_budget_policy_persists_changes(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "budgeted-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Budgeted Project", project_path=project_dir)
    prd = normalize_prd({"title": "Budgeted Project", "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}]})
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")

    policy = update_project_budget_policy(
        config,
        project["id"],
        project_max_worker_iterations=12,
        auto_pause_on_exhaustion=False,
    )
    state = load_project_state(config, project["id"])

    assert policy["project_max_worker_iterations"] == 12
    assert state["budget_policy"]["auto_pause_on_exhaustion"] is False


def test_auto_pause_project_run_marks_project_paused(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "paused-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Paused Project", project_path=project_dir)
    prd = normalize_prd({"title": "Paused Project", "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}]})
    save_project_prd(project, prd)
    state = ensure_project_state(config, project, seed_mode="new")
    state["pid"] = 1234
    state["status"] = "running"
    save_project_state(config, project["id"], state)

    auto_pause_project_run(config, project["id"], message="Runtime budget exhausted.", story_id=1)
    paused = load_project_state(config, project["id"])

    assert paused["status"] == "paused"
    assert paused["paused"] is True
    assert paused["last_error"] == "Runtime budget exhausted."


def test_emit_project_event_dispatches_notifications_when_configured(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "notify-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Notify Project", project_path=project_dir)
    prd = normalize_prd({"title": "Notify Project", "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}]})
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")

    captured: dict[str, object] = {}

    def fake_dispatch(*args, **kwargs):
        captured["project_entry"] = kwargs["project_entry"]
        captured["story_title"] = kwargs["story_title"]
        captured["event"] = kwargs["event_record"]["event"]
        return True

    monkeypatch.setattr("autopilot.core.notifiers.dispatch_project_event_notification", fake_dispatch)

    emit_project_event(
        config,
        project["id"],
        event="story_stuck",
        status="stuck",
        message="Still blocked.",
        story_id=1,
    )

    assert captured["project_entry"]["id"] == project["id"]
    assert captured["story_title"] == "Bootstrap"
    assert captured["event"] == "story_stuck"


@patch("autopilot.core.project_store.subprocess.Popen")
@patch("autopilot.core.project_store.init_ralph_project")
@patch("autopilot.core.project_store.check_ralph_installed")
def test_launch_project_run_initializes_ralph_before_background_run(
    mock_check_ralph: MagicMock,
    mock_init_ralph: MagicMock,
    mock_popen: MagicMock,
    tmp_path: Path,
) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "launch-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Launch Project", project_path=project_dir)
    prd = normalize_prd(
        {
            "title": "Launch Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")

    mock_check_ralph.return_value = True
    mock_init_ralph.return_value = True
    mock_popen.return_value = MagicMock(pid=43210)

    launched, log_path, message = launch_project_run(config, project["id"])

    assert launched is True
    assert log_path is not None
    assert "Background run started" in message
    mock_init_ralph.assert_called_once_with(project_dir)
    popen_cmd = mock_popen.call_args.args[0]
    assert "autopilot run" in popen_cmd[-1]
    assert "--headless" in popen_cmd[-1]
    assert "autopilot init" not in popen_cmd[-1]
