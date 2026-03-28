"""Project routes for portfolio, workspace detail, and lifecycle actions."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from autopilot.api.deps import get_config
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import (
    append_guidance,
    archive_project,
    build_project_detail,
    build_project_summary,
    get_project_entry,
    launch_project_run,
    load_project_state,
    load_projects_registry,
    mark_story_skipped,
    pause_project_run,
    resume_project_run,
)

router = APIRouter()


class CreateProjectRequest(BaseModel):
    prd: dict
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"


class GuidanceRequest(BaseModel):
    payload: str


class LaunchProfileRequest(BaseModel):
    preset: str = "fast"
    story_execution_mode: str | None = None
    project_concurrency_mode: str | None = None
    max_parallel_stories: int | None = None


class LaunchRequest(BaseModel):
    launch_profile: LaunchProfileRequest | None = None


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


@router.post("/{project_id}/resume")
async def resume_project(project_id: str) -> dict[str, str | bool]:
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


@router.post("/{project_id}/archive")
async def archive_project_route(project_id: str) -> dict[str, str]:
    config = get_config()
    try:
        archived = archive_project(config, project_id)
    except KeyError as exc:
        raise HTTPException(404, f"Project {project_id} not found") from exc

    return {"status": "ok", "message": f"Archived {archived['name']}"}
