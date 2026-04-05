"""CLI command: `autopilot audit`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from autopilot.core.audit_chain import build_audit_bundle, read_jsonl_records, verify_audit_chain
from autopilot.core.config import load_config
from autopilot.core.project_store import get_project_entry
from autopilot.core.run_trace import build_trace_audit_bundle

console = Console()


def _resolve_project(project_path: str, project_id: str | None) -> tuple[dict[str, Any], Any]:
    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    if project_id:
        project = get_project_entry(config, project_id=project_id, include_archived=True)
    else:
        project = get_project_entry(
            config,
            project_path=Path(project_path).expanduser().resolve(),
            include_archived=True,
        )
    if project is None:
        console.print("[red]Project not found in the Autopilot registry.[/red]")
        raise typer.Exit(1)
    return project, config


def audit(
    project_path: str = ".",
    project_id: str | None = None,
    limit: int = 200,
    json_output: bool = False,
    *,
    story_id: int | None = None,
    run_id: str | None = None,
    include_entries: bool = True,
    export_path: str | None = None,
    events_log: bool = False,
) -> None:
    """Inspect or export the append-only audit bundle for one project or the shared events log."""

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    payload: dict[str, Any]
    project: dict[str, Any] | None = None

    if events_log:
        entries = read_jsonl_records(config.events_log_path)
        selected_entries = entries[-limit:] if limit > 0 else entries
        bundle = build_audit_bundle(
            selected_entries,
            chain_kind="events",
            config=config,
            include_entries=include_entries,
            source_verification=verify_audit_chain(entries, chain_kind="events", config=config),
            source_entry_count=len(entries),
        )
        payload = {
            "scope": "events",
            "events_log_path": str(config.events_log_path),
            "audit": bundle,
        }
    else:
        project, config = _resolve_project(project_path, project_id)
        bundle = build_trace_audit_bundle(
            config,
            str(project["id"]),
            story_id=story_id,
            run_id=run_id,
            limit=limit if limit > 0 else None,
            include_entries=include_entries,
        )
        payload = {
            "scope": "trace",
            "project_id": project["id"],
            "project_name": project["name"],
            "project_path": project["path"],
            "audit": bundle,
        }

    if export_path:
        destination = Path(export_path).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    chain = dict((payload.get("audit") or {}).get("audit_chain") or {})
    verification = dict(chain.get("verification") or {})
    source_verification = dict(chain.get("source_verification") or {})
    target_label = "Events Log" if events_log else str((project or {}).get("name") or "Project")

    console.print(f"[bold]Audit[/bold] - {target_label}")
    console.print(
        f"{chain.get('entry_count') or 0} packaged entries · "
        f"package verified={bool(verification.get('verified'))} · "
        f"source verified={bool(source_verification.get('verified'))}"
    )
    if verification.get("latest_hash"):
        console.print(f"Latest package hash: {verification['latest_hash']}")
    if export_path:
        console.print(f"Exported bundle: {Path(export_path).expanduser()}")
    if not verification.get("verified"):
        console.print(f"[yellow]Package verification errors:[/yellow] {verification.get('errors') or []}")
    if source_verification and not source_verification.get("verified"):
        console.print(f"[yellow]Source verification errors:[/yellow] {source_verification.get('errors') or []}")
