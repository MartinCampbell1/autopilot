"""CLI command: `autopilot ship`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.shipping import ShippingError, ship_repo

console = Console()


def _render_ship_payload(payload: dict[str, object]) -> None:
    console.print(Panel("[bold]Autopilot Ship[/bold]"))
    console.print(f"Repo root: {payload.get('repo_root')}")
    console.print(f"GitHub repo: [cyan]{payload.get('github_repo')}[/cyan]")

    summary = Table(title="Ship Summary")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Branch", str(payload.get("branch") or ""))
    summary.add_row("Base branch", str(payload.get("base_branch") or ""))
    summary.add_row("Dirty before ship", "yes" if bool(payload.get("dirty_before_ship")) else "no")
    summary.add_row("Commit created", "yes" if bool(payload.get("commit_created")) else "no")
    summary.add_row("PR created", "yes" if bool(payload.get("pr_created")) else "no")
    console.print(summary)

    pull_request = dict(payload.get("pull_request") or {})
    if pull_request:
        pr_table = Table(title="Pull Request")
        pr_table.add_column("Field")
        pr_table.add_column("Value")
        pr_table.add_row("Number", str(pull_request.get("number") or ""))
        pr_table.add_row("Title", str(pull_request.get("title") or ""))
        pr_table.add_row("URL", str(pull_request.get("url") or ""))
        pr_table.add_row("State", str(pull_request.get("state") or ""))
        pr_table.add_row("Draft", "yes" if bool(pull_request.get("draft")) else "no")
        console.print(pr_table)


def ship(
    project_path: str = ".",
    *,
    message: str | None = None,
    title: str | None = None,
    body: str | None = None,
    draft: bool = False,
    base_branch: str | None = None,
    json_output: bool = False,
) -> None:
    """Commit, push, and open or reuse a PR for the current branch."""

    try:
        payload = ship_repo(
            Path(project_path).expanduser().resolve(),
            commit_message=message,
            title=title,
            body=body,
            draft=draft,
            base_branch=base_branch,
        )
    except ShippingError as exc:
        if json_output:
            typer.echo(json.dumps({"ok": False, "error": str(exc)}))
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload))
        return
    _render_ship_payload(payload)
