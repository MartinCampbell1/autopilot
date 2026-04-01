"""Tests for the live TUI snapshot command."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console

from autopilot.cli import live as live_cli
from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    emit_project_event,
    ensure_project_state,
    register_project,
    save_project_prd,
    save_project_state,
)


class _FakeAccountManager:
    def __init__(self, profiles_dir, cooldown_base=300, config=None):
        self.profiles_dir = profiles_dir
        self.cooldown_base = cooldown_base
        self.config = config

    def discover(self) -> None:
        return None

    def pool_status(self, provider: str) -> list[dict]:
        if provider != "codex":
            return []
        return [
            {
                "name": "default",
                "available": True,
                "requests_made": 3,
                "cooldown_remaining_sec": 0,
            }
        ]


def test_live_once_renders_project_snapshot(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    project_dir = tmp_path / "live-project"
    project_dir.mkdir(parents=True)

    project = register_project(config, name="Live Project", project_path=project_dir)
    save_project_prd(
        project,
        {
            "title": "Live Project",
            "description": "Observe runtime state",
            "stories": [{"id": 1, "title": "Bootstrap", "description": "Start", "status": "open"}],
        },
    )
    state = ensure_project_state(config, project, seed_mode="new")
    state["status"] = "running"
    state["current_story_id"] = 1
    state["current_iteration"] = 2
    state["active_worker"] = "codex/default"
    state["active_critic"] = "codex/default"
    state["story_state"]["1"]["status"] = "in_progress"
    state["story_state"]["1"]["iteration"] = 2
    state["story_state"]["1"]["agent"] = "codex/default"
    state["story_state"]["1"]["critic"] = "codex/default"
    save_project_state(config, project["id"], state)
    emit_project_event(
        config,
        project["id"],
        event="iteration_started",
        status="in_progress",
        story_id=1,
        message="Iteration 2 started.",
    )

    recorded_console = Console(record=True, width=140)
    monkeypatch.setattr(live_cli, "console", recorded_console)
    monkeypatch.setattr(live_cli, "load_config", lambda path: config)
    monkeypatch.setattr(live_cli, "AccountManager", _FakeAccountManager)

    live_cli.live(once=True)

    output = recorded_console.export_text()
    assert "Autopilot Live" in output
    assert "Live Project" in output
    assert "Bootstrap" in output
    assert "Iteration 2 started." in output
