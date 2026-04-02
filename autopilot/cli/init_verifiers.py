"""CLI command: `autopilot init-verifiers`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.verification_bootstrap import VerificationBootstrapError, build_verification_bootstrap

console = Console()


def _config_path() -> Path:
    return Path.home() / ".autopilot" / "config.yaml"


def _render_verification_bootstrap(payload: dict[str, object]) -> None:
    console.print(Panel("[bold]Verifier Bootstrap[/bold]"))
    console.print(f"Project path: {payload.get('project_path')}")
    if str(payload.get("project_id") or "").strip():
        console.print(f"Project id: [cyan]{payload.get('project_id')}[/cyan]")
    if bool(payload.get("artifact_written")):
        console.print(f"Artifact: {payload.get('artifact_path')}")

    repo = dict(payload.get("repo") or {})
    tooling = dict(payload.get("tooling") or {})
    checks = list(payload.get("checks") or [])

    summary = Table(title="Bootstrap Summary")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Registered project", "yes" if bool(payload.get("project_registered")) else "no")
    summary.add_row("Stacks", ", ".join(str(item) for item in tooling.get("stacks") or []) or "-")
    summary.add_row("Package manager", str(tooling.get("package_manager") or "-"))
    summary.add_row("Repo", str(repo.get("github_repo") or repo.get("repo_root") or "-"))
    summary.add_row("Gate count", str(len(list(tooling.get("gates") or []))))
    summary.add_row("Check count", str(len(checks)))
    console.print(summary)

    if checks:
        checks_table = Table(title="Generated Checks")
        checks_table.add_column("Check")
        checks_table.add_column("Kind")
        checks_table.add_column("Command")
        checks_table.add_column("Tool")
        checks_table.add_column("Available")
        for check in checks:
            checks_table.add_row(
                str(check.get("name") or ""),
                str(check.get("kind") or ""),
                str(check.get("command") or ""),
                str(check.get("tool_name") or ""),
                "yes" if bool(check.get("tool_available")) else "no",
            )
        console.print(checks_table)

    recommendations = list(payload.get("recommendations") or [])
    if recommendations:
        console.print("[bold]Recommendations[/bold]")
        for recommendation in recommendations:
            console.print(f"- {recommendation}")


def init_verifiers(
    project_path: str = ".",
    *,
    project_id: str | None = None,
    write_artifact: bool = True,
    json_output: bool = False,
) -> None:
    """Bootstrap verifier checks for one checkout and persist the artifact."""

    config = load_config(_config_path())
    try:
        payload = build_verification_bootstrap(
            config,
            project_path=project_path,
            project_id=project_id,
            write_artifact=write_artifact,
        )
    except VerificationBootstrapError as exc:
        if json_output:
            typer.echo(json.dumps({"ok": False, "error": str(exc)}))
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    _render_verification_bootstrap(payload)
