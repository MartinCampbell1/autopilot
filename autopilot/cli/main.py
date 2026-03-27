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
