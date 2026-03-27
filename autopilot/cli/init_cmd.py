"""CLI command: `autopilot init <project-path>`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.loop_runner import check_ralph_installed, init_ralph_project

console = Console()


def init(project_path: str = typer.Argument(help="Path to the project directory")) -> None:
    """Initialize a project for autopilot and Ralph."""
    project = Path(project_path).expanduser().resolve()

    if not project.exists():
        console.print(f"[red]Directory not found: {project}[/red]")
        raise typer.Exit(1)

    if not check_ralph_installed():
        console.print("[red]Ralph is not installed. Run: npm i -g @iannuttall/ralph[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Initializing autopilot in {project.name}...[/bold]")

    if not init_ralph_project(project):
        console.print("[red]Ralph install failed.[/red]")
        raise typer.Exit(1)

    ralph_dir = project / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    (ralph_dir / "progress.md").write_text("# Progress\n\n")
    (ralph_dir / "guardrails.md").write_text("# Guardrails\n\nDo not repeat these mistakes:\n\n")

    console.print("[green]Done![/green] Project initialized.")
    console.print("\nNext steps:")
    console.print("  1. Create PRD: ralph prd")
    console.print(f"  2. Run: autopilot run {project}")
