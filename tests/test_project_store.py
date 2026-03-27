"""Tests for project registry/runtime state helpers."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    ensure_project_state,
    get_project_entry,
    launch_project_run,
    load_project_state,
    migrate_projects_registry,
    normalize_prd,
    requeue_recoverable_stuck_stories,
    register_project,
    save_project_prd,
    save_project_state,
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
    assert "autopilot init" not in popen_cmd[-1]
