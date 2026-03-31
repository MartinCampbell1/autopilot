"""CLI helpers for explicit execution-plane preview/apply flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.agent_action_runs import get_agent_action_batch_run
from autopilot.core.config import load_config
from autopilot.core.execution_plane import (
    execute_execution_plane_agent_actions,
    execute_execution_plane_orchestrator_session_actions,
)

console = Console()
DEFAULT_CONTROL_ACTOR = "cli-control-plane"


def _config():
    return load_config(Path.home() / ".autopilot" / "config.yaml")


def _string_array(value: Any) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _string_value(value: Any, fallback: str = "") -> str:
    return str(value).strip() if str(value).strip() else fallback


def _int_value(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _render_batch_run_payload(payload: dict[str, Any], *, heading: str) -> None:
    run = dict(payload.get("run") or {})
    diff_summary = dict(payload.get("diff_summary") or {})
    command_counts = dict(diff_summary.get("command_counts") or {})

    console.print(Panel.fit(f"[bold]{heading}[/bold]"))
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Run", _string_value(run.get("id"), "-"))
    table.add_row("Preview", _string_value(payload.get("preview_id"), _string_value(run.get("preview_id"), "-")))
    table.add_row("Status", _string_value(payload.get("status"), "-"))
    table.add_row("Apply Mode", _string_value(payload.get("apply_mode"), _string_value(run.get("apply_mode"), "-")))
    table.add_row("Approval Required", "yes" if bool(payload.get("approval_required")) else "no")
    table.add_row("Artifact", _string_value(payload.get("artifact_ref"), _string_value(run.get("artifact_ref"), "-")))
    table.add_row(
        "Selection",
        f"{int(diff_summary.get('selected_count') or run.get('summary', {}).get('selected_count') or 0)} selected",
    )
    table.add_row(
        "Processed",
        f"{int(diff_summary.get('processed_count') or run.get('summary', {}).get('processed_count') or 0)} processed",
    )
    console.print(table)

    if command_counts:
        commands = Table(title="Command Breakdown")
        commands.add_column("Command")
        commands.add_column("Count", justify="right")
        for command, count in sorted(command_counts.items()):
            commands.add_row(str(command), str(count))
        console.print(commands)


def preview_actions(
    session_id: str,
    *,
    actor: str = DEFAULT_CONTROL_ACTOR,
    reason: str = "",
    approval_required: bool = False,
    policy_profile: str | None = None,
    limit: int = 20,
    json_output: bool = False,
) -> None:
    """Preview safe or approval-gated session actions without applying them."""

    config = _config()
    resolved_profile = (
        policy_profile
        or ("budget_maintenance_with_high_priority_escalation" if approval_required else "safe_budget_maintenance")
    )
    try:
        payload = execute_execution_plane_orchestrator_session_actions(
            config,
            session_id,
            actor=actor,
            mode="auto",
            reason=reason,
            policy_profile=resolved_profile,
            dry_run=True,
            actionable_only=True,
            command_requires_approval=approval_required,
            limit=limit,
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    if json_output:
        typer.echo(json.dumps({"session_id": session_id, **payload}, indent=2, ensure_ascii=False))
        return
    _render_batch_run_payload({"session_id": session_id, **payload}, heading=f"Session Preview {session_id}")


def apply_preview(
    preview_id: str,
    *,
    actor: str = DEFAULT_CONTROL_ACTOR,
    reason: str = "",
    json_output: bool = False,
) -> None:
    """Apply or escalate a previously recorded preview run."""

    config = _config()
    preview = get_agent_action_batch_run(config, preview_id)
    if preview is None:
        console.print(f"[red]Preview run {preview_id} not found.[/red]")
        raise typer.Exit(1)
    if not preview.dry_run:
        console.print(f"[red]Run {preview_id} is not a preview run.[/red]")
        raise typer.Exit(1)

    selected_action_keys = _string_array((preview.selection or {}).get("selected_action_keys"))
    if not selected_action_keys:
        console.print(f"[red]Preview run {preview_id} has no selected action keys to apply.[/red]")
        raise typer.Exit(1)

    payload_kwargs = {
        "action_keys": selected_action_keys,
        "preview_id": _string_value(preview.preview_id, preview.id),
        "actor": actor,
        "mode": _string_value(preview.mode, "auto"),
        "reason": reason.strip()
        or (
            f"CLI requested approval from preview {preview_id}"
            if preview.approval_required
            else f"CLI applied preview {preview_id}"
        ),
        "policy_profile": _string_value(preview.policy_profile) or None,
        "limit": max(len(selected_action_keys), _int_value((preview.selection or {}).get("limit"), 20)),
        "include_non_executable": bool((preview.selection or {}).get("include_non_executable", False)),
        "continue_on_error": True,
    }

    try:
        if preview.orchestrator_session_id:
            payload = execute_execution_plane_orchestrator_session_actions(
                config,
                preview.orchestrator_session_id,
                dry_run=False,
                **payload_kwargs,
            )
            rendered: dict[str, Any] = {"session_id": preview.orchestrator_session_id, **payload}
        else:
            payload = execute_execution_plane_agent_actions(
                config,
                orchestrator_session_id="",
                dry_run=False,
                **payload_kwargs,
            )
            rendered = payload
    except (KeyError, ValueError, RuntimeError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(rendered, indent=2, ensure_ascii=False))
        return
    _render_batch_run_payload(rendered, heading=f"Applied Preview {preview_id}")
