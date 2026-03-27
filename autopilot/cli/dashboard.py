"""CLI command: `autopilot dashboard`."""

from __future__ import annotations

import subprocess
import time
import webbrowser

import typer
from rich.console import Console

console = Console()


def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
) -> None:
    """Start the dashboard API server and optionally open the browser."""
    console.print(f"[bold]Starting Autopilot dashboard on port {port}...[/bold]")

    try:
        process = subprocess.Popen(
            ["uvicorn", "autopilot.api.main:app", "--port", str(port), "--host", "0.0.0.0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        time.sleep(2)

        if not no_browser:
            webbrowser.open("http://localhost:3000")

        console.print(f"[green]API running on http://localhost:{port}[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]")

        process.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")
        process.terminate()
