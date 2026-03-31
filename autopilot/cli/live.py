"""CLI command: `autopilot live`."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import AutopilotConfig, load_config
from autopilot.core.project_store import build_project_summary, load_project_state, load_projects_registry

console = Console()


def _tail_events(path: Path, *, limit: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text().splitlines()[-limit:]
    except Exception:
        return []

    events: list[dict[str, Any]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _account_table(account_mgr: AccountManager) -> Table:
    table = Table(title="Accounts")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Cooldown")
    table.add_column("Requests")

    for provider in ("codex", "claude", "gemini"):
        pool = account_mgr.pool_status(provider)
        if not pool:
            continue
        available = sum(1 for item in pool if item["available"])
        cooldown = sum(1 for item in pool if item["cooldown_remaining_sec"] > 0)
        requests = sum(int(item["requests_made"]) for item in pool)
        table.add_row(provider, f"{available}/{len(pool)}", str(cooldown), str(requests))
    if table.row_count == 0:
        table.add_row("-", "0/0", "0", "0")
    return table


def _projects_table(config: AutopilotConfig) -> tuple[Table, Table]:
    projects_table = Table(title="Projects")
    projects_table.add_column("Project")
    projects_table.add_column("Status")
    projects_table.add_column("Progress")
    projects_table.add_column("Current")
    projects_table.add_column("Last")

    runs_table = Table(title="Active Stories / Runs")
    runs_table.add_column("Project")
    runs_table.add_column("Story")
    runs_table.add_column("Iteration")
    runs_table.add_column("Worker")
    runs_table.add_column("Critic")

    projects = load_projects_registry(config, include_archived=False)
    if not projects:
        projects_table.add_row("No projects", "-", "-", "-", "-")
        runs_table.add_row("No active stories", "-", "-", "-", "-")
        return projects_table, runs_table

    summaries = [build_project_summary(config, project) for project in projects]
    summaries.sort(
        key=lambda item: (
            item["status"] not in {"running", "paused"},
            item.get("last_activity_at") or "",
            item["name"].lower(),
        ),
        reverse=True,
    )
    active_rows = 0
    for summary in summaries:
        projects_table.add_row(
            str(summary["name"]),
            f"{summary['status']}{' (paused)' if summary.get('paused') else ''}",
            f"{summary['stories_done']}/{summary['stories_total']}",
            str(summary.get("current_story_title") or "-"),
            str(summary.get("last_message") or "-")[:48],
        )
        if summary["status"] == "running" and summary.get("current_story_id") is not None:
            state = load_project_state(config, str(summary["id"]))
            story_state = (state.get("story_state") or {}).get(str(summary["current_story_id"]), {})
            runs_table.add_row(
                str(summary["name"]),
                str(summary.get("current_story_title") or summary["current_story_id"]),
                str(story_state.get("iteration") or state.get("current_iteration") or 0),
                str(story_state.get("agent") or state.get("active_worker") or "-"),
                str(story_state.get("critic") or state.get("active_critic") or "-"),
            )
            active_rows += 1

    if active_rows == 0:
        runs_table.add_row("No active stories", "-", "-", "-", "-")
    return projects_table, runs_table


def _events_table(config: AutopilotConfig) -> Table:
    table = Table(title="Recent Events")
    table.add_column("Time")
    table.add_column("Project")
    table.add_column("Event")
    table.add_column("Message")

    events = _tail_events(config.events_log_path)
    if not events:
        table.add_row("-", "-", "-", "No events yet")
        return table

    for event in reversed(events):
        timestamp = str(event.get("timestamp") or "")
        table.add_row(
            timestamp[-8:] if len(timestamp) >= 8 else timestamp,
            str(event.get("project_id") or "-"),
            str(event.get("event") or "-"),
            str(event.get("message") or "-")[:56],
        )
    return table


def render_live_snapshot(config: AutopilotConfig) -> Group:
    account_mgr = AccountManager(profiles_dir=config.profiles_dir, cooldown_base=config.cooldown_base_sec)
    account_mgr.discover()
    projects_table, runs_table = _projects_table(config)
    return Group(
        Panel(f"[bold]Autopilot Live[/bold]\nHome: {config.autopilot_home}", border_style="blue"),
        _account_table(account_mgr),
        projects_table,
        runs_table,
        _events_table(config),
    )


def live(
    refresh_sec: float = 2.0,
    *,
    once: bool = False,
) -> None:
    """Render an SSH-friendly live view of accounts, projects, and active stories."""

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    if once:
        console.print(render_live_snapshot(config))
        return

    refresh_sec = max(0.5, float(refresh_sec))
    with Live(render_live_snapshot(config), console=console, refresh_per_second=max(1, int(1 / refresh_sec))) as view:
        try:
            while True:
                time.sleep(refresh_sec)
                view.update(render_live_snapshot(config))
        except KeyboardInterrupt:
            return
