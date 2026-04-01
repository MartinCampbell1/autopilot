"""CLI helpers for explicit execution-plane approval flows."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.approvals import ApprovalRecord, decide_approval, get_approval, list_approvals
from autopilot.core.config import load_config
from autopilot.core.control_plane_issues import get_issue
from autopilot.core.execution_plane import apply_execution_command_approval

console = Console()
DEFAULT_APPROVAL_ACTOR = "cli-control-plane"


def _config():
    return load_config(Path.home() / ".autopilot" / "config.yaml")


def _string_value(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized if normalized else fallback


def _string_array(value: Any) -> list[str]:
    return [str(item).strip() for item in (value or []) if str(item).strip()]


def _optional_filter(value: str | None) -> str | None:
    normalized = _string_value(value)
    return None if normalized.lower() in {"", "all", "*"} else normalized


def _issue_payload(config: Any, approval: ApprovalRecord) -> dict[str, Any] | None:
    if not approval.issue_id:
        return None
    issue = get_issue(config, approval.issue_id)
    return issue.model_dump() if issue is not None else None


def _render_approval_detail(
    approval_payload: dict[str, Any],
    *,
    issue_payload: dict[str, Any] | None = None,
    heading: str,
) -> None:
    console.print(Panel.fit(f"[bold]{heading}[/bold]"))

    table = Table(show_header=False, box=None)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Approval", _string_value(approval_payload.get("id"), "-"))
    table.add_row("Status", _string_value(approval_payload.get("status"), "-"))
    table.add_row("Action", _string_value(approval_payload.get("action"), "-"))
    table.add_row("Project", _string_value(approval_payload.get("project_name"), _string_value(approval_payload.get("project_id"), "-")))
    table.add_row("Requested By", _string_value(approval_payload.get("requested_by"), "-"))
    table.add_row("Created", _string_value(approval_payload.get("created_at"), "-"))
    table.add_row("Issue", _string_value(approval_payload.get("issue_id"), "No linked issue"))
    table.add_row(
        "Runtime Agents",
        ", ".join(_string_array(approval_payload.get("runtime_agent_ids"))) or "No runtime-agent linkage",
    )
    table.add_row("Reason", _string_value(approval_payload.get("reason"), "No approval reason recorded"))
    if _string_value(approval_payload.get("decided_at")):
        table.add_row(
            "Decision",
            f"{_string_value(approval_payload.get('status'), '-')}"
            f" by {_string_value(approval_payload.get('decided_by'), 'unknown')}"
            f" at {_string_value(approval_payload.get('decided_at'), '-')}",
        )
    if _string_value(approval_payload.get("decision_note")):
        table.add_row("Decision Note", _string_value(approval_payload.get("decision_note")))
    if _string_value(approval_payload.get("applied_at")):
        table.add_row(
            "Applied",
            f"{_string_value(approval_payload.get('applied_by'), 'unknown')}"
            f" at {_string_value(approval_payload.get('applied_at'), '-')}",
        )
    console.print(table)

    policy_reasons = _string_array(approval_payload.get("policy_reasons"))
    if policy_reasons:
        console.print(
            Panel("\n".join(f"- {reason}" for reason in policy_reasons), title="Policy Reasons", expand=False)
        )

    if issue_payload:
        issue_table = Table(title="Linked Issue")
        issue_table.add_column("Issue")
        issue_table.add_column("Status")
        issue_table.add_column("Category")
        issue_table.add_column("Severity")
        issue_table.add_row(
            _string_value(issue_payload.get("id"), "-"),
            _string_value(issue_payload.get("status"), "-"),
            _string_value(issue_payload.get("category"), "-"),
            _string_value(issue_payload.get("severity"), "-"),
        )
        console.print(issue_table)

    approval_id = _string_value(approval_payload.get("id"), "<approval-id>")
    status = _string_value(approval_payload.get("status"), "pending")
    if status == "pending":
        message = (
            f"Approve with `autopilot approve-approval {approval_id}` or reject with "
            f"`autopilot reject-approval {approval_id}`."
        )
    elif status == "approved":
        message = f"Apply this approved action with `autopilot apply-approval {approval_id}`."
    elif status == "applied":
        message = "Approval has already been applied."
    else:
        message = f"Approval is {status}. No further mutation is available."
    console.print(Panel.fit(message, title="Next Step"))


def list_execution_approvals(
    *,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = "pending",
    action: str | None = None,
    issue_id: str | None = None,
    runtime_agent_id: str | None = None,
    json_output: bool = False,
) -> None:
    """List approval records for the operator queue."""

    config = _config()
    approvals = list(
        reversed(
            list_approvals(
                config,
                project_id=_optional_filter(project_id),
                initiative_id=_optional_filter(initiative_id),
                orchestrator=_optional_filter(orchestrator),
                status=_optional_filter(status),
                action=_optional_filter(action),
                issue_id=_optional_filter(issue_id),
                runtime_agent_id=_optional_filter(runtime_agent_id),
            )
        )
    )
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "filters": {
                        "project_id": _optional_filter(project_id),
                        "initiative_id": _optional_filter(initiative_id),
                        "orchestrator": _optional_filter(orchestrator),
                        "status": _optional_filter(status),
                        "action": _optional_filter(action),
                        "issue_id": _optional_filter(issue_id),
                        "runtime_agent_id": _optional_filter(runtime_agent_id),
                    },
                    "approvals": [approval.model_dump() for approval in approvals],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    console.print(Panel.fit("[bold]Approval Queue[/bold]"))
    if not approvals:
        console.print("No approvals matched the current filters.")
        return

    table = Table(title=f"{len(approvals)} approval(s)")
    table.add_column("Approval")
    table.add_column("Status")
    table.add_column("Action")
    table.add_column("Project")
    table.add_column("Issue")
    table.add_column("Requested By")
    for approval in approvals:
        table.add_row(
            approval.id,
            approval.status,
            approval.action,
            approval.project_name or approval.project_id,
            approval.issue_id or "-",
            approval.requested_by or "-",
        )
    console.print(table)


def show_approval(
    approval_id: str,
    *,
    json_output: bool = False,
) -> None:
    """Show one approval and its linked issue context."""

    config = _config()
    approval = get_approval(config, approval_id)
    if approval is None:
        console.print(f"[red]Approval {approval_id} not found.[/red]")
        raise typer.Exit(1)

    issue_payload = _issue_payload(config, approval)
    if json_output:
        typer.echo(
            json.dumps(
                {"approval": approval.model_dump(), "issue": issue_payload},
                indent=2,
                ensure_ascii=False,
            )
        )
        return
    _render_approval_detail(approval.model_dump(), issue_payload=issue_payload, heading=f"Approval {approval_id}")


def approve_approval(
    approval_id: str,
    *,
    actor: str = DEFAULT_APPROVAL_ACTOR,
    note: str = "",
    json_output: bool = False,
) -> None:
    """Approve one pending approval."""

    config = _config()
    try:
        approval = decide_approval(config, approval_id, decision="approved", actor=actor, note=note)
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    issue_payload = _issue_payload(config, approval)
    payload = {"status": "ok", "approval": approval.model_dump(), "issue": issue_payload}
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    _render_approval_detail(payload["approval"], issue_payload=issue_payload, heading=f"Approved {approval_id}")


def reject_approval(
    approval_id: str,
    *,
    actor: str = DEFAULT_APPROVAL_ACTOR,
    note: str = "",
    json_output: bool = False,
) -> None:
    """Reject one pending approval."""

    config = _config()
    try:
        approval = decide_approval(config, approval_id, decision="rejected", actor=actor, note=note)
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    issue_payload = _issue_payload(config, approval)
    payload = {"status": "ok", "approval": approval.model_dump(), "issue": issue_payload}
    if json_output:
        typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return
    _render_approval_detail(payload["approval"], issue_payload=issue_payload, heading=f"Rejected {approval_id}")


def apply_approval(
    approval_id: str,
    *,
    actor: str = DEFAULT_APPROVAL_ACTOR,
    json_output: bool = False,
) -> None:
    """Apply one approved approval."""

    config = _config()
    try:
        payload = apply_execution_command_approval(config, approval_id=approval_id, actor=actor)
    except (KeyError, RuntimeError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc

    approval_payload = dict(payload.get("approval") or {})
    issue_payload = None
    if _string_value(approval_payload.get("issue_id")):
        issue = get_issue(config, _string_value(approval_payload.get("issue_id")))
        issue_payload = issue.model_dump() if issue is not None else None

    if json_output:
        typer.echo(json.dumps({**payload, "issue": issue_payload}, indent=2, ensure_ascii=False))
        return

    _render_approval_detail(approval_payload, issue_payload=issue_payload, heading=f"Applied {approval_id}")
    command_result = dict(payload.get("command_result") or {})
    if command_result:
        table = Table(title="Command Result")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("Status", _string_value(command_result.get("status"), "-"))
        table.add_row("Message", _string_value(command_result.get("message"), "No command message recorded"))
        table.add_row(
            "Project",
            _string_value(
                (command_result.get("project") or {}).get("name"),
                _string_value((command_result.get("project") or {}).get("id"), "-"),
            ),
        )
        console.print(table)
