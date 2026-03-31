"""CLI command: `autopilot dashboard`."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import time
import webbrowser

import typer
from rich.console import Console

console = Console()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    frontend_port: int = typer.Option(3020, help="Frontend server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
) -> None:
    """Start the dashboard frontend and API server."""
    repo_root = _repo_root()
    dashboard_dir = repo_root / "dashboard"

    if not dashboard_dir.exists():
        console.print(f"[red]Dashboard directory not found: {dashboard_dir}[/red]")
        raise typer.Exit(1)

    console.print("[bold]Starting Autopilot dashboard stack...[/bold]")
    console.print(f"[dim]Frontend: http://localhost:{frontend_port}[/dim]")
    console.print(f"[dim]API: http://localhost:{port}[/dim]")

    process: subprocess.Popen[bytes] | None = None
    try:
        env = os.environ.copy()
        env["AUTOPILOT_API_PORT"] = str(port)
        env["AUTOPILOT_FRONTEND_PORT"] = str(frontend_port)

        process = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=str(dashboard_dir),
            env=env,
        )

        time.sleep(2)

        if not no_browser:
            webbrowser.open(f"http://localhost:{frontend_port}")

        console.print("[dim]Press Ctrl+C to stop[/dim]")

        process.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        if process is not None:
            process.send_signal(signal.SIGINT)
