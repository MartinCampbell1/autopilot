"""Project routes for portfolio, workspace detail, lifecycle actions, and brief import."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.brief_metadata import raise_if_founder_approval_missing_for_project
from autopilot.core.control_messages import ControlRequestEnvelope
from autopilot.core.execution_brief import ExecutionBrief, TaskSource
from autopilot.core.execution_plane import (
    build_execution_plane_project_detail,
    ingest_execution_brief_project,
    ingest_execution_brief_v2_project,
    ingest_shared_execution_brief_project,
    sync_execution_brief_v2_project,
)
from autopilot.core.intake_sessions import link_intake_session_project
from autopilot.core.shared_contract_adapters import SHARED_EXECUTION_BRIEF_RELPATH
from autopilot.core.shared_contract_codec import load_shared_execution_brief, shared_execution_brief_json_schema
from autopilot.core.headless_event_bridge import append_event_log_message
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import (
    append_guidance,
    archive_project,
    build_project_detail,
    build_project_summary,
    ensure_project_state,
    emit_project_event,
    get_project_entry,
    launch_project_run,
    load_project_prd,
    utcnow_iso,
    load_project_state,
    load_projects_registry,
    mark_story_skipped,
    merge_project_stories,
    pause_project_run,
    resume_project_run,
    update_project_budget_policy,
)
from autopilot.core.workspace_policy import inspect_project_workspace_policy, recover_story_checkout, sweep_stale_project_checkouts

router = APIRouter()


class CreateProjectRequest(BaseModel):
    prd: dict
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    task_source: TaskSource | None = None
    intake_session_id: str | None = None


class GuidanceRequest(BaseModel):
    payload: str


class LaunchProfileRequest(BaseModel):
    preset: str = "fast"
    provider: str | None = None
    provider_config_id: str | None = None
    runtime_profile_id: str | None = None
    story_execution_mode: str | None = None
    project_concurrency_mode: str | None = None
    max_parallel_stories: int | None = None
    story_pipeline: list[str] | None = None
    review_phases: list[str] | None = None


class LaunchRequest(BaseModel):
    launch_profile: LaunchProfileRequest | None = None


class BudgetPolicyRequest(BaseModel):
    project_max_worker_iterations: int | None = Field(default=None, ge=1)
    project_max_critic_reviews: int | None = Field(default=None, ge=1)
    run_max_worker_iterations: int | None = Field(default=None, ge=1)
    run_max_critic_reviews: int | None = Field(default=None, ge=1)
    story_max_worker_iterations: int | None = Field(default=None, ge=1)
    story_max_critic_reviews: int | None = Field(default=None, ge=1)
    agent_max_worker_iterations: int | None = Field(default=None, ge=1)
    agent_max_critic_reviews: int | None = Field(default=None, ge=1)
    run_max_runtime_seconds: int | None = Field(default=None, ge=60)
    story_max_runtime_seconds: int | None = Field(default=None, ge=60)
    auto_pause_on_exhaustion: bool | None = None


class RecoverCheckoutRequest(BaseModel):
    cleanup_worktree: bool = True
    reopen_story: bool = False


class RecoverStaleCheckoutsRequest(BaseModel):
    cleanup_worktrees: bool = True
    reopen_stories: bool = True
    stale_after_sec: int = Field(default=900, ge=30)


class ProjectRuntimeControlRequest(BaseModel):
    request_id: str = ""
    request: dict[str, Any] = Field(default_factory=dict)


class ImportExecutionBriefRequest(BaseModel):
    brief: ExecutionBrief
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: LaunchProfileRequest | None = None


class ImportSharedExecutionBriefRequest(BaseModel):
    brief: dict[str, Any] = Field(default_factory=dict)
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: LaunchProfileRequest | None = None


def _build_intake_task_source(session_id: str | None) -> dict[str, str] | None:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None
    return {
        "source_kind": "intake_session",
        "external_id": normalized_session_id,
        "repo": "",
        "branch_policy": "isolated_worktree",
        "brief_ref": ".agents/tasks/prd.json",
    }


@router.get("/execution-brief/schema")
async def execution_brief_schema() -> dict:
    return ExecutionBrief.model_json_schema()


@router.get("/shared-execution-brief/schema")
async def shared_execution_brief_schema() -> dict:
    return shared_execution_brief_json_schema()


@router.post("/from-execution-brief")
async def create_project_from_execution_brief(request: ImportExecutionBriefRequest) -> dict[str, str | bool | dict]:
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
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, str(exc)) from exc

    state = load_project_state(config, ingested.created.project_id)
    return {
        "status": "ok" if (not request.launch or ingested.launched) else "error",
        "project_id": ingested.created.project_id,
        "project_name": ingested.created.name,
        "project_path": str(ingested.created.path),
        "prd_path": str(ingested.created.prd_path),
        "execution_brief_path": str(ingested.brief_path),
        "prd": ingested.prd,
        "project": build_execution_plane_project_detail(config, ingested.created.project_id),
        "launched": ingested.launched,
        "message": ingested.message,
        "log_path": str(ingested.log_path) if ingested.log_path else "",
        "launch_profile": state.get("launch_profile"),
    }


@router.post("/from-shared-execution-brief")
async def create_project_from_shared_execution_brief(
    request: ImportSharedExecutionBriefRequest,
) -> dict[str, str | bool | dict]:
    if request.launch:
        raise HTTPException(
            409,
            "Legacy shared brief launch is disabled — founder approval gate "
            "cannot be enforced on this path. Use POST /api/projects/from-brief-v2 "
            "with an approved ExecutionBriefV2 to launch execution.",
        )
    config = get_config()
    manager = get_account_manager()
    try:
        brief = load_shared_execution_brief(request.brief)
        ingested = ingest_shared_execution_brief_project(
            config,
            manager,
            brief=brief,
            project_name=request.project_name,
            project_path=request.project_path,
            priority=request.priority,
            launch=request.launch,
            launch_profile=request.launch_profile.model_dump() if request.launch_profile else None,
        )
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, str(exc)) from exc

    state = load_project_state(config, ingested.created.project_id)
    shared_brief_path = ingested.created.path / SHARED_EXECUTION_BRIEF_RELPATH
    return {
        "status": "ok" if (not request.launch or ingested.launched) else "error",
        "project_id": ingested.created.project_id,
        "project_name": ingested.created.name,
        "project_path": str(ingested.created.path),
        "prd_path": str(ingested.created.prd_path),
        "execution_brief_path": str(ingested.brief_path),
        "shared_execution_brief_path": str(shared_brief_path.resolve()),
        "brief_id": brief.brief_id,
        "idea_id": brief.idea_id,
        "prd": ingested.prd,
        "project": build_execution_plane_project_detail(config, ingested.created.project_id),
        "launched": ingested.launched,
        "message": ingested.message,
        "log_path": str(ingested.log_path) if ingested.log_path else "",
        "launch_profile": state.get("launch_profile"),
    }


class ImportBriefV2Request(BaseModel):
    """Request to ingest a canonical ExecutionBriefV2."""

    brief: dict[str, Any]
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: LaunchProfileRequest | None = None


class SyncBriefV2Request(BaseModel):
    """Request to refresh a linked project's canonical ExecutionBriefV2."""

    brief: dict[str, Any]


@router.post("/from-brief-v2")
async def create_project_from_brief_v2(request: ImportBriefV2Request):
    """Ingest a canonical ExecutionBriefV2 and create an execution project.

    This is the canonical route for Quorum → Autopilot handoff.
    Includes founder approval gate: launch blocked if brief not approved
    and approval_policy.founder_approval_required is true.
    Creates a real project, persists the V2 artifact, and optionally launches.
    """
    try:
        from founderos_contracts.brief_v2 import ExecutionBriefV2
    except ImportError:
        raise HTTPException(501, "founderos_contracts package not installed")

    try:
        brief = ExecutionBriefV2.model_validate(request.brief)
    except ValidationError as exc:
        raise HTTPException(422, f"Invalid ExecutionBriefV2 payload: {exc}") from exc

    config = get_config()
    manager = get_account_manager()
    try:
        ingested = ingest_execution_brief_v2_project(
            config,
            manager,
            brief=brief,
            project_name=request.project_name,
            project_path=request.project_path,
            priority=request.priority,
            launch=request.launch,
            launch_profile=request.launch_profile.model_dump() if request.launch_profile else None,
        )
    except ValueError as exc:
        # Approval gate raises ValueError when launch is blocked
        raise HTTPException(409, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc

    return {
        "status": "ok" if (not request.launch or ingested.launched) else "error",
        "project": build_execution_plane_project_detail(config, ingested.created.project_id),
        "prd": ingested.prd,
        "launched": ingested.launched,
        "message": ingested.message,
        "log_path": str(ingested.log_path) if ingested.log_path else "",
        "brief_id": brief.brief_id,
        "initiative_id": brief.initiative_id,
        "schema_version": brief.schema_version,
        "brief_approval_status": brief.brief_approval_status,
    }


@router.post("/briefs/{brief_id}/sync-v2")
async def sync_project_brief_v2(brief_id: str, request: SyncBriefV2Request):
    """Refresh the V2 brief artifact and metadata for an existing linked project."""

    try:
        from founderos_contracts.brief_v2 import ExecutionBriefV2
    except ImportError:
        raise HTTPException(501, "founderos_contracts package not installed")

    try:
        brief = ExecutionBriefV2.model_validate(request.brief)
    except ValidationError as exc:
        raise HTTPException(422, f"Invalid ExecutionBriefV2 payload: {exc}") from exc

    if brief.brief_id != brief_id:
        raise HTTPException(
            409,
            f"Path brief_id {brief_id} does not match body brief_id {brief.brief_id}",
        )

    config = get_config()
    try:
        project, brief_path = sync_execution_brief_v2_project(config, brief=brief)
    except KeyError as exc:
        raise HTTPException(404, f"No project linked to brief {brief_id}") from exc

    return {
        "status": "ok",
        "project": project,
        "brief_id": brief.brief_id,
        "initiative_id": brief.initiative_id,
        "schema_version": brief.schema_version,
        "brief_approval_status": brief.brief_approval_status,
        "execution_brief_path": str(brief_path),
    }


@router.get("/")
async def list_projects(include_archived: bool = Query(False)) -> dict[str, list[dict]]:
    config = get_config()
    projects = [
        build_project_summary(config, project)
        for project in load_projects_registry(config, include_archived=include_archived)
    ]
    projects.sort(
        key=lambda project: (
            project["status"] not in {"running", "paused"},
            project["last_activity_at"] or "",
            project["name"].lower(),
        ),
        reverse=True,
    )
    return {"projects": projects}


@router.get("/{project_id}")
async def get_project(project_id: str) -> dict:
    config = get_config()
    try:
        return build_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc


@router.get("/{project_id}/cost")
async def get_project_cost(project_id: str) -> dict[str, object]:
    config = get_config()
    try:
        detail = build_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc
    monitoring = dict(detail.get("monitoring") or {})
    return {
        "project_id": project_id,
        "cost_usage": detail.get("cost_usage") or {},
        "monitoring": {
            "cost": monitoring.get("cost") or {},
            "latest_run": monitoring.get("latest_run") or {},
            "benchmarks": monitoring.get("benchmarks") or {},
            "regressions": monitoring.get("regressions") or {},
        },
    }


@router.get("/{project_id}/trace")
async def get_project_trace(
    project_id: str,
    story_id: int | None = Query(default=None),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=2000),
) -> dict[str, object]:
    config = get_config()
    try:
        detail = build_project_detail(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc

    from autopilot.core.monitoring.traces import build_trace_monitor, build_trace_replay
    from autopilot.core.run_trace import read_trace_entries

    entries = read_trace_entries(config, project_id, limit=max(limit, 1))
    return {
        "project_id": project_id,
        "trace": {
            "path": detail.get("trace_path") or "",
            "summary": detail.get("trace_summary") or {},
            "monitoring": build_trace_monitor(entries),
            "replay": build_trace_replay(entries, story_id=story_id, run_id=run_id, limit=limit),
        },
    }


@router.get("/{project_id}/audit")
async def get_project_audit(
    project_id: str,
    story_id: int | None = Query(default=None),
    run_id: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=5000),
    include_entries: bool = Query(default=True),
) -> dict[str, object]:
    config = get_config()
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

    from autopilot.core.run_trace import build_trace_audit_bundle

    bundle = build_trace_audit_bundle(
        config,
        project_id,
        story_id=story_id,
        run_id=run_id,
        limit=limit,
        include_entries=include_entries,
    )
    return {"project_id": project_id, "audit": bundle}


@router.get("/{project_id}/runtime-control")
async def get_project_runtime_control(
    project_id: str,
    stale_after_sec: int = Query(900, ge=30),
) -> dict[str, object]:
    config = get_config()
    try:
        payload = inspect_project_workspace_policy(config, project_id, stale_after_sec=stale_after_sec)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")
    state = ensure_project_state(config, project, seed_mode="migrate")
    company: dict[str, Any] = {}
    try:
        from autopilot.core.bootstrap_visibility import build_bootstrap_status
        from autopilot.core.company import build_company_shell
        from autopilot.core.runtime_diagnostics import build_runtime_diagnostics

        summary = build_project_summary(config, project)
        company = build_company_shell(
            config,
            project=project,
            prd=load_project_prd(project, seed_mode="migrate"),
            stories=merge_project_stories(config, project, state),
            state=state,
            delivery_status=dict(summary.get("delivery_status") or {}),
            latest_handoff=dict(summary.get("latest_handoff") or {}),
            bootstrap=build_bootstrap_status(project_path=project["path"], project=project),
            runtime_diagnostics=build_runtime_diagnostics(
                config=config,
                config_path=config.autopilot_home / "config.yaml",
                project_path=project["path"],
            ),
            runtime_control=payload,
        )
    except Exception:
        pass
    return {
        **payload,
        "runtime_session_id": str(state.get("runtime_session_id") or ""),
        "runtime_control_available": bool(
            str(state.get("runtime_session_id") or "").strip()
            and str(state.get("status") or "") == "running"
            and not bool(state.get("paused"))
        ),
        "company": company,
    }


@router.post("/{project_id}/runtime-control/request")
async def request_project_runtime_control(
    project_id: str,
    payload: ProjectRuntimeControlRequest,
) -> dict[str, object]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

    state = ensure_project_state(config, project, seed_mode="migrate")
    runtime_session_id = str(state.get("runtime_session_id") or "").strip()
    if (
        not runtime_session_id
        or str(state.get("status") or "") != "running"
        or bool(state.get("paused"))
    ):
        raise HTTPException(409, f"Project {project_id} does not have an active runtime control session")

    request_id = str(payload.request_id or "").strip() or str(uuid.uuid4())
    try:
        request = ControlRequestEnvelope(
            type="control_request",
            request_id=request_id,
            request=payload.request,
            session_id=runtime_session_id,
        )
    except Exception as exc:
        raise HTTPException(400, f"Invalid runtime control request: {exc}") from exc

    append_event_log_message(
        config,
        {
            **request.model_dump(exclude_none=True),
            "project_id": project_id,
            "runtime_session_id": runtime_session_id,
            "timestamp": utcnow_iso(),
            "source": "projects_api",
        },
    )
    return {
        "status": "queued",
        "project_id": project_id,
        "runtime_session_id": runtime_session_id,
        "request": request.model_dump(exclude_none=True),
    }


@router.post("/")
async def create_project(request: CreateProjectRequest) -> dict[str, str | bool]:
    config = get_config()
    task_source = (
        request.task_source.model_dump()
        if request.task_source
        else _build_intake_task_source(request.intake_session_id)
    )
    created = create_project_from_prd(
        config=config,
        prd=request.prd,
        project_name=request.project_name,
        project_path=request.project_path,
        priority=request.priority,
        launch=False,
        task_source=task_source,
    )
    if request.intake_session_id:
        link_intake_session_project(
            config,
            session_id=request.intake_session_id,
            project_id=created.project_id,
            project_name=created.name,
        )
    return {
        "status": "ok",
        "project_id": created.project_id,
        "project_name": created.name,
        "project_path": str(created.path),
        "prd_path": str(created.prd_path),
        "launched": False,
        "message": created.message,
        "intake_session_id": str(request.intake_session_id or "").strip(),
    }


@router.post("/{project_id}/launch")
async def launch_project(project_id: str, request: LaunchRequest | None = None) -> dict[str, str | bool | dict]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

    try:
        raise_if_founder_approval_missing_for_project(project)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    launch_profile = request.launch_profile.model_dump() if request and request.launch_profile else None
    launched, log_path, message = launch_project_run(config, project_id, launch_profile=launch_profile)
    state = load_project_state(config, project_id)
    return {
        "status": "ok" if launched else "error",
        "project_id": project_id,
        "launched": launched,
        "message": message,
        "log_path": str(log_path) if log_path else "",
        "launch_profile": state.get("launch_profile"),
    }


@router.post("/{project_id}/pause")
async def pause_project(project_id: str) -> dict[str, str]:
    config = get_config()
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

    return {"status": "ok", "message": pause_project_run(config, project_id)}


@router.patch("/{project_id}/budget-policy")
async def patch_project_budget_policy(project_id: str, request: BudgetPolicyRequest) -> dict[str, object]:
    config = get_config()
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

    policy = update_project_budget_policy(config, project_id, **request.model_dump())
    state = load_project_state(config, project_id)
    return {
        "status": "ok",
        "project_id": project_id,
        "budget_policy": policy,
        "budget_usage": state.get("budget_usage"),
    }


@router.post("/{project_id}/resume")
async def resume_project(project_id: str) -> dict[str, str | bool | dict]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

    try:
        raise_if_founder_approval_missing_for_project(project)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc

    launched, log_path, message = resume_project_run(config, project_id)
    state = load_project_state(config, project_id)
    return {
        "status": "ok" if launched else "error",
        "project_id": project_id,
        "launched": launched,
        "message": message,
        "log_path": str(log_path) if log_path else "",
        "launch_profile": state.get("launch_profile"),
    }


@router.post("/{project_id}/stories/{story_id}/skip")
async def skip_story(project_id: str, story_id: int) -> dict[str, str]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

    state = load_project_state(config, project_id)
    if str(story_id) not in state.get("story_state", {}):
        raise HTTPException(404, f"Story {story_id} not found")

    should_resume = state.get("status") == "running" and state.get("current_story_id") == story_id
    if should_resume:
        pause_project_run(config, project_id)

    mark_story_skipped(config, project_id, story_id)

    if should_resume:
        resume_project_run(config, project_id)

    return {"status": "ok", "message": f"Story #{story_id} skipped"}


@router.post("/{project_id}/stories/{story_id}/guidance")
async def add_story_guidance(project_id: str, story_id: int, request: GuidanceRequest) -> dict[str, str]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

    state = load_project_state(config, project_id)
    if str(story_id) not in state.get("story_state", {}):
        raise HTTPException(404, f"Story {story_id} not found")

    append_guidance(config, project_id, request.payload, story_id)
    return {"status": "ok", "message": "Guidance added to guardrails.md"}


@router.post("/{project_id}/stories/{story_id}/recover-checkout")
async def recover_project_story_checkout(
    project_id: str,
    story_id: int,
    request: RecoverCheckoutRequest | None = None,
) -> dict[str, object]:
    config = get_config()
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

    try:
        result = recover_story_checkout(
            config,
            project_id,
            story_id,
            cleanup_worktree=request.cleanup_worktree if request else True,
            reopen_story=request.reopen_story if request else False,
        )
    except KeyError as exc:
        raise HTTPException(404, f"Story {story_id} not found") from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    emit_project_event(
        config,
        project_id,
        event="checkout_recovered",
        status="ok",
        message="Story checkout metadata recovered.",
        story_id=story_id,
        extra={
            "cleanup_performed": result["cleanup_performed"],
            "reopened": result["reopened"],
        },
    )

    return {
        "status": "ok",
        "project_id": project_id,
        **result,
    }


@router.post("/{project_id}/runtime-control/recover-stale")
async def recover_project_stale_checkouts(
    project_id: str,
    request: RecoverStaleCheckoutsRequest | None = None,
) -> dict[str, object]:
    config = get_config()
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

    payload = request or RecoverStaleCheckoutsRequest()
    try:
        result = sweep_stale_project_checkouts(
            config,
            project_id,
            stale_after_sec=payload.stale_after_sec,
            cleanup_worktrees=payload.cleanup_worktrees,
            reopen_stories=payload.reopen_stories,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc

    emit_project_event(
        config,
        project_id,
        event="stale_checkouts_recovered",
        status="ok",
        message="Recovered stale story checkouts.",
        extra={
            "recovered_count": len(result["recovered"]),
            "stale_after_sec": result["stale_after_sec"],
        },
    )
    return {
        "status": "ok",
        **result,
    }


@router.post("/{project_id}/archive")
async def archive_project_route(project_id: str) -> dict[str, str]:
    config = get_config()
    try:
        archived = archive_project(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc

    return {"status": "ok", "message": f"Archived {archived['name']}"}
