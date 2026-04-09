"""File-backed execution issues for the FounderOS control plane."""

from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.permission_sync import annotate_permission_sync
from autopilot.core.project_store import emit_project_event, load_project_prd, load_project_state
from autopilot.core.runtime_agents import build_runtime_agents, resolve_story_runtime_agent_id


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


class ExecutionIssueRecord(BaseModel):
    """Stable execution/control-plane issue linked to projects and approvals."""

    id: str
    project_id: str
    project_name: str
    title: str
    description: str = ""
    root_cause: str = ""
    category: str = "control_plane"
    severity: str = "medium"
    status: str = "open"
    source_event: str = ""
    related_command: str = ""
    story_id: int | None = None
    runtime_agent_id: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    approval_id: str = ""
    permission_sync_key: str = ""
    dedupe_key: str = ""
    initiative_id: str = ""
    orchestrator: str = ""
    orchestration_run_id: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_note: str = ""


def issue_path(config: AutopilotConfig, issue_id: str) -> Path:
    """Return the persisted issue path."""

    return config.control_plane_state_dir / "issues" / f"{issue_id}.json"


def _build_project_context(project: dict[str, Any]) -> tuple[str, str, str]:
    control_plane = project.get("control_plane") or {}
    initiative = control_plane.get("initiative") or {}
    orchestration = control_plane.get("orchestration") or {}
    return (
        str(initiative.get("id") or ""),
        str(orchestration.get("orchestrator") or ""),
        str(orchestration.get("run_id") or ""),
    )


def get_issue(config: AutopilotConfig, issue_id: str) -> ExecutionIssueRecord | None:
    """Load a single issue if it exists."""

    path = issue_path(config, issue_id)
    if not path.exists():
        return None
    try:
        return ExecutionIssueRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_issue(config: AutopilotConfig, issue: ExecutionIssueRecord) -> ExecutionIssueRecord:
    """Persist an issue record."""

    issue.updated_at = _utcnow_iso()
    _atomic_write_json(issue_path(config, issue.id), issue.model_dump())
    return issue


def list_issues(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    category: str | None = None,
    approval_id: str | None = None,
    runtime_agent_id: str | None = None,
) -> list[ExecutionIssueRecord]:
    """List stored issues with simple filtering."""

    directory = config.control_plane_state_dir / "issues"
    if not directory.exists():
        return []

    issues: list[ExecutionIssueRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            issue = ExecutionIssueRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if project_id and issue.project_id != project_id:
            continue
        if initiative_id and issue.initiative_id != initiative_id:
            continue
        if orchestrator and issue.orchestrator != orchestrator:
            continue
        if status and issue.status != status:
            continue
        if category and issue.category != category:
            continue
        if approval_id and issue.approval_id != approval_id:
            continue
        if (
            runtime_agent_id
            and runtime_agent_id != issue.runtime_agent_id
            and runtime_agent_id not in issue.runtime_agent_ids
        ):
            continue
        issues.append(issue)

    issues.sort(key=lambda item: (item.created_at, item.id))
    return issues


def create_issue(
    config: AutopilotConfig,
    *,
    project: dict[str, Any],
    title: str,
    description: str = "",
    root_cause: str = "",
    category: str = "control_plane",
    severity: str = "medium",
    source_event: str = "",
    related_command: str = "",
    story_id: int | None = None,
    runtime_agent_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    approval_id: str = "",
    permission_sync_key: str = "",
    dedupe_key: str = "",
    context: dict[str, Any] | None = None,
    run_id: str = "",
) -> ExecutionIssueRecord:
    """Create a new issue, or reuse an open issue with the same dedupe key."""

    if dedupe_key:
        for existing in list_issues(config, project_id=str(project["id"]), status="open"):
            if existing.dedupe_key == dedupe_key:
                existing.title = title
                existing.description = description
                existing.root_cause = root_cause
                existing.category = category
                existing.severity = severity
                existing.source_event = source_event
                existing.related_command = related_command
                existing.story_id = story_id
                existing.runtime_agent_id = runtime_agent_id
                existing.runtime_agent_ids = list(runtime_agent_ids or [])
                existing.context = deepcopy(context or {})
                if permission_sync_key:
                    existing.permission_sync_key = permission_sync_key
                if approval_id and not existing.approval_id:
                    existing.approval_id = approval_id
                save_issue(config, existing)
                return existing

    created_at = _utcnow_iso()
    initiative_id, orchestrator, orchestration_run_id = _build_project_context(project)
    issue = ExecutionIssueRecord(
        id=f"iss_{uuid.uuid4().hex[:10]}",
        project_id=str(project["id"]),
        project_name=str(project["name"]),
        title=title,
        description=description,
        root_cause=root_cause,
        category=category,
        severity=severity,
        source_event=source_event,
        related_command=related_command,
        story_id=story_id,
        runtime_agent_id=runtime_agent_id,
        runtime_agent_ids=list(runtime_agent_ids or []),
        approval_id=approval_id,
        permission_sync_key=permission_sync_key,
        dedupe_key=dedupe_key,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        orchestration_run_id=orchestration_run_id,
        context=deepcopy(context or {}),
        created_at=created_at,
        updated_at=created_at,
    )
    save_issue(config, issue)
    emit_project_event(
        config,
        issue.project_id,
        event="execution_issue_created",
        status=issue.severity,
        message=issue.title,
        story_id=story_id,
        extra={
            "issue_id": issue.id,
            "issue_category": issue.category,
            "related_command": related_command,
            "runtime_agent_id": runtime_agent_id,
            "runtime_agent_ids": list(runtime_agent_ids or []),
            **({"run_id": run_id} if str(run_id or "").strip() else {}),
        },
    )
    if issue.permission_sync_key:
        annotate_permission_sync(
            config,
            issue.permission_sync_key,
            metadata_updates={
                "settlement": {
                    "stage": "issue_open",
                    "issue_id": issue.id,
                    "approval_id": issue.approval_id,
                    "updated_at": issue.updated_at,
                }
            },
        )
    return issue


def resolve_matching_issues(
    config: AutopilotConfig,
    *,
    project_id: str,
    categories: set[str] | None = None,
    story_id: int | None = None,
    actor: str,
    note: str,
) -> list[ExecutionIssueRecord]:
    """Resolve all matching open issues for a project."""

    resolved: list[ExecutionIssueRecord] = []
    for issue in list_issues(config, project_id=project_id, status="open"):
        if categories and issue.category not in categories:
            continue
        if story_id is not None and issue.story_id != story_id:
            continue
        if story_id is None and issue.story_id is not None:
            continue
        resolved.append(resolve_issue(config, issue.id, actor=actor, note=note))
    return resolved


def link_issue_approval(
    config: AutopilotConfig,
    *,
    issue_id: str,
    approval_id: str,
) -> ExecutionIssueRecord:
    """Attach an approval id to an existing issue."""

    issue = get_issue(config, issue_id)
    if issue is None:
        raise KeyError(issue_id)
    issue.approval_id = approval_id
    issue = save_issue(config, issue)
    if issue.permission_sync_key:
        annotate_permission_sync(
            config,
            issue.permission_sync_key,
            metadata_updates={
                "settlement": {
                    "stage": "issue_linked",
                    "issue_id": issue.id,
                    "approval_id": approval_id,
                    "updated_at": issue.updated_at,
                }
            },
        )
    return issue


def resolve_issue(
    config: AutopilotConfig,
    issue_id: str,
    *,
    actor: str,
    note: str = "",
) -> ExecutionIssueRecord:
    """Resolve an open execution issue."""

    issue = get_issue(config, issue_id)
    if issue is None:
        raise KeyError(issue_id)
    if issue.status == "resolved":
        raise RuntimeError(f"Issue {issue_id} is already resolved.")

    issue.status = "resolved"
    issue.resolved_at = _utcnow_iso()
    issue.resolved_by = actor
    issue.resolution_note = note
    save_issue(config, issue)
    emit_project_event(
        config,
        issue.project_id,
        event="execution_issue_resolved",
        status="ok",
        message=f"Issue `{issue.title}` resolved by {actor}.",
        story_id=issue.story_id,
        extra={
            "issue_id": issue.id,
            "issue_category": issue.category,
            "actor": actor,
        },
    )
    if issue.permission_sync_key:
        annotate_permission_sync(
            config,
            issue.permission_sync_key,
            metadata_updates={
                "settlement": {
                    "stage": "issue_resolved",
                    "issue_id": issue.id,
                    "approval_id": issue.approval_id,
                    "actor": actor,
                    "note": note,
                    "updated_at": issue.updated_at,
                }
            },
        )
    return issue


RUNTIME_ISSUE_SPECS: dict[str, dict[str, str]] = {
    "worker_failed": {
        "category": "runtime_worker_failure",
        "severity": "high",
        "title": "Worker execution failed",
    },
    "story_gate_failed": {
        "category": "runtime_gate_failure",
        "severity": "high",
        "title": "Quality gates failed",
    },
    "critic_rejected": {
        "category": "runtime_critic_rejection",
        "severity": "medium",
        "title": "Critic rejected story output",
    },
    "story_stuck": {
        "category": "runtime_story_stuck",
        "severity": "high",
        "title": "Story execution is stuck",
    },
    "story_merge_blocked": {
        "category": "runtime_merge_blocked",
        "severity": "high",
        "title": "Story merge back to main is blocked",
    },
    "budget_paused": {
        "category": "runtime_budget_paused",
        "severity": "high",
        "title": "Project auto-paused by budget policy",
    },
    "run_failed": {
        "category": "runtime_run_failed",
        "severity": "high",
        "title": "Project run failed",
    },
    "connector_activation_failed": {
        "category": "runtime_connector_activation_failed",
        "severity": "high",
        "title": "Required connector activation failed",
    },
    "story_lease_conflict": {
        "category": "runtime_lease_conflict",
        "severity": "high",
        "title": "Story checkout lease conflict",
    },
    "github_ci_failed": {
        "category": "github_ci_failure",
        "severity": "high",
        "title": "GitHub CI failed",
    },
    "github_review_comment_received": {
        "category": "github_review_feedback",
        "severity": "medium",
        "title": "GitHub review comment received",
    },
    "github_changes_requested": {
        "category": "github_changes_requested",
        "severity": "high",
        "title": "GitHub changes requested",
    },
}

GITHUB_ISSUE_CATEGORIES_BY_EVENT: dict[str, list[str]] = {
    "github_ci_failed": ["github_ci_failure"],
    "github_review_comment_received": ["github_review_feedback"],
    "github_changes_requested": ["github_changes_requested"],
    "github_approved_and_green": [
        "github_ci_failure",
        "github_review_feedback",
        "github_changes_requested",
    ],
}


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _story_definition(project: dict[str, Any], story_id: int) -> dict[str, Any] | None:
    prd = load_project_prd(project, seed_mode="migrate")
    for story in prd.get("stories", []):
        if int(story.get("id", -1)) == story_id:
            return story
    return None


def _runtime_issue_context(
    config: AutopilotConfig,
    *,
    project: dict[str, Any],
    event_record: dict[str, Any],
    story_id: int | None,
) -> dict[str, Any]:
    state = load_project_state(config, str(project["id"]))
    project_context = {
        "status": state.get("status"),
        "paused": state.get("paused"),
        "current_story_id": state.get("current_story_id"),
        "current_iteration": state.get("current_iteration"),
        "active_worker": state.get("active_worker"),
        "active_critic": state.get("active_critic"),
        "last_error": state.get("last_error"),
    }

    event_context = {
        key: value
        for key, value in event_record.items()
        if key not in {"event", "project_id", "story_id", "status", "message", "timestamp"}
    }

    context: dict[str, Any] = {
        "project": _json_safe(project_context),
        "event": {
            "name": event_record.get("event"),
            "status": event_record.get("status"),
            "message": event_record.get("message"),
            "timestamp": event_record.get("timestamp"),
            "extra": _json_safe(event_context),
        },
    }
    if event_record.get("event") in {"budget_paused", "run_failed"}:
        context["budget"] = _json_safe(
            {
                "policy": state.get("budget_policy") or {},
                "usage": state.get("budget_usage") or {},
            }
        )

    if story_id is not None:
        runtime_story = state.get("story_state", {}).get(str(story_id), {})
        story_def = _story_definition(project, story_id) or {}
        context["story"] = _json_safe(
            {
                "id": story_id,
                "title": story_def.get("title"),
                "description": story_def.get("description"),
                "status": runtime_story.get("status"),
                "phase_id": story_def.get("phase_id"),
                "phase_title": story_def.get("phase_title"),
                "iteration": runtime_story.get("iteration"),
                "agent": runtime_story.get("agent"),
                "critic": runtime_story.get("critic"),
                "last_error": runtime_story.get("last_error"),
                "team_mode": runtime_story.get("team_mode"),
                "team_members": runtime_story.get("team_members"),
                "connector_activation": runtime_story.get("connector_activation"),
                "activation_errors": runtime_story.get("activation_errors"),
                "worktree_path": runtime_story.get("worktree_path"),
                "branch_name": runtime_story.get("branch_name"),
                "ownership": runtime_story.get("ownership"),
                "checkout": runtime_story.get("checkout"),
                "github_pr": runtime_story.get("github_pr") or {},
            }
        )
    return context


def _resolve_runtime_issue_agent_id(
    project: dict[str, Any],
    *,
    event: str,
    story_id: int | None,
    context: dict[str, Any],
) -> str:
    event_extra = context.get("event", {}).get("extra") or {}
    explicit_runtime_agent_id = str(event_extra.get("runtime_agent_id") or "").strip()
    if explicit_runtime_agent_id:
        return explicit_runtime_agent_id

    if event == "critic_rejected":
        role = "critic"
    elif event in {
        "worker_failed",
        "story_gate_failed",
        "story_stuck",
        "story_merge_blocked",
        "connector_activation_failed",
        "story_lease_conflict",
        "budget_paused",
    }:
        role = "worker"
    else:
        role = ""

    if event == "budget_paused":
        for key in ("worker_runtime_agent_id", "critic_runtime_agent_id"):
            explicit_agent_id = str(event_extra.get(key) or "").strip()
            if explicit_agent_id:
                return explicit_agent_id

    if not role:
        return ""

    resolved_story_id = story_id
    if resolved_story_id is None:
        current_story_id = context.get("project", {}).get("current_story_id")
        resolved_story_id = int(current_story_id) if current_story_id is not None else None
    if resolved_story_id is None:
        return ""

    story_context = context.get("story") or {}
    runtime_label = (
        str(story_context.get("critic") or "").strip()
        if role == "critic"
        else str(story_context.get("agent") or "").strip()
    ) or None
    return (
        resolve_story_runtime_agent_id(
            str(project["id"]),
            resolved_story_id,
            role=role,
            team_members=story_context.get("team_members") or [],
            runtime_label=runtime_label,
        )
        or ""
    )


def _derive_runtime_root_cause(event: str, message: str, context: dict[str, Any]) -> str:
    story_context = context.get("story") or {}
    budget_context = context.get("budget") or {}
    event_extra = context.get("event", {}).get("extra") or {}

    def first_text(*values: Any) -> str:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    if event == "worker_failed":
        return (
            first_text(
                event_extra.get("worker_error"),
                event_extra.get("critic_feedback"),
                story_context.get("last_error"),
                message,
            )
            or "Worker execution failed."
        )
    if event == "story_gate_failed":
        gate_failures = event_extra.get("gate_failures") or []
        if gate_failures and isinstance(gate_failures[0], dict):
            first_failure = gate_failures[0]
            gate_name = str(first_failure.get("name") or "gate").strip()
            gate_output = str(first_failure.get("output") or "").strip()
            if gate_output:
                return f"{gate_name}: {gate_output}".strip()
            return f"{gate_name} failed.".strip()
        return (
            first_text(
                event_extra.get("critic_feedback"),
                story_context.get("last_error"),
                message,
            )
            or "Quality gates failed."
        )
    if event == "critic_rejected":
        return (
            first_text(
                event_extra.get("critic_feedback"),
                story_context.get("last_error"),
                message,
            )
            or "Critic rejected the story output."
        )
    if event == "story_stuck":
        return (
            first_text(
                event_extra.get("stuck_summary"),
                event_extra.get("error"),
                story_context.get("last_error"),
                message,
            )
            or "Story became stuck."
        )
    if event == "story_merge_blocked":
        branch_name = event_extra.get("branch_name") or story_context.get("branch_name")
        if branch_name:
            return first_text(message) or f"Merge blocked for branch `{branch_name}`."
        return first_text(message) or "Merge back to main is blocked."
    if event == "connector_activation_failed":
        activation_errors = event_extra.get("activation_errors") or story_context.get("activation_errors") or []
        if activation_errors:
            return str(activation_errors[0]).strip()
        return first_text(message) or "Required connectors could not be activated."
    if event == "story_lease_conflict":
        return first_text(message) or "Story lease conflict detected."
    if event == "budget_paused":
        usage = budget_context.get("usage") or {}
        project_usage = usage.get("project") or {}
        if message:
            return str(message).strip()
        return (
            "Runtime budget exhausted "
            f"(worker_iterations={project_usage.get('worker_iterations', 0)}, "
            f"critic_reviews={project_usage.get('critic_reviews', 0)})."
        )
    if event == "run_failed":
        root_cause = first_text(
            context.get("project", {}).get("last_error"),
            message,
        )
        exception_type = str(event_extra.get("exception_type") or "").strip()
        if root_cause and exception_type and exception_type not in root_cause:
            return f"{root_cause} ({exception_type})"
        return root_cause or "Project run failed."
    if event == "github_ci_failed":
        return (
            first_text(
                event_extra.get("check_summary"),
                event_extra.get("message"),
                message,
            )
            or "GitHub CI failed."
        )
    if event == "github_review_comment_received":
        return (
            first_text(
                event_extra.get("review_comment"),
                message,
            )
            or "GitHub review comment received."
        )
    if event == "github_changes_requested":
        return (
            first_text(
                event_extra.get("review_comment"),
                event_extra.get("review_state"),
                message,
            )
            or "GitHub changes requested."
        )
    return first_text(message) or "Execution issue detected."


def sync_runtime_issue_from_event(config: AutopilotConfig, event_record: dict[str, Any]) -> None:
    """Create or resolve execution issues based on runtime events."""

    event = str(event_record.get("event") or "")
    if not event or event.startswith("execution_issue_") or event.startswith("approval_"):
        return

    from autopilot.core.project_store import get_project_entry

    project_id = str(event_record.get("project_id") or "")
    if not project_id:
        return
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        return

    story_id_raw = event_record.get("story_id")
    story_id = int(story_id_raw) if story_id_raw is not None else None

    spec = RUNTIME_ISSUE_SPECS.get(event)
    if spec is not None:
        dedupe_scope = f"story:{story_id}" if story_id is not None else "project"
        context = _runtime_issue_context(
            config,
            project=project,
            event_record=event_record,
            story_id=story_id,
        )
        runtime_agent_id = _resolve_runtime_issue_agent_id(
            project,
            event=event,
            story_id=story_id,
            context=context,
        )
        if runtime_agent_id and "story" in context:
            matching_agents = [
                agent
                for agent in build_runtime_agents(str(project["id"]), [context["story"]])
                if agent["agent_id"] == runtime_agent_id
            ]
            if matching_agents:
                context["runtime_agent"] = matching_agents[0]
        create_issue(
            config,
            project=project,
            title=spec["title"],
            description=str(event_record.get("message") or ""),
            root_cause=_derive_runtime_root_cause(event, str(event_record.get("message") or ""), context),
            category=spec["category"],
            severity=spec["severity"],
            source_event=event,
            story_id=story_id,
            runtime_agent_id=runtime_agent_id,
            runtime_agent_ids=[runtime_agent_id]
            if runtime_agent_id
            else list(context.get("event", {}).get("extra", {}).get("runtime_agent_ids") or []),
            dedupe_key=f"{project_id}:{spec['category']}:{dedupe_scope}",
            context=context,
            run_id=str(event_record.get("run_id") or "").strip(),
        )
        return

    if event in {"story_done", "story_skipped", "checkout_recovered"} and story_id is not None:
        resolve_matching_issues(
            config,
            project_id=project_id,
            categories={
                "runtime_worker_failure",
                "runtime_gate_failure",
                "runtime_critic_rejection",
                "runtime_story_stuck",
                "runtime_merge_blocked",
                "runtime_connector_activation_failed",
                "runtime_lease_conflict",
            },
            story_id=story_id,
            actor="runtime",
            note=f"Story state recovered via `{event}`.",
        )
        return

    if event == "github_approved_and_green" and story_id is not None:
        resolve_matching_issues(
            config,
            project_id=project_id,
            categories=set(GITHUB_ISSUE_CATEGORIES_BY_EVENT["github_approved_and_green"]),
            story_id=story_id,
            actor="github",
            note="GitHub PR is approved and green.",
        )
        return

    if event in {"run_started", "resumed", "run_finished", "run_completed"}:
        resolve_matching_issues(
            config,
            project_id=project_id,
            categories={"runtime_budget_paused", "runtime_run_failed"},
            actor="runtime",
            note=f"Project state recovered via `{event}`.",
        )
