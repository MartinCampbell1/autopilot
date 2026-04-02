"""CLI command: `autopilot resume`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.project_store import resume_project_run
from autopilot.core.session_history import build_resume_discovery

console = Console()


def _config_path() -> Path:
    return Path.home() / ".autopilot" / "config.yaml"


def _render_resume_discovery(payload: dict[str, object]) -> None:
    console.print(Panel("[bold]Resume Discovery[/bold]"))
    console.print(f"Current path: {payload.get('current_path')}")
    current_repo_key = str(payload.get("current_repo_key") or "").strip()
    if current_repo_key:
        console.print(f"Repo identity: [cyan]{current_repo_key}[/cyan]")

    projects = list(payload.get("projects") or [])
    if projects:
        table = Table()
        table.add_column("Project")
        table.add_column("Relation")
        table.add_column("Status")
        table.add_column("Resume")
        table.add_column("Path")
        for project in projects:
            table.add_row(
                str(project.get("name") or ""),
                str(project.get("relation") or ""),
                str(project.get("status") or "idle"),
                "yes" if bool(project.get("can_resume")) else "running",
                str(project.get("path") or ""),
            )
        console.print(table)
    else:
        console.print("No registered projects found.")

    extra_paths = list(payload.get("unregistered_same_repo_paths") or [])
    if extra_paths:
        console.print("[bold]Known Same-Repo Paths[/bold]")
        for extra_path in extra_paths:
            console.print(f"- {extra_path}")


def resume(
    project_path: str = ".",
    *,
    project_id: str | None = None,
    json_output: bool = False,
) -> None:
    """Inspect resume candidates or resume one known project."""

    config = load_config(_config_path())
    if project_id:
        launched, log_path, message = resume_project_run(config, project_id)
        payload = {
            "project_id": project_id,
            "launched": bool(launched),
            "log_path": str(log_path) if log_path else None,
            "message": message,
        }
        if json_output:
            typer.echo(json.dumps(payload))
            return
        console.print(message)
        if log_path:
            console.print(f"Log: {log_path}")
        return

    payload = build_resume_discovery(config, project_path)
    if json_output:
        typer.echo(json.dumps(payload))
        return
    _render_resume_discovery(payload)
