"""Tests for project registry/runtime state helpers."""

import json
from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    ensure_project_state,
    get_project_entry,
    load_project_state,
    migrate_projects_registry,
    normalize_prd,
    register_project,
    save_project_prd,
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
