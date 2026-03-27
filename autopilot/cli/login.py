"""CLI command: `autopilot login <provider>`."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from autopilot.core.config import load_config

console = Console()

PROVIDER_SOURCE_DIRS = {
    "codex": Path.home() / ".codex",
    "claude": Path.home(),
    "gemini": Path.home(),
}

PROVIDER_VALIDATION = {
    "codex": lambda src: (src / "auth.json").exists() or (src / "config.toml").exists(),
    "claude": lambda src: (src / ".claude").exists(),
    "gemini": lambda src: (src / ".config" / "gemini").exists() or (src / ".gemini").exists(),
}


def login(provider: str = typer.Argument(help="Provider: codex, claude, or gemini")) -> None:
    """Save a logged-in CLI session as a reusable profile."""
    if provider not in ("codex", "claude", "gemini"):
        console.print(f"[red]Unknown provider: {provider}. Use: codex, claude, gemini[/red]")
        raise typer.Exit(1)

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    provider_dir = config.profiles_dir / provider

    console.print(f"\n[bold]Autopilot Login - {provider}[/bold]\n")

    count = 0
    while True:
        console.print(
            f"[yellow]Log in to {provider} in your browser/terminal, then press Enter here...[/yellow]"
        )
        input()

        source = PROVIDER_SOURCE_DIRS[provider]
        validate = PROVIDER_VALIDATION[provider]

        if not validate(source):
            console.print(f"[red]No valid {provider} session found at {source}.[/red]")
            console.print("[dim]Make sure you're logged in and try again.[/dim]")
            continue

        provider_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(
            account_dir.name
            for account_dir in provider_dir.iterdir()
            if account_dir.is_dir() and account_dir.name.startswith("acc")
        )
        name = f"acc{len(existing) + 1}"
        destination = provider_dir / name

        if provider == "codex":
            shutil.copytree(source, destination)
        else:
            home_dir = destination / "home"
            home_dir.mkdir(parents=True)
            if provider == "claude":
                shutil.copytree(source / ".claude", home_dir / ".claude")
            elif provider == "gemini":
                for candidate in (".config/gemini", ".gemini"):
                    source_path = source / candidate
                    if source_path.exists():
                        destination_path = home_dir / candidate
                        destination_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(source_path, destination_path)

        count += 1
        console.print(f"[green]Account {name} saved.[/green] Total: {count}")

        if not typer.confirm("Add another account?", default=True):
            break

    console.print(f"\n[bold green]Done! {count} {provider} account(s) saved to {provider_dir}[/bold green]")

    table = Table(title=f"{provider} profiles")
    table.add_column("Name")
    table.add_column("Path")
    for account_dir in sorted(provider_dir.iterdir()):
        if account_dir.is_dir() and account_dir.name.startswith("acc"):
            table.add_row(account_dir.name, str(account_dir))
    console.print(table)
