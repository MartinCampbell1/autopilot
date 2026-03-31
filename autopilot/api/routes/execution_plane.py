"""Stable execution-plane API for FounderOS and external orchestrators."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.approvals import decide_approval, get_approval, list_approvals
from autopilot.core.control_plane_issues import get_issue, list_issues, resolve_issue
from autopilot.core.execution_brief import ExecutionBrief
from autopilot.core.execution_plane import (
    apply_execution_plane_orchestrator_session_control_plan,
    apply_execution_plane_orchestrator_session_recommendation,
    apply_execution_command_approval,
    build_execution_plane_orchestrator_session_control,
    build_execution_plane_project_detail,
    create_execution_command_approval,
    create_execution_command_issue,
    execute_execution_plane_agent_action_with_run,
    execute_execution_plane_agent_actions,
    execute_execution_plane_orchestrator_session_actions,
    create_execution_plane_orchestrator_session,
    evaluate_execution_command_policy,
    execute_execution_plane_command,
    get_execution_plane_agent_detail,
    get_execution_plane_agent_action,
    get_execution_plane_agent_action_run,
    get_execution_plane_orchestrator_session,
    get_execution_plane_orchestrator_session_control_pass,
    list_execution_plane_orchestrator_session_events,
    list_execution_plane_orchestrator_session_actions,
    list_execution_plane_orchestrator_session_control_passes,
    list_execution_plane_orchestrator_session_control_profiles,
    load_project_command_policy,
    ingest_execution_brief_project,
    list_execution_plane_agent_action_policy_profiles,
    list_execution_plane_agent_actions,
    list_execution_plane_agent_action_runs,
    list_execution_plane_agents,
    list_execution_plane_events,
    list_execution_plane_orchestrator_sessions,
    list_execution_plane_projects,
    summarize_execution_plane_orchestrator_session_actions,
    summarize_execution_plane_orchestrator_session_control_passes,
    summarize_execution_plane_orchestrator_sessions,
    summarize_execution_plane_agent_action_runs,
    summarize_execution_plane_agents,
    update_execution_plane_orchestrator_session_status,
    update_project_command_policy,
)
from autopilot.core.github_reactions import ingest_story_github_reaction, sync_story_github_pr

router = APIRouter()


class LaunchProfileRequest(BaseModel):
    preset: str = "fast"
    story_execution_mode: str | None = None
    project_concurrency_mode: str | None = None
    max_parallel_stories: int | None = None
    story_pipeline: list[str] | None = None
    review_phases: list[str] | None = None


class ImportExecutionBriefRequest(BaseModel):
    brief: ExecutionBrief
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: LaunchProfileRequest | None = None


class BudgetPolicyRequest(BaseModel):
    project_max_worker_iterations: int | None = Field(default=None, ge=1)
    project_max_critic_reviews: int | None = Field(default=None, ge=1)
    agent_max_worker_iterations: int | None = Field(default=None, ge=1)
    agent_max_critic_reviews: int | None = Field(default=None, ge=1)
    auto_pause_on_exhaustion: bool | None = None


class ExecutionCommandRequest(BaseModel):
    require_approval: bool = False
    requested_by: str = "external-orchestrator"
    reason: str = ""
    launch_profile: LaunchProfileRequest | None = None
    budget_policy: BudgetPolicyRequest | None = None


class ApprovalDecisionRequest(BaseModel):
    actor: str = "human"
    note: str = ""


class AgentActionExecutionRequest(BaseModel):
    action_key: str
    orchestrator_session_id: str = ""
    idempotency_key: str = ""
    actor: str = "external-orchestrator"
    mode: str = "auto"
    reason: str = ""


class AgentActionBatchPolicyRequest(BaseModel):
    include_action_types: list[str] | None = None
    skip_paused_projects: bool | None = None
    exclude_attention_states: list[str] | None = None
    priority_at_least: str | None = None
    approval_strategy: str | None = None
    approval_priority_at_least: str | None = None
    allowed_commands: list[str] | None = None
    allowed_recommendation_kinds: list[str] | None = None
    max_actions_per_project: int | None = Field(default=None, ge=1, le=100)


class AgentActionBatchExecutionRequest(BaseModel):
    action_keys: list[str] = Field(default_factory=list)
    orchestrator_session_id: str = ""
    idempotency_key: str = ""
    actor: str = "external-orchestrator"
    mode: str = "auto"
    reason: str = ""
    policy_profile: str | None = None
    policy: AgentActionBatchPolicyRequest | None = None
    include_archived: bool = False
    project_id: str | None = None
    initiative_id: str | None = None
    orchestrator: str | None = None
    status: str | None = None
    role: str | None = None
    attention_state: str | None = None
    recommendation_kind: str | None = None
    suggested_command: str | None = None
    actionable_only: bool = True
    command_requires_approval: bool | None = None
    priority: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    continue_on_error: bool = True
    include_non_executable: bool = False


class IssueResolutionRequest(BaseModel):
    actor: str = "human"
    note: str = ""


class OrchestratorSessionCreateRequest(BaseModel):
    orchestrator: str = "founderos"
    actor: str = "external-orchestrator"
    title: str = ""
    initiative_id: str = ""
    project_ids: list[str] = Field(default_factory=list)
    reason: str = ""
    context: dict[str, object] = Field(default_factory=dict)


class OrchestratorSessionStatusRequest(BaseModel):
    status: str = "completed"
    actor: str = "external-orchestrator"
    note: str = ""


class OrchestratorSessionActionBatchRequest(BaseModel):
    action_keys: list[str] = Field(default_factory=list)
    idempotency_key: str = ""
    actor: str = "external-orchestrator"
    mode: str = "auto"
    reason: str = ""
    policy_profile: str | None = None
    policy: AgentActionBatchPolicyRequest | None = None
    include_archived: bool = False
    status: str | None = None
    role: str | None = None
    attention_state: str | None = None
    recommendation_kind: str | None = None
    suggested_command: str | None = None
    actionable_only: bool = True
    command_requires_approval: bool | None = None
    priority: str | None = None
    limit: int = Field(default=20, ge=1, le=100)
    continue_on_error: bool = True
    include_non_executable: bool = False


class OrchestratorSessionRecommendationRequest(BaseModel):
    recommendation_kind: str
    actor: str = "external-orchestrator"
    reason: str = ""
    idempotency_key: str = ""


class OrchestratorSessionControlPlanRequest(BaseModel):
    profile: str = "safe_progress"
    recommendation_kinds: list[str] = Field(default_factory=list)
    actor: str = "external-orchestrator"
    reason: str = ""
    max_operations: int = Field(default=10, ge=1, le=50)
    continue_on_error: bool = True


class CommandPolicyRequest(BaseModel):
    approval_required_commands: list[str] | None = None
    parallel_launch_requires_approval: bool | None = None
    max_parallel_stories_without_approval: int | None = Field(default=None, ge=1)
    disable_auto_pause_requires_approval: bool | None = None
    github_approved_and_green_auto_resume: bool | None = None
    project_max_worker_iterations_without_approval: int | None = Field(default=None, ge=1)
    project_max_critic_reviews_without_approval: int | None = Field(default=None, ge=1)
    agent_max_worker_iterations_without_approval: int | None = Field(default=None, ge=1)
    agent_max_critic_reviews_without_approval: int | None = Field(default=None, ge=1)


class GitHubPullRequestSyncRequest(BaseModel):
    number: int | None = Field(default=None, ge=1)
    url: str = ""
    title: str = ""
    state: str = ""
    base_branch: str | None = None
    head_branch: str | None = None
    ci_status: str = ""
    review_status: str = ""
    handoff_status: str = ""
    merge_state: str = ""
    draft: bool | None = None
    author: str = ""
    labels: list[str] = Field(default_factory=list)
    comment_count: int | None = Field(default=None, ge=0)
    review_comment_count: int | None = Field(default=None, ge=0)
    last_commit_sha: str = ""
    checks_url: str = ""
    opened_at: str | None = None
    merged_at: str | None = None
    closed_at: str | None = None
    actor: str = "github"
    orchestrator_session_id: str = ""
    agent_action_run_id: str = ""
    runtime_agent_id: str = ""


class GitHubReactionRequest(BaseModel):
    reaction_type: str
    summary: str = ""
    actor: str = "github"
    details: dict[str, object] = Field(default_factory=dict)
    orchestrator_session_id: str = ""
    agent_action_run_id: str = ""
    runtime_agent_id: str = ""


def _command_payload(request: ExecutionCommandRequest) -> dict[str, object]:
    payload: dict[str, object] = {}
    if request.launch_profile is not None:
        payload["launch_profile"] = request.launch_profile.model_dump(exclude_none=True)
    if request.budget_policy is not None:
        payload["budget_policy"] = request.budget_policy.model_dump(exclude_none=True)
    return payload


@router.get("/execution-brief/schema")
async def execution_brief_schema() -> dict:
    return ExecutionBrief.model_json_schema()


@router.get("/projects")
async def list_execution_projects(
    include_archived: bool = Query(False),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "projects": list_execution_plane_projects(
            config,
            include_archived=include_archived,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
        )
    }


@router.get("/agents")
async def list_execution_agents(
    include_archived: bool = Query(False),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    attention_state: str | None = Query(default=None),
    recommendation_kind: str | None = Query(default=None),
    suggested_command: str | None = Query(default=None),
    actionable_only: bool = Query(False),
    command_requires_approval: bool | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "agents": list_execution_plane_agents(
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
    }


@router.get("/agents/actions")
async def list_execution_agent_actions(
    include_archived: bool = Query(False),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    attention_state: str | None = Query(default=None),
    recommendation_kind: str | None = Query(default=None),
    suggested_command: str | None = Query(default=None),
    actionable_only: bool = Query(True),
    command_requires_approval: bool | None = Query(default=None),
    priority: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "actions": list_execution_plane_agent_actions(
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
    }


@router.get("/agents/actions/policy-profiles")
async def list_execution_agent_action_policy_profiles() -> dict[str, object]:
    return {"profiles": list_execution_plane_agent_action_policy_profiles()}


@router.post("/orchestrator-sessions")
async def create_execution_orchestrator_session(
    request: OrchestratorSessionCreateRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "status": "ok",
            "session": create_execution_plane_orchestrator_session(
                config,
                orchestrator=request.orchestrator,
                actor=request.actor,
                title=request.title,
                initiative_id=request.initiative_id,
                project_ids=request.project_ids,
                reason=request.reason,
                context=request.context,
            ),
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/orchestrator-sessions")
async def list_execution_orchestrator_sessions(
    session_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "sessions": list_execution_plane_orchestrator_sessions(
            config,
            session_id=session_id,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            actor=actor,
            status=status,
        )
    }


@router.get("/orchestrator-sessions/summary")
async def summarize_execution_orchestrator_sessions(
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    return summarize_execution_plane_orchestrator_sessions(
        config,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        actor=actor,
        status=status,
    )


@router.get("/orchestrator-sessions/{session_id}")
async def get_execution_orchestrator_session(
    session_id: str,
    event_limit: int = Query(100, ge=1, le=1000),
) -> dict[str, object]:
    config = get_config()
    try:
        return get_execution_plane_orchestrator_session(config, session_id, event_limit=event_limit)
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/{session_id}/events")
async def get_execution_orchestrator_session_events(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "session_id": session_id,
            "events": list_execution_plane_orchestrator_session_events(config, session_id, limit=limit),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/control/passes")
async def list_execution_orchestrator_session_control_passes(
    orchestrator_session_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    profile: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    return {
        "control_passes": list_execution_plane_orchestrator_session_control_passes(
            config,
            orchestrator_session_id=orchestrator_session_id,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            actor=actor,
            profile=profile,
            status=status,
        )
    }


@router.get("/orchestrator-sessions/control/passes/summary")
async def summarize_execution_orchestrator_session_control_passes(
    orchestrator_session_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    profile: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    return summarize_execution_plane_orchestrator_session_control_passes(
        config,
        orchestrator_session_id=orchestrator_session_id,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        actor=actor,
        profile=profile,
        status=status,
    )


@router.get("/orchestrator-sessions/control/passes/{control_pass_id}")
async def get_execution_orchestrator_session_control_pass(control_pass_id: str) -> dict[str, object]:
    config = get_config()
    try:
        return get_execution_plane_orchestrator_session_control_pass(config, control_pass_id)
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session control pass {control_pass_id} not found") from exc


@router.get("/orchestrator-sessions/{session_id}/control/passes/summary")
async def summarize_execution_orchestrator_session_control_passes_for_session(
    session_id: str,
    profile: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    try:
        get_execution_plane_orchestrator_session(config, session_id, event_limit=1)
        return {
            "session_id": session_id,
            **summarize_execution_plane_orchestrator_session_control_passes(
                config,
                orchestrator_session_id=session_id,
                profile=profile,
                status=status,
            ),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/{session_id}/control/passes")
async def list_execution_orchestrator_session_control_passes_for_session(
    session_id: str,
    profile: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    try:
        get_execution_plane_orchestrator_session(config, session_id, event_limit=1)
        return {
            "session_id": session_id,
            "control_passes": list_execution_plane_orchestrator_session_control_passes(
                config,
                orchestrator_session_id=session_id,
                profile=profile,
                status=status,
            ),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/{session_id}/actions")
async def list_execution_orchestrator_session_actions(
    session_id: str,
    include_archived: bool = Query(False),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    attention_state: str | None = Query(default=None),
    recommendation_kind: str | None = Query(default=None),
    suggested_command: str | None = Query(default=None),
    actionable_only: bool = Query(True),
    command_requires_approval: bool | None = Query(default=None),
    priority: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "session_id": session_id,
            "actions": list_execution_plane_orchestrator_session_actions(
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
            ),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/{session_id}/actions/summary")
async def summarize_execution_orchestrator_session_actions(
    session_id: str,
    include_archived: bool = Query(False),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    attention_state: str | None = Query(default=None),
    recommendation_kind: str | None = Query(default=None),
    suggested_command: str | None = Query(default=None),
    actionable_only: bool = Query(True),
    command_requires_approval: bool | None = Query(default=None),
    priority: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "session_id": session_id,
            **summarize_execution_plane_orchestrator_session_actions(
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
            ),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.post("/orchestrator-sessions/{session_id}/actions/execute")
async def execute_execution_orchestrator_session_actions(
    session_id: str,
    request: OrchestratorSessionActionBatchRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        payload = execute_execution_plane_orchestrator_session_actions(
            config,
            session_id,
            action_keys=request.action_keys,
            idempotency_key=request.idempotency_key,
            actor=request.actor,
            mode=request.mode,
            reason=request.reason,
            policy_profile=request.policy_profile,
            policy_overrides=request.policy.model_dump(exclude_none=True) if request.policy is not None else None,
            dry_run=False,
            include_archived=request.include_archived,
            status=request.status,
            role=request.role,
            attention_state=request.attention_state,
            recommendation_kind=request.recommendation_kind,
            suggested_command=request.suggested_command,
            actionable_only=request.actionable_only,
            command_requires_approval=request.command_requires_approval,
            priority=request.priority,
            limit=request.limit,
            continue_on_error=request.continue_on_error,
            include_non_executable=request.include_non_executable,
        )
        return {"session_id": session_id, **payload}
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/orchestrator-sessions/{session_id}/actions/preview")
async def preview_execution_orchestrator_session_actions(
    session_id: str,
    request: OrchestratorSessionActionBatchRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        payload = execute_execution_plane_orchestrator_session_actions(
            config,
            session_id,
            action_keys=request.action_keys,
            idempotency_key=request.idempotency_key,
            actor=request.actor,
            mode=request.mode,
            reason=request.reason,
            policy_profile=request.policy_profile,
            policy_overrides=request.policy.model_dump(exclude_none=True) if request.policy is not None else None,
            dry_run=True,
            include_archived=request.include_archived,
            status=request.status,
            role=request.role,
            attention_state=request.attention_state,
            recommendation_kind=request.recommendation_kind,
            suggested_command=request.suggested_command,
            actionable_only=request.actionable_only,
            command_requires_approval=request.command_requires_approval,
            priority=request.priority,
            limit=request.limit,
            continue_on_error=request.continue_on_error,
            include_non_executable=request.include_non_executable,
        )
        return {"session_id": session_id, **payload}
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/orchestrator-sessions/{session_id}/control")
async def get_execution_orchestrator_session_control(session_id: str) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "session_id": session_id,
            "control": build_execution_plane_orchestrator_session_control(config, session_id),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc


@router.get("/orchestrator-sessions/control/profiles")
async def list_execution_orchestrator_session_control_profiles() -> dict[str, object]:
    return {"profiles": list_execution_plane_orchestrator_session_control_profiles()}


@router.post("/orchestrator-sessions/{session_id}/control/apply")
async def apply_execution_orchestrator_session_recommendation(
    session_id: str,
    request: OrchestratorSessionRecommendationRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        return apply_execution_plane_orchestrator_session_recommendation(
            config,
            session_id,
            recommendation_kind=request.recommendation_kind,
            actor=request.actor,
            reason=request.reason,
            idempotency_key=request.idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/orchestrator-sessions/{session_id}/control/apply-plan")
async def apply_execution_orchestrator_session_control_plan(
    session_id: str,
    request: OrchestratorSessionControlPlanRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        return apply_execution_plane_orchestrator_session_control_plan(
            config,
            session_id,
            actor=request.actor,
            reason=request.reason,
            profile=request.profile,
            recommendation_kinds=request.recommendation_kinds,
            max_operations=request.max_operations,
            continue_on_error=request.continue_on_error,
        )
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/orchestrator-sessions/{session_id}/status")
async def update_execution_orchestrator_session(
    session_id: str,
    request: OrchestratorSessionStatusRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "status": "ok",
            "session": update_execution_plane_orchestrator_session_status(
                config,
                session_id=session_id,
                status=request.status,
                actor=request.actor,
                note=request.note,
            ),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Orchestrator session {session_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/agents/action-runs")
async def list_execution_agent_action_runs(
    run_kind: str | None = Query(default=None),
    orchestrator_session_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    status: str | None = Query(default=None),
    idempotency_key: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "runs": list_execution_plane_agent_action_runs(
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
    }


@router.get("/agents/action-runs/summary")
async def summarize_execution_agent_action_runs(
    run_kind: str | None = Query(default=None),
    orchestrator_session_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    actor: str | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    status: str | None = Query(default=None),
    idempotency_key: str | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    return summarize_execution_plane_agent_action_runs(
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


@router.get("/agents/action-runs/{run_id}")
async def get_execution_agent_action_run(run_id: str) -> dict[str, object]:
    config = get_config()
    try:
        return get_execution_plane_agent_action_run(config, run_id)
    except KeyError as exc:
        raise HTTPException(404, f"Runtime agent action run {run_id} not found") from exc


@router.get("/agents/actions/{action_key:path}")
async def get_execution_agent_action(action_key: str) -> dict[str, object]:
    config = get_config()
    try:
        return get_execution_plane_agent_action(config, action_key)
    except KeyError as exc:
        raise HTTPException(404, f"Runtime agent action {action_key} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/agents/actions/execute")
async def execute_execution_agent_action(request: AgentActionExecutionRequest) -> dict[str, object]:
    config = get_config()
    try:
        return execute_execution_plane_agent_action_with_run(
            config,
            action_key=request.action_key,
            orchestrator_session_id=request.orchestrator_session_id,
            idempotency_key=request.idempotency_key,
            actor=request.actor,
            mode=request.mode,
            reason=request.reason,
        )
    except KeyError as exc:
        raise HTTPException(404, f"Runtime agent action {request.action_key} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/agents/actions/execute-batch")
async def execute_execution_agent_actions_batch(request: AgentActionBatchExecutionRequest) -> dict[str, object]:
    config = get_config()
    try:
        return execute_execution_plane_agent_actions(
            config,
            action_keys=request.action_keys,
            orchestrator_session_id=request.orchestrator_session_id,
            idempotency_key=request.idempotency_key,
            actor=request.actor,
            mode=request.mode,
            reason=request.reason,
            policy_profile=request.policy_profile,
            policy_overrides=request.policy.model_dump(exclude_none=True) if request.policy is not None else None,
            dry_run=False,
            include_archived=request.include_archived,
            project_id=request.project_id,
            initiative_id=request.initiative_id,
            orchestrator=request.orchestrator,
            status=request.status,
            role=request.role,
            attention_state=request.attention_state,
            recommendation_kind=request.recommendation_kind,
            suggested_command=request.suggested_command,
            actionable_only=request.actionable_only,
            command_requires_approval=request.command_requires_approval,
            priority=request.priority,
            limit=request.limit,
            continue_on_error=request.continue_on_error,
            include_non_executable=request.include_non_executable,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/agents/actions/preview-batch")
async def preview_execution_agent_actions_batch(request: AgentActionBatchExecutionRequest) -> dict[str, object]:
    config = get_config()
    try:
        return execute_execution_plane_agent_actions(
            config,
            action_keys=request.action_keys,
            orchestrator_session_id=request.orchestrator_session_id,
            idempotency_key=request.idempotency_key,
            actor=request.actor,
            mode=request.mode,
            reason=request.reason,
            policy_profile=request.policy_profile,
            policy_overrides=request.policy.model_dump(exclude_none=True) if request.policy is not None else None,
            dry_run=True,
            include_archived=request.include_archived,
            project_id=request.project_id,
            initiative_id=request.initiative_id,
            orchestrator=request.orchestrator,
            status=request.status,
            role=request.role,
            attention_state=request.attention_state,
            recommendation_kind=request.recommendation_kind,
            suggested_command=request.suggested_command,
            actionable_only=request.actionable_only,
            command_requires_approval=request.command_requires_approval,
            priority=request.priority,
            limit=request.limit,
            continue_on_error=request.continue_on_error,
            include_non_executable=request.include_non_executable,
        )
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/agents/summary")
async def summarize_execution_agents(
    include_archived: bool = Query(False),
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    status: str | None = Query(default=None),
    role: str | None = Query(default=None),
    attention_state: str | None = Query(default=None),
    recommendation_kind: str | None = Query(default=None),
    suggested_command: str | None = Query(default=None),
    actionable_only: bool = Query(False),
    command_requires_approval: bool | None = Query(default=None),
) -> dict[str, object]:
    config = get_config()
    return summarize_execution_plane_agents(
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


@router.get("/agents/{runtime_agent_id}")
async def get_execution_agent(
    runtime_agent_id: str,
    event_limit: int = Query(100, ge=1, le=1000),
) -> dict[str, object]:
    config = get_config()
    try:
        return get_execution_plane_agent_detail(config, runtime_agent_id, event_limit=event_limit)
    except KeyError as exc:
        raise HTTPException(404, f"Runtime agent {runtime_agent_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}")
async def get_execution_project(project_id: str) -> dict:
    config = get_config()
    try:
        return build_execution_plane_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc


@router.get("/projects/{project_id}/agents")
async def list_execution_project_agents(project_id: str) -> dict[str, object]:
    config = get_config()
    try:
        detail = build_execution_plane_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc
    return {
        "project_id": project_id,
        "runtime_agent_count": detail.get("runtime_agent_count", 0),
        "agents": detail.get("runtime_agents") or [],
    }


@router.get("/projects/{project_id}/issues")
async def list_execution_project_issues(
    project_id: str,
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    runtime_agent_id: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    issues = list_issues(
        config,
        project_id=project_id,
        status=status,
        category=category,
        runtime_agent_id=runtime_agent_id,
    )
    return {"issues": [issue.model_dump() for issue in issues]}


@router.get("/projects/{project_id}/command-policy")
async def get_execution_project_command_policy(project_id: str) -> dict[str, object]:
    config = get_config()
    try:
        return {
            "project_id": project_id,
            "command_policy": load_project_command_policy(config, project_id),
        }
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc


@router.patch("/projects/{project_id}/command-policy")
async def patch_execution_project_command_policy(
    project_id: str,
    request: CommandPolicyRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        policy = update_project_command_policy(config, project_id, **request.model_dump())
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc
    return {
        "status": "ok",
        "project_id": project_id,
        "command_policy": policy,
    }


@router.post("/projects/{project_id}/stories/{story_id}/github-pr")
async def sync_execution_project_story_github_pr(
    project_id: str,
    story_id: int,
    request: GitHubPullRequestSyncRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        github_pr = sync_story_github_pr(
            config,
            project_id=project_id,
            story_id=story_id,
            payload=request.model_dump(
                exclude={"actor", "orchestrator_session_id", "agent_action_run_id", "runtime_agent_id"},
                exclude_none=True,
            ),
            actor=request.actor,
            orchestrator_session_id=request.orchestrator_session_id,
            agent_action_run_id=request.agent_action_run_id,
            runtime_agent_id=request.runtime_agent_id,
            emit_event_record=True,
        )
        project = build_execution_plane_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project/story not found for {project_id}:{story_id}") from exc
    return {
        "status": "ok",
        "project_id": project_id,
        "story_id": story_id,
        "github_pr": github_pr,
        "project": project,
    }


@router.post("/projects/{project_id}/stories/{story_id}/github-reactions")
async def ingest_execution_project_story_github_reaction(
    project_id: str,
    story_id: int,
    request: GitHubReactionRequest,
) -> dict[str, object]:
    config = get_config()
    try:
        payload = ingest_story_github_reaction(
            config,
            project_id=project_id,
            story_id=story_id,
            reaction_type=request.reaction_type,
            summary=request.summary,
            actor=request.actor,
            details=request.details,
            orchestrator_session_id=request.orchestrator_session_id,
            agent_action_run_id=request.agent_action_run_id,
            runtime_agent_id=request.runtime_agent_id,
        )
        payload["project"] = build_execution_plane_project_detail(config, project_id)
        return payload
    except KeyError as exc:
        raise HTTPException(404, f"Project/story not found for {project_id}:{story_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/projects/{project_id}/approvals")
async def list_execution_project_approvals(
    project_id: str,
    status: str | None = Query(default=None),
    action: str | None = Query(default=None),
    runtime_agent_id: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    approvals = list_approvals(
        config,
        project_id=project_id,
        status=status,
        action=action,
        runtime_agent_id=runtime_agent_id,
    )
    return {"approvals": [approval.model_dump() for approval in approvals]}


@router.get("/projects/{project_id}/events")
async def get_execution_project_events(
    project_id: str,
    runtime_agent_id: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "events": list_execution_plane_events(
            config,
            project_id=project_id,
            runtime_agent_id=runtime_agent_id,
            limit=limit,
        )
    }


@router.get("/events")
async def get_execution_events(
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    runtime_agent_id: str | None = Query(default=None),
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, list[dict]]:
    config = get_config()
    return {
        "events": list_execution_plane_events(
            config,
            project_id=project_id,
            initiative_id=initiative_id,
            orchestrator=orchestrator,
            runtime_agent_id=runtime_agent_id,
            limit=limit,
        )
    }


@router.get("/issues")
async def get_execution_issues(
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    runtime_agent_id: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    issues = list_issues(
        config,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        status=status,
        category=category,
        runtime_agent_id=runtime_agent_id,
    )
    return {"issues": [issue.model_dump() for issue in issues]}


@router.get("/issues/{issue_id}")
async def get_execution_issue(issue_id: str) -> dict:
    config = get_config()
    issue = get_issue(config, issue_id)
    if issue is None:
        raise HTTPException(404, f"Issue {issue_id} not found")
    return issue.model_dump()


@router.post("/issues/{issue_id}/resolve")
async def resolve_execution_issue(issue_id: str, request: IssueResolutionRequest | None = None) -> dict[str, object]:
    config = get_config()
    payload = request or IssueResolutionRequest()
    try:
        issue = resolve_issue(config, issue_id, actor=payload.actor, note=payload.note)
    except KeyError as exc:
        raise HTTPException(404, f"Issue {issue_id} not found") from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "ok", "issue": issue.model_dump()}


@router.get("/approvals")
async def get_execution_approvals(
    project_id: str | None = Query(default=None),
    initiative_id: str | None = Query(default=None),
    orchestrator: str | None = Query(default=None),
    status: str | None = Query(default=None),
    action: str | None = Query(default=None),
    runtime_agent_id: str | None = Query(default=None),
) -> dict[str, list[dict]]:
    config = get_config()
    approvals = list_approvals(
        config,
        project_id=project_id,
        initiative_id=initiative_id,
        orchestrator=orchestrator,
        status=status,
        action=action,
        runtime_agent_id=runtime_agent_id,
    )
    return {"approvals": [approval.model_dump() for approval in approvals]}


@router.get("/approvals/{approval_id}")
async def get_execution_approval(approval_id: str) -> dict:
    config = get_config()
    approval = get_approval(config, approval_id)
    if approval is None:
        raise HTTPException(404, f"Approval {approval_id} not found")
    return approval.model_dump()


@router.post("/approvals/{approval_id}/approve")
async def approve_execution_approval(approval_id: str, request: ApprovalDecisionRequest | None = None) -> dict[str, object]:
    config = get_config()
    payload = request or ApprovalDecisionRequest()
    try:
        approval = decide_approval(config, approval_id, decision="approved", actor=payload.actor, note=payload.note)
    except KeyError as exc:
        raise HTTPException(404, f"Approval {approval_id} not found") from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "ok", "approval": approval.model_dump()}


@router.post("/approvals/{approval_id}/reject")
async def reject_execution_approval(approval_id: str, request: ApprovalDecisionRequest | None = None) -> dict[str, object]:
    config = get_config()
    payload = request or ApprovalDecisionRequest()
    try:
        approval = decide_approval(config, approval_id, decision="rejected", actor=payload.actor, note=payload.note)
    except KeyError as exc:
        raise HTTPException(404, f"Approval {approval_id} not found") from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"status": "ok", "approval": approval.model_dump()}


@router.post("/approvals/{approval_id}/apply")
async def apply_execution_approval(approval_id: str, request: ApprovalDecisionRequest | None = None) -> dict[str, object]:
    config = get_config()
    payload = request or ApprovalDecisionRequest(actor="control-plane")
    try:
        return apply_execution_command_approval(config, approval_id=approval_id, actor=payload.actor)
    except KeyError as exc:
        raise HTTPException(404, f"Approval {approval_id} not found") from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/projects/from-brief")
async def create_execution_project_from_brief(request: ImportExecutionBriefRequest) -> dict[str, object]:
    config = get_config()
    manager = get_account_manager()
    try:
        ingested = ingest_execution_brief_project(
            config,
            manager,
            brief=request.brief,
            project_name=request.project_name,
            project_path=request.project_path,
            priority=request.priority,
            launch=request.launch,
            launch_profile=request.launch_profile.model_dump() if request.launch_profile else None,
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "status": "ok" if (not request.launch or ingested.launched) else "error",
        "project": build_execution_plane_project_detail(config, ingested.created.project_id),
        "prd": ingested.prd,
        "launched": ingested.launched,
        "message": ingested.message,
        "log_path": str(ingested.log_path) if ingested.log_path else "",
    }


@router.post("/projects/{project_id}/commands/{command_name}")
async def execute_project_command(
    project_id: str,
    command_name: str,
    request: ExecutionCommandRequest | None = None,
) -> dict[str, object]:
    config = get_config()
    payload = request or ExecutionCommandRequest()
    command_payload = _command_payload(payload)
    try:
        policy = evaluate_execution_command_policy(
            config,
            project_id=project_id,
            command=command_name,
            payload=command_payload,
        )
        requires_approval = payload.require_approval or policy["requires_approval"]
        if requires_approval:
            issue = create_execution_command_issue(
                config,
                project_id=project_id,
                command=command_name,
                requested_by=payload.requested_by,
                reason=payload.reason,
                policy_reasons=policy["reasons"],
            )
            approval = create_execution_command_approval(
                config,
                project_id=project_id,
                command=command_name,
                payload=command_payload,
                requested_by=payload.requested_by,
                reason=payload.reason,
                issue_id=issue["id"],
                policy_reasons=policy["reasons"],
            )
            issue["approval_id"] = approval["id"]
            return {
                "status": "pending_approval",
                "approval": approval,
                "issue": issue,
                "policy_triggered": policy["requires_approval"],
                "policy_reasons": policy["reasons"],
                "project": build_execution_plane_project_detail(config, project_id),
            }
        return execute_execution_plane_command(
            config,
            project_id=project_id,
            command=command_name,
            payload=command_payload,
        )
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
