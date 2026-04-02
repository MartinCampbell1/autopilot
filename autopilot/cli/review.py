"""CLI command: `autopilot review`."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.config import load_config
from autopilot.core.review_runtime import build_local_review

console = Console()


def _config_path() -> Path:
    return Path.home() / ".autopilot" / "config.yaml"


def _render_review_payload(payload: dict[str, object]) -> None:
    verdict = str(payload.get("verdict") or "PARTIAL")
    color = {"PASS": "green", "FAIL": "red", "PARTIAL": "yellow"}.get(verdict, "white")
    console.print(Panel(f"[bold {color}]VERDICT: {verdict}[/bold {color}]"))

    repo = dict(payload.get("repo") or {})
    console.print(f"Project path: {payload.get('project_path')}")
    if str(repo.get("repo_root") or "").strip():
        console.print(f"Repo root: {repo.get('repo_root')}")
    if str(repo.get("github_repo") or "").strip():
        console.print(f"GitHub repo: [cyan]{repo.get('github_repo')}[/cyan]")

    findings = list(payload.get("findings") or [])
    if findings:
        findings_table = Table(title="Findings")
        findings_table.add_column("Severity")
        findings_table.add_column("Code")
        findings_table.add_column("Message")
        findings_table.add_column("Fix")
        for finding in findings:
            findings_table.add_row(
                str(finding.get("severity") or ""),
                str(finding.get("code") or ""),
                str(finding.get("message") or ""),
                str(finding.get("fix") or ""),
            )
        console.print(findings_table)

    gates = list(payload.get("gates") or [])
    if gates:
        gates_table = Table(title="Gate Evidence")
        gates_table.add_column("Gate")
        gates_table.add_column("Result")
        gates_table.add_column("Command")
        gates_table.add_column("Semantics")
        for gate in gates:
            gates_table.add_row(
                str(gate.get("name") or ""),
                "PASS" if bool(gate.get("passed")) else "FAIL",
                str(gate.get("cmd") or ""),
                str(gate.get("exit_semantics") or ""),
            )
        console.print(gates_table)

    checks = list(payload.get("checks") or [])
    if checks:
        checks_table = Table(title="Checks")
        checks_table.add_column("Check")
        checks_table.add_column("Status")
        checks_table.add_column("Command")
        for check in checks:
            checks_table.add_row(
                str(check.get("name") or ""),
                str(check.get("status") or ""),
                str(check.get("command") or ""),
            )
        console.print(checks_table)


def review(
    project_path: str = ".",
    *,
    project_id: str | None = None,
    base_branch: str | None = None,
    json_output: bool = False,
) -> None:
    """Run a structured local review against the current checkout."""

    config = load_config(_config_path())
    payload = build_local_review(
        config,
        project_path=project_path,
        project_id=project_id,
        base_branch=base_branch,
    )
    if json_output:
        typer.echo(json.dumps(payload))
    else:
        _render_review_payload(payload)

    if str(payload.get("verdict") or "").upper() == "FAIL":
        raise typer.Exit(code=1)
