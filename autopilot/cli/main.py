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
    project_id: str | None = typer.Option(None, "--project-id", help="Stable project id from the dashboard"),
    headless: bool = typer.Option(False, "--headless", help="Emit machine-readable logs and a JSON summary."),
    schedule: str | None = typer.Option(None, "--schedule", help="Repeat the run on a cadence like 30m or 6h."),
    max_runs: int | None = typer.Option(None, "--max-runs", help="Stop a scheduled run after N iterations."),
) -> None:
    """Run autopilot loop on a project until all stories are done."""
    from autopilot.cli.run import run as _run

    exit_code = _run(project_path, prd, project_id, headless=headless, schedule=schedule, max_runs=max_runs)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command(name="run-all")
def run_all_projects(
    headless: bool = typer.Option(False, "--headless", help="Emit machine-readable logs and a JSON summary."),
    schedule: str | None = typer.Option(None, "--schedule", help="Repeat the run-all loop on a cadence like 30m or 6h."),
    max_runs: int | None = typer.Option(None, "--max-runs", help="Stop a scheduled run after N iterations."),
) -> None:
    """Run autopilot on all configured projects in parallel."""
    from autopilot.cli.run import run_all

    exit_code = run_all(headless=headless, schedule=schedule, max_runs=max_runs)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


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


@app.command()
def doctor(
    project_path: str = typer.Argument(".", help="Path to inspect for onboarding and gates."),
    refresh: bool = typer.Option(False, "--refresh", help="Refresh provider diagnostics probes."),
    json_output: bool = typer.Option(False, "--json", help="Emit the doctor report as JSON."),
) -> None:
    """Inspect provider readiness plus local project onboarding state."""
    from autopilot.cli.doctor import doctor as _doctor

    _doctor(project_path, refresh, json_output)


@app.command()
def trace(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    project_id: str | None = typer.Option(None, "--project-id", help="Stable project id from the dashboard."),
    limit: int = typer.Option(50, "--limit", help="Maximum number of trace entries to read."),
    json_output: bool = typer.Option(False, "--json", help="Emit the trace payload as JSON."),
) -> None:
    """Inspect the structured runtime trace for one project."""
    from autopilot.cli.trace import trace as _trace

    _trace(project_path, project_id, limit, json_output)


@app.command()
def live(
    refresh_sec: float = typer.Option(2.0, "--refresh-sec", help="Seconds between live refreshes."),
    once: bool = typer.Option(False, "--once", help="Render one snapshot and exit."),
) -> None:
    """Render an SSH-friendly live view of projects, stories, and recent events."""
    from autopilot.cli.live import live as _live

    _live(refresh_sec=refresh_sec, once=once)


@app.command(name="init")
def init_project(
    project_path: str = typer.Argument(help="Path to the project directory"),
    idea: str = typer.Option("", "--idea", help="Natural-language project idea to bootstrap into a starter spec/PRD."),
    bootstrap_only: bool = typer.Option(False, "--bootstrap-only", help="Save only the generated spec bootstrap and skip PRD generation."),
) -> None:
    """Initialize a project for autopilot."""
    from autopilot.cli.init_cmd import init as _init

    _init(project_path, idea=idea, bootstrap_only=bootstrap_only)
