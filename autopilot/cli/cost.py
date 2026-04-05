"""CLI command: `autopilot cost`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.config import load_config
from autopilot.core.project_store import build_project_detail, get_project_entry

console = Console()


def cost(
    project_path: str = ".",
    project_id: str | None = None,
    json_output: bool = False,
) -> None:
    """Inspect cost telemetry for one project."""

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
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

    detail = build_project_detail(config, project["id"])
    monitoring = dict(detail.get("monitoring") or {})
    payload = {
        "project_id": project["id"],
        "project_name": project["name"],
        "project_path": project["path"],
        "cost_usage": detail.get("cost_usage") or {},
        "monitoring": {
            "cost": monitoring.get("cost") or {},
            "latest_run": monitoring.get("latest_run") or {},
            "benchmarks": monitoring.get("benchmarks") or {},
            "regressions": monitoring.get("regressions") or {},
        },
    }
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    cost_summary = dict((monitoring.get("cost") or {}))
    project_cost = dict(cost_summary.get("project") or {})
    run_cost = dict(cost_summary.get("run") or {})
    console.print(f"[bold]Cost[/bold] - {project['name']}")
    console.print(
        "Project total: "
        f"${float(project_cost.get('estimated_cost_usd') or 0.0):.6f} · "
        f"{int(project_cost.get('total_tokens') or 0)} tokens"
    )
    console.print(
        "Current run: "
        f"${float(run_cost.get('estimated_cost_usd') or 0.0):.6f} · "
        f"{int(run_cost.get('total_tokens') or 0)} tokens"
    )

    top_stories = list(cost_summary.get("top_stories") or [])[:3]
    if top_stories:
        console.print("\n[bold]Top stories[/bold]")
        for story in top_stories:
            console.print(
                f"- Story #{story.get('story_id')}: "
                f"${float(story.get('estimated_cost_usd') or 0.0):.6f} · "
                f"{int(story.get('total_tokens') or 0)} tokens"
            )

    latest_run = dict((monitoring.get("latest_run") or {}))
    if latest_run:
        console.print("\n[bold]Latest run[/bold]")
        console.print(
            f"{latest_run.get('status') or 'unknown'} · "
            f"{int(latest_run.get('iteration_count') or 0)} iterations · "
            f"{int(latest_run.get('failure_count') or 0)} failures"
        )
