"""CLI command: `autopilot trace`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.config import load_config
from autopilot.core.project_store import get_project_entry
from autopilot.core.monitoring.traces import build_trace_replay
from autopilot.core.run_trace import build_trace_summary, read_trace_entries

console = Console()


def trace(
    project_path: str = ".",
    project_id: str | None = None,
    limit: int = 50,
    json_output: bool = False,
    *,
    story_id: int | None = None,
    run_id: str | None = None,
) -> None:
    """Inspect the structured runtime trace for one project."""
    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    project = None
    if project_id:
        project = get_project_entry(config, project_id=project_id, include_archived=True)
    else:
        project = get_project_entry(
            config,
            project_path=Path(project_path).expanduser().resolve(),
            include_archived=True,
        )
    if project is None:
        console.print("[red]Project not found in the Autopilot registry.[/red]")
        raise typer.Exit(1)

    entries = read_trace_entries(config, project["id"], limit=limit if limit > 0 else None)
    replay = build_trace_replay(entries, story_id=story_id, run_id=run_id, limit=limit if limit > 0 else None)
    payload = {
        "project_id": project["id"],
        "project_name": project["name"],
        "project_path": project["path"],
        "summary": build_trace_summary(entries),
        "replay": replay,
        "entries": replay["entries"] if (story_id is not None or run_id) else entries,
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    console.print(f"[bold]Trace[/bold] - {project['name']}")
    console.print(f"{payload['summary']['entry_count']} entries")
    if not replay["entries"]:
        console.print("[yellow]No trace entries yet.[/yellow]")
        return

    for entry in replay["entries"][-10:]:
        label = str(entry.get("kind") or "entry")
        timestamp = str(entry.get("timestamp") or "")
        story = f" story #{entry['story_id']}" if entry.get("story_id") not in (None, "") else ""
        status = str(entry.get("status") or entry.get("event") or "")
        run_label = f" [{entry['run_id']}]" if entry.get("run_id") else ""
        message = str(entry.get("message") or entry.get("critic_feedback") or "")
        suffix = f" · {status}" if status else ""
        console.print(f"[cyan]{timestamp}[/cyan] {label}{run_label}{story}{suffix}")
        if message:
            console.print(f"  {message[:240]}")
