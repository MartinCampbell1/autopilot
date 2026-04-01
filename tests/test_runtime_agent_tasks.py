"""Tests for async runtime-agent task persistence and lifecycle syncing."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    ensure_project_state,
    load_project_state,
    normalize_prd,
    register_project,
    save_project_prd,
    save_project_state,
)
from autopilot.core.runtime_agent_tasks import (
    create_or_reuse_runtime_agent_task,
    list_runtime_agent_tasks,
    refresh_runtime_agent_task,
)


def _seed_project(config: AutopilotConfig, project_path: Path) -> dict[str, object]:
    project_path.mkdir(parents=True, exist_ok=True)
    project = register_project(config, name="Async Project", project_path=project_path)
    prd = normalize_prd(
        {
            "title": "Async Project",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start"}],
        }
    )
    save_project_prd(project, prd)
    ensure_project_state(config, project, seed_mode="new")
    return project


def test_runtime_agent_task_stays_running_until_project_state_advances(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="launch",
        actor="founderos",
        reason="Launch background work.",
        orchestrator_session_id="ors_async_1",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(config.autopilot_home / "logs" / "async.log"),
    )

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "running"
    assert refreshed.result_summary == ""
    assert refreshed.placeholder_result

    stored = list_runtime_agent_tasks(
        config,
        project_id=str(project["id"]),
        orchestrator_session_id="ors_async_1",
        runtime_agent_id="proj:1:worker:a",
        command="launch",
    )
    assert len(stored) == 1
    assert stored[0].id == task.id


def test_runtime_agent_task_transitions_to_completed_with_terminal_summary(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project = _seed_project(config, tmp_path / "async-task-terminal-project")

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=str(project["id"]),
        command="resume",
        actor="founderos",
        reason="Resume background work.",
        runtime_agent_ids=["proj:1:worker:a"],
        output_path=str(config.autopilot_home / "logs" / "resume.log"),
    )

    state = load_project_state(config, str(project["id"]))
    state["status"] = "completed"
    state["paused"] = False
    state["finished_at"] = "2026-04-01T12:34:56+00:00"
    state["log_path"] = str(config.autopilot_home / "logs" / "resume.log")
    save_project_state(config, str(project["id"]), state)

    refreshed = refresh_runtime_agent_task(config, task.id)

    assert refreshed.status == "completed"
    assert refreshed.placeholder_result == ""
    assert refreshed.result_summary == "Background run completed."
    assert refreshed.result_payload["project_status"] == "completed"
    assert refreshed.completed_at == "2026-04-01T12:34:56+00:00"
