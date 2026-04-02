"""CLI command: `autopilot github`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.github_repo_setup import GitHubBootstrapError, bootstrap_github_repo

console = Console()


def _config_path() -> Path:
    return Path.home() / ".autopilot" / "config.yaml"


def _render_github_bootstrap(payload: dict[str, object]) -> None:
    console.print(Panel("[bold]Autopilot GitHub Bootstrap[/bold]"))
    console.print(f"Project path: {payload.get('project_path')}")
    console.print(f"GitHub repo: [cyan]{payload.get('github_repo')}[/cyan]")

    summary = Table(title="Bootstrap Summary")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Registered project", "yes" if bool(payload.get("project_registered")) else "no")
    summary.add_row("Authenticated", "yes" if bool(payload.get("gh_authenticated")) else "no")
    summary.add_row("Branch", str(payload.get("current_branch") or ""))
    summary.add_row("Base branch", str(payload.get("default_branch") or ""))
    summary.add_row("Workflow install", "yes" if bool(payload.get("install_workflow")) else "no")
    console.print(summary)

    workflow = dict(payload.get("workflow") or {})
    workflow_table = Table(title="Workflow")
    workflow_table.add_column("Field")
    workflow_table.add_column("Value")
    workflow_table.add_row("Path", str(workflow.get("workflow_path") or ""))
    workflow_table.add_row("Exists", "yes" if bool(workflow.get("workflow_exists")) else "no")
    workflow_table.add_row("Changed", "yes" if bool(workflow.get("changed")) else "no")
    console.print(workflow_table)

    checks = list(payload.get("checks") or [])
    if checks:
        checks_table = Table(title="Checks")
        checks_table.add_column("Check")
        checks_table.add_column("Kind")
        checks_table.add_column("Command")
        for check in checks:
            checks_table.add_row(
                str(check.get("name") or ""),
                str(check.get("kind") or ""),
                str(check.get("command") or ""),
            )
        console.print(checks_table)

    if str(payload.get("compare_url") or "").strip():
        console.print(f"Compare URL: {payload.get('compare_url')}")
    if str(payload.get("workflow_url") or "").strip():
        console.print(f"Workflow URL: {payload.get('workflow_url')}")


def github(
    project_path: str = ".",
    *,
    project_id: str | None = None,
    install_workflow: bool = True,
    overwrite: bool = False,
    json_output: bool = False,
) -> None:
    """Bootstrap GitHub workflow setup for the current checkout."""

    config = load_config(_config_path())
    try:
        payload = bootstrap_github_repo(
            config,
            project_path=project_path,
            project_id=project_id,
            install_workflow=install_workflow,
            overwrite=overwrite,
        )
    except GitHubBootstrapError as exc:
        if json_output:
            typer.echo(json.dumps({"ok": False, "error": str(exc)}))
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    _render_github_bootstrap(payload)
