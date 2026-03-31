"""CLI command: `autopilot doctor [project-path]`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.account_diagnostics import build_provider_setup_snapshot
from autopilot.core.account_manager import AccountManager
from autopilot.core.config import load_config
from autopilot.core.onboarding import detect_project_tooling

console = Console()


def _doctor_report(
    *,
    config_path: Path,
    project_path: Path,
    refresh: bool,
) -> dict[str, Any]:
    config = load_config(config_path)
    manager = AccountManager(profiles_dir=config.profiles_dir)
    manager.discover()

    provider_snapshot = build_provider_setup_snapshot(config, manager, refresh=refresh)
    project_report = detect_project_tooling(project_path)

    recommendations: list[str] = []
    for provider, payload in provider_snapshot["providers"].items():
        cli_status = (payload.get("cli_probe") or {}).get("status")
        if cli_status != "ready":
            recommendations.append(f"Install or repair the {provider} CLI.")
        if not payload.get("source_session_available") and payload.get("managed_profile_count", 0) == 0:
            recommendations.append(f"Log into {provider} and import at least one managed profile.")

    if not project_report.prd_present:
        recommendations.append("Run `autopilot init` to create a starter PRD and register the project.")
    if not project_report.gates:
        recommendations.append("Add at least one reproducible build, test, or lint command for quality gates.")

    return {
        "config": {
            "path": str(config_path),
            "exists": config_path.exists(),
            "autopilot_home": str(config.autopilot_home),
            "profiles_dir": str(config.profiles_dir),
            "projects_yaml_path": str(config.projects_yaml_path),
        },
        "providers": provider_snapshot,
        "project": project_report.to_dict(),
        "recommendations": recommendations,
    }


def doctor(
    project_path: str = typer.Argument(".", help="Project path to inspect for onboarding and gates."),
    refresh: bool = typer.Option(False, "--refresh", help="Refresh provider diagnostics probes."),
    json_output: bool = typer.Option(False, "--json", help="Emit the doctor report as JSON."),
) -> None:
    """Inspect provider readiness plus local project onboarding state."""
    config_path = Path.home() / ".autopilot" / "config.yaml"
    project = Path(project_path).expanduser().resolve()
    report = _doctor_report(
        config_path=config_path,
        project_path=project,
        refresh=refresh,
    )

    if json_output:
        console.print_json(json.dumps(report))
        return

    config_payload = report["config"]
    console.print(Panel("[bold]Autopilot Doctor[/bold]"))
    console.print(f"Config: {config_payload['path']}")
    console.print(f"Autopilot home: {config_payload['autopilot_home']}")
    console.print(f"Profiles dir: {config_payload['profiles_dir']}")

    provider_table = Table(title="Providers")
    provider_table.add_column("Provider")
    provider_table.add_column("CLI")
    provider_table.add_column("Imported")
    provider_table.add_column("Source Session")
    provider_table.add_column("Ready Profiles")
    provider_table.add_column("Notes")
    for provider, payload in report["providers"]["providers"].items():
        cli_probe = payload.get("cli_probe") or {}
        provider_table.add_row(
            provider,
            str(cli_probe.get("status", "unknown")),
            str(payload.get("managed_profile_count", 0)),
            "yes" if payload.get("source_session_available") else "no",
            str(payload.get("ready_profile_count", 0)),
            str(cli_probe.get("summary", "")),
        )
    console.print(provider_table)

    project_payload = report["project"]
    project_table = Table(title=f"Project: {project_payload['path']}")
    project_table.add_column("Field")
    project_table.add_column("Value")
    project_table.add_row("Exists", "yes" if project_payload["exists"] else "no")
    project_table.add_row("Git", "yes" if project_payload["git_present"] else "no")
    project_table.add_row("PRD", "yes" if project_payload["prd_present"] else "no")
    project_table.add_row("Ralph", "yes" if project_payload["ralph_initialized"] else "no")
    project_table.add_row("Stacks", ", ".join(project_payload["stacks"]) or "none detected")
    project_table.add_row("Package manager", project_payload["package_manager"] or "-")
    project_table.add_row("Detected files", ", ".join(project_payload["files_found"]) or "-")
    console.print(project_table)

    gates = project_payload["gates"]
    if gates:
        gates_table = Table(title="Detected Gates")
        gates_table.add_column("Name")
        gates_table.add_column("Command")
        gates_table.add_column("Source")
        for gate in gates:
            gates_table.add_row(str(gate["name"]), str(gate["cmd"]), str(gate.get("source", "")))
        console.print(gates_table)

    notes = list(project_payload["notes"]) + list(report["recommendations"])
    if notes:
        console.print(Panel("\n".join(f"- {note}" for note in notes), title="Next Steps"))
