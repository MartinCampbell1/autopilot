"""Project routes for portfolio, workspace detail, lifecycle actions, and brief import."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.execution_brief import ExecutionBrief, TaskSource
from autopilot.core.execution_plane import build_execution_plane_project_detail, ingest_execution_brief_project
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import (
    append_guidance,
    archive_project,
    build_project_detail,
    build_project_summary,
    emit_project_event,
    get_project_entry,
    launch_project_run,
    load_project_state,
    load_projects_registry,
    mark_story_skipped,
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
    agent_max_worker_iterations: int | None = Field(default=None, ge=1)
    agent_max_critic_reviews: int | None = Field(default=None, ge=1)
    auto_pause_on_exhaustion: bool | None = None


class RecoverCheckoutRequest(BaseModel):
    cleanup_worktree: bool = True
    reopen_story: bool = False


class RecoverStaleCheckoutsRequest(BaseModel):
    cleanup_worktrees: bool = True
    reopen_stories: bool = True
    stale_after_sec: int = Field(default=900, ge=30)


class ImportExecutionBriefRequest(BaseModel):
    brief: ExecutionBrief
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False
    launch_profile: LaunchProfileRequest | None = None


@router.get("/execution-brief/schema")
async def execution_brief_schema() -> dict:
    return ExecutionBrief.model_json_schema()


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
    except ValueError as exc:
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


@router.get("/{project_id}/runtime-control")
async def get_project_runtime_control(
    project_id: str,
    stale_after_sec: int = Query(900, ge=30),
) -> dict[str, object]:
    config = get_config()
    try:
        return inspect_project_workspace_policy(config, project_id, stale_after_sec=stale_after_sec)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc


@router.post("/")
async def create_project(request: CreateProjectRequest) -> dict[str, str | bool]:
    config = get_config()
    created = create_project_from_prd(
        config=config,
        prd=request.prd,
        project_name=request.project_name,
        project_path=request.project_path,
        priority=request.priority,
        launch=False,
        task_source=request.task_source.model_dump() if request.task_source else None,
    )
    return {
        "status": "ok",
        "project_id": created.project_id,
        "project_name": created.name,
        "project_path": str(created.path),
        "prd_path": str(created.prd_path),
        "launched": False,
        "message": created.message,
    }


@router.post("/{project_id}/launch")
async def launch_project(project_id: str, request: LaunchRequest | None = None) -> dict[str, str | bool | dict]:
    config = get_config()
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise HTTPException(404, f"Project {project_id} not found")

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
    if get_project_entry(config, project_id=project_id, include_archived=True) is None:
        raise HTTPException(404, f"Project {project_id} not found")

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
