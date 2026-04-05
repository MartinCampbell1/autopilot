"""Structured always-on routine builders for the company shell."""

from __future__ import annotations

from typing import Any


def _routine(
    *,
    routine_id: str,
    title: str,
    cadence: str,
    status: str,
    description: str,
    guardrail: str,
    recommended_action: dict[str, Any] | None = None,
    blocked_by: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": routine_id,
        "title": title,
        "cadence": cadence,
        "status": status,
        "description": description,
        "guardrail": guardrail,
        "blocked_by": list(blocked_by or []),
        "recommended_action": dict(recommended_action or {}),
    }


def build_company_routines(
    *,
    project: dict[str, Any],
    state: dict[str, Any],
    delivery_status: dict[str, Any],
    latest_handoff: dict[str, Any] | None,
    bootstrap: dict[str, Any],
    runtime_diagnostics: dict[str, Any],
    runtime_control_available: bool,
    channels: dict[str, Any],
    secrets: dict[str, Any],
) -> dict[str, Any]:
    """Build first-class routines that stay inside the existing runtime wall."""

    project_id = str(project.get("id") or "").strip()
    project_status = str(state.get("status") or "idle").strip() or "idle"
    paused = bool(state.get("paused"))
    runtime_session_id = str(state.get("runtime_session_id") or "").strip()
    delivery_code = str(delivery_status.get("status") or "").strip()
    diagnostics_summary = dict(runtime_diagnostics.get("summary") or {})
    error_count = int(diagnostics_summary.get("error_count") or 0)
    warning_count = int(diagnostics_summary.get("warning_count") or 0)
    verification_ready = bool(dict(bootstrap.get("verification") or {}).get("artifact_exists"))
    github = dict(bootstrap.get("github") or {})
    github_repo = str(github.get("github_repo") or "").strip()
    github_workflow_ready = not github_repo or bool(github.get("workflow_exists"))
    ready_channel_count = int(dict(channels.get("summary") or {}).get("ready_count") or 0)
    interactive_count = int(dict(channels.get("summary") or {}).get("interactive_count") or 0)
    missing_secret_count = int(dict(secrets.get("summary") or {}).get("missing_count") or 0)

    if project_status == "running" and not paused:
        run_status = "active"
        run_action = {"action_id": "pause", "label": "Pause runtime", "project_id": project_id}
        run_description = "Project execution is active and can keep moving without leaving the company shell."
    elif paused or project_status == "paused":
        run_status = "paused"
        run_action = {"action_id": "resume", "label": "Resume project", "project_id": project_id}
        run_description = "Project execution is paused and waiting for an explicit resume."
    elif project_status == "failed":
        run_status = "blocked"
        run_action = {"action_id": "launch", "label": "Relaunch project", "project_id": project_id}
        run_description = "The last execution attempt failed and needs a fresh launch through the standard runtime wall."
    elif delivery_code == "ready_to_run":
        run_status = "queued"
        run_action = {"action_id": "launch", "label": "Launch project", "project_id": project_id}
        run_description = "The project is ready for a fresh execution run."
    elif delivery_code == "merged":
        run_status = "completed"
        run_action = {}
        run_description = "The project already produced a merged handoff."
    else:
        run_status = "standby"
        run_action = {"action_id": "open_control_plane", "label": "Open control plane", "project_id": project_id}
        run_description = "The run loop is standing by behind the existing runtime-control surface."

    doctor_status = "blocked" if error_count > 0 else "warning" if warning_count > 0 else "ready"
    doctor_action = {
        "action_id": "run_doctor",
        "label": "Run doctor",
        "command": f"autopilot doctor {project.get('path') or ''} --refresh".strip(),
    }

    review_action: dict[str, Any] = {"action_id": "open_control_plane", "label": "Open control plane", "project_id": project_id}
    if latest_handoff and str(latest_handoff.get("url") or "").strip():
        review_action = {
            "action_id": "open_pr",
            "label": "Open PR",
            "url": str(latest_handoff.get("url") or "").strip(),
        }
    elif str(github.get("compare_url") or "").strip():
        review_action = {
            "action_id": "open_compare",
            "label": "Open compare",
            "url": str(github.get("compare_url") or "").strip(),
        }

    if delivery_code in {"in_review", "ready_to_merge"}:
        review_status = "active"
    elif delivery_code == "blocked":
        review_status = "blocked"
    elif delivery_code == "handoff_pending":
        review_status = "queued"
    elif delivery_code == "merged":
        review_status = "completed"
    else:
        review_status = "standby"

    ship_blockers: list[str] = []
    if not verification_ready:
        ship_blockers.append("verifier_bootstrap_missing")
    if not github_workflow_ready:
        ship_blockers.append("github_workflow_missing")

    if ship_blockers:
        ship_status = "blocked"
    elif delivery_code == "merged":
        ship_status = "completed"
    elif delivery_code in {"in_review", "ready_to_merge", "handoff_pending"}:
        ship_status = "active"
    else:
        ship_status = "queued"

    ship_action = {
        "action_id": "run_ship",
        "label": "Ship handoff",
        "command": f"autopilot ship {project.get('path') or ''}".strip(),
    }
    if latest_handoff and str(latest_handoff.get("url") or "").strip():
        ship_action = {
            "action_id": "open_pr",
            "label": "Open PR",
            "url": str(latest_handoff.get("url") or "").strip(),
        }

    if runtime_control_available:
        heartbeat_status = "active"
    elif interactive_count > 0:
        heartbeat_status = "standby"
    else:
        heartbeat_status = "blocked"

    heartbeat_blockers: list[str] = []
    if ready_channel_count <= 0:
        heartbeat_blockers.append("no_ready_channels")
    if missing_secret_count > 0:
        heartbeat_blockers.append("channel_secrets_missing")
    if not runtime_control_available and runtime_session_id:
        heartbeat_blockers.append("runtime_control_standby")

    items = [
        _routine(
            routine_id="run_loop",
            title="Run loop",
            cadence="continuous",
            status=run_status,
            description=run_description,
            guardrail="Uses the existing launch/resume/pause lifecycle routes and never starts a side-channel runtime.",
            recommended_action=run_action,
        ),
        _routine(
            routine_id="doctor_watch",
            title="Doctor watch",
            cadence="preflight",
            status=doctor_status,
            description="Keeps runtime diagnostics visible before review and ship decisions.",
            guardrail="Doctor output is advisory only; operators still act through the same guarded runtime and GitHub paths.",
            recommended_action=doctor_action,
        ),
        _routine(
            routine_id="review_loop",
            title="Review loop",
            cadence="handoff",
            status=review_status,
            description="Tracks whether the current handoff is waiting for review, blocked, or ready to merge.",
            guardrail="Review remains command-backed and evidence-gated; this shell only surfaces the state.",
            recommended_action=review_action,
        ),
        _routine(
            routine_id="ship_loop",
            title="Ship loop",
            cadence="handoff",
            status=ship_status,
            description="Keeps shipping readiness tied to verifier bootstrap and managed GitHub workflow state.",
            guardrail="Shipping still goes through the same bootstrap and protected-branch checks as the CLI.",
            recommended_action=ship_action,
            blocked_by=ship_blockers,
        ),
        _routine(
            routine_id="heartbeat",
            title="Operator heartbeat",
            cadence="continuous",
            status=heartbeat_status,
            description="Maintains a live operator surface for approvals, quarantines, and runtime follow-through.",
            guardrail="All operator actions route through dashboard or structured runtime-control requests; the wall stays enforced.",
            recommended_action={
                "action_id": "open_control_plane",
                "label": "Open control plane",
                "project_id": project_id,
            },
            blocked_by=heartbeat_blockers,
        ),
    ]

    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("status") or "unknown")
        counts[key] = counts.get(key, 0) + 1

    return {
        "items": items,
        "summary": {
            "routine_count": len(items),
            "active_count": counts.get("active", 0),
            "ready_count": counts.get("ready", 0),
            "blocked_count": counts.get("blocked", 0),
            "paused_count": counts.get("paused", 0),
            "queued_count": counts.get("queued", 0),
            "completed_count": counts.get("completed", 0),
            "warning_count": counts.get("warning", 0),
            "standby_count": counts.get("standby", 0),
        },
    }

