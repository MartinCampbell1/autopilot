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


def _dict_records(value: Any) -> list[dict[str, Any]]:
    return [item for item in (value or []) if isinstance(item, dict)]


def _dedupe_records_by_id(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        record_id = _string_value(record.get("id"))
        if not record_id or record_id in seen_ids:
            continue
        deduped.append(record)
        seen_ids.add(record_id)
    return deduped


def _render_batch_run_payload(payload: dict[str, Any], *, heading: str) -> None:
    run = dict(payload.get("run") or {})
    diff_summary = dict(payload.get("diff_summary") or {})
    command_counts = dict(diff_summary.get("command_counts") or {})
    policy_reason_counts = dict(diff_summary.get("policy_reason_counts") or {})
    why = [item for item in (diff_summary.get("why") or []) if _string_value(item)]
    results = _dict_records(payload.get("results"))
    approvals = _dedupe_records_by_id(
        [dict(result.get("approval") or {}) for result in results if isinstance(result.get("approval"), dict)]
    )
    issues = _dedupe_records_by_id(
        [dict(result.get("issue") or {}) for result in results if isinstance(result.get("issue"), dict)]
    )

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

    if policy_reason_counts:
        reasons = Table(title="Gate Reasons")
        reasons.add_column("Reason")
        reasons.add_column("Count", justify="right")
        for reason, count in sorted(policy_reason_counts.items()):
            reasons.add_row(str(reason), str(count))
        console.print(reasons)

    if why:
        console.print(Panel("\n".join(f"- {item}" for item in why[:5]), title="Why", expand=False))

    if approvals:
        approvals_table = Table(title="Approvals")
        approvals_table.add_column("Approval")
        approvals_table.add_column("Status")
        approvals_table.add_column("Action")
        approvals_table.add_column("Issue")
        for approval in approvals:
            approvals_table.add_row(
                _string_value(approval.get("id"), "-"),
                _string_value(approval.get("status"), "-"),
                _string_value(approval.get("action"), "-"),
                _string_value(approval.get("issue_id"), "-"),
            )
        console.print(approvals_table)

    if issues:
        issues_table = Table(title="Issues")
        issues_table.add_column("Issue")
        issues_table.add_column("Status")
        issues_table.add_column("Category")
        issues_table.add_column("Approval")
        for issue in issues:
            issues_table.add_row(
                _string_value(issue.get("id"), "-"),
                _string_value(issue.get("status"), "-"),
                _string_value(issue.get("category"), "-"),
                _string_value(issue.get("approval_id"), "-"),
            )
        console.print(issues_table)

    if approvals:
        console.print(
            Panel.fit(
                "Approvals were created from this preview path. Review them in the dashboard before continuing.",
                title="Next Step",
            )
        )
    elif issues:
        console.print(
            Panel.fit(
                "Linked issues were created during apply. Resolve or reject them before retrying execution.",
                title="Next Step",
            )
        )
    elif bool(payload.get("approval_required")):
        console.print(
            Panel.fit(
                "This preview is approval-gated. Applying it will request approval instead of mutating directly.",
                title="Next Step",
            )
        )


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
