"""CLI command: `autopilot context`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.context_visibility import build_context_snapshot

console = Console()


def _config_path() -> Path:
    return Path.home() / ".autopilot" / "config.yaml"


def _render_context_snapshot(payload: dict[str, object]) -> None:
    console.print(Panel("[bold]Autopilot Context[/bold]"))
    console.print(f"Project: {payload.get('project_name')} ({payload.get('project_id')})")
    console.print(f"Path: {payload.get('project_path')}")
    console.print(f"Summary: {payload.get('microcompact')}")

    status = dict(payload.get("status") or {})
    delivery = dict(payload.get("delivery") or {}).get("status") or {}
    repo = dict(payload.get("repo") or {})
    bootstrap = dict(payload.get("bootstrap") or {})
    layers = dict(payload.get("instruction_layers") or {})

    summary = Table(title="Snapshot")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Runtime status", str(status.get("status") or ""))
    summary.add_row("Current story", str(status.get("current_story_title") or ""))
    summary.add_row("Delivery", str(dict(delivery).get("status") or ""))
    summary.add_row("Repo", str(repo.get("github_repo") or repo.get("repo_key") or ""))
    summary.add_row("Known paths", str(len(list(repo.get("known_paths") or []))))
    summary.add_row(
        "Verifier bootstrap",
        "yes" if bool(dict(bootstrap.get("verification") or {}).get("artifact_exists")) else "no",
    )
    summary.add_row(
        "GitHub workflow",
        "yes" if bool(dict(bootstrap.get("github") or {}).get("workflow_exists")) else "no",
    )
    summary.add_row("Discoveries", str(dict(layers.get("discoveries") or {}).get("count") or 0))
    summary.add_row("Guardrails", "yes" if bool(dict(layers.get("guardrails") or {}).get("present")) else "no")
    console.print(summary)

    recent_events = list(payload.get("recent_events") or [])
    if recent_events:
        events_table = Table(title="Recent Events")
        events_table.add_column("When")
        events_table.add_column("Event")
        events_table.add_column("Status")
        events_table.add_column("Message")
        for event in recent_events[-8:]:
            events_table.add_row(
                str(event.get("timestamp") or ""),
                str(event.get("event") or ""),
                str(event.get("status") or ""),
                str(event.get("message") or ""),
            )
        console.print(events_table)


def context(
    project_path: str = ".",
    *,
    project_id: str | None = None,
    event_limit: int = 12,
    json_output: bool = False,
) -> None:
    """Inspect repo-aware context visibility for one project checkout."""

    config = load_config(_config_path())
    try:
        payload = build_context_snapshot(
            config,
            project_path=project_path,
            project_id=project_id,
            event_limit=event_limit,
        )
    except KeyError:
        console.print("[red]Project not found in the Autopilot registry.[/red]")
        raise typer.Exit(code=1)

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    _render_context_snapshot(payload)
