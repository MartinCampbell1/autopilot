"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="autopilot",
    help="Autonomous AI programmer platform with account rotation and critic loops.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Autopilot CLI."""


@app.command()
def version() -> None:
    """Show version."""
    from autopilot import __version__

    typer.echo(f"autopilot v{__version__}")


@app.command()
def login(provider: str = typer.Argument(help="Provider: codex, claude, or gemini")) -> None:
    """Save a logged-in CLI session as a reusable profile."""
    from autopilot.cli.login import login as _login

    _login(provider)


@app.command()
def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="PRD JSON path relative to project"),
) -> None:
    """Run autopilot loop on a project until all stories are done."""
    from autopilot.cli.run import run as _run

    _run(project_path, prd)


@app.command(name="run-all")
def run_all_projects() -> None:
    """Run autopilot on all configured projects in parallel."""
    from autopilot.cli.run import run_all

    run_all()


@app.command()
def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    frontend_port: int = typer.Option(3020, help="Frontend server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
) -> None:
    """Start the Autopilot dashboard."""
    from autopilot.cli.dashboard import dashboard as _dashboard

    _dashboard(port, frontend_port, no_browser)


@app.command()
def status() -> None:
    """Show status of accounts and projects."""
    from autopilot.cli.status import status as _status

    _status()


@app.command(name="init")
def init_project(project_path: str = typer.Argument(help="Path to the project directory")) -> None:
    """Initialize a project for autopilot."""
    from autopilot.cli.init_cmd import init as _init

    _init(project_path)
