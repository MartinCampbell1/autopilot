"""Main CLI entrypoint."""

import typer

app = typer.Typer(
    name="autopilot",
    help="Autonomous AI programmer platform with account rotation and critic loops.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Autopilot CLI."""


@app.command()
def version() -> None:
    """Show version."""
    from autopilot import __version__

    typer.echo(f"autopilot v{__version__}")


@app.command()
def login(provider: str = typer.Argument(help="Provider: codex, claude, or gemini")) -> None:
    """Save a logged-in CLI session as a reusable profile."""
    from autopilot.cli.login import login as _login

    _login(provider)


@app.command()
def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="PRD JSON path relative to project"),
    project_id: str | None = typer.Option(None, "--project-id", help="Stable project id from the dashboard"),
    headless: bool = typer.Option(False, "--headless", help="Emit machine-readable logs and a JSON summary."),
    schedule: str | None = typer.Option(None, "--schedule", help="Repeat the run on a cadence like 30m or 6h."),
    max_runs: int | None = typer.Option(None, "--max-runs", help="Stop a scheduled run after N iterations."),
) -> None:
    """Run autopilot loop on a project until all stories are done."""
    from autopilot.cli.run import run as _run

    exit_code = _run(project_path, prd, project_id, headless=headless, schedule=schedule, max_runs=max_runs)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command(name="run-all")
def run_all_projects(
    headless: bool = typer.Option(False, "--headless", help="Emit machine-readable logs and a JSON summary."),
    schedule: str | None = typer.Option(None, "--schedule", help="Repeat the run-all loop on a cadence like 30m or 6h."),
    max_runs: int | None = typer.Option(None, "--max-runs", help="Stop a scheduled run after N iterations."),
) -> None:
    """Run autopilot on all configured projects in parallel."""
    from autopilot.cli.run import run_all

    exit_code = run_all(headless=headless, schedule=schedule, max_runs=max_runs)
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


@app.command()
def dashboard(
    port: int = typer.Option(8420, help="API server port"),
    frontend_port: int = typer.Option(3020, help="Frontend server port"),
    no_browser: bool = typer.Option(False, help="Don't open browser"),
) -> None:
    """Start the Autopilot dashboard."""
    from autopilot.cli.dashboard import dashboard as _dashboard

    _dashboard(port, frontend_port, no_browser)


@app.command()
def status() -> None:
    """Show status of accounts and projects."""
    from autopilot.cli.status import status as _status

    _status()


@app.command()
def doctor(
    project_path: str = typer.Argument(".", help="Path to inspect for onboarding and gates."),
    refresh: bool = typer.Option(False, "--refresh", help="Refresh provider diagnostics probes."),
    json_output: bool = typer.Option(False, "--json", help="Emit the doctor report as JSON."),
) -> None:
    """Inspect provider readiness plus local project onboarding state."""
    from autopilot.cli.doctor import doctor as _doctor

    _doctor(project_path, refresh, json_output)


@app.command()
def trace(
    project_path: str = typer.Argument(".", help="Path to the project directory."),
    project_id: str | None = typer.Option(None, "--project-id", help="Stable project id from the dashboard."),
    limit: int = typer.Option(50, "--limit", help="Maximum number of trace entries to read."),
    json_output: bool = typer.Option(False, "--json", help="Emit the trace payload as JSON."),
) -> None:
    """Inspect the structured runtime trace for one project."""
    from autopilot.cli.trace import trace as _trace

    _trace(project_path, project_id, limit, json_output)


@app.command()
def live(
    refresh_sec: float = typer.Option(2.0, "--refresh-sec", help="Seconds between live refreshes."),
    once: bool = typer.Option(False, "--once", help="Render one snapshot and exit."),
) -> None:
    """Render an SSH-friendly live view of projects, stories, and recent events."""
    from autopilot.cli.live import live as _live

    _live(refresh_sec=refresh_sec, once=once)


@app.command(name="preview-actions")
def preview_actions(
    session_id: str = typer.Argument(help="Orchestrator session id to preview."),
    approval_required: bool = typer.Option(
        False,
        "--approval-required",
        help="Preview approval-gated actions instead of safe actions.",
    ),
    policy_profile: str | None = typer.Option(
        None,
        "--policy-profile",
        help="Override the batch policy profile used for the preview.",
    ),
    limit: int = typer.Option(20, "--limit", help="Maximum number of actions to include in the preview."),
    actor: str = typer.Option("cli-control-plane", "--actor", help="Actor label recorded on the preview."),
    reason: str = typer.Option("", "--reason", help="Optional operator rationale for the preview."),
    json_output: bool = typer.Option(False, "--json", help="Emit the preview payload as JSON."),
) -> None:
    """Preview session-scoped execution-plane actions without applying them."""
    from autopilot.cli.execution_preview import preview_actions as _preview_actions

    _preview_actions(
        session_id,
        actor=actor,
        reason=reason,
        approval_required=approval_required,
        policy_profile=policy_profile,
        limit=limit,
        json_output=json_output,
    )


@app.command(name="apply-preview")
def apply_preview(
    preview_id: str = typer.Argument(help="Preview run id to apply."),
    actor: str = typer.Option("cli-control-plane", "--actor", help="Actor label recorded on the apply."),
    reason: str = typer.Option("", "--reason", help="Optional operator rationale for the apply."),
    json_output: bool = typer.Option(False, "--json", help="Emit the apply payload as JSON."),
) -> None:
    """Apply a previously recorded execution-plane preview run."""
    from autopilot.cli.execution_preview import apply_preview as _apply_preview

    _apply_preview(preview_id, actor=actor, reason=reason, json_output=json_output)


@app.command(name="approvals")
def approvals(
    project_id: str | None = typer.Option(None, "--project-id", help="Filter approvals by project id."),
    initiative_id: str | None = typer.Option(None, "--initiative-id", help="Filter approvals by initiative id."),
    orchestrator: str | None = typer.Option(None, "--orchestrator", help="Filter approvals by orchestrator."),
    status: str = typer.Option("pending", "--status", help="Filter approvals by status. Use 'all' for every status."),
    action: str | None = typer.Option(None, "--action", help="Filter approvals by action name."),
    issue_id: str | None = typer.Option(None, "--issue-id", help="Filter approvals by linked issue id."),
    runtime_agent_id: str | None = typer.Option(None, "--runtime-agent-id", help="Filter approvals by runtime agent id."),
    json_output: bool = typer.Option(False, "--json", help="Emit the approvals payload as JSON."),
) -> None:
    """List execution-plane approvals for operator review."""
    from autopilot.cli.execution_approval import list_execution_approvals as _list_execution_approvals

    _list_execution_approvals(
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        status=status,
        action=action,
        issue_id=issue_id,
        runtime_agent_id=runtime_agent_id,
        json_output=json_output,
    )


@app.command(name="show-approval")
def show_approval(
    approval_id: str = typer.Argument(help="Approval id to inspect."),
    json_output: bool = typer.Option(False, "--json", help="Emit the approval payload as JSON."),
) -> None:
    """Show one execution-plane approval and its linked issue context."""
    from autopilot.cli.execution_approval import show_approval as _show_approval

    _show_approval(approval_id, json_output=json_output)


@app.command(name="approve-approval")
def approve_approval(
    approval_id: str = typer.Argument(help="Approval id to approve."),
    actor: str = typer.Option("cli-control-plane", "--actor", help="Actor label recorded on the approval decision."),
    note: str = typer.Option("", "--note", help="Optional operator note stored with the approval decision."),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision payload as JSON."),
) -> None:
    """Approve one pending execution-plane approval."""
    from autopilot.cli.execution_approval import approve_approval as _approve_approval

    _approve_approval(approval_id, actor=actor, note=note, json_output=json_output)


@app.command(name="reject-approval")
def reject_approval(
    approval_id: str = typer.Argument(help="Approval id to reject."),
    actor: str = typer.Option("cli-control-plane", "--actor", help="Actor label recorded on the approval decision."),
    note: str = typer.Option("", "--note", help="Optional operator note stored with the approval decision."),
    json_output: bool = typer.Option(False, "--json", help="Emit the decision payload as JSON."),
) -> None:
    """Reject one pending execution-plane approval."""
    from autopilot.cli.execution_approval import reject_approval as _reject_approval

    _reject_approval(approval_id, actor=actor, note=note, json_output=json_output)


@app.command(name="apply-approval")
def apply_approval(
    approval_id: str = typer.Argument(help="Approval id to apply."),
    actor: str = typer.Option("cli-control-plane", "--actor", help="Actor label recorded on the apply."),
    json_output: bool = typer.Option(False, "--json", help="Emit the apply payload as JSON."),
) -> None:
    """Apply one approved execution-plane approval."""
    from autopilot.cli.execution_approval import apply_approval as _apply_approval

    _apply_approval(approval_id, actor=actor, json_output=json_output)


@app.command(name="init")
def init_project(
    project_path: str = typer.Argument(help="Path to the project directory"),
    idea: str = typer.Option("", "--idea", help="Natural-language project idea to bootstrap into a starter spec/PRD."),
    bootstrap_only: bool = typer.Option(False, "--bootstrap-only", help="Save only the generated spec bootstrap and skip PRD generation."),
) -> None:
    """Initialize a project for autopilot."""
    from autopilot.cli.init_cmd import init as _init

    _init(project_path, idea=idea, bootstrap_only=bootstrap_only)
