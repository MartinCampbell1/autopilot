"""FounderOS-facing execution-plane helpers and stable project snapshots."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.capability_store import (
    build_planning_context,
    load_connectors_registry,
    load_role_templates,
    load_skill_packs_registry,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.execution_brief import (
    ExecutionBrief,
    InitiativeContext,
    OrchestrationContext,
    ProvenanceContext,
    TaskSource,
    render_execution_brief_as_spec,
)
from autopilot.core.github_prs import normalize_story_github_pr
from autopilot.core.intake import generate_prd_from_spec
from autopilot.core.project_bootstrap import CreatedProject, create_project_from_prd
from autopilot.core.project_store import (
    archive_project,
    build_project_detail,
    build_project_summary,
    emit_project_event,
    ensure_project_state,
    get_project_entry,
    launch_project_run,
    load_projects_registry,
    load_project_state,
    merge_project_stories,
    pause_project_run,
    resolve_project_task_source,
    resume_project_run,
    update_project_budget_policy,
    update_project_entry,
)
from autopilot.core.approvals import create_approval, get_approval, list_approvals, mark_approval_applied
from autopilot.core.agent_action_runs import (
    AgentActionBatchRunRecord,
    create_agent_action_batch_run,
    find_agent_action_batch_run_by_idempotency_key,
    get_agent_action_batch_run,
    list_agent_action_batch_runs,
    save_agent_action_batch_run,
)
from autopilot.core.control_plane_issues import create_issue, link_issue_approval, list_issues, resolve_issue
from autopilot.core.tool_contracts import ToolResult, ToolUseContext, build_tool
from autopilot.core.tool_permissions import (
    PermissionContextOverlay,
    PermissionRuleValue,
    load_tool_permission_context,
    permission_rule_value_to_string,
    resolve_tool_permission_decision,
)
from autopilot.core.tool_runner import run_tool_use
from autopilot.core.orchestrator_control_passes import (
    create_orchestrator_control_pass,
    get_orchestrator_control_pass,
    list_orchestrator_control_passes,
)
from autopilot.core.orchestrator_sessions import (
    create_orchestrator_session,
    get_orchestrator_session,
    link_orchestrator_session_entities,
    list_orchestrator_sessions,
    update_orchestrator_session_runtime_state,
    update_orchestrator_session_status,
)
from autopilot.core.runtime_agents import build_runtime_agents, parse_runtime_agent_id
from autopilot.core.runtime_agent_tasks import (
    RuntimeAgentTaskRecord,
    create_or_reuse_runtime_agent_task,
    get_runtime_agent_task,
    link_runtime_agent_task_run,
    list_runtime_agent_tasks,
    refresh_runtime_agent_task,
)
from autopilot.core.runtime_budgets import ensure_budget_state
from autopilot.core.runtime_control import list_project_work_item_leases
from autopilot.core.workspace_policy import inspect_project_workspace_policy

EXECUTION_BRIEF_RELPATH = ".agents/tasks/execution-brief.json"


class ExecutionPlaneProgress(BaseModel):
    """Stable progress counters for upstream control-plane consumers."""

    stories_total: int = 0
    stories_done: int = 0
    stories_open: int = 0
    stories_in_progress: int = 0
    stories_blocked: int = 0
    stories_skipped: int = 0


class ExecutionPlaneRuntime(BaseModel):
    """Stable runtime snapshot for one execution project."""

    status: str = "idle"
    paused: bool = False
    pid: int | None = None
    started_at: str | None = None
    updated_at: str | None = None
    finished_at: str | None = None
    current_story_id: int | None = None
    current_story_title: str | None = None
    current_iteration: int = 0
    active_worker: str | None = None
    active_critic: str | None = None
    last_error: str = ""


class ExecutionPlaneBudget(BaseModel):
    """Budget policy and current usage for one execution project."""

    policy: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlaneProjectSnapshot(BaseModel):
    """Stable execution-plane summary exposed to FounderOS/Quorum."""

    project_id: str
    name: str
    path: str
    prd_path: str
    priority: str = "normal"
    archived: bool = False
    created_at: str | None = None
    last_opened_at: str | None = None
    source_kind: str = "manual"
    task_source: TaskSource = Field(default_factory=TaskSource)
    execution_brief_path: str | None = None
    delivery_loop: dict[str, Any] = Field(default_factory=dict)
    delivery_status: dict[str, Any] = Field(default_factory=dict)
    initiative: InitiativeContext = Field(default_factory=InitiativeContext)
    orchestration: OrchestrationContext = Field(default_factory=OrchestrationContext)
    provenance: ProvenanceContext = Field(default_factory=ProvenanceContext)
    launch_profile: dict[str, Any] = Field(default_factory=dict)
    provider_config: dict[str, Any] = Field(default_factory=dict)
    runtime_profile: dict[str, Any] = Field(default_factory=dict)
    command_policy: dict[str, Any] = Field(default_factory=dict)
    runtime_agent_count: int = 0
    open_issue_count: int = 0
    runtime: ExecutionPlaneRuntime = Field(default_factory=ExecutionPlaneRuntime)
    progress: ExecutionPlaneProgress = Field(default_factory=ExecutionPlaneProgress)
    budget: ExecutionPlaneBudget = Field(default_factory=ExecutionPlaneBudget)
    cost: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlaneProjectDetail(ExecutionPlaneProjectSnapshot):
    """Detailed execution-plane state for one project."""

    description: str = ""
    phases: list[dict[str, Any]] = Field(default_factory=list)
    stories: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    runtime_control: dict[str, Any] = Field(default_factory=dict)
    runtime_agents: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    brief: dict[str, Any] | None = None
    trace: dict[str, Any] = Field(default_factory=dict)


@dataclass(slots=True)
class IngestedExecutionProject:
    """Result of execution-brief ingestion into a local Autopilot project."""

    created: CreatedProject
    prd: dict[str, Any]
    brief_path: Path
    launched: bool
    message: str
    log_path: Path | None
    launch_profile: dict[str, Any] | None


@dataclass(slots=True)
class ParsedExecutionPlaneAgentActionKey:
    """Parsed runtime-agent action key emitted by the action feed."""

    runtime_agent_id: str
    action_type: str
    name: str


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


def execution_brief_path(project_root: Path, *, relpath: str = EXECUTION_BRIEF_RELPATH) -> Path:
    """Resolve the persisted execution-brief path for a project root."""

    return (project_root / relpath).resolve()


def persist_execution_brief(
    project_root: Path,
    brief: ExecutionBrief,
    *,
    relpath: str = EXECUTION_BRIEF_RELPATH,
) -> Path:
    """Persist the typed execution brief alongside the project PRD."""

    path = execution_brief_path(project_root, relpath=relpath)
    _atomic_write_json(path, brief.model_dump())
    return path


def _brief_control_plane_metadata(brief: ExecutionBrief, *, brief_relpath: str) -> dict[str, Any]:
    return {
        "source_kind": "execution_brief",
        "task_source": brief.task_source.model_dump(),
        "execution_brief": {
            "version": brief.version,
            "relpath": brief_relpath,
            "title": brief.title,
            "summary": brief.summary,
            "tags": list(brief.tags),
        },
        "initiative": brief.initiative.model_dump(),
        "orchestration": brief.orchestration.model_dump(),
        "provenance": brief.provenance.model_dump(),
    }


def attach_execution_brief_metadata(
    config: AutopilotConfig,
    *,
    project_id: str,
    brief: ExecutionBrief,
    brief_relpath: str = EXECUTION_BRIEF_RELPATH,
) -> dict[str, Any]:
    """Attach execution-brief control-plane metadata to a registered project."""

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    existing_control_plane = dict(project.get("control_plane") or {})
    incoming = _brief_control_plane_metadata(brief, brief_relpath=brief_relpath)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(existing_control_plane.get(key), dict):
            existing_control_plane[key] = {**existing_control_plane[key], **value}
        else:
            existing_control_plane[key] = value

    project["control_plane"] = existing_control_plane
    return update_project_entry(config, project)


def load_project_execution_brief(project: dict[str, Any]) -> ExecutionBrief | None:
    """Load a persisted execution brief from a project if present."""

    control_plane = project.get("control_plane") or {}
    relpath = str(control_plane.get("execution_brief", {}).get("relpath") or EXECUTION_BRIEF_RELPATH)
    path = Path(project["path"]) / relpath
    if not path.exists():
        return None
    try:
        return ExecutionBrief.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def _resolve_control_plane_context(project: dict[str, Any], brief: ExecutionBrief | None) -> tuple[str, str | None, dict[str, Any]]:
    control_plane = dict(project.get("control_plane") or {})
    execution_brief_meta = dict(control_plane.get("execution_brief") or {})
    brief_relpath = str(execution_brief_meta.get("relpath") or EXECUTION_BRIEF_RELPATH)
    brief_path = str((Path(project["path"]) / brief_relpath).resolve()) if (Path(project["path"]) / brief_relpath).exists() else None

    initiative_payload = control_plane.get("initiative") or {}
    orchestration_payload = control_plane.get("orchestration") or {}
    provenance_payload = control_plane.get("provenance") or {}
    source_kind = str(control_plane.get("source_kind") or "")

    if brief is not None:
        if not initiative_payload:
            initiative_payload = brief.initiative.model_dump()
        if not orchestration_payload:
            orchestration_payload = brief.orchestration.model_dump()
        if not provenance_payload:
            provenance_payload = brief.provenance.model_dump()
        if not source_kind:
            source_kind = "execution_brief"

    task_source = resolve_project_task_source(project)
    if not source_kind:
        source_kind = str(task_source.get("source_kind") or "").strip() or "manual"

    return (
        source_kind,
        brief_path,
        {
            "initiative": InitiativeContext.model_validate(initiative_payload or {}).model_dump(),
            "orchestration": OrchestrationContext.model_validate(orchestration_payload or {}).model_dump(),
            "provenance": ProvenanceContext.model_validate(provenance_payload or {}).model_dump(),
        },
    )


def _resolve_execution_brief_task_source(brief: ExecutionBrief) -> TaskSource:
    """Return the canonical TaskSource contract for an execution brief."""

    current = brief.task_source
    source_kind = current.source_kind.strip() or "execution_brief"
    external_id = (
        current.external_id.strip()
        or brief.initiative.id.strip()
        or brief.orchestration.project_ref.strip()
        or brief.provenance.source_session_id.strip()
    )
    repo = current.repo.strip() or next(
        (str(repo).strip() for repo in brief.execution.existing_repos if str(repo).strip()),
        "",
    )
    branch_policy = current.branch_policy.strip() or "isolated_worktree"
    if branch_policy not in {"shared_main", "isolated_worktree"}:
        branch_policy = "isolated_worktree"
    brief_ref = current.brief_ref.strip() or EXECUTION_BRIEF_RELPATH
    return TaskSource(
        source_kind=source_kind,
        external_id=external_id,
        repo=repo,
        branch_policy=branch_policy,
        brief_ref=brief_ref,
    )


DEFAULT_COMMAND_POLICY: dict[str, Any] = {
    "approval_required_commands": [],
    "parallel_launch_requires_approval": True,
    "max_parallel_stories_without_approval": 1,
    "disable_auto_pause_requires_approval": False,
    "github_approved_and_green_auto_resume": False,
    "project_max_worker_iterations_without_approval": 14,
    "project_max_critic_reviews_without_approval": 6,
    "run_max_worker_iterations_without_approval": 60,
    "run_max_critic_reviews_without_approval": 60,
    "story_max_worker_iterations_without_approval": 16,
    "story_max_critic_reviews_without_approval": 16,
    "agent_max_worker_iterations_without_approval": 8,
    "agent_max_critic_reviews_without_approval": 4,
    "run_max_runtime_seconds_without_approval": 43200,
    "story_max_runtime_seconds_without_approval": 14400,
}


def default_execution_command_policy() -> dict[str, Any]:
    """Return the default external command policy for one project."""

    return {
        "approval_required_commands": list(DEFAULT_COMMAND_POLICY["approval_required_commands"]),
        "parallel_launch_requires_approval": DEFAULT_COMMAND_POLICY["parallel_launch_requires_approval"],
        "max_parallel_stories_without_approval": DEFAULT_COMMAND_POLICY["max_parallel_stories_without_approval"],
        "disable_auto_pause_requires_approval": DEFAULT_COMMAND_POLICY["disable_auto_pause_requires_approval"],
        "github_approved_and_green_auto_resume": DEFAULT_COMMAND_POLICY["github_approved_and_green_auto_resume"],
        "project_max_worker_iterations_without_approval": DEFAULT_COMMAND_POLICY["project_max_worker_iterations_without_approval"],
        "project_max_critic_reviews_without_approval": DEFAULT_COMMAND_POLICY["project_max_critic_reviews_without_approval"],
        "run_max_worker_iterations_without_approval": DEFAULT_COMMAND_POLICY["run_max_worker_iterations_without_approval"],
        "run_max_critic_reviews_without_approval": DEFAULT_COMMAND_POLICY["run_max_critic_reviews_without_approval"],
        "story_max_worker_iterations_without_approval": DEFAULT_COMMAND_POLICY["story_max_worker_iterations_without_approval"],
        "story_max_critic_reviews_without_approval": DEFAULT_COMMAND_POLICY["story_max_critic_reviews_without_approval"],
        "agent_max_worker_iterations_without_approval": DEFAULT_COMMAND_POLICY["agent_max_worker_iterations_without_approval"],
        "agent_max_critic_reviews_without_approval": DEFAULT_COMMAND_POLICY["agent_max_critic_reviews_without_approval"],
        "run_max_runtime_seconds_without_approval": DEFAULT_COMMAND_POLICY["run_max_runtime_seconds_without_approval"],
        "story_max_runtime_seconds_without_approval": DEFAULT_COMMAND_POLICY["story_max_runtime_seconds_without_approval"],
    }


def load_project_command_policy(config: AutopilotConfig, project_id: str) -> dict[str, Any]:
    """Load one project's execution command policy with defaults applied."""

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)
    control_plane = dict(project.get("control_plane") or {})
    stored_policy = dict(control_plane.get("command_policy") or {})
    policy = default_execution_command_policy()
    if isinstance(stored_policy.get("approval_required_commands"), list):
        policy["approval_required_commands"] = [str(item) for item in stored_policy["approval_required_commands"]]
    for key, default_value in DEFAULT_COMMAND_POLICY.items():
        if key == "approval_required_commands":
            continue
        if key in stored_policy and stored_policy[key] is not None:
            policy[key] = stored_policy[key]
    return policy


def update_project_command_policy(config: AutopilotConfig, project_id: str, **fields: Any) -> dict[str, Any]:
    """Update a project's execution command policy in control-plane metadata."""

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    control_plane = dict(project.get("control_plane") or {})
    policy = load_project_command_policy(config, project_id)
    for key, value in fields.items():
        if value is None:
            continue
        if key == "approval_required_commands":
            policy[key] = [str(item) for item in value]
        else:
            policy[key] = value
    control_plane["command_policy"] = policy
    project["control_plane"] = control_plane
    update_project_entry(config, project)
    return policy


def evaluate_execution_command_policy(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None = None,
    record_denial: bool = False,
) -> dict[str, Any]:
    """Evaluate whether a command should require approval under project policy."""

    policy = load_project_command_policy(config, project_id)
    tool = _build_execution_command_tool(config, project_id=project_id, command=command)
    permission_context = _execution_command_permission_context(
        config,
        project_id=project_id,
        command=command,
        payload=payload,
    )
    decision = resolve_tool_permission_decision(
        tool,
        payload or {},
        permission_context,
        config=config,
        project_id=project_id,
        record_denial=record_denial,
        actor="execution_plane",
        source="execution_plane.evaluate",
    )
    reasons = list(decision.reasons)
    if decision.behavior == "deny" and not reasons and decision.message:
        reasons = [decision.message]

    return {
        "requires_approval": decision.behavior == "ask",
        "denied": decision.behavior == "deny",
        "allowed": decision.behavior == "allow",
        "behavior": decision.behavior,
        "message": decision.message,
        "reasons": reasons,
        "policy": policy,
    }


def create_execution_command_issue(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    requested_by: str,
    reason: str,
    policy_reasons: list[str],
    runtime_agent_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Create or reuse a control-plane issue for a command needing approval."""

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)
    runtime_agent_ids = list(runtime_agent_ids or _affected_runtime_agent_ids(config, project))

    is_policy_issue = bool(policy_reasons)
    state = load_project_state(config, project_id)
    description_lines = []
    if reason.strip():
        description_lines.append(reason.strip())
    if policy_reasons:
        description_lines.append("Policy reasons:")
        description_lines.extend(f"- {item}" for item in policy_reasons)
    if requested_by.strip():
        description_lines.append(f"Requested by: {requested_by.strip()}")

    root_cause = policy_reasons[0] if policy_reasons else (reason.strip() or f"Approval requested for `{command}`.")

    issue = create_issue(
        config,
        project=project,
        title=f"Approval required for `{command}`",
        description="\n".join(description_lines).strip(),
        root_cause=root_cause,
        category="policy_approval" if is_policy_issue else "approval_request",
        severity="high" if is_policy_issue else "medium",
        related_command=command,
        runtime_agent_id=runtime_agent_ids[0] if len(runtime_agent_ids) == 1 else "",
        runtime_agent_ids=runtime_agent_ids,
        dedupe_key=f"{project_id}:{command}:approval",
        context={
            "project": {
                "status": state.get("status"),
                "paused": state.get("paused"),
                "current_story_id": state.get("current_story_id"),
                "current_iteration": state.get("current_iteration"),
            },
            "command": {
                "name": command,
                "requested_by": requested_by,
                "reason": reason,
                "policy_reasons": list(policy_reasons),
                "runtime_agent_ids": runtime_agent_ids,
            },
        },
    )
    return issue.model_dump()


def _build_progress_snapshot(stories: list[dict[str, Any]]) -> ExecutionPlaneProgress:
    status_counts = {
        "open": 0,
        "done": 0,
        "in_progress": 0,
        "skipped": 0,
        "blocked": 0,
    }
    for story in stories:
        status = str(story.get("status") or "open")
        if status == "done":
            status_counts["done"] += 1
        elif status == "skipped":
            status_counts["skipped"] += 1
        elif status == "in_progress":
            status_counts["in_progress"] += 1
        elif status in {"merge_blocked", "stuck"}:
            status_counts["blocked"] += 1
        else:
            status_counts["open"] += 1

    return ExecutionPlaneProgress(
        stories_total=len(stories),
        stories_done=status_counts["done"],
        stories_open=status_counts["open"],
        stories_in_progress=status_counts["in_progress"],
        stories_blocked=status_counts["blocked"],
        stories_skipped=status_counts["skipped"],
    )


def build_execution_plane_runtime_agents(
    config: AutopilotConfig,
    project: dict[str, Any],
    stories: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Derive stable runtime-agent snapshots from team plans, story state, and leases."""

    leases = {lease.story_id: lease for lease in list_project_work_item_leases(config, str(project["id"]))}
    return build_runtime_agents(str(project["id"]), stories, leases_by_story=leases)


def _affected_runtime_agent_ids(config: AutopilotConfig, project: dict[str, Any]) -> list[str]:
    state = ensure_project_state(config, project, seed_mode="migrate")
    stories = merge_project_stories(config, project, state)
    runtime_agents = build_execution_plane_runtime_agents(config, project, stories)
    active_agent_ids = [str(agent["agent_id"]) for agent in runtime_agents if agent.get("status") == "active"]
    if active_agent_ids:
        return active_agent_ids

    current_story_id = state.get("current_story_id")
    if current_story_id is not None:
        story_agent_ids = [
            str(agent["agent_id"])
            for agent in runtime_agents
            if int(agent.get("story_id") or -1) == int(current_story_id)
        ]
        if story_agent_ids:
            return story_agent_ids
    return []


def _runtime_agent_usage_label(agent: dict[str, Any]) -> str:
    provider = str(agent.get("provider") or "").strip()
    profile_name = str(agent.get("profile_name") or "").strip()
    if provider and profile_name:
        return f"{provider}/{profile_name}"
    label = str(agent.get("label") or "").strip()
    if "/" in label:
        return label
    return ""


def _runtime_agent_budget_summary(
    state: dict[str, Any],
    agent: dict[str, Any] | None,
    *,
    role: str,
) -> dict[str, Any]:
    policy, usage = ensure_budget_state(state)
    normalized_role = str(role or "").strip()
    metric = ""
    limit: int | None = None
    if normalized_role == "worker":
        metric = "worker_iterations"
        limit = int(policy.get("agent_max_worker_iterations") or 0)
    elif normalized_role == "critic":
        metric = "critic_reviews"
        limit = int(policy.get("agent_max_critic_reviews") or 0)

    usage_label = _runtime_agent_usage_label(agent or {})
    agent_usage = dict((usage.get("agents") or {}).get(usage_label) or {}) if usage_label else {}
    used = int(agent_usage.get(metric) or 0) if metric else 0
    exhausted = bool(metric and limit is not None and limit > 0 and used >= limit)
    remaining = (limit - used) if metric and limit is not None else None
    return {
        "tracked": bool(metric),
        "usage_label": usage_label or None,
        "metric": metric or None,
        "used": used if metric else None,
        "limit": limit,
        "remaining": remaining,
        "exhausted": exhausted,
        "auto_pause_on_exhaustion": bool(policy.get("auto_pause_on_exhaustion", True)),
        "last_exhaustion_reason": usage.get("last_exhaustion_reason"),
        "auto_paused_at": usage.get("auto_paused_at"),
    }


def _runtime_agent_attention_summary(
    *,
    agent: dict[str, Any] | None,
    project_snapshot: dict[str, Any],
    budget: dict[str, Any],
    open_issues: list[dict[str, Any]],
    pending_approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    agent_status = str((agent or {}).get("status") or "")

    if open_issues:
        reasons.append(
            f"{len(open_issues)} open issue(s): "
            + ", ".join(str(issue.get("title") or issue.get("category") or "issue") for issue in open_issues[:2])
        )
    if pending_approvals:
        reasons.append(
            f"{len(pending_approvals)} pending approval(s): "
            + ", ".join(str(approval.get("action") or "approval") for approval in pending_approvals[:2])
        )
    if budget.get("tracked") and budget.get("exhausted"):
        reasons.append("Agent budget is exhausted.")
    elif budget.get("tracked") and isinstance(budget.get("remaining"), int) and int(budget["remaining"]) <= 2:
        reasons.append(f"Agent budget is low ({budget['remaining']} remaining).")
    if project_snapshot["runtime"]["paused"]:
        reasons.append("Project is currently paused.")
    if agent_status in {"blocked", "stuck"}:
        reasons.append(f"Agent status is `{agent_status}`.")

    if open_issues or agent_status in {"blocked", "stuck"}:
        state = "blocked"
        recommended_action = "Resolve linked issues before resuming execution."
    elif pending_approvals:
        state = "needs_approval"
        recommended_action = "Review and apply or reject pending control-plane actions."
    elif budget.get("tracked") and budget.get("exhausted"):
        state = "budget_exhausted"
        recommended_action = "Increase the relevant budget or rotate to another account."
    elif budget.get("tracked") and isinstance(budget.get("remaining"), int) and int(budget["remaining"]) <= 2:
        state = "budget_risk"
        recommended_action = "Watch remaining budget or rotate this agent soon."
    elif project_snapshot["runtime"]["paused"]:
        state = "paused"
        recommended_action = "Resume the project or inspect the pause reason."
    elif agent_status == "active":
        state = "active"
        recommended_action = "Monitor current execution."
    else:
        state = "healthy"
        recommended_action = "No immediate action required."

    return {
        "state": state,
        "recommended_action": recommended_action,
        "reasons": reasons[:4],
    }


def _budget_policy_update_suggestion(
    *,
    role: str,
    limit: int | None,
) -> dict[str, Any] | None:
    if limit is None or limit <= 0:
        return None
    if role == "worker":
        key = "agent_max_worker_iterations"
    elif role == "critic":
        key = "agent_max_critic_reviews"
    else:
        return None
    suggested_limit = max(limit + 5, int(limit * 1.25) if limit >= 4 else limit + 5)
    if suggested_limit <= limit:
        suggested_limit = limit + 5
    return {"budget_policy": {key: suggested_limit}}


def _command_suggestion(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None,
    title: str,
    reason: str,
    priority: str,
) -> dict[str, Any]:
    policy = evaluate_execution_command_policy(
        config,
        project_id=project_id,
        command=command,
        payload=payload or {},
    )
    return {
        "command": command,
        "payload": payload or {},
        "title": title,
        "reason": reason,
        "priority": priority,
        "approval_required": bool(policy["requires_approval"]),
        "policy_reasons": list(policy["reasons"]),
    }


def parse_execution_plane_agent_action_key(action_key: str) -> ParsedExecutionPlaneAgentActionKey | None:
    """Parse one flattened runtime-agent action key."""

    if not action_key.strip():
        return None
    parts = action_key.rsplit(":", 2)
    if len(parts) != 3:
        return None
    runtime_agent_id, raw_type, name = parts
    if parse_runtime_agent_id(runtime_agent_id) is None:
        return None
    if raw_type == "recommendation":
        action_type = "recommendation"
    elif raw_type == "command":
        action_type = "suggested_command"
    else:
        return None
    if not name.strip():
        return None
    return ParsedExecutionPlaneAgentActionKey(runtime_agent_id=runtime_agent_id, action_type=action_type, name=name)


def _runtime_agent_recommendations(
    config: AutopilotConfig,
    *,
    project_id: str,
    project_snapshot: dict[str, Any],
    agent: dict[str, Any] | None,
    budget: dict[str, Any],
    attention: dict[str, Any],
    open_issues: list[dict[str, Any]],
    pending_approvals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recommendations: list[dict[str, Any]] = []
    suggested_commands: list[dict[str, Any]] = []
    role = str((agent or {}).get("role") or "")

    if open_issues:
        recommendations.append(
            {
                "kind": "resolve_issues",
                "priority": "high",
                "title": "Resolve linked runtime issues",
                "reason": attention["recommended_action"],
                "issue_ids": [str(issue["id"]) for issue in open_issues],
                "issue_categories": sorted({str(issue.get("category") or "") for issue in open_issues if issue.get("category")}),
            }
        )

    if pending_approvals:
        recommendations.append(
            {
                "kind": "review_approvals",
                "priority": "high",
                "title": "Review pending approvals",
                "reason": attention["recommended_action"],
                "approval_ids": [str(approval["id"]) for approval in pending_approvals],
                "actions": [str(approval.get("action") or "") for approval in pending_approvals],
            }
        )

    if budget.get("tracked") and budget.get("exhausted"):
        recommendations.append(
            {
                "kind": "rotate_account",
                "priority": "high",
                "title": "Rotate this runtime account",
                "reason": "This agent has exhausted its tracked runtime budget.",
                "usage_label": budget.get("usage_label"),
            }
        )
        payload = _budget_policy_update_suggestion(role=role, limit=budget.get("limit"))
        if payload is not None:
            suggested_commands.append(
                _command_suggestion(
                    config,
                    project_id=project_id,
                    command="update_budget_policy",
                    payload=payload,
                    title="Increase per-agent budget limit",
                    reason="This runtime agent exhausted its tracked budget.",
                    priority="high",
                )
            )
    elif budget.get("tracked") and isinstance(budget.get("remaining"), int) and int(budget["remaining"]) <= 2:
        recommendations.append(
            {
                "kind": "rotate_account",
                "priority": "medium",
                "title": "Rotate this runtime account soon",
                "reason": f"Only {budget['remaining']} unit(s) of tracked budget remain.",
                "usage_label": budget.get("usage_label"),
            }
        )
        payload = _budget_policy_update_suggestion(role=role, limit=budget.get("limit"))
        if payload is not None:
            suggested_commands.append(
                _command_suggestion(
                    config,
                    project_id=project_id,
                    command="update_budget_policy",
                    payload=payload,
                    title="Preemptively raise per-agent budget",
                    reason="This runtime agent is approaching its per-agent budget limit.",
                    priority="medium",
                )
            )

    if project_snapshot["runtime"]["paused"]:
        suggested_commands.append(
            _command_suggestion(
                config,
                project_id=project_id,
                command="resume",
                payload={},
                title="Resume project execution",
                reason="The project is paused and this agent is waiting on project-level execution to continue.",
                priority="medium",
            )
        )

    if not recommendations and not suggested_commands:
        recommendations.append(
            {
                "kind": "monitor",
                "priority": "low",
                "title": "Monitor runtime agent",
                "reason": attention["recommended_action"],
            }
        )

    return recommendations, suggested_commands


ACTION_PRIORITY_ORDER: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}
ACTION_BATCH_POLICY_PROFILES: dict[str, dict[str, Any]] = {
    "balanced_safe": {
        "include_action_types": ["suggested_command"],
        "skip_paused_projects": False,
        "exclude_attention_states": [],
        "priority_at_least": None,
        "approval_strategy": None,
        "approval_priority_at_least": None,
        "allowed_commands": [],
        "allowed_recommendation_kinds": [],
        "max_actions_per_project": None,
    },
    "safe_budget_maintenance": {
        "include_action_types": ["suggested_command"],
        "skip_paused_projects": True,
        "exclude_attention_states": ["healthy"],
        "priority_at_least": "medium",
        "approval_strategy": "skip",
        "approval_priority_at_least": "high",
        "allowed_commands": ["update_budget_policy"],
        "allowed_recommendation_kinds": [],
        "max_actions_per_project": 1,
    },
    "budget_maintenance_with_high_priority_escalation": {
        "include_action_types": ["suggested_command"],
        "skip_paused_projects": True,
        "exclude_attention_states": ["healthy"],
        "priority_at_least": "medium",
        "approval_strategy": "request",
        "approval_priority_at_least": "high",
        "allowed_commands": ["update_budget_policy"],
        "allowed_recommendation_kinds": [],
        "max_actions_per_project": 1,
    },
}


def _priority_meets_threshold(priority: str | None, threshold: str | None) -> bool:
    if not threshold:
        return True
    if not priority:
        return False
    normalized_priority = str(priority).strip().lower()
    normalized_threshold = str(threshold).strip().lower()
    if normalized_priority not in ACTION_PRIORITY_ORDER or normalized_threshold not in ACTION_PRIORITY_ORDER:
        return False
    return ACTION_PRIORITY_ORDER[normalized_priority] <= ACTION_PRIORITY_ORDER[normalized_threshold]


def list_execution_plane_agent_action_policy_profiles() -> dict[str, dict[str, Any]]:
    """Return built-in batch action policy profiles."""

    return {
        name: {"name": name, **policy}
        for name, policy in ACTION_BATCH_POLICY_PROFILES.items()
    }


def resolve_execution_plane_agent_action_batch_policy(
    *,
    profile_name: str | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve one batch action policy from a built-in profile plus overrides."""

    base_policy: dict[str, Any] = {}
    if profile_name:
        base_policy = ACTION_BATCH_POLICY_PROFILES.get(profile_name) or {}
        if not base_policy:
            raise ValueError(f"Unknown runtime-agent action policy profile: {profile_name}")

    overrides = dict(overrides or {})
    resolved = {
        "profile_name": profile_name or "",
        "include_action_types": [str(item) for item in base_policy.get("include_action_types") or []],
        "skip_paused_projects": bool(base_policy.get("skip_paused_projects", False)),
        "exclude_attention_states": [str(item) for item in base_policy.get("exclude_attention_states") or []],
        "priority_at_least": base_policy.get("priority_at_least"),
        "approval_strategy": base_policy.get("approval_strategy"),
        "approval_priority_at_least": base_policy.get("approval_priority_at_least"),
        "allowed_commands": [str(item) for item in base_policy.get("allowed_commands") or []],
        "allowed_recommendation_kinds": [str(item) for item in base_policy.get("allowed_recommendation_kinds") or []],
        "max_actions_per_project": base_policy.get("max_actions_per_project"),
    }

    for key, value in overrides.items():
        if value is None:
            continue
        if key in {"include_action_types", "exclude_attention_states", "allowed_commands", "allowed_recommendation_kinds"}:
            resolved[key] = [str(item) for item in value]
        else:
            resolved[key] = value

    for action_type in resolved["include_action_types"]:
        if action_type not in {"recommendation", "suggested_command"}:
            raise ValueError(f"Unsupported batch action policy action type: {action_type}")
    if resolved["approval_strategy"] not in {None, "", "skip", "request"}:
        raise ValueError(
            "Unsupported batch action approval strategy: "
            f"{resolved['approval_strategy']}. Expected one of skip or request."
        )
    for key in ("priority_at_least", "approval_priority_at_least"):
        value = resolved.get(key)
        if value not in {None, "", "high", "medium", "low"}:
            raise ValueError(
                f"Unsupported batch action policy priority threshold `{value}` for `{key}`."
            )
    max_actions = resolved.get("max_actions_per_project")
    if max_actions is not None and int(max_actions) <= 0:
        raise ValueError("Batch action policy `max_actions_per_project` must be positive.")

    return resolved


def _execution_plane_agent_action_batch_request_fingerprint(payload: dict[str, Any]) -> str:
    """Build a stable fingerprint for one batch action request."""

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _execution_plane_agent_action_request_fingerprint(payload: dict[str, Any]) -> str:
    """Build a stable fingerprint for one single-action execution request."""

    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _increment_count(bucket: dict[str, int], key: str) -> None:
    normalized = str(key or "").strip()
    if not normalized:
        return
    bucket[normalized] = bucket.get(normalized, 0) + 1


def _listify_strings(values: list[Any] | None) -> list[str]:
    return [str(item).strip() for item in (values or []) if str(item).strip()]


def _execution_plane_agent_action_run_requires_approval(
    selected_actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> bool:
    if any(bool(action.get("approval_required")) for action in selected_actions):
        return True
    for result in results:
        if str(result.get("status") or "") in {"planned_request_approval", "pending_approval"}:
            return True
        approval = result.get("approval") or {}
        if str(approval.get("id") or "").strip():
            return True
    return False


def _execution_plane_agent_action_apply_mode(
    *,
    dry_run: bool,
    requested_mode: str,
    approval_required: bool,
) -> str:
    if approval_required or requested_mode == "request_approval":
        return "policy"
    if dry_run:
        return "manual"
    return "auto"


def _build_execution_plane_agent_action_diff_summary(
    selected_actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    status_counts: dict[str, int],
    approval_required: bool,
    apply_mode: str,
) -> dict[str, Any]:
    command_counts: dict[str, int] = {}
    recommendation_counts: dict[str, int] = {}
    attention_state_counts: dict[str, int] = {}
    policy_reason_counts: dict[str, int] = {}
    planned_mode_counts: dict[str, int] = {}
    why: list[str] = []
    seen_why: set[str] = set()

    project_ids = {
        str(action.get("project_id") or "").strip()
        for action in selected_actions
        if str(action.get("project_id") or "").strip()
    }
    runtime_agent_ids = {
        str(action.get("runtime_agent_id") or "").strip()
        for action in selected_actions
        if str(action.get("runtime_agent_id") or "").strip()
    }

    approval_required_count = 0
    for action in selected_actions:
        action_type = str(action.get("action_type") or "")
        if action_type == "suggested_command":
            _increment_count(command_counts, str(action.get("command") or "unknown"))
        elif action_type == "recommendation":
            _increment_count(recommendation_counts, str(action.get("kind") or "unknown"))
        _increment_count(attention_state_counts, str((action.get("attention") or {}).get("state") or "unknown"))
        for policy_reason in _listify_strings(action.get("policy_reasons")):
            _increment_count(policy_reason_counts, policy_reason)
        reason = str(action.get("reason") or "").strip()
        if reason and reason not in seen_why:
            why.append(reason)
            seen_why.add(reason)
        if bool(action.get("approval_required")):
            approval_required_count += 1

    for result in results:
        _increment_count(planned_mode_counts, str(result.get("planned_mode") or ""))

    return {
        "selected_count": len(selected_actions),
        "processed_count": len(results),
        "project_count": len(project_ids),
        "runtime_agent_count": len(runtime_agent_ids),
        "approval_required": approval_required,
        "approval_required_count": approval_required_count,
        "apply_mode": apply_mode,
        "status_counts": dict(status_counts),
        "planned_mode_counts": planned_mode_counts,
        "command_counts": command_counts,
        "recommendation_counts": recommendation_counts,
        "attention_state_counts": attention_state_counts,
        "policy_reason_counts": policy_reason_counts,
        "why": why[:5],
    }


def _build_execution_plane_agent_action_patch_bundle(
    selected_actions: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    requested_mode: str,
    dry_run: bool,
    default_apply_mode: str,
) -> dict[str, Any]:
    result_by_action_key: dict[str, dict[str, Any]] = {}
    for result in results:
        action = result.get("action") or {}
        action_key = str(action.get("action_key") or "").strip()
        if action_key and action_key not in result_by_action_key:
            result_by_action_key[action_key] = result

    operations: list[dict[str, Any]] = []
    for index, action in enumerate(selected_actions):
        action_key = str(action.get("action_key") or "").strip()
        result = result_by_action_key.get(action_key)
        if result is None and index < len(results):
            result = results[index]
        result = dict(result or {})

        action_requires_approval = bool(action.get("approval_required"))
        operation_planned_mode = str(result.get("planned_mode") or requested_mode or "").strip()
        operation_apply_mode = (
            "policy"
            if action_requires_approval or operation_planned_mode == "request_approval"
            else default_apply_mode
        )
        operations.append(
            {
                "action_key": action_key,
                "project_id": str(action.get("project_id") or ""),
                "project_name": str(action.get("project_name") or ""),
                "runtime_agent_id": str(action.get("runtime_agent_id") or ""),
                "action_type": str(action.get("action_type") or ""),
                "command": str(action.get("command") or ""),
                "kind": str(action.get("kind") or ""),
                "title": str(action.get("title") or ""),
                "reason": str(action.get("reason") or ""),
                "attention_state": str((action.get("attention") or {}).get("state") or ""),
                "attention_reasons": _listify_strings((action.get("attention") or {}).get("reasons")),
                "policy_reasons": _listify_strings(action.get("policy_reasons")),
                "approval_required": action_requires_approval,
                "requested_mode": requested_mode,
                "planned_mode": operation_planned_mode,
                "apply_mode": operation_apply_mode,
                "result_status": str(result.get("status") or ""),
                "message": str(result.get("message") or ""),
            }
        )

    return {
        "kind": "runtime_agent_action_batch",
        "dry_run": dry_run,
        "operations": operations,
    }


def _materialize_execution_plane_runtime_agent_task_record(
    record: RuntimeAgentTaskRecord,
) -> dict[str, Any]:
    payload = record.model_dump()
    payload["artifact_ref"] = f"/api/execution-plane/agents/tasks/{record.id}"
    payload["active"] = record.status in {"queued", "running"}
    payload["terminal"] = record.status in {"completed", "failed", "cancelled"}
    return payload


def _refresh_result_async_tasks(
    config: AutopilotConfig,
    results: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for raw_result in results or []:
        result = dict(raw_result)
        async_task = result.get("async_task")
        async_task_id = ""
        if isinstance(async_task, dict):
            async_task_id = str(async_task.get("id") or "").strip()
        if not async_task_id:
            async_task_id = str(result.get("async_task_id") or "").strip()
        if async_task_id:
            task = get_runtime_agent_task(config, async_task_id)
            if task is not None:
                result["async_task"] = _materialize_execution_plane_runtime_agent_task_record(
                    refresh_runtime_agent_task(config, task)
                )
        refreshed.append(result)
    return refreshed


def _materialize_execution_plane_agent_action_run_record(
    config: AutopilotConfig,
    record: AgentActionBatchRunRecord,
) -> dict[str, Any]:
    payload = record.model_dump()
    payload["results"] = _refresh_result_async_tasks(config, record.results)
    approval_required = bool(payload.get("approval_required")) or _execution_plane_agent_action_run_requires_approval(
        [],
        list(payload.get("results") or []),
    )
    preview_id = str(payload.get("preview_id") or "").strip()
    artifact_ref = str(payload.get("artifact_ref") or "").strip()
    apply_mode = str(payload.get("apply_mode") or "").strip()

    if record.dry_run and not preview_id:
        preview_id = record.id
    if not artifact_ref:
        artifact_ref = f"/api/execution-plane/agents/action-runs/{record.id}"
    if not apply_mode:
        apply_mode = _execution_plane_agent_action_apply_mode(
            dry_run=record.dry_run,
            requested_mode=record.mode,
            approval_required=approval_required,
        )

    payload["preview_id"] = preview_id
    payload["artifact_ref"] = artifact_ref
    payload["approval_required"] = approval_required
    payload["apply_mode"] = apply_mode
    payload.setdefault("diff_summary", {})
    payload.setdefault("patch_bundle", {})
    return payload


def _execution_plane_agent_action_batch_run_response(
    config: AutopilotConfig,
    record: AgentActionBatchRunRecord,
    *,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    """Project one persisted batch run record back into API response shape."""

    run_payload = _materialize_execution_plane_agent_action_run_record(config, record)
    return {
        "status": record.status,
        "selection": record.selection,
        "policy": record.policy,
        "summary": record.summary,
        "diff_summary": run_payload["diff_summary"],
        "patch_bundle": run_payload["patch_bundle"],
        "preview_id": run_payload["preview_id"],
        "artifact_ref": run_payload["artifact_ref"],
        "approval_required": run_payload["approval_required"],
        "apply_mode": run_payload["apply_mode"],
        "dry_run": record.dry_run,
        "results": run_payload["results"],
        "run": run_payload,
        "idempotent_replay": idempotent_replay,
    }


def _execution_plane_agent_action_run_response(
    config: AutopilotConfig,
    record: AgentActionBatchRunRecord,
    *,
    idempotent_replay: bool = False,
) -> dict[str, Any]:
    """Project one persisted single-action run record back into API response shape."""

    run_payload = _materialize_execution_plane_agent_action_run_record(config, record)
    payload = dict((record.results or [{}])[0])
    if run_payload["results"]:
        payload = dict(run_payload["results"][0])
    payload.setdefault("status", record.status)
    payload["preview_id"] = run_payload["preview_id"]
    payload["diff_summary"] = run_payload["diff_summary"]
    payload["patch_bundle"] = run_payload["patch_bundle"]
    payload["artifact_ref"] = run_payload["artifact_ref"]
    payload["approval_required"] = run_payload["approval_required"]
    payload["apply_mode"] = run_payload["apply_mode"]
    payload["run"] = run_payload
    payload["idempotent_replay"] = idempotent_replay
    return payload


def _emit_execution_plane_agent_action_batch_run_events(
    config: AutopilotConfig,
    record: AgentActionBatchRunRecord,
) -> None:
    """Emit per-project lifecycle events for one persisted batch run report."""

    event_name = "execution_plane_agent_batch_previewed" if record.dry_run else "execution_plane_agent_batch_executed"
    summary = dict(record.summary or {})
    status_counts = dict(summary.get("status_counts") or {})
    project_ids = list(record.project_ids)
    scoped_project_id = str((record.selection or {}).get("project_id") or "")
    if not project_ids and scoped_project_id:
        project_ids = [scoped_project_id]
    for project_id in project_ids:
        emit_project_event(
            config,
            project_id,
            event=event_name,
            status=str(record.status or "ok"),
            message=f"Runtime-agent batch {'preview' if record.dry_run else 'execution'} `{record.id}` recorded.",
            extra={
                "agent_action_run_id": record.id,
                "idempotency_key": record.idempotency_key,
                "actor": record.actor,
                "batch_mode": record.mode,
                "dry_run": record.dry_run,
                "policy_profile": record.policy_profile,
                "orchestrator_session_id": record.orchestrator_session_id,
                "selected_count": int(summary.get("selected_count") or 0),
                "processed_count": int(summary.get("processed_count") or 0),
                "status_counts": status_counts,
            },
        )


def _build_execution_plane_snapshot_index(
    config: AutopilotConfig,
) -> dict[str, dict[str, Any]]:
    """Build execution-plane project snapshots for event enrichment."""

    snapshot_index: dict[str, dict[str, Any]] = {}
    for project in load_projects_registry(config, include_archived=True):
        snapshot_index[project["id"]] = build_execution_plane_project_snapshot(config, project)
    return snapshot_index


def _event_runtime_agent_ids(event: dict[str, Any]) -> set[str]:
    """Collect all runtime-agent ids attached to one raw event."""

    agent_ids = {
        str(value).strip()
        for value in (
            event.get("runtime_agent_id"),
            event.get("worker_runtime_agent_id"),
            event.get("critic_runtime_agent_id"),
            event.get("specialist_runtime_agent_id"),
        )
        if str(value or "").strip()
    }
    agent_ids.update(
        str(value).strip()
        for value in (event.get("runtime_agent_ids") or [])
        if str(value or "").strip()
    )
    return agent_ids


def _enrich_execution_plane_event(
    event: dict[str, Any],
    snapshot_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Attach stable project/initiative/orchestration context to one raw event."""

    event_project_id = str(event.get("project_id") or "")
    snapshot = snapshot_index.get(event_project_id)
    return {
        **event,
        "project_name": snapshot["name"] if snapshot is not None else None,
        "initiative": snapshot["initiative"] if snapshot is not None else InitiativeContext().model_dump(),
        "orchestration": snapshot["orchestration"] if snapshot is not None else OrchestrationContext().model_dump(),
    }


def _load_enriched_execution_plane_events(
    config: AutopilotConfig,
) -> list[dict[str, Any]]:
    """Load and enrich the raw execution event log."""

    path = config.events_log_path
    if not path.exists():
        return []

    snapshot_index = _build_execution_plane_snapshot_index(config)
    events: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(_enrich_execution_plane_event(event, snapshot_index))
    return events


def _runtime_agent_has_recommendation(agent: dict[str, Any], kind: str) -> bool:
    return any(str(rec.get("kind") or "") == kind for rec in agent.get("recommendations") or [])


def _runtime_agent_has_suggested_command(
    agent: dict[str, Any],
    command: str,
    *,
    approval_required: bool | None = None,
) -> bool:
    for suggestion in agent.get("suggested_commands") or []:
        if str(suggestion.get("command") or "") != command:
            continue
        if approval_required is not None and bool(suggestion.get("approval_required")) != approval_required:
            continue
        return True
    return False


def _runtime_agent_is_actionable(agent: dict[str, Any]) -> bool:
    return any(
        str(rec.get("kind") or "") not in {"", "monitor"}
        for rec in agent.get("recommendations") or []
    ) or bool(agent.get("suggested_commands"))


def _decorate_runtime_agent(
    config: AutopilotConfig,
    *,
    state: dict[str, Any],
    project_snapshot: dict[str, Any],
    agent: dict[str, Any],
    issues: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
) -> dict[str, Any]:
    budget = _runtime_agent_budget_summary(state, agent, role=str(agent.get("role") or ""))
    open_issues = [issue for issue in issues if issue.get("status") == "open"]
    pending_approvals = [approval for approval in approvals if approval.get("status") == "pending"]
    attention = _runtime_agent_attention_summary(
        agent=agent,
        project_snapshot=project_snapshot,
        budget=budget,
        open_issues=open_issues,
        pending_approvals=pending_approvals,
    )
    recommendations, suggested_commands = _runtime_agent_recommendations(
        config,
        project_id=str(project_snapshot["project_id"]),
        project_snapshot=project_snapshot,
        agent=agent,
        budget=budget,
        attention=attention,
        open_issues=open_issues,
        pending_approvals=pending_approvals,
    )
    return {
        **agent,
        "open_issue_count": len(open_issues),
        "pending_approval_count": len(pending_approvals),
        "budget": budget,
        "attention": attention,
        "recommendations": recommendations,
        "suggested_commands": suggested_commands,
    }


def build_execution_plane_project_snapshot(
    config: AutopilotConfig,
    project: dict[str, Any],
) -> dict[str, Any]:
    """Build a stable FounderOS-facing summary for one Autopilot project."""

    state = ensure_project_state(config, project, seed_mode="migrate")
    summary = build_project_summary(config, project)
    stories = merge_project_stories(config, project, state)
    brief = load_project_execution_brief(project)
    source_kind, brief_path, context = _resolve_control_plane_context(project, brief)
    command_policy = load_project_command_policy(config, project["id"])
    runtime_agents = build_execution_plane_runtime_agents(config, project, stories)
    open_issues = list_issues(config, project_id=project["id"], status="open")
    task_source = TaskSource.model_validate(resolve_project_task_source(project))
    snapshot = ExecutionPlaneProjectSnapshot(
        project_id=project["id"],
        name=project["name"],
        path=project["path"],
        prd_path=str((Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")).resolve()),
        priority=project.get("priority", "normal"),
        archived=bool(project.get("archived", False)),
        created_at=project.get("created_at"),
        last_opened_at=project.get("last_opened_at"),
        source_kind=source_kind,
        task_source=task_source,
        execution_brief_path=brief_path,
        delivery_loop=summary.get("delivery_loop") or {},
        delivery_status=summary.get("delivery_status") or {},
        initiative=InitiativeContext.model_validate(context["initiative"]),
        orchestration=OrchestrationContext.model_validate(context["orchestration"]),
        provenance=ProvenanceContext.model_validate(context["provenance"]),
        launch_profile=summary.get("launch_profile") or {},
        provider_config=summary.get("provider_config") or {},
        runtime_profile=summary.get("runtime_profile") or {},
        command_policy=command_policy,
        runtime_agent_count=len(runtime_agents),
        open_issue_count=len(open_issues),
        runtime=ExecutionPlaneRuntime(
            status=str(summary.get("status") or "idle"),
            paused=bool(summary.get("paused", False)),
            pid=summary.get("pid"),
            started_at=state.get("started_at"),
            updated_at=summary.get("last_activity_at"),
            finished_at=state.get("finished_at"),
            current_story_id=summary.get("current_story_id"),
            current_story_title=summary.get("current_story_title"),
            current_iteration=int(state.get("current_iteration") or 0),
            active_worker=state.get("active_worker"),
            active_critic=state.get("active_critic"),
            last_error=str(state.get("last_error") or ""),
        ),
        progress=_build_progress_snapshot(stories),
        budget=ExecutionPlaneBudget(
            policy=summary.get("budget_policy") or {},
            usage=summary.get("budget_usage") or {},
        ),
        cost=summary.get("cost_usage") or {},
    )
    return snapshot.model_dump()


def build_execution_plane_project_detail(
    config: AutopilotConfig,
    project_id: str,
) -> dict[str, Any]:
    """Build a detailed FounderOS-facing view for one project."""

    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)

    detail = build_project_detail(config, project_id)
    brief = load_project_execution_brief(project)
    source_kind, brief_path, context = _resolve_control_plane_context(project, brief)
    command_policy = load_project_command_policy(config, project_id)
    issues = [issue.model_dump() for issue in list_issues(config, project_id=project_id)]
    approvals = [approval.model_dump() for approval in list_approvals(config, project_id=project_id)]
    task_source = TaskSource.model_validate(resolve_project_task_source(project))
    runtime_agents = [
        _decorate_runtime_agent(
            config,
            state=detail,
            project_snapshot={
                "project_id": project["id"],
                "runtime": {
                    "status": str(detail.get("status") or "idle"),
                    "paused": bool(detail.get("paused", False)),
                    "current_story_id": detail.get("current_story_id"),
                    "current_iteration": int(detail.get("current_iteration") or 0),
                },
            },
            agent=agent,
            issues=[
                issue
                for issue in issues
                if str(agent["agent_id"]) == issue.get("runtime_agent_id")
                or str(agent["agent_id"]) in (issue.get("runtime_agent_ids") or [])
            ],
            approvals=[
                approval
                for approval in approvals
                if str(agent["agent_id"]) in (approval.get("runtime_agent_ids") or [])
            ],
        )
        for agent in build_execution_plane_runtime_agents(config, project, detail.get("stories") or [])
    ]
    snapshot = ExecutionPlaneProjectDetail(
        project_id=project["id"],
        name=project["name"],
        path=project["path"],
        prd_path=str((Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")).resolve()),
        priority=project.get("priority", "normal"),
        archived=bool(project.get("archived", False)),
        created_at=project.get("created_at"),
        last_opened_at=project.get("last_opened_at"),
        source_kind=source_kind,
        task_source=task_source,
        execution_brief_path=brief_path,
        delivery_loop=detail.get("delivery_loop") or {},
        delivery_status=detail.get("delivery_status") or {},
        initiative=InitiativeContext.model_validate(context["initiative"]),
        orchestration=OrchestrationContext.model_validate(context["orchestration"]),
        provenance=ProvenanceContext.model_validate(context["provenance"]),
        launch_profile=detail.get("launch_profile") or {},
        provider_config=detail.get("provider_config") or {},
        runtime_profile=detail.get("runtime_profile") or {},
        command_policy=command_policy,
        runtime_agent_count=len(runtime_agents),
        open_issue_count=sum(1 for issue in issues if issue.get("status") == "open"),
        runtime=ExecutionPlaneRuntime(
            status=str(detail.get("status") or "idle"),
            paused=bool(detail.get("paused", False)),
            pid=detail.get("pid"),
            started_at=detail.get("started_at"),
            updated_at=detail.get("last_activity_at"),
            finished_at=detail.get("finished_at"),
            current_story_id=detail.get("current_story_id"),
            current_story_title=detail.get("current_story_title"),
            current_iteration=int(detail.get("current_iteration") or 0),
            active_worker=detail.get("active_worker"),
            active_critic=detail.get("active_critic"),
            last_error=str(detail.get("last_error") or ""),
        ),
        progress=_build_progress_snapshot(detail.get("stories") or []),
        budget=ExecutionPlaneBudget(
            policy=detail.get("budget_policy") or {},
            usage=detail.get("budget_usage") or {},
        ),
        cost=detail.get("cost_usage") or {},
        description=str(detail.get("description") or ""),
        phases=detail.get("phases") or [],
        stories=detail.get("stories") or [],
        timeline=detail.get("timeline") or [],
        runtime_control=inspect_project_workspace_policy(config, project_id),
        runtime_agents=runtime_agents,
        issues=issues,
        brief=brief.model_dump() if brief is not None else None,
        trace={
            "summary": detail.get("trace_summary") or {},
            "path": detail.get("trace_path") or "",
        },
    )
    return snapshot.model_dump()


def list_execution_plane_projects(
    config: AutopilotConfig,
    *,
    include_archived: bool = False,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
) -> list[dict[str, Any]]:
    """List projects through the stable execution-plane snapshot contract."""

    snapshots: list[dict[str, Any]] = []
    for project in load_projects_registry(config, include_archived=include_archived):
        snapshot = build_execution_plane_project_snapshot(config, project)
        if initiative_id and snapshot["initiative"].get("id") != initiative_id:
            continue
        if orchestrator and snapshot["orchestration"].get("orchestrator") != orchestrator:
            continue
        snapshots.append(snapshot)

    snapshots.sort(
        key=lambda item: (
            item["runtime"]["status"] not in {"running", "paused"},
            item["runtime"]["updated_at"] or "",
            item["name"].lower(),
        ),
        reverse=True,
    )
    return snapshots


def list_execution_plane_agents(
    config: AutopilotConfig,
    *,
    include_archived: bool = False,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = False,
    command_requires_approval: bool | None = None,
) -> list[dict[str, Any]]:
    """Return a global flattened runtime-agent view across execution projects."""

    issues_by_agent: dict[str, list[dict[str, Any]]] = {}
    for issue in list_issues(config):
        agent_ids = set(issue.runtime_agent_ids or [])
        if issue.runtime_agent_id:
            agent_ids.add(issue.runtime_agent_id)
        for runtime_agent_id in agent_ids:
            issues_by_agent.setdefault(runtime_agent_id, []).append(issue.model_dump())

    approvals_by_agent: dict[str, list[dict[str, Any]]] = {}
    for approval in list_approvals(config):
        for runtime_agent_id in approval.runtime_agent_ids:
            approvals_by_agent.setdefault(runtime_agent_id, []).append(approval.model_dump())

    agents: list[dict[str, Any]] = []
    for project in load_projects_registry(config, include_archived=include_archived):
        if project_id and str(project["id"]) != project_id:
            continue
        snapshot = build_execution_plane_project_snapshot(config, project)
        if initiative_id and snapshot["initiative"].get("id") != initiative_id:
            continue
        if orchestrator and snapshot["orchestration"].get("orchestrator") != orchestrator:
            continue

        state = ensure_project_state(config, project, seed_mode="migrate")
        stories = merge_project_stories(config, project, state)
        for agent in build_execution_plane_runtime_agents(config, project, stories):
            if status and agent.get("status") != status:
                continue
            if role and agent.get("role") != role:
                continue
            decorated = _decorate_runtime_agent(
                config,
                state=state,
                project_snapshot=snapshot,
                agent=agent,
                issues=issues_by_agent.get(str(agent["agent_id"]), []),
                approvals=approvals_by_agent.get(str(agent["agent_id"]), []),
            )
            if attention_state and decorated["attention"]["state"] != attention_state:
                continue
            if recommendation_kind and not _runtime_agent_has_recommendation(decorated, recommendation_kind):
                continue
            if suggested_command and not _runtime_agent_has_suggested_command(
                decorated,
                suggested_command,
                approval_required=command_requires_approval,
            ):
                continue
            if command_requires_approval is not None and not suggested_command and not any(
                bool(suggestion.get("approval_required")) == command_requires_approval
                for suggestion in decorated.get("suggested_commands") or []
            ):
                continue
            if actionable_only and not _runtime_agent_is_actionable(decorated):
                continue
            agents.append(
                {
                    **decorated,
                    "project_id": project["id"],
                    "project_name": project["name"],
                    "project_status": snapshot["runtime"]["status"],
                    "project_paused": snapshot["runtime"]["paused"],
                    "initiative": snapshot["initiative"],
                    "orchestration": snapshot["orchestration"],
                }
            )

    agents.sort(
        key=lambda item: (
            item["attention"]["state"] not in {"blocked", "needs_approval", "budget_exhausted", "budget_risk"},
            item["status"] != "active",
            item["open_issue_count"] == 0,
            item["project_name"].lower(),
            item["story_id"] or 0,
            item["role"],
            item["label"].lower(),
        )
    )
    return agents


def summarize_execution_plane_agents(
    config: AutopilotConfig,
    *,
    include_archived: bool = False,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = False,
    command_requires_approval: bool | None = None,
) -> dict[str, Any]:
    """Return aggregate runtime-agent counts for quick control-plane triage."""

    agents = list_execution_plane_agents(
        config,
        include_archived=include_archived,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        status=status,
        role=role,
        attention_state=attention_state,
        recommendation_kind=recommendation_kind,
        suggested_command=suggested_command,
        actionable_only=actionable_only,
        command_requires_approval=command_requires_approval,
    )

    by_attention_state: dict[str, int] = {}
    by_role: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_recommendation_kind: dict[str, int] = {}
    by_suggested_command: dict[str, int] = {}
    for agent in agents:
        attention_state = str(agent.get("attention", {}).get("state") or "unknown")
        by_attention_state[attention_state] = by_attention_state.get(attention_state, 0) + 1

        role = str(agent.get("role") or "unknown")
        by_role[role] = by_role.get(role, 0) + 1

        project_name = str(agent.get("project_name") or agent.get("project_id") or "unknown")
        by_project[project_name] = by_project.get(project_name, 0) + 1

        for recommendation in agent.get("recommendations") or []:
            kind = str(recommendation.get("kind") or "")
            if not kind or kind == "monitor":
                continue
            by_recommendation_kind[kind] = by_recommendation_kind.get(kind, 0) + 1

        for suggestion in agent.get("suggested_commands") or []:
            command = str(suggestion.get("command") or "")
            if not command:
                continue
            by_suggested_command[command] = by_suggested_command.get(command, 0) + 1

    return {
        "totals": {
            "agents": len(agents),
            "active": sum(1 for agent in agents if agent.get("status") == "active"),
            "blocked": sum(1 for agent in agents if agent.get("attention", {}).get("state") == "blocked"),
            "needs_approval": sum(1 for agent in agents if agent.get("attention", {}).get("state") == "needs_approval"),
            "budget_risk": sum(1 for agent in agents if agent.get("attention", {}).get("state") == "budget_risk"),
            "budget_exhausted": sum(
                1 for agent in agents if agent.get("attention", {}).get("state") == "budget_exhausted"
            ),
            "actionable": sum(1 for agent in agents if _runtime_agent_is_actionable(agent)),
            "with_suggested_commands": sum(1 for agent in agents if agent.get("suggested_commands")),
            "approval_required_suggestions": sum(
                1
                for agent in agents
                if any(bool(suggestion.get("approval_required")) for suggestion in agent.get("suggested_commands") or [])
            ),
        },
        "by_attention_state": by_attention_state,
        "by_role": by_role,
        "by_project": by_project,
        "by_recommendation_kind": by_recommendation_kind,
        "by_suggested_command": by_suggested_command,
    }


def list_execution_plane_agent_actions(
    config: AutopilotConfig,
    *,
    include_archived: bool = False,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = True,
    command_requires_approval: bool | None = None,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """Flatten agent recommendations and command suggestions into an action feed."""

    agents = list_execution_plane_agents(
        config,
        include_archived=include_archived,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        status=status,
        role=role,
        attention_state=attention_state,
        actionable_only=actionable_only,
    )
    attention_order = {
        "blocked": 0,
        "needs_approval": 1,
        "budget_exhausted": 2,
        "budget_risk": 3,
        "paused": 4,
        "active": 5,
        "healthy": 6,
    }

    actions: list[dict[str, Any]] = []
    for agent in agents:
        include_recommendations = recommendation_kind is not None or (
            suggested_command is None and command_requires_approval is None
        )
        include_suggested_commands = (
            suggested_command is not None
            or command_requires_approval is not None
            or recommendation_kind is None
        )
        common = {
            "runtime_agent_id": agent["agent_id"],
            "project_id": agent["project_id"],
            "project_name": agent["project_name"],
            "project_status": agent.get("project_status"),
            "project_paused": bool(agent.get("project_paused")),
            "initiative": agent["initiative"],
            "orchestration": agent["orchestration"],
            "role": agent.get("role"),
            "status": agent.get("status"),
            "label": agent.get("label"),
            "story_id": agent.get("story_id"),
            "story_title": agent.get("story_title"),
            "attention": agent.get("attention") or {},
        }

        if include_recommendations:
            for recommendation in agent.get("recommendations") or []:
                kind = str(recommendation.get("kind") or "")
                if not kind or kind == "monitor":
                    continue
                if recommendation_kind and kind != recommendation_kind:
                    continue
                if priority and str(recommendation.get("priority") or "") != priority:
                    continue
                actions.append(
                    {
                        **common,
                        "action_key": f"{agent['agent_id']}:recommendation:{kind}",
                        "action_type": "recommendation",
                        "priority": recommendation.get("priority") or "medium",
                        "kind": kind,
                        "title": recommendation.get("title") or kind,
                        "reason": recommendation.get("reason") or "",
                        "issue_ids": list(recommendation.get("issue_ids") or []),
                        "approval_ids": list(recommendation.get("approval_ids") or []),
                        "details": recommendation,
                    }
                )

        if include_suggested_commands:
            for suggestion in agent.get("suggested_commands") or []:
                command = str(suggestion.get("command") or "")
                if not command:
                    continue
                if suggested_command and command != suggested_command:
                    continue
                if command_requires_approval is not None and bool(suggestion.get("approval_required")) != command_requires_approval:
                    continue
                if priority and str(suggestion.get("priority") or "") != priority:
                    continue
                actions.append(
                    {
                        **common,
                        "action_key": f"{agent['agent_id']}:command:{command}",
                        "action_type": "suggested_command",
                        "priority": suggestion.get("priority") or "medium",
                        "command": command,
                        "title": suggestion.get("title") or command,
                        "reason": suggestion.get("reason") or "",
                        "payload": suggestion.get("payload") or {},
                        "approval_required": bool(suggestion.get("approval_required")),
                        "policy_reasons": list(suggestion.get("policy_reasons") or []),
                        "details": suggestion,
                    }
                )

    actions.sort(
        key=lambda item: (
            ACTION_PRIORITY_ORDER.get(str(item.get("priority") or "medium"), 99),
            attention_order.get(str(item.get("attention", {}).get("state") or "healthy"), 99),
            str(item.get("project_name") or "").lower(),
            int(item.get("story_id") or 0),
            str(item.get("runtime_agent_id") or ""),
            str(item.get("action_key") or ""),
        )
    )
    return actions


def get_execution_plane_agent_action(
    config: AutopilotConfig,
    action_key: str,
) -> dict[str, Any]:
    """Resolve one runtime-agent action key into current action detail."""

    parsed = parse_execution_plane_agent_action_key(action_key)
    if parsed is None:
        raise ValueError(f"Invalid runtime agent action key: {action_key}")

    detail = get_execution_plane_agent_detail(config, parsed.runtime_agent_id)
    common = {
        "action_key": action_key,
        "action_type": parsed.action_type,
        "runtime_agent_id": parsed.runtime_agent_id,
        "project_id": detail["project_id"],
        "project_name": detail["project_name"],
        "project_status": detail["project"]["status"],
        "project_paused": detail["project"]["paused"],
        "initiative": detail["initiative"],
        "orchestration": detail["orchestration"],
        "role": detail["role"],
        "status": detail["status"],
        "story_id": detail["story_id"],
        "story_title": detail["story_title"],
        "attention": detail["attention"],
        "budget": detail["budget"],
    }

    if parsed.action_type == "recommendation":
        for recommendation in detail.get("recommendations") or []:
            if str(recommendation.get("kind") or "") != parsed.name:
                continue
            return {
                **common,
                "priority": recommendation.get("priority") or "medium",
                "kind": parsed.name,
                "title": recommendation.get("title") or parsed.name,
                "reason": recommendation.get("reason") or "",
                "issue_ids": list(recommendation.get("issue_ids") or []),
                "approval_ids": list(recommendation.get("approval_ids") or []),
                "details": recommendation,
                "project": detail["project"],
                "story": detail["story"],
            }
    else:
        for suggestion in detail.get("suggested_commands") or []:
            if str(suggestion.get("command") or "") != parsed.name:
                continue
            return {
                **common,
                "priority": suggestion.get("priority") or "medium",
                "command": parsed.name,
                "title": suggestion.get("title") or parsed.name,
                "reason": suggestion.get("reason") or "",
                "payload": suggestion.get("payload") or {},
                "approval_required": bool(suggestion.get("approval_required")),
                "policy_reasons": list(suggestion.get("policy_reasons") or []),
                "details": suggestion,
                "project": detail["project"],
                "story": detail["story"],
            }
    raise KeyError(action_key)


def list_execution_plane_agent_action_runs(
    config: AutopilotConfig,
    *,
    run_kind: str | None = None,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    dry_run: bool | None = None,
    status: str | None = None,
    idempotency_key: str | None = None,
) -> list[dict[str, Any]]:
    """List persisted runtime-agent batch run reports."""

    return [
        _materialize_execution_plane_agent_action_run_record(config, record)
        for record in list_agent_action_batch_runs(
            config,
            run_kind=run_kind,
            orchestrator_session_id=orchestrator_session_id,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            actor=actor,
            dry_run=dry_run,
            status=status,
            idempotency_key=idempotency_key,
        )
    ]


def summarize_execution_plane_agent_action_runs(
    config: AutopilotConfig,
    *,
    run_kind: str | None = None,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    dry_run: bool | None = None,
    status: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Return aggregate counts across persisted runtime-agent batch runs."""

    records = list_agent_action_batch_runs(
        config,
        run_kind=run_kind,
        orchestrator_session_id=orchestrator_session_id,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        actor=actor,
        dry_run=dry_run,
        status=status,
        idempotency_key=idempotency_key,
    )

    by_status: dict[str, int] = {}
    by_run_kind: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    by_policy_profile: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_orchestrator: dict[str, int] = {}
    status_counts_total: dict[str, int] = {}
    for record in records:
        by_status[record.status] = by_status.get(record.status, 0) + 1
        by_run_kind[record.run_kind] = by_run_kind.get(record.run_kind, 0) + 1
        by_actor[record.actor] = by_actor.get(record.actor, 0) + 1
        profile = record.policy_profile or "custom"
        by_policy_profile[profile] = by_policy_profile.get(profile, 0) + 1
        for item in record.project_ids:
            by_project[item] = by_project.get(item, 0) + 1
        for item in record.orchestrators:
            by_orchestrator[item] = by_orchestrator.get(item, 0) + 1
        for key, value in (record.summary.get("status_counts") or {}).items():
            status_counts_total[str(key)] = status_counts_total.get(str(key), 0) + int(value or 0)

    return {
        "totals": {
            "runs": len(records),
            "dry_runs": sum(1 for record in records if record.dry_run),
            "executions": sum(1 for record in records if not record.dry_run),
            "single_action_runs": sum(1 for record in records if record.run_kind == "single_action"),
            "batch_runs": sum(1 for record in records if record.run_kind == "batch"),
            "ok": sum(1 for record in records if record.status == "ok"),
            "partial": sum(1 for record in records if record.status == "partial"),
            "error": sum(1 for record in records if record.status == "error"),
        },
        "by_status": by_status,
        "by_run_kind": by_run_kind,
        "by_actor": by_actor,
        "by_policy_profile": by_policy_profile,
        "by_project": by_project,
        "by_orchestrator": by_orchestrator,
        "result_status_counts": status_counts_total,
        "latest_run_at": records[0].created_at if records else None,
    }


def get_execution_plane_agent_action_run(
    config: AutopilotConfig,
    run_id: str,
) -> dict[str, Any]:
    """Load one persisted runtime-agent batch run report."""

    record = get_agent_action_batch_run(config, run_id)
    if record is None:
        raise KeyError(run_id)
    return _materialize_execution_plane_agent_action_run_record(config, record)


def list_execution_plane_runtime_agent_tasks(
    config: AutopilotConfig,
    *,
    task_id: str | None = None,
    project_id: str | None = None,
    orchestrator_session_id: str | None = None,
    runtime_agent_id: str | None = None,
    status: str | None = None,
    command: str | None = None,
    agent_action_run_id: str | None = None,
) -> list[dict[str, Any]]:
    """List persisted async runtime-agent tasks with refreshed lifecycle state."""

    tasks = list_runtime_agent_tasks(
        config,
        task_id=task_id,
        project_id=project_id,
        orchestrator_session_id=orchestrator_session_id,
        runtime_agent_id=runtime_agent_id,
        status=status,
        command=command,
        agent_action_run_id=agent_action_run_id,
    )
    return [
        _materialize_execution_plane_runtime_agent_task_record(refresh_runtime_agent_task(config, task))
        for task in tasks
    ]


def get_execution_plane_runtime_agent_task(
    config: AutopilotConfig,
    task_id: str,
) -> dict[str, Any]:
    """Load one persisted async runtime-agent task."""

    task = get_runtime_agent_task(config, task_id)
    if task is None:
        raise KeyError(task_id)
    return _materialize_execution_plane_runtime_agent_task_record(refresh_runtime_agent_task(config, task))


def list_execution_plane_orchestrator_sessions(
    config: AutopilotConfig,
    *,
    session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List orchestrator sessions for external control planes."""

    return [
        session.model_dump()
        for session in list_orchestrator_sessions(
            config,
            session_id=session_id,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            actor=actor,
            status=status,
        )
    ]


def list_execution_plane_orchestrator_session_actions(
    config: AutopilotConfig,
    session_id: str,
    *,
    include_archived: bool = False,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = True,
    command_requires_approval: bool | None = None,
    priority: str | None = None,
) -> list[dict[str, Any]]:
    """Return the current action feed constrained to one orchestrator session scope."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    actions = list_execution_plane_agent_actions(
        config,
        include_archived=include_archived,
        initiative_id=session.initiative_id or None,
        orchestrator=session.orchestrator or None,
        status=status,
        role=role,
        attention_state=attention_state,
        recommendation_kind=recommendation_kind,
        suggested_command=suggested_command,
        actionable_only=actionable_only,
        command_requires_approval=command_requires_approval,
        priority=priority,
    )
    if session.project_ids:
        allowed_project_ids = set(session.project_ids)
        actions = [item for item in actions if str(item.get("project_id") or "") in allowed_project_ids]
    return actions


def summarize_execution_plane_orchestrator_session_actions(
    config: AutopilotConfig,
    session_id: str,
    *,
    include_archived: bool = False,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = True,
    command_requires_approval: bool | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    """Return aggregate counts for the current session-scoped action feed."""

    actions = list_execution_plane_orchestrator_session_actions(
        config,
        session_id,
        include_archived=include_archived,
        status=status,
        role=role,
        attention_state=attention_state,
        recommendation_kind=recommendation_kind,
        suggested_command=suggested_command,
        actionable_only=actionable_only,
        command_requires_approval=command_requires_approval,
        priority=priority,
    )
    by_action_type: dict[str, int] = {}
    by_priority: dict[str, int] = {}
    by_project: dict[str, int] = {}
    by_command: dict[str, int] = {}
    by_recommendation_kind: dict[str, int] = {}
    for action in actions:
        action_type = str(action.get("action_type") or "unknown")
        by_action_type[action_type] = by_action_type.get(action_type, 0) + 1
        priority_key = str(action.get("priority") or "unknown")
        by_priority[priority_key] = by_priority.get(priority_key, 0) + 1
        project_name = str(action.get("project_name") or action.get("project_id") or "unknown")
        by_project[project_name] = by_project.get(project_name, 0) + 1
        if action_type == "suggested_command":
            command = str(action.get("command") or "")
            if command:
                by_command[command] = by_command.get(command, 0) + 1
        if action_type == "recommendation":
            kind = str(action.get("kind") or "")
            if kind:
                by_recommendation_kind[kind] = by_recommendation_kind.get(kind, 0) + 1
    return {
        "totals": {
            "actions": len(actions),
            "suggested_commands": sum(1 for action in actions if action.get("action_type") == "suggested_command"),
            "recommendations": sum(1 for action in actions if action.get("action_type") == "recommendation"),
            "approval_required": sum(1 for action in actions if bool(action.get("approval_required"))),
            "projects": len({str(action.get("project_id") or "") for action in actions if str(action.get("project_id") or "").strip()}),
        },
        "by_action_type": by_action_type,
        "by_priority": by_priority,
        "by_project": by_project,
        "by_command": by_command,
        "by_recommendation_kind": by_recommendation_kind,
    }


def _session_action_policy_profile(commands: set[str], *, approval_required: bool) -> str:
    if commands and commands <= {"update_budget_policy"}:
        return "budget_maintenance_with_high_priority_escalation" if approval_required else "safe_budget_maintenance"
    return "balanced_safe"


ORCHESTRATOR_SESSION_CONTROL_PROFILES: dict[str, dict[str, Any]] = {
    "safe_progress": {
        "description": (
            "Inspect blocking approvals, execute safe session actions, preview approval-gated actions, "
            "triage linked issues, and close the session once it becomes healthy."
        ),
        "recommendation_kinds": [
            "review_pending_approvals",
            "execute_safe_actions",
            "preview_approval_gated_actions",
            "triage_open_issues",
            "complete_session",
        ],
        "repeatable_kinds": ["execute_safe_actions"],
    },
    "review_only": {
        "description": (
            "Inspect approvals and issues, preview session actions, but do not apply mutating session actions."
        ),
        "recommendation_kinds": [
            "review_pending_approvals",
            "preview_safe_actions",
            "preview_approval_gated_actions",
            "triage_open_issues",
        ],
        "repeatable_kinds": [],
    },
    "close_healthy": {
        "description": "Only complete the session when no other work remains.",
        "recommendation_kinds": ["complete_session"],
        "repeatable_kinds": [],
    },
}


def list_execution_plane_orchestrator_session_control_profiles() -> list[dict[str, Any]]:
    """Return supported session-level control-pass profiles."""

    profiles: list[dict[str, Any]] = []
    for name, profile in ORCHESTRATOR_SESSION_CONTROL_PROFILES.items():
        profiles.append(
            {
                "name": name,
                "description": str(profile.get("description") or ""),
                "recommendation_kinds": [
                    str(item)
                    for item in (profile.get("recommendation_kinds") or [])
                    if str(item).strip()
                ],
                "repeatable_kinds": [
                    str(item)
                    for item in (profile.get("repeatable_kinds") or [])
                    if str(item).strip()
                ],
                "default": name == "safe_progress",
            }
        )
    return profiles


def _resolve_execution_plane_orchestrator_session_control_profile(
    profile: str,
    recommendation_kinds: list[str] | None = None,
) -> dict[str, Any]:
    normalized_profile = profile.strip() or "safe_progress"
    profile_payload = ORCHESTRATOR_SESSION_CONTROL_PROFILES.get(normalized_profile)
    if profile_payload is None:
        raise ValueError(
            f"Unsupported orchestrator-session control profile: {normalized_profile}. "
            f"Expected one of {sorted(ORCHESTRATOR_SESSION_CONTROL_PROFILES)}."
        )

    explicit_kinds = [
        str(item).strip()
        for item in (recommendation_kinds or [])
        if str(item).strip()
    ]
    if explicit_kinds:
        deduped_kinds = list(dict.fromkeys(explicit_kinds))
    else:
        deduped_kinds = [
            str(item).strip()
            for item in (profile_payload.get("recommendation_kinds") or [])
            if str(item).strip()
        ]

    return {
        "name": normalized_profile,
        "description": str(profile_payload.get("description") or ""),
        "recommendation_kinds": deduped_kinds,
        "repeatable_kinds": {
            str(item).strip()
            for item in (profile_payload.get("repeatable_kinds") or [])
            if str(item).strip()
        },
        "customized": bool(explicit_kinds),
    }


def _build_orchestrator_session_pending_action(
    session_id: str,
    recommendations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Select one stable pending-action payload from current control recommendations."""

    if not recommendations:
        return None

    priority_rank = {"high": 0, "medium": 1, "low": 2}
    ranked = sorted(
        enumerate(recommendations),
        key=lambda item: (priority_rank.get(str(item[1].get("priority") or "medium"), 99), item[0]),
    )
    selected = dict(ranked[0][1])
    operation_payload = selected.get("operation")
    operation = None
    if isinstance(operation_payload, dict) and operation_payload:
        operation = {
            "type": str(operation_payload.get("type") or "").strip(),
            "session_id": str(operation_payload.get("session_id") or session_id).strip(),
            "endpoint": str(operation_payload.get("endpoint") or "").strip(),
            "mode": str(operation_payload.get("mode") or "").strip(),
            "payload": dict(operation_payload.get("payload") or {}),
        }
    return {
        "kind": str(selected.get("kind") or "").strip(),
        "priority": str(selected.get("priority") or "medium").strip() or "medium",
        "title": str(selected.get("title") or "").strip(),
        "reason": str(selected.get("reason") or "").strip(),
        "session_id": session_id,
        "counts": {
            str(key): int(value)
            for key, value in dict(selected.get("counts") or {}).items()
            if str(key).strip()
        },
        "operation": operation,
    }


def _derive_orchestrator_session_runtime_state(
    session: Any,
    control: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Map control state to the explicit idle|running|requires_action contract."""

    if str(session.status) != "open":
        return "idle", None
    if str(control.get("state") or "") == "in_progress":
        return "running", None
    pending_action = _build_orchestrator_session_pending_action(
        str(session.id),
        list(control.get("recommendations") or []),
    )
    if pending_action is not None:
        return "requires_action", pending_action
    return "idle", None


def build_execution_plane_orchestrator_session_control(
    config: AutopilotConfig,
    session_id: str,
) -> dict[str, Any]:
    """Build a control summary and next-step recommendations for one session."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    actions = list_execution_plane_orchestrator_session_actions(config, session_id)
    action_summary = summarize_execution_plane_orchestrator_session_actions(config, session_id)

    approvals = [
        approval.model_dump()
        for approval in list_approvals(config)
        if approval.id in set(session.linked_approval_ids)
    ]
    issues = [
        issue.model_dump()
        for issue in list_issues(config)
        if issue.id in set(session.linked_issue_ids)
    ]
    async_tasks = list_execution_plane_runtime_agent_tasks(
        config,
        orchestrator_session_id=session_id,
    )

    pending_approvals = [approval for approval in approvals if approval.get("status") == "pending"]
    open_issues = [issue for issue in issues if issue.get("status") == "open"]
    active_async_tasks = [
        task
        for task in async_tasks
        if str(task.get("status") or "") in {"queued", "running"}
    ]
    safe_actions = [
        action
        for action in actions
        if action.get("action_type") == "suggested_command" and not bool(action.get("approval_required"))
    ]
    approval_actions = [
        action
        for action in actions
        if action.get("action_type") == "suggested_command" and bool(action.get("approval_required"))
    ]
    recommendation_actions = [action for action in actions if action.get("action_type") == "recommendation"]

    if session.status != "open":
        state = "closed"
    elif pending_approvals:
        state = "needs_approval"
    elif active_async_tasks:
        state = "in_progress"
    elif safe_actions or approval_actions or recommendation_actions:
        state = "actionable"
    elif open_issues:
        state = "attention_required"
    else:
        state = "healthy"

    recommendations: list[dict[str, Any]] = []
    if pending_approvals:
        recommendations.append(
            {
                "kind": "review_pending_approvals",
                "priority": "high",
                "title": "Review pending approvals",
                "reason": f"{len(pending_approvals)} pending approval(s) are blocking session progress.",
                "counts": {"pending_approvals": len(pending_approvals)},
                "operation": {
                    "type": "inspect_session_approvals",
                    "session_id": session_id,
                },
            }
        )
    if active_async_tasks:
        recommendations.append(
            {
                "kind": "inspect_background_tasks",
                "priority": "high",
                "title": "Inspect background tasks",
                "reason": f"{len(active_async_tasks)} background task(s) are still running; do not treat the session as complete yet.",
                "counts": {"active_async_tasks": len(active_async_tasks)},
                "operation": {
                    "type": "inspect_background_tasks",
                    "session_id": session_id,
                    "endpoint": f"/api/execution-plane/agents/tasks?orchestrator_session_id={session_id}&status=running",
                },
            }
        )
    if safe_actions:
        safe_commands = {str(action.get("command") or "") for action in safe_actions if str(action.get("command") or "").strip()}
        preview_payload = {
            "policy_profile": _session_action_policy_profile(safe_commands, approval_required=False),
            "actionable_only": True,
            "command_requires_approval": False,
            "limit": min(len(safe_actions), 100),
        }
        recommendations.append(
            {
                "kind": "preview_safe_actions",
                "priority": "high",
                "title": "Preview safe session actions",
                "reason": f"{len(safe_actions)} safe action(s) are ready for session-level preview.",
                "counts": {"safe_actions": len(safe_actions)},
                "operation": {
                    "type": "session_action_batch",
                    "mode": "preview",
                    "session_id": session_id,
                    "endpoint": f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/preview",
                    "payload": preview_payload,
                },
            }
        )
        if not pending_approvals:
            recommendations.append(
                {
                    "kind": "execute_safe_actions",
                    "priority": "medium",
                    "title": "Execute safe session actions",
                    "reason": f"{len(safe_actions)} safe action(s) can be applied immediately.",
                    "counts": {"safe_actions": len(safe_actions)},
                    "operation": {
                        "type": "session_action_batch",
                        "mode": "execute",
                        "session_id": session_id,
                        "endpoint": f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/execute",
                        "payload": preview_payload,
                    },
                }
            )
    if approval_actions:
        approval_commands = {
            str(action.get("command") or "")
            for action in approval_actions
            if str(action.get("command") or "").strip()
        }
        recommendations.append(
            {
                "kind": "preview_approval_gated_actions",
                "priority": "high",
                "title": "Preview approval-gated actions",
                "reason": f"{len(approval_actions)} action(s) require approval before apply.",
                "counts": {"approval_required_actions": len(approval_actions)},
                "operation": {
                    "type": "session_action_batch",
                    "mode": "preview",
                    "session_id": session_id,
                    "endpoint": f"/api/execution-plane/orchestrator-sessions/{session_id}/actions/preview",
                    "payload": {
                        "policy_profile": _session_action_policy_profile(approval_commands, approval_required=True),
                        "actionable_only": True,
                        "command_requires_approval": True,
                        "limit": min(len(approval_actions), 100),
                    },
                },
            }
        )
    if open_issues:
        recommendations.append(
            {
                "kind": "triage_open_issues",
                "priority": "medium",
                "title": "Triage open issues",
                "reason": f"{len(open_issues)} open issue(s) remain linked to this session.",
                "counts": {"open_issues": len(open_issues)},
                "operation": {
                    "type": "inspect_session_issues",
                    "session_id": session_id,
                },
            }
        )
    if session.status == "open" and not recommendations:
        recommendations.append(
            {
                "kind": "complete_session",
                "priority": "low",
                "title": "Complete orchestration session",
                "reason": "No pending approvals, open issues, or actionable commands remain in this session.",
                "counts": {},
                "operation": {
                    "type": "session_status_update",
                    "session_id": session_id,
                    "endpoint": f"/api/execution-plane/orchestrator-sessions/{session_id}/status",
                    "payload": {"status": "completed"},
                },
            }
        )

    runtime_state, pending_action = _derive_orchestrator_session_runtime_state(
        session,
        {
            "state": state,
            "recommendations": recommendations,
        },
    )
    session = update_orchestrator_session_runtime_state(
        config,
        session.id,
        runtime_state=runtime_state,
        pending_action=pending_action,
    )

    return {
        "state": state,
        "session_state": session.runtime_state,
        "pending_action": session.pending_action,
        "counts": {
            "pending_approvals": len(pending_approvals),
            "open_issues": len(open_issues),
            "active_async_tasks": len(active_async_tasks),
            "safe_actions": len(safe_actions),
            "approval_required_actions": len(approval_actions),
            "recommendation_actions": len(recommendation_actions),
        },
        "action_summary": action_summary,
        "recommendations": recommendations,
    }


def _get_execution_plane_orchestrator_session_control_recommendation(
    config: AutopilotConfig,
    session_id: str,
    recommendation_kind: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    control = build_execution_plane_orchestrator_session_control(config, session_id)
    normalized_kind = recommendation_kind.strip()
    recommendation = next(
        (
            item
            for item in control.get("recommendations") or []
            if str(item.get("kind") or "") == normalized_kind
        ),
        None,
    )
    if recommendation is None:
        raise ValueError(
            f"Orchestrator session `{session_id}` does not currently expose recommendation `{normalized_kind}`."
        )
    return control, recommendation


def apply_execution_plane_orchestrator_session_recommendation(
    config: AutopilotConfig,
    session_id: str,
    *,
    recommendation_kind: str,
    actor: str,
    reason: str = "",
    idempotency_key: str = "",
) -> dict[str, Any]:
    """Apply one typed orchestrator-session control recommendation."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    control, recommendation = _get_execution_plane_orchestrator_session_control_recommendation(
        config,
        session_id,
        recommendation_kind,
    )
    operation = dict(recommendation.get("operation") or {})
    operation_type = str(operation.get("type") or "").strip()
    operation_mode = str(operation.get("mode") or "").strip()
    operation_payload = dict(operation.get("payload") or {})
    normalized_reason = reason.strip() or str(recommendation.get("reason") or "")
    normalized_idempotency_key = idempotency_key.strip()

    result: dict[str, Any]
    if operation_type == "session_action_batch":
        result = execute_execution_plane_orchestrator_session_actions(
            config,
            session_id,
            action_keys=[str(item) for item in (operation_payload.get("action_keys") or []) if str(item).strip()] or None,
            idempotency_key=normalized_idempotency_key,
            actor=actor,
            mode=str(operation_payload.get("mode") or "auto"),
            reason=normalized_reason,
            policy_profile=(
                str(operation_payload.get("policy_profile") or "").strip() or None
            ),
            policy_overrides=None,
            dry_run=operation_mode == "preview",
            include_archived=bool(operation_payload.get("include_archived", False)),
            status=str(operation_payload.get("status") or "").strip() or None,
            role=str(operation_payload.get("role") or "").strip() or None,
            attention_state=str(operation_payload.get("attention_state") or "").strip() or None,
            recommendation_kind=str(operation_payload.get("recommendation_kind") or "").strip() or None,
            suggested_command=str(operation_payload.get("suggested_command") or "").strip() or None,
            actionable_only=bool(operation_payload.get("actionable_only", True)),
            command_requires_approval=operation_payload.get("command_requires_approval"),
            priority=str(operation_payload.get("priority") or "").strip() or None,
            limit=int(operation_payload.get("limit") or 20),
            continue_on_error=bool(operation_payload.get("continue_on_error", True)),
            include_non_executable=bool(operation_payload.get("include_non_executable", False)),
        )
    elif operation_type == "session_status_update":
        result = {
            "status": "ok",
            "session": update_execution_plane_orchestrator_session_status(
                config,
                session_id=session_id,
                status=str(operation_payload.get("status") or "completed"),
                actor=actor,
                note=normalized_reason,
            ),
        }
    elif operation_type == "inspect_session_approvals":
        approvals = [
            approval.model_dump()
            for approval in list_approvals(config)
            if approval.id in set(session.linked_approval_ids)
        ]
        pending_approvals = [approval for approval in approvals if approval.get("status") == "pending"]
        result = {
            "status": "ok",
            "approvals": approvals,
            "pending_approvals": pending_approvals,
            "counts": {
                "approvals": len(approvals),
                "pending_approvals": len(pending_approvals),
            },
        }
    elif operation_type == "inspect_session_issues":
        issues = [
            issue.model_dump()
            for issue in list_issues(config)
            if issue.id in set(session.linked_issue_ids)
        ]
        open_issues = [issue for issue in issues if issue.get("status") == "open"]
        result = {
            "status": "ok",
            "issues": issues,
            "open_issues": open_issues,
            "counts": {
                "issues": len(issues),
                "open_issues": len(open_issues),
            },
        }
    else:
        raise ValueError(
            f"Unsupported orchestrator-session recommendation operation `{operation_type}` for `{recommendation_kind}`."
        )

    updated_control = build_execution_plane_orchestrator_session_control(config, session_id)
    result_status = str(result.get("status") or "ok")
    event_extra: dict[str, Any] = {
        "orchestrator_session_id": session_id,
        "recommendation_kind": str(recommendation.get("kind") or recommendation_kind),
        "recommendation_title": str(recommendation.get("title") or ""),
        "operation_type": operation_type,
        "operation_mode": operation_mode,
        "actor": actor,
        "reason": normalized_reason,
    }
    if normalized_idempotency_key:
        event_extra["idempotency_key"] = normalized_idempotency_key
    run = result.get("run") or {}
    if run.get("id"):
        event_extra["agent_action_run_id"] = str(run["id"])
    if result.get("approval", {}).get("id"):
        event_extra["approval_id"] = str(result["approval"]["id"])
    if result.get("issue", {}).get("id"):
        event_extra["issue_id"] = str(result["issue"]["id"])
    for project_id in session.project_ids:
        emit_project_event(
            config,
            project_id,
            event="execution_plane_orchestrator_session_recommendation_applied",
            status=result_status,
            message=(
                f"Orchestrator session recommendation "
                f"`{recommendation.get('kind') or recommendation_kind}` applied."
            ),
            extra=event_extra,
        )

    return {
        "status": result_status,
        "session_id": session_id,
        "recommendation": recommendation,
        "operation": operation,
        "result": result,
        "control_before": control,
        "control": updated_control,
    }


def apply_execution_plane_orchestrator_session_control_plan(
    config: AutopilotConfig,
    session_id: str,
    *,
    actor: str,
    reason: str = "",
    profile: str = "safe_progress",
    recommendation_kinds: list[str] | None = None,
    max_operations: int = 10,
    continue_on_error: bool = True,
) -> dict[str, Any]:
    """Apply a policy-driven pass across current session-level control recommendations."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    resolved_profile = _resolve_execution_plane_orchestrator_session_control_profile(
        profile,
        recommendation_kinds,
    )
    initial_control = build_execution_plane_orchestrator_session_control(config, session_id)
    initial_session_status = session.status
    applied: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    skipped_kinds: list[str] = []
    applied_once: set[str] = set()
    stopped_reason = "no_matching_recommendations"

    for step in range(1, max_operations + 1):
        current_control = build_execution_plane_orchestrator_session_control(config, session_id)
        if current_control["state"] == "closed":
            stopped_reason = "session_closed"
            break

        current_map = {
            str(item.get("kind") or ""): item
            for item in current_control.get("recommendations") or []
            if str(item.get("kind") or "").strip()
        }

        selected_kind = ""
        for kind in resolved_profile["recommendation_kinds"]:
            if kind not in current_map:
                continue
            if kind in applied_once and kind not in resolved_profile["repeatable_kinds"]:
                continue
            selected_kind = kind
            break

        if not selected_kind:
            stopped_reason = "no_matching_recommendations"
            break

        recommendation = current_map[selected_kind]
        try:
            result = apply_execution_plane_orchestrator_session_recommendation(
                config,
                session_id,
                recommendation_kind=selected_kind,
                actor=actor,
                reason=reason,
                idempotency_key="",
            )
            applied.append(
                {
                    "step": step,
                    "recommendation_kind": selected_kind,
                    "title": recommendation.get("title") or selected_kind,
                    "priority": recommendation.get("priority") or "medium",
                    "status": result.get("status") or "ok",
                    "operation_type": str(result.get("operation", {}).get("type") or ""),
                    "operation_mode": str(result.get("operation", {}).get("mode") or ""),
                    "result": result.get("result") or {},
                    "control_state_before": str(result.get("control_before", {}).get("state") or ""),
                    "control_state_after": str(result.get("control", {}).get("state") or ""),
                }
            )
            applied_once.add(selected_kind)
            if str(result.get("control", {}).get("state") or "") == "closed":
                stopped_reason = "session_closed"
                break
        except (RuntimeError, ValueError) as exc:
            errors.append(
                {
                    "step": step,
                    "recommendation_kind": selected_kind,
                    "title": recommendation.get("title") or selected_kind,
                    "error": str(exc),
                }
            )
            applied_once.add(selected_kind)
            if not continue_on_error:
                stopped_reason = "error"
                break

    final_control = build_execution_plane_orchestrator_session_control(config, session_id)
    for kind in resolved_profile["recommendation_kinds"]:
        if kind in applied_once:
            continue
        skipped_kinds.append(kind)

    if errors and applied:
        status = "partial"
    elif errors:
        status = "error"
    elif applied:
        status = "ok"
    else:
        status = "noop"

    updated_session = get_orchestrator_session(config, session_id)
    control_pass = create_orchestrator_control_pass(
        config,
        orchestrator_session_id=session_id,
        actor=actor,
        reason=reason,
        profile=str(resolved_profile["name"]),
        customized=bool(resolved_profile["customized"]),
        recommendation_kinds=list(resolved_profile["recommendation_kinds"]),
        control_before=initial_control,
        control_after=final_control,
        applied=applied,
        errors=errors,
        summary={
            "applied": len(applied),
            "errors": len(errors),
            "skipped": len(skipped_kinds),
            "stopped_reason": stopped_reason,
            "final_state": final_control.get("state"),
        },
        status=status,
        project_ids=session.project_ids,
        initiative_id=session.initiative_id,
        orchestrator=session.orchestrator,
        session_status_before=initial_session_status,
        session_status_after=(updated_session.status if updated_session is not None else ""),
    )
    link_orchestrator_session_entities(
        config,
        session_id,
        linked_control_pass_ids=[control_pass.id],
    )

    event_extra = {
        "orchestrator_session_id": session_id,
        "profile": resolved_profile["name"],
        "customized": bool(resolved_profile["customized"]),
        "actor": actor,
        "reason": reason.strip(),
        "control_pass_id": control_pass.id,
        "applied_recommendation_kinds": [item["recommendation_kind"] for item in applied],
        "error_count": len(errors),
        "stopped_reason": stopped_reason,
    }
    for project_id in session.project_ids:
        emit_project_event(
            config,
            project_id,
            event="execution_plane_orchestrator_session_control_plan_applied",
            status=status,
            message=(
                f"Orchestrator session control plan `{resolved_profile['name']}` applied "
                f"with {len(applied)} step(s)."
            ),
            extra=event_extra,
        )
        emit_project_event(
            config,
            project_id,
            event="execution_plane_orchestrator_session_control_pass_recorded",
            status=status,
            message=f"Orchestrator session control pass `{control_pass.id}` recorded.",
            extra=event_extra,
        )

    return {
        "status": status,
        "session_id": session_id,
        "profile": resolved_profile,
        "control_pass": control_pass.model_dump(),
        "control_before": initial_control,
        "control": final_control,
        "applied": applied,
        "errors": errors,
        "summary": {
            "applied": len(applied),
            "errors": len(errors),
            "skipped": len(skipped_kinds),
            "stopped_reason": stopped_reason,
            "final_state": final_control.get("state"),
        },
        "skipped_recommendation_kinds": skipped_kinds,
    }


def summarize_execution_plane_orchestrator_sessions(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Return aggregate counts for persisted orchestrator sessions."""

    sessions = list_orchestrator_sessions(
        config,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        actor=actor,
        status=status,
    )
    by_status: dict[str, int] = {}
    by_orchestrator: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    for session in sessions:
        by_status[session.status] = by_status.get(session.status, 0) + 1
        if session.orchestrator:
            by_orchestrator[session.orchestrator] = by_orchestrator.get(session.orchestrator, 0) + 1
        if session.actor:
            by_actor[session.actor] = by_actor.get(session.actor, 0) + 1
    return {
        "totals": {
            "sessions": len(sessions),
            "open": sum(1 for session in sessions if session.status == "open"),
            "completed": sum(1 for session in sessions if session.status == "completed"),
            "archived": sum(1 for session in sessions if session.status == "archived"),
        },
        "by_status": by_status,
        "by_orchestrator": by_orchestrator,
        "by_actor": by_actor,
        "latest_session_at": sessions[0].created_at if sessions else None,
    }


def list_execution_plane_orchestrator_session_control_passes(
    config: AutopilotConfig,
    *,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    profile: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List persisted session-level control-pass records."""

    return [
        record.model_dump()
        for record in list_orchestrator_control_passes(
            config,
            orchestrator_session_id=orchestrator_session_id,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            actor=actor,
            profile=profile,
            status=status,
        )
    ]


def summarize_execution_plane_orchestrator_session_control_passes(
    config: AutopilotConfig,
    *,
    orchestrator_session_id: str | None = None,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    actor: str | None = None,
    profile: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Return aggregate counts across persisted session-level control-pass records."""

    records = list_orchestrator_control_passes(
        config,
        orchestrator_session_id=orchestrator_session_id,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        actor=actor,
        profile=profile,
        status=status,
    )

    by_status: dict[str, int] = {}
    by_profile: dict[str, int] = {}
    by_actor: dict[str, int] = {}
    by_orchestrator: dict[str, int] = {}
    by_final_state: dict[str, int] = {}
    by_stopped_reason: dict[str, int] = {}
    by_session_status_before: dict[str, int] = {}
    by_session_status_after: dict[str, int] = {}
    for record in records:
        by_status[record.status] = by_status.get(record.status, 0) + 1
        by_profile[record.profile] = by_profile.get(record.profile, 0) + 1
        by_actor[record.actor] = by_actor.get(record.actor, 0) + 1
        if record.orchestrator:
            by_orchestrator[record.orchestrator] = by_orchestrator.get(record.orchestrator, 0) + 1
        final_state = str(record.summary.get("final_state") or "")
        if final_state:
            by_final_state[final_state] = by_final_state.get(final_state, 0) + 1
        stopped_reason = str(record.summary.get("stopped_reason") or "")
        if stopped_reason:
            by_stopped_reason[stopped_reason] = by_stopped_reason.get(stopped_reason, 0) + 1
        if record.session_status_before:
            by_session_status_before[record.session_status_before] = (
                by_session_status_before.get(record.session_status_before, 0) + 1
            )
        if record.session_status_after:
            by_session_status_after[record.session_status_after] = (
                by_session_status_after.get(record.session_status_after, 0) + 1
            )

    return {
        "totals": {
            "control_passes": len(records),
            "ok": sum(1 for record in records if record.status == "ok"),
            "partial": sum(1 for record in records if record.status == "partial"),
            "error": sum(1 for record in records if record.status == "error"),
            "noop": sum(1 for record in records if record.status == "noop"),
            "customized": sum(1 for record in records if record.customized),
            "sessions": len(
                {
                    record.orchestrator_session_id
                    for record in records
                    if record.orchestrator_session_id.strip()
                }
            ),
            "projects": len(
                {
                    project_id_item
                    for record in records
                    for project_id_item in record.project_ids
                    if project_id_item.strip()
                }
            ),
            "applied_steps": sum(int(record.summary.get("applied") or 0) for record in records),
            "error_steps": sum(int(record.summary.get("errors") or 0) for record in records),
        },
        "by_status": by_status,
        "by_profile": by_profile,
        "by_actor": by_actor,
        "by_orchestrator": by_orchestrator,
        "by_final_state": by_final_state,
        "by_stopped_reason": by_stopped_reason,
        "by_session_status_before": by_session_status_before,
        "by_session_status_after": by_session_status_after,
        "latest_control_pass_at": records[0].created_at if records else None,
    }


def get_execution_plane_orchestrator_session_control_pass(
    config: AutopilotConfig,
    control_pass_id: str,
) -> dict[str, Any]:
    """Load one persisted session-level control-pass record."""

    record = get_orchestrator_control_pass(config, control_pass_id)
    if record is None:
        raise KeyError(control_pass_id)
    return record.model_dump()


def get_execution_plane_orchestrator_session(
    config: AutopilotConfig,
    session_id: str,
    *,
    event_limit: int = 100,
) -> dict[str, Any]:
    """Return one orchestrator session with linked runs, approvals, and issues."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    runs = list_execution_plane_agent_action_runs(config, orchestrator_session_id=session_id)
    control_passes = list_execution_plane_orchestrator_session_control_passes(
        config,
        orchestrator_session_id=session_id,
    )
    approvals = [
        approval.model_dump()
        for approval in list_approvals(config)
        if approval.id in set(session.linked_approval_ids)
    ]
    issues = [
        issue.model_dump()
        for issue in list_issues(config)
        if issue.id in set(session.linked_issue_ids)
    ]
    async_tasks = list_execution_plane_runtime_agent_tasks(
        config,
        orchestrator_session_id=session_id,
    )
    all_events = list_execution_plane_orchestrator_session_events(config, session_id, limit=None)
    events = all_events[-event_limit:] if event_limit > 0 else []
    control = build_execution_plane_orchestrator_session_control(config, session_id)
    session = get_orchestrator_session(config, session_id) or session
    event_by_name: dict[str, int] = {}
    event_by_status: dict[str, int] = {}
    for event in all_events:
        event_name = str(event.get("event") or "unknown")
        event_status = str(event.get("status") or "unknown")
        event_by_name[event_name] = event_by_name.get(event_name, 0) + 1
        event_by_status[event_status] = event_by_status.get(event_status, 0) + 1
    return {
        **session.model_dump(),
        "runs": runs,
        "control_passes": control_passes,
        "approvals": approvals,
        "issues": issues,
        "async_tasks": async_tasks,
        "events": events,
        "control": control,
        "summary": {
            "run_count": len(runs),
            "control_pass_count": len(control_passes),
            "approval_count": len(approvals),
            "pending_approval_count": sum(1 for approval in approvals if approval.get("status") == "pending"),
            "issue_count": len(issues),
            "open_issue_count": sum(1 for issue in issues if issue.get("status") == "open"),
            "async_task_count": len(async_tasks),
            "active_async_task_count": sum(
                1 for task in async_tasks if str(task.get("status") or "") in {"queued", "running"}
            ),
            "event_count": len(all_events),
            "event_limit": event_limit,
            "latest_event_at": all_events[-1]["timestamp"] if all_events else None,
            "by_event": event_by_name,
            "by_event_status": event_by_status,
        },
    }


def list_execution_plane_orchestrator_session_events(
    config: AutopilotConfig,
    session_id: str,
    *,
    limit: int | None = 100,
) -> list[dict[str, Any]]:
    """Return execution events directly linked to one orchestrator session."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    linked_run_ids = set(session.linked_run_ids)
    linked_approval_ids = set(session.linked_approval_ids)
    linked_issue_ids = set(session.linked_issue_ids)
    project_ids = set(session.project_ids)

    matched: list[dict[str, Any]] = []
    for event in _load_enriched_execution_plane_events(config):
        event_project_id = str(event.get("project_id") or "")
        if project_ids and event_project_id and event_project_id not in project_ids:
            if str(event.get("orchestrator_session_id") or "") != session.id:
                continue

        if str(event.get("orchestrator_session_id") or "") == session.id:
            matched.append(event)
            continue
        if str(event.get("agent_action_run_id") or "") in linked_run_ids:
            matched.append(event)
            continue
        if str(event.get("approval_id") or "") in linked_approval_ids:
            matched.append(event)
            continue
        if str(event.get("issue_id") or "") in linked_issue_ids:
            matched.append(event)
            continue

    if limit is None:
        return matched
    return matched[-limit:]


def execute_execution_plane_orchestrator_session_actions(
    config: AutopilotConfig,
    session_id: str,
    *,
    action_keys: list[str] | None = None,
    preview_id: str = "",
    idempotency_key: str = "",
    actor: str,
    mode: str = "auto",
    reason: str = "",
    policy_profile: str | None = None,
    policy_overrides: dict[str, Any] | None = None,
    dry_run: bool = False,
    include_archived: bool = False,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = True,
    command_requires_approval: bool | None = None,
    priority: str | None = None,
    limit: int = 20,
    continue_on_error: bool = True,
    include_non_executable: bool = False,
) -> dict[str, Any]:
    """Preview or execute the current action scope of one orchestrator session."""

    session = get_orchestrator_session(config, session_id)
    if session is None:
        raise KeyError(session_id)

    requested_keys: list[str] = []
    seen: set[str] = set()
    for item in action_keys or []:
        key = str(item or "").strip()
        if not key or key in seen:
            continue
        requested_keys.append(key)
        seen.add(key)

    scoped_actions = list_execution_plane_orchestrator_session_actions(
        config,
        session_id,
        include_archived=include_archived,
        status=status,
        role=role,
        attention_state=attention_state,
        recommendation_kind=recommendation_kind,
        suggested_command=suggested_command,
        actionable_only=actionable_only,
        command_requires_approval=command_requires_approval,
        priority=priority,
    )
    scoped_action_map = {str(item["action_key"]): item for item in scoped_actions}
    if requested_keys:
        invalid_keys = [key for key in requested_keys if key not in scoped_action_map]
        if invalid_keys:
            raise ValueError(
                f"Runtime-agent action keys are outside orchestrator session `{session_id}` scope: {', '.join(invalid_keys)}"
            )
        selected_keys = requested_keys[:limit]
    else:
        selected_keys = [str(item["action_key"]) for item in scoped_actions[:limit]]
        if not selected_keys:
            raise ValueError(f"Orchestrator session `{session_id}` has no matching runtime-agent actions.")

    return execute_execution_plane_agent_actions(
        config,
        action_keys=selected_keys,
        orchestrator_session_id=session_id,
        preview_id=preview_id,
        idempotency_key=idempotency_key,
        actor=actor,
        mode=mode,
        reason=reason,
        policy_profile=policy_profile,
        policy_overrides=policy_overrides,
        dry_run=dry_run,
        include_archived=include_archived,
        limit=limit,
        continue_on_error=continue_on_error,
        include_non_executable=include_non_executable,
    )


def create_execution_plane_orchestrator_session(
    config: AutopilotConfig,
    *,
    orchestrator: str,
    actor: str,
    title: str = "",
    initiative_id: str = "",
    project_ids: list[str] | None = None,
    reason: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one orchestrator session and return the persisted record."""

    return create_orchestrator_session(
        config,
        orchestrator=orchestrator,
        actor=actor,
        title=title,
        initiative_id=initiative_id,
        project_ids=project_ids,
        reason=reason,
        context=context,
    ).model_dump()


def update_execution_plane_orchestrator_session_status(
    config: AutopilotConfig,
    *,
    session_id: str,
    status: str,
    actor: str,
    note: str = "",
) -> dict[str, Any]:
    """Update one orchestrator session status and return the record."""

    return update_orchestrator_session_status(
        config,
        session_id,
        status=status,
        actor=actor,
        note=note,
    ).model_dump()


def get_execution_plane_agent_detail(
    config: AutopilotConfig,
    runtime_agent_id: str,
    *,
    event_limit: int = 100,
) -> dict[str, Any]:
    """Return current and historical control-plane detail for one runtime agent."""

    parsed = parse_runtime_agent_id(runtime_agent_id)
    if parsed is None:
        raise ValueError(f"Invalid runtime agent id: {runtime_agent_id}")

    project = get_project_entry(config, project_id=parsed.project_id, include_archived=True)
    if project is None:
        raise KeyError(parsed.project_id)

    project_snapshot = build_execution_plane_project_snapshot(config, project)
    state = ensure_project_state(config, project, seed_mode="migrate")
    stories = merge_project_stories(config, project, state)
    current_agents = build_execution_plane_runtime_agents(config, project, stories)
    current_agent = next((agent for agent in current_agents if agent["agent_id"] == runtime_agent_id), None)

    issues = [issue.model_dump() for issue in list_issues(
        config,
        project_id=parsed.project_id,
        runtime_agent_id=runtime_agent_id,
    )]
    approvals = [approval.model_dump() for approval in list_approvals(
        config,
        project_id=parsed.project_id,
        runtime_agent_id=runtime_agent_id,
    )]
    async_tasks = list_execution_plane_runtime_agent_tasks(
        config,
        project_id=parsed.project_id,
        runtime_agent_id=runtime_agent_id,
    )
    events = list_execution_plane_events(
        config,
        project_id=parsed.project_id,
        runtime_agent_id=runtime_agent_id,
        limit=event_limit,
    )

    if current_agent is None and not issues and not approvals and not async_tasks and not events:
        raise KeyError(runtime_agent_id)

    story = next((item for item in stories if int(item["id"]) == parsed.story_id), None)
    current_story_id = current_agent.get("story_id") if current_agent is not None else parsed.story_id
    current_story_title = (
        current_agent.get("story_title")
        if current_agent is not None
        else story.get("title")
        if story is not None
        else None
    )
    status = (
        str(current_agent.get("status") or "unknown")
        if current_agent is not None
        else "historical"
        if (issues or approvals or events)
        else "unknown"
    )
    role = str(current_agent.get("role") or parsed.role) if current_agent is not None else parsed.role
    current_budget = _runtime_agent_budget_summary(state, current_agent, role=role)
    attention = _runtime_agent_attention_summary(
        agent=current_agent,
        project_snapshot=project_snapshot,
        budget=current_budget,
        open_issues=[issue for issue in issues if issue.get("status") == "open"],
        pending_approvals=[approval for approval in approvals if approval.get("status") == "pending"],
    )
    recommendations, suggested_commands = _runtime_agent_recommendations(
        config,
        project_id=parsed.project_id,
        project_snapshot=project_snapshot,
        agent=current_agent,
        budget=current_budget,
        attention=attention,
        open_issues=[issue for issue in issues if issue.get("status") == "open"],
        pending_approvals=[approval for approval in approvals if approval.get("status") == "pending"],
    )
    if current_agent is not None:
        current_agent = _decorate_runtime_agent(
            config,
            state=state,
            project_snapshot=project_snapshot,
            agent=current_agent,
            issues=issues,
            approvals=approvals,
        )

    return {
        "runtime_agent_id": runtime_agent_id,
        "project_id": parsed.project_id,
        "project_name": project["name"],
        "initiative": project_snapshot["initiative"],
        "orchestration": project_snapshot["orchestration"],
        "role": role,
        "status": status,
        "budget": current_budget,
        "attention": attention,
        "recommendations": recommendations,
        "suggested_commands": suggested_commands,
        "story_id": current_story_id,
        "story_title": current_story_title,
        "project": {
            "project_id": project_snapshot["project_id"],
            "name": project_snapshot["name"],
            "path": project_snapshot["path"],
            "status": project_snapshot["runtime"]["status"],
            "paused": project_snapshot["runtime"]["paused"],
            "current_story_id": project_snapshot["runtime"]["current_story_id"],
            "current_iteration": project_snapshot["runtime"]["current_iteration"],
        },
        "story": {
            "id": story.get("id") if story is not None else parsed.story_id,
            "title": story.get("title") if story is not None else current_story_title,
            "status": story.get("status") if story is not None else current_agent.get("story_status") if current_agent else "unknown",
            "phase_id": story.get("phase_id") if story is not None else None,
            "phase_title": story.get("phase_title") if story is not None else None,
            "iteration": story.get("iteration") if story is not None else None,
            "discoveries": story.get("discoveries", []) if story is not None else [],
            "github_pr": (
                story.get("github_pr")
                if story is not None
                else normalize_story_github_pr(
                    project["name"],
                    {"id": parsed.story_id, "title": current_story_title or f"Story {parsed.story_id}"},
                )
            ),
        },
        "current": current_agent,
        "history": {
            "issue_count": len(issues),
            "open_issue_count": sum(1 for issue in issues if issue.get("status") == "open"),
            "approval_count": len(approvals),
            "pending_approval_count": sum(1 for approval in approvals if approval.get("status") == "pending"),
            "async_task_count": len(async_tasks),
            "active_async_task_count": sum(
                1 for task in async_tasks if str(task.get("status") or "") in {"queued", "running"}
            ),
            "event_count": len(events),
            "last_event_at": events[-1].get("timestamp") if events else None,
        },
        "issues": issues,
        "approvals": approvals,
        "async_tasks": async_tasks,
        "events": events,
    }


def list_execution_plane_events(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    runtime_agent_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return a stable, enriched execution event feed for external orchestrators."""

    eligible_project_ids: set[str] = set()
    snapshot_index = _build_execution_plane_snapshot_index(config)
    for project_id_key, snapshot in snapshot_index.items():
        if initiative_id and snapshot["initiative"].get("id") != initiative_id:
            continue
        if orchestrator and snapshot["orchestration"].get("orchestrator") != orchestrator:
            continue
        eligible_project_ids.add(project_id_key)

    if project_id is not None:
        eligible_project_ids = {project_id}

    events: list[dict[str, Any]] = []
    for event in _load_enriched_execution_plane_events(config):
        event_project_id = str(event.get("project_id") or "")
        if event_project_id and event_project_id not in eligible_project_ids:
            continue
        if not event_project_id and (project_id or initiative_id or orchestrator):
            continue
        if runtime_agent_id:
            event_agent_ids = _event_runtime_agent_ids(event)
            if runtime_agent_id not in event_agent_ids:
                continue
        events.append(event)

    return events[-limit:]


SUPPORTED_EXECUTION_COMMANDS = {
    "launch",
    "pause",
    "resume",
    "archive",
    "update_budget_policy",
}
SUPPORTED_AGENT_ACTION_EXECUTION_MODES = {
    "auto",
    "execute_now",
    "request_approval",
}
EXECUTION_COMMAND_TOOL_DESCRIPTIONS: dict[str, str] = {
    "launch": "Launch a project run from the execution-plane control surface.",
    "pause": "Pause the active project run.",
    "resume": "Resume a paused or stopped project run.",
    "archive": "Archive the project from the execution plane.",
    "update_budget_policy": "Update the project runtime budget policy.",
}


def _execution_command_tool_name(command: str) -> str:
    return f"execution.{command}"


def _execution_command_policy_reasons(
    policy: dict[str, Any],
    *,
    command: str,
    payload: dict[str, Any] | None = None,
) -> list[str]:
    payload = payload or {}
    reasons: list[str] = []

    if command in policy.get("approval_required_commands", []):
        reasons.append(f"`{command}` is configured to always require approval.")

    if command == "launch":
        launch_profile = payload.get("launch_profile") or {}
        if (
            policy.get("parallel_launch_requires_approval")
            and launch_profile.get("project_concurrency_mode") == "parallel"
        ):
            reasons.append("Parallel project launch requires approval under current policy.")
        max_parallel_stories = int(launch_profile.get("max_parallel_stories") or 1)
        if max_parallel_stories > int(policy.get("max_parallel_stories_without_approval") or 1):
            reasons.append(
                "Requested parallel story fan-out exceeds the non-approved threshold "
                f"({max_parallel_stories} > {policy['max_parallel_stories_without_approval']})."
            )

    if command == "update_budget_policy":
        budget_policy = payload.get("budget_policy") or {}
        if (
            policy.get("disable_auto_pause_requires_approval")
            and budget_policy.get("auto_pause_on_exhaustion") is False
        ):
            reasons.append("Disabling auto-pause on budget exhaustion requires approval.")
        threshold_map = {
            "project_max_worker_iterations": "project_max_worker_iterations_without_approval",
            "project_max_critic_reviews": "project_max_critic_reviews_without_approval",
            "run_max_worker_iterations": "run_max_worker_iterations_without_approval",
            "run_max_critic_reviews": "run_max_critic_reviews_without_approval",
            "story_max_worker_iterations": "story_max_worker_iterations_without_approval",
            "story_max_critic_reviews": "story_max_critic_reviews_without_approval",
            "agent_max_worker_iterations": "agent_max_worker_iterations_without_approval",
            "agent_max_critic_reviews": "agent_max_critic_reviews_without_approval",
            "run_max_runtime_seconds": "run_max_runtime_seconds_without_approval",
            "story_max_runtime_seconds": "story_max_runtime_seconds_without_approval",
        }
        for requested_key, threshold_key in threshold_map.items():
            requested_value = budget_policy.get(requested_key)
            if requested_value is None:
                continue
            if int(requested_value) > int(policy.get(threshold_key) or 0):
                reasons.append(
                    f"`{requested_key}` exceeds the non-approved threshold "
                    f"({requested_value} > {policy[threshold_key]})."
                )
    return reasons


def _execution_command_permission_context(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None = None,
    mode: str = "default",
) -> Any:
    reasons = _execution_command_policy_reasons(
        load_project_command_policy(config, project_id),
        command=command,
        payload=payload,
    )
    tool_name = _execution_command_tool_name(command)
    overlay = PermissionContextOverlay(mode=mode if mode != "default" else None)
    if reasons:
        overlay.ask_rules = [permission_rule_value_to_string(PermissionRuleValue(tool_name=tool_name))]
        overlay.tool_reasons = {tool_name: reasons}
    overlays = {"command": overlay} if overlay.mode is not None or overlay.ask_rules or overlay.tool_reasons else None
    return load_tool_permission_context(config, project_id=project_id, overlays=overlays)


def _build_execution_command_tool(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
) -> Any:
    if command not in SUPPORTED_EXECUTION_COMMANDS:
        raise ValueError(f"Unsupported execution-plane command: {command}")
    return build_tool(
        name=_execution_command_tool_name(command),
        description=EXECUTION_COMMAND_TOOL_DESCRIPTIONS[command],
        input_schema={"type": "object", "properties": {}},
        execute=lambda tool_input, use_context: _execute_execution_plane_command_impl(
            config,
            project_id=project_id,
            command=command,
            payload=tool_input,
            use_context=use_context,
        ),
        kind="execution_command",
        scope="project",
        approval_policy="policy",
        metadata={"project_id": project_id, "command": command},
    )


def _execute_execution_plane_command_impl(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None,
    use_context: ToolUseContext,
) -> ToolResult:
    del use_context

    payload = payload or {}
    result: dict[str, Any] = {
        "project_id": project_id,
        "command": command,
    }
    if command == "launch":
        launched, log_path, message = launch_project_run(
            config,
            project_id,
            launch_profile=payload.get("launch_profile"),
        )
        result.update(
            {
                "status": "ok" if launched else "error",
                "launched": launched,
                "message": message,
                "log_path": str(log_path) if log_path else "",
            }
        )
    elif command == "pause":
        result.update(
            {
                "status": "ok",
                "message": pause_project_run(config, project_id),
            }
        )
    elif command == "resume":
        launched, log_path, message = resume_project_run(config, project_id)
        result.update(
            {
                "status": "ok" if launched else "error",
                "launched": launched,
                "message": message,
                "log_path": str(log_path) if log_path else "",
            }
        )
    elif command == "archive":
        archived = archive_project(config, project_id)
        result.update(
            {
                "status": "ok",
                "archived": True,
                "message": f"Archived {archived['name']}",
            }
        )
    elif command == "update_budget_policy":
        policy = update_project_budget_policy(config, project_id, **(payload.get("budget_policy") or {}))
        state = load_project_state(config, project_id)
        result.update(
            {
                "status": "ok",
                "message": "Budget policy updated.",
                "budget_policy": policy,
                "budget_usage": state.get("budget_usage"),
            }
        )
    return ToolResult(
        status=str(result.get("status") or "ok"),
        message=str(result.get("message") or ""),
        payload=result,
    )


def create_execution_command_approval(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None = None,
    requested_by: str = "",
    reason: str = "",
    issue_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    policy_reasons: list[str] | None = None,
) -> dict[str, Any]:
    """Create a pending approval for an execution-plane command."""

    if command not in SUPPORTED_EXECUTION_COMMANDS:
        raise ValueError(f"Unsupported execution-plane command: {command}")
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)
    runtime_agent_ids = list(runtime_agent_ids or _affected_runtime_agent_ids(config, project))
    if issue_id:
        existing = list_approvals(
            config,
            project_id=project_id,
            action=command,
            status="pending",
            issue_id=issue_id,
        )
        if existing:
            return existing[-1].model_dump()

    approval = create_approval(
        config,
        project=project,
        action=command,
        payload=payload,
        requested_by=requested_by,
        reason=reason,
        issue_id=issue_id,
        runtime_agent_ids=runtime_agent_ids,
        policy_reasons=policy_reasons,
    )
    if issue_id:
        link_issue_approval(config, issue_id=issue_id, approval_id=approval.id)
    return approval.model_dump()


def execute_execution_plane_agent_action(
    config: AutopilotConfig,
    *,
    action_key: str,
    actor: str,
    mode: str = "auto",
    reason: str = "",
    orchestrator_session_id: str = "",
) -> dict[str, Any]:
    """Execute or escalate one flattened runtime-agent action."""

    if mode not in SUPPORTED_AGENT_ACTION_EXECUTION_MODES:
        raise ValueError(
            f"Unsupported runtime-agent action execution mode: {mode}. "
            f"Expected one of {sorted(SUPPORTED_AGENT_ACTION_EXECUTION_MODES)}."
        )

    action = get_execution_plane_agent_action(config, action_key)
    if action["action_type"] != "suggested_command":
        return {
            "status": "not_executable",
            "message": "Only suggested-command actions are directly executable.",
            "action": action,
        }

    project_id = str(action["project_id"])
    command = str(action["command"])
    payload = dict(action.get("payload") or {})
    policy_reasons = [str(item) for item in (action.get("policy_reasons") or [])]
    approval_required = bool(action.get("approval_required"))
    action_reason = reason.strip() or str(action.get("reason") or "")
    event_extra = {
        "runtime_agent_id": str(action["runtime_agent_id"]),
        "runtime_agent_ids": [str(action["runtime_agent_id"])],
        "action_key": action_key,
        "action_type": action["action_type"],
        "action_mode": mode,
        "actor": actor,
    }
    normalized_session_id = orchestrator_session_id.strip()
    if normalized_session_id:
        event_extra["orchestrator_session_id"] = normalized_session_id

    if mode == "request_approval" or (mode == "auto" and approval_required):
        issue = create_execution_command_issue(
            config,
            project_id=project_id,
            command=command,
            requested_by=actor,
            reason=action_reason,
            policy_reasons=policy_reasons,
            runtime_agent_ids=[str(action["runtime_agent_id"])],
        )
        approval = create_execution_command_approval(
            config,
            project_id=project_id,
            command=command,
            payload=payload,
            requested_by=actor,
            reason=action_reason,
            issue_id=issue["id"],
            runtime_agent_ids=[str(action["runtime_agent_id"])],
            policy_reasons=policy_reasons,
        )
        issue["approval_id"] = approval["id"]
        emit_project_event(
            config,
            project_id,
            event="execution_plane_agent_action_pending_approval",
            status="pending_approval",
            message=f"Runtime-agent action `{action_key}` escalated to approval.",
            story_id=action.get("story_id"),
            extra={
                **event_extra,
                "command": command,
                "approval_id": approval["id"],
                "issue_id": issue["id"],
                "policy_reasons": policy_reasons,
            },
        )
        return {
            "status": "pending_approval",
            "action": action,
            "approval": approval,
            "issue": issue,
            "policy_triggered": approval_required,
            "policy_reasons": policy_reasons,
            "project": build_execution_plane_project_detail(config, project_id),
        }

    if approval_required:
        raise RuntimeError(
            f"Runtime-agent action `{action_key}` requires approval under current project policy."
        )

    command_result = execute_execution_plane_command(
        config,
        project_id=project_id,
        command=command,
        payload=payload,
        actor=actor,
        orchestrator_session_id=normalized_session_id,
        runtime_agent_ids=[str(action["runtime_agent_id"])],
        reason=action_reason,
    )
    emit_project_event(
        config,
        project_id,
        event="execution_plane_agent_action_executed",
        status=str(command_result.get("status") or "ok"),
        message=f"Runtime-agent action `{action_key}` executed via `{command}`.",
        story_id=action.get("story_id"),
        extra={
            **event_extra,
            "command": command,
            "command_result_status": command_result.get("status"),
            "command_result_message": command_result.get("message"),
        },
    )
    return {
        "status": str(command_result.get("status") or "ok"),
        "action": action,
        "command_result": command_result,
        "project": command_result.get("project"),
    }


def execute_execution_plane_agent_action_with_run(
    config: AutopilotConfig,
    *,
    action_key: str,
    orchestrator_session_id: str = "",
    idempotency_key: str = "",
    actor: str,
    mode: str = "auto",
    reason: str = "",
) -> dict[str, Any]:
    """Execute one runtime-agent action with persisted run reporting and idempotency."""

    normalized_idempotency_key = idempotency_key.strip()
    request_fingerprint = _execution_plane_agent_action_request_fingerprint(
        {
            "action_key": action_key,
            "orchestrator_session_id": orchestrator_session_id,
            "actor": actor,
            "mode": mode,
            "reason": reason,
        }
    )
    normalized_session_id = orchestrator_session_id.strip()
    if normalized_session_id and get_orchestrator_session(config, normalized_session_id) is None:
        raise KeyError(normalized_session_id)
    if normalized_idempotency_key:
        existing = find_agent_action_batch_run_by_idempotency_key(config, normalized_idempotency_key)
        if existing is not None:
            if existing.request_fingerprint and existing.request_fingerprint != request_fingerprint:
                raise RuntimeError(
                    f"Idempotency key `{normalized_idempotency_key}` was already used for a different runtime-agent action request."
                )
            return _execution_plane_agent_action_run_response(config, existing, idempotent_replay=True)

    action = get_execution_plane_agent_action(config, action_key)
    result = execute_execution_plane_agent_action(
        config,
        action_key=action_key,
        actor=actor,
        mode=mode,
        reason=reason,
        orchestrator_session_id=normalized_session_id,
    )
    approval_required = _execution_plane_agent_action_run_requires_approval([action], [result])
    apply_mode = _execution_plane_agent_action_apply_mode(
        dry_run=False,
        requested_mode=mode,
        approval_required=approval_required,
    )
    diff_summary = _build_execution_plane_agent_action_diff_summary(
        [action],
        [result],
        status_counts={str(result.get("status") or "unknown"): 1},
        approval_required=approval_required,
        apply_mode=apply_mode,
    )
    patch_bundle = _build_execution_plane_agent_action_patch_bundle(
        [action],
        [result],
        requested_mode=mode,
        dry_run=False,
        default_apply_mode=apply_mode,
    )
    run = create_agent_action_batch_run(
        config,
        run_kind="single_action",
        orchestrator_session_id=normalized_session_id,
        idempotency_key=normalized_idempotency_key,
        request_fingerprint=request_fingerprint,
        actor=actor,
        mode=mode,
        reason=reason,
        dry_run=False,
        policy_profile="",
        policy={},
        selection={
            "mode": "single_action",
            "requested_action_keys": [action_key],
            "selected_action_keys": [action_key],
            "preview_id": "",
            "project_id": action.get("project_id"),
            "initiative_id": (action.get("initiative") or {}).get("id"),
            "orchestrator": (action.get("orchestration") or {}).get("orchestrator"),
            "runtime_agent_id": action.get("runtime_agent_id"),
        },
        summary={
            "selected_count": 1,
            "processed_count": 1,
            "status_counts": {str(result.get("status") or "unknown"): 1},
            "approval_required_count": 1 if approval_required else 0,
            "apply_mode": apply_mode,
        },
        diff_summary=diff_summary,
        patch_bundle=patch_bundle,
        preview_id="",
        artifact_ref="",
        approval_required=approval_required,
        apply_mode=apply_mode,
        results=[result],
        status=str(result.get("status") or "ok"),
        project_ids=[str(action.get("project_id") or "")],
        initiative_ids=[str((action.get("initiative") or {}).get("id") or "")],
        orchestrators=[str((action.get("orchestration") or {}).get("orchestrator") or "")],
        runtime_agent_ids=[str(action.get("runtime_agent_id") or "")],
    )
    if not run.artifact_ref:
        run.artifact_ref = f"/api/execution-plane/agents/action-runs/{run.id}"
        run = save_agent_action_batch_run(config, run)
    linked_approval_ids: list[str] = []
    linked_issue_ids: list[str] = []
    if result.get("approval", {}).get("id"):
        linked_approval_ids.append(str(result["approval"]["id"]))
    if result.get("issue", {}).get("id"):
        linked_issue_ids.append(str(result["issue"]["id"]))
    if normalized_session_id:
        link_orchestrator_session_entities(
            config,
            normalized_session_id,
            project_ids=[str(action.get("project_id") or "")],
            linked_run_ids=[run.id],
            linked_approval_ids=linked_approval_ids,
            linked_issue_ids=linked_issue_ids,
            linked_runtime_agent_ids=[str(action.get("runtime_agent_id") or "")],
        )
    emit_project_event(
        config,
        str(action.get("project_id") or ""),
        event="execution_plane_agent_action_run_recorded",
        status=str(result.get("status") or "ok"),
        message=f"Runtime-agent action run `{run.id}` recorded.",
        story_id=action.get("story_id"),
        extra={
            "agent_action_run_id": run.id,
            "orchestrator_session_id": normalized_session_id,
            "idempotency_key": run.idempotency_key,
            "action_key": action_key,
            "actor": actor,
            "action_mode": mode,
            "runtime_agent_id": str(action.get("runtime_agent_id") or ""),
            "runtime_agent_ids": [str(action.get("runtime_agent_id") or "")] if str(action.get("runtime_agent_id") or "").strip() else [],
        },
    )
    task_id = str((result.get("async_task") or {}).get("id") or "")
    if task_id:
        link_runtime_agent_task_run(config, task_id, agent_action_run_id=run.id)
        run.results = _refresh_result_async_tasks(config, run.results)
        run = save_agent_action_batch_run(config, run)
    return _execution_plane_agent_action_run_response(config, run, idempotent_replay=False)


def execute_execution_plane_agent_actions(
    config: AutopilotConfig,
    *,
    action_keys: list[str] | None = None,
    preview_id: str = "",
    orchestrator_session_id: str = "",
    idempotency_key: str = "",
    actor: str,
    mode: str = "auto",
    reason: str = "",
    policy_profile: str | None = None,
    policy_overrides: dict[str, Any] | None = None,
    dry_run: bool = False,
    include_archived: bool = False,
    project_id: str | None = None,
    initiative_id: str | None = None,
    orchestrator: str | None = None,
    status: str | None = None,
    role: str | None = None,
    attention_state: str | None = None,
    recommendation_kind: str | None = None,
    suggested_command: str | None = None,
    actionable_only: bool = True,
    command_requires_approval: bool | None = None,
    priority: str | None = None,
    limit: int = 20,
    continue_on_error: bool = True,
    include_non_executable: bool = False,
) -> dict[str, Any]:
    """Execute a batch of runtime-agent actions using explicit keys or filtered selection."""

    normalized_keys: list[str] = []
    seen_keys: set[str] = set()
    for item in action_keys or []:
        key = str(item or "").strip()
        if not key or key in seen_keys:
            continue
        normalized_keys.append(key)
        seen_keys.add(key)

    if not normalized_keys and not any([project_id, initiative_id, orchestrator]):
        raise ValueError(
            "Batch runtime-agent action execution requires explicit action_keys or a project/initiative/orchestrator scope."
        )

    resolved_policy = resolve_execution_plane_agent_action_batch_policy(
        profile_name=policy_profile,
        overrides=policy_overrides,
    )
    normalized_session_id = orchestrator_session_id.strip()
    if normalized_session_id and get_orchestrator_session(config, normalized_session_id) is None:
        raise KeyError(normalized_session_id)
    normalized_preview_id = preview_id.strip()
    if dry_run and normalized_preview_id:
        raise ValueError("preview_id can only be used when applying a previously generated preview.")
    normalized_idempotency_key = idempotency_key.strip()
    request_fingerprint = _execution_plane_agent_action_batch_request_fingerprint(
        {
            "action_keys": normalized_keys,
            "preview_id": normalized_preview_id,
            "orchestrator_session_id": normalized_session_id,
            "actor": actor,
            "mode": mode,
            "reason": reason,
            "policy_profile": policy_profile or "",
            "policy_overrides": policy_overrides or {},
            "dry_run": dry_run,
            "include_archived": include_archived,
            "project_id": project_id,
            "initiative_id": initiative_id,
            "orchestrator": orchestrator,
            "status": status,
            "role": role,
            "attention_state": attention_state,
            "recommendation_kind": recommendation_kind,
            "suggested_command": suggested_command,
            "actionable_only": actionable_only,
            "command_requires_approval": command_requires_approval,
            "priority": priority,
            "limit": limit,
            "continue_on_error": continue_on_error,
            "include_non_executable": include_non_executable,
            "resolved_policy": resolved_policy,
        }
    )
    if normalized_idempotency_key:
        existing = find_agent_action_batch_run_by_idempotency_key(config, normalized_idempotency_key)
        if existing is not None:
            if existing.request_fingerprint and existing.request_fingerprint != request_fingerprint:
                raise RuntimeError(
                    f"Idempotency key `{normalized_idempotency_key}` was already used for a different batch action request."
                )
            return _execution_plane_agent_action_batch_run_response(config, existing, idempotent_replay=True)

    selected_actions: list[dict[str, Any]]
    if normalized_keys:
        selected_actions = []
        for key in normalized_keys[:limit]:
            selected_actions.append(get_execution_plane_agent_action(config, key))
    else:
        selected_actions = list_execution_plane_agent_actions(
            config,
            include_archived=include_archived,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            status=status,
            role=role,
            attention_state=attention_state,
            recommendation_kind=recommendation_kind,
            suggested_command=suggested_command,
            actionable_only=actionable_only,
            command_requires_approval=command_requires_approval,
            priority=priority,
        )
        if not include_non_executable:
            selected_actions = [item for item in selected_actions if item.get("action_type") == "suggested_command"]
        selected_actions = selected_actions[:limit]

    if normalized_preview_id:
        preview_record = get_agent_action_batch_run(config, normalized_preview_id)
        if preview_record is None:
            raise KeyError(normalized_preview_id)
        if not preview_record.dry_run:
            raise ValueError(f"Runtime-agent action run `{normalized_preview_id}` is not a preview run.")
        if preview_record.mode != mode:
            raise RuntimeError(
                f"Preview run `{normalized_preview_id}` was created with mode `{preview_record.mode}`, not `{mode}`."
            )
        if dict(preview_record.policy or {}) != dict(resolved_policy or {}):
            raise RuntimeError(
                f"Preview run `{normalized_preview_id}` was created under a different batch policy."
            )
        preview_session_id = str(preview_record.orchestrator_session_id or "").strip()
        if preview_session_id != normalized_session_id:
            raise RuntimeError(
                f"Preview run `{normalized_preview_id}` belongs to orchestrator session `{preview_session_id or 'none'}`."
            )
        preview_selected_keys = _listify_strings((preview_record.selection or {}).get("selected_action_keys"))
        current_selected_keys = [str(item["action_key"]) for item in selected_actions]
        if preview_selected_keys != current_selected_keys:
            raise RuntimeError(
                f"Preview run `{normalized_preview_id}` no longer matches the current runtime-agent action selection."
            )

    executed_per_project: dict[str, int] = {}
    results: list[dict[str, Any]] = []
    for action in selected_actions:
        action_type = str(action.get("action_type") or "")
        action_priority = str(action.get("priority") or "")
        project_key = str(action.get("project_id") or "")
        if resolved_policy["include_action_types"] and action_type not in resolved_policy["include_action_types"]:
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": f"Skipped by batch policy: action type `{action_type}` is not allowed.",
                }
            )
            continue
        if (
            resolved_policy["skip_paused_projects"]
            and bool(action.get("project_paused"))
        ):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: paused projects are excluded.",
                }
            )
            continue
        if (
            resolved_policy["exclude_attention_states"]
            and str(action.get("attention", {}).get("state") or "") in resolved_policy["exclude_attention_states"]
        ):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: attention state is excluded.",
                }
            )
            continue
        if not _priority_meets_threshold(action_priority, resolved_policy.get("priority_at_least")):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: action priority is below threshold.",
                }
            )
            continue
        if (
            action_type == "suggested_command"
            and resolved_policy["allowed_commands"]
            and str(action.get("command") or "") not in resolved_policy["allowed_commands"]
        ):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: command is not allowed.",
                }
            )
            continue
        if (
            action_type == "recommendation"
            and resolved_policy["allowed_recommendation_kinds"]
            and str(action.get("kind") or "") not in resolved_policy["allowed_recommendation_kinds"]
        ):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: recommendation kind is not allowed.",
                }
            )
            continue
        if (
            resolved_policy.get("max_actions_per_project") is not None
            and executed_per_project.get(project_key, 0) >= int(resolved_policy["max_actions_per_project"])
        ):
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: per-project action limit reached.",
                }
            )
            continue

        execution_mode = mode
        if action_type == "suggested_command":
            approval_required = bool(action.get("approval_required"))
            if approval_required and mode == "auto":
                approval_strategy = str(resolved_policy.get("approval_strategy") or "").strip()
                approval_priority_threshold = resolved_policy.get("approval_priority_at_least")
                if approval_strategy == "skip":
                    results.append(
                        {
                            "status": "skipped",
                            "action": action,
                            "message": "Skipped by batch policy: approval-required actions are disabled.",
                        }
                    )
                    continue
                if approval_strategy == "request":
                    if not _priority_meets_threshold(action_priority, approval_priority_threshold):
                        results.append(
                            {
                                "status": "skipped",
                                "action": action,
                                "message": "Skipped by batch policy: approval escalation priority threshold not met.",
                            }
                        )
                        continue
                    execution_mode = "request_approval"
        elif not include_non_executable:
            results.append(
                {
                    "status": "skipped",
                    "action": action,
                    "message": "Skipped by batch policy: recommendation-only actions are not executable.",
                }
            )
            continue

        try:
            if dry_run:
                approval_required = bool(action.get("approval_required"))
                if action_type == "suggested_command" and approval_required and execution_mode == "execute_now":
                    results.append(
                        {
                            "status": "error",
                            "action": action,
                            "message": "Runtime-agent action requires approval and cannot be previewed as execute_now.",
                        }
                    )
                    if not continue_on_error:
                        break
                    continue

                planned_status = "planned_execute"
                if action_type == "suggested_command" and (
                    execution_mode == "request_approval" or (execution_mode == "auto" and approval_required)
                ):
                    planned_status = "planned_request_approval"
                results.append(
                    {
                        "status": planned_status,
                        "action": action,
                        "planned_mode": execution_mode,
                        "message": "Dry-run preview only. No control-plane mutation was applied.",
                    }
                )
                executed_per_project[project_key] = executed_per_project.get(project_key, 0) + 1
                continue

            result = execute_execution_plane_agent_action(
                config,
                action_key=str(action["action_key"]),
                actor=actor,
                mode=execution_mode,
                reason=reason,
                orchestrator_session_id=normalized_session_id,
            )
            results.append(result)
            if str(result.get("status") or "") not in {"error", "skipped", "not_executable"}:
                executed_per_project[project_key] = executed_per_project.get(project_key, 0) + 1
        except Exception as exc:
            results.append(
                {
                    "status": "error",
                    "action": action,
                    "message": str(exc),
                }
            )
            if not continue_on_error:
                break

    status_counts: dict[str, int] = {}
    for result in results:
        result_status = str(result.get("status") or "unknown")
        status_counts[result_status] = status_counts.get(result_status, 0) + 1

    overall_status = "ok"
    if status_counts.get("error"):
        overall_status = "partial" if len(status_counts) > 1 else "error"
    elif not results:
        overall_status = "ok"

    approval_required = _execution_plane_agent_action_run_requires_approval(selected_actions, results)
    apply_mode = _execution_plane_agent_action_apply_mode(
        dry_run=dry_run,
        requested_mode=mode,
        approval_required=approval_required,
    )

    selection = {
        "mode": "action_keys" if normalized_keys else "filters",
        "requested_action_keys": normalized_keys,
        "selected_action_keys": [str(item["action_key"]) for item in selected_actions],
        "preview_id": normalized_preview_id,
        "include_non_executable": include_non_executable,
        "limit": limit,
        "project_id": project_id,
        "initiative_id": initiative_id,
        "orchestrator": orchestrator,
        "status_filter": status,
        "role_filter": role,
        "attention_state": attention_state,
        "recommendation_kind": recommendation_kind,
        "suggested_command": suggested_command,
        "actionable_only": actionable_only,
        "command_requires_approval": command_requires_approval,
        "priority": priority,
    }
    summary = {
        "selected_count": len(selected_actions),
        "processed_count": len(results),
        "status_counts": status_counts,
        "approval_required_count": sum(1 for item in selected_actions if bool(item.get("approval_required"))),
        "apply_mode": apply_mode,
    }
    diff_summary = _build_execution_plane_agent_action_diff_summary(
        selected_actions,
        results,
        status_counts=status_counts,
        approval_required=approval_required,
        apply_mode=apply_mode,
    )
    patch_bundle = _build_execution_plane_agent_action_patch_bundle(
        selected_actions,
        results,
        requested_mode=mode,
        dry_run=dry_run,
        default_apply_mode=apply_mode,
    )
    project_ids = {str(item.get("project_id") or "") for item in selected_actions if str(item.get("project_id") or "").strip()}
    initiative_ids = {
        str((item.get("initiative") or {}).get("id") or "")
        for item in selected_actions
        if str((item.get("initiative") or {}).get("id") or "").strip()
    }
    orchestrators = {
        str((item.get("orchestration") or {}).get("orchestrator") or "")
        for item in selected_actions
        if str((item.get("orchestration") or {}).get("orchestrator") or "").strip()
    }
    runtime_agent_ids = {
        str(item.get("runtime_agent_id") or "")
        for item in selected_actions
        if str(item.get("runtime_agent_id") or "").strip()
    }
    if project_id:
        project_ids.add(str(project_id))
    if initiative_id:
        initiative_ids.add(str(initiative_id))
    if orchestrator:
        orchestrators.add(str(orchestrator))
    run = create_agent_action_batch_run(
        config,
        idempotency_key=normalized_idempotency_key,
        orchestrator_session_id=normalized_session_id,
        request_fingerprint=request_fingerprint,
        actor=actor,
        mode=mode,
        reason=reason,
        dry_run=dry_run,
        policy_profile=str(resolved_policy.get("profile_name") or ""),
        policy=resolved_policy,
        selection=selection,
        summary=summary,
        diff_summary=diff_summary,
        patch_bundle=patch_bundle,
        preview_id=normalized_preview_id,
        artifact_ref="",
        approval_required=approval_required,
        apply_mode=apply_mode,
        results=results,
        status=overall_status,
        project_ids=sorted(project_ids),
        initiative_ids=sorted(initiative_ids),
        orchestrators=sorted(orchestrators),
        runtime_agent_ids=sorted(runtime_agent_ids),
    )
    run_updated = False
    if dry_run and not run.preview_id:
        run.preview_id = run.id
        run_updated = True
    if not run.artifact_ref:
        run.artifact_ref = f"/api/execution-plane/agents/action-runs/{run.id}"
        run_updated = True
    if run_updated:
        run = save_agent_action_batch_run(config, run)
    for result in results:
        task_id = str((result.get("async_task") or {}).get("id") or "")
        if task_id:
            link_runtime_agent_task_run(config, task_id, agent_action_run_id=run.id)
    run.results = _refresh_result_async_tasks(config, run.results)
    run = save_agent_action_batch_run(config, run)
    if normalized_session_id:
        linked_approval_ids = [
            str(result.get("approval", {}).get("id") or "")
            for result in results
            if str(result.get("approval", {}).get("id") or "").strip()
        ]
        linked_issue_ids = [
            str(result.get("issue", {}).get("id") or "")
            for result in results
            if str(result.get("issue", {}).get("id") or "").strip()
        ]
        link_orchestrator_session_entities(
            config,
            normalized_session_id,
            project_ids=sorted(project_ids),
            linked_run_ids=[run.id],
            linked_approval_ids=linked_approval_ids,
            linked_issue_ids=linked_issue_ids,
            linked_runtime_agent_ids=sorted(runtime_agent_ids),
        )
    _emit_execution_plane_agent_action_batch_run_events(config, run)
    return _execution_plane_agent_action_batch_run_response(config, run, idempotent_replay=False)


def _attach_execution_plane_runtime_agent_task(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    actor: str,
    result: dict[str, Any],
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    reason: str = "",
    approval_id: str = "",
    issue_id: str = "",
) -> dict[str, Any]:
    normalized_command = str(command or "").strip()
    if normalized_command not in {"launch", "resume"}:
        return result
    if not bool(result.get("launched")):
        return result

    task = create_or_reuse_runtime_agent_task(
        config,
        project_id=project_id,
        command=normalized_command,
        actor=actor,
        reason=reason,
        orchestrator_session_id=orchestrator_session_id,
        runtime_agent_ids=runtime_agent_ids,
        output_path=str(result.get("log_path") or ""),
        approval_id=approval_id,
        issue_id=issue_id,
    )
    payload = dict(result)
    payload["async_task"] = _materialize_execution_plane_runtime_agent_task_record(task)
    payload["async_task_id"] = task.id
    base_message = str(payload.get("message") or "").strip()
    honesty_suffix = f"Async task `{task.id}` is running; final completion is not available yet."
    payload["message"] = f"{base_message} {honesty_suffix}".strip() if base_message else honesty_suffix
    return payload


def execute_execution_plane_command(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    payload: dict[str, Any] | None = None,
    actor: str = "",
    permission_mode: str = "default",
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    reason: str = "",
    approval_id: str = "",
    issue_id: str = "",
) -> dict[str, Any]:
    """Execute one explicit external control-plane command against a project."""

    if command not in SUPPORTED_EXECUTION_COMMANDS:
        raise ValueError(f"Unsupported execution-plane command: {command}")
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise KeyError(project_id)

    tool = _build_execution_command_tool(config, project_id=project_id, command=command)
    permission_context = _execution_command_permission_context(
        config,
        project_id=project_id,
        command=command,
        payload=payload,
        mode=permission_mode,
    )
    run_result = run_tool_use(
        tool,
        payload or {},
        ToolUseContext(
            config=config,
            actor=actor,
            project_id=project_id,
            metadata={"command": command},
        ),
        permission_context=permission_context,
    )
    if run_result.status == "approval_required":
        raise RuntimeError(run_result.message or f"Execution command `{command}` requires approval.")
    if run_result.status in {"denied", "blocked", "error"}:
        raise RuntimeError(run_result.message or f"Execution command `{command}` failed.")
    result = dict((run_result.tool_result.payload if run_result.tool_result else {}) or {})
    result["project"] = build_execution_plane_project_detail(config, project_id)
    return _attach_execution_plane_runtime_agent_task(
        config,
        project_id=project_id,
        command=command,
        actor=actor,
        result=result,
        orchestrator_session_id=orchestrator_session_id.strip(),
        runtime_agent_ids=runtime_agent_ids,
        reason=reason,
        approval_id=approval_id,
        issue_id=issue_id,
    )


def apply_execution_command_approval(
    config: AutopilotConfig,
    *,
    approval_id: str,
    actor: str,
) -> dict[str, Any]:
    """Apply an approved execution-plane approval and return the command result."""

    approval = get_approval(config, approval_id)
    if approval is None:
        raise KeyError(approval_id)
    if approval.status != "approved":
        raise RuntimeError(f"Approval {approval_id} must be approved before apply.")

    command_result = execute_execution_plane_command(
        config,
        project_id=approval.project_id,
        command=approval.action,
        payload=approval.payload,
        actor=actor,
        permission_mode="approved",
        runtime_agent_ids=list(approval.runtime_agent_ids),
        reason=approval.reason,
        approval_id=approval.id,
        issue_id=approval.issue_id,
    )
    if command_result.get("status") != "ok":
        raise RuntimeError(str(command_result.get("message") or f"Execution command `{approval.action}` failed."))
    applied = mark_approval_applied(config, approval_id, actor=actor)
    if applied.issue_id:
        try:
            resolve_issue(
                config,
                applied.issue_id,
                actor=actor,
                note=f"Approved command `{applied.action}` applied successfully.",
            )
        except RuntimeError:
            pass
    return {
        "status": command_result.get("status", "ok"),
        "approval": applied.model_dump(),
        "command_result": command_result,
    }


def ingest_execution_brief_project(
    config: AutopilotConfig,
    manager: Any,
    *,
    brief: ExecutionBrief,
    project_name: str | None = None,
    project_path: str | None = None,
    priority: str = "normal",
    launch: bool = False,
    launch_profile: dict[str, Any] | None = None,
) -> IngestedExecutionProject:
    """Convert a typed execution brief into a registered Autopilot project."""

    effective_brief = brief.model_copy(update={"task_source": _resolve_execution_brief_task_source(brief)})
    profile = manager.get_next("codex")
    if profile is None:
        raise RuntimeError("No available accounts for execution brief planning")

    env = manager.build_env(profile)
    planning_context = build_planning_context(
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        role_templates=load_role_templates(),
    )
    spec = render_execution_brief_as_spec(effective_brief)
    prd = generate_prd_from_spec(
        spec,
        provider="codex",
        env=env,
        planning_context=planning_context,
        timeout_sec=config.codex_timeout_sec,
    )

    created = create_project_from_prd(
        config=config,
        prd=prd,
        project_name=project_name or brief.title,
        project_path=project_path,
        priority=priority,
        launch=False,
        task_source=effective_brief.task_source.model_dump(),
    )
    brief_path = persist_execution_brief(created.path, effective_brief)
    attach_execution_brief_metadata(config, project_id=created.project_id, brief=effective_brief)

    launched = False
    log_path: Path | None = None
    message = created.message
    if launch:
        from autopilot.core.project_store import launch_project_run

        launched, log_path, message = launch_project_run(
            config,
            created.project_id,
            launch_profile=launch_profile,
        )

    return IngestedExecutionProject(
        created=created,
        prd=prd,
        brief_path=brief_path,
        launched=launched,
        message=message,
        log_path=log_path,
        launch_profile=launch_profile,
    )
