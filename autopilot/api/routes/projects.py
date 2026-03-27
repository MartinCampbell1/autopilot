"""Project routes for listing projects, stories, and story actions."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot.api.deps import get_config
from autopilot.core.project_bootstrap import create_project_from_prd

router = APIRouter()


class StoryAction(BaseModel):
    action: str
    payload: str = ""


class CreateProjectRequest(BaseModel):
    prd: dict
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = True


@router.get("/")
async def list_projects() -> dict[str, list[dict]]:
    config = get_config()
    projects_path = config.projects_yaml_path
    if not projects_path.exists():
        return {"projects": []}

    data = yaml.safe_load(projects_path.read_text()) or {}
    projects: list[dict] = []

    for project in data.get("projects", []):
        prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
        stories: list[dict] = []
        if prd_path.exists():
            try:
                prd_data = json.loads(prd_path.read_text())
                stories = prd_data.get("stories", [])
            except Exception:
                pass

        projects.append(
            {
                "name": project["name"],
                "path": project["path"],
                "priority": project.get("priority", "normal"),
                "stories": stories,
                "stories_done": sum(1 for story in stories if story.get("status") == "done"),
                "stories_total": len(stories),
            }
        )

    return {"projects": projects}


@router.get("/{project_name}")
async def get_project(project_name: str) -> dict:
    config = get_config()
    projects_path = config.projects_yaml_path
    if not projects_path.exists():
        raise HTTPException(404, "No projects configured")

    data = yaml.safe_load(projects_path.read_text()) or {}
    for project in data.get("projects", []):
        if project["name"] == project_name:
            prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
            stories: list[dict] = []
            if prd_path.exists():
                prd_data = json.loads(prd_path.read_text())
                stories = prd_data.get("stories", [])

            ralph_dir = Path(project["path"]) / ".ralph"
            progress = (ralph_dir / "progress.md").read_text() if (ralph_dir / "progress.md").exists() else ""
            guardrails = (
                (ralph_dir / "guardrails.md").read_text() if (ralph_dir / "guardrails.md").exists() else ""
            )

            return {
                **project,
                "stories": stories,
                "progress": progress,
                "guardrails": guardrails,
            }

    raise HTTPException(404, f"Project {project_name} not found")


@router.post("/{project_name}/stories/{story_id}/action")
async def story_action(project_name: str, story_id: int, action: StoryAction) -> dict[str, str]:
    config = get_config()
    projects_path = config.projects_yaml_path
    data = yaml.safe_load(projects_path.read_text()) or {}

    for project in data.get("projects", []):
        if project["name"] != project_name:
            continue

        if action.action == "add_guidance":
            ralph_dir = Path(project["path"]) / ".ralph"
            ralph_dir.mkdir(exist_ok=True)
            guardrails = ralph_dir / "guardrails.md"
            existing = guardrails.read_text() if guardrails.exists() else ""
            guardrails.write_text(f"{existing}\n- [HUMAN]: {action.payload}\n")
            return {"status": "ok", "message": "Guidance added to guardrails.md"}

        if action.action == "skip":
            prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
            prd_data = json.loads(prd_path.read_text())
            for story in prd_data["stories"]:
                if story["id"] == story_id:
                    story["status"] = "skipped"
            prd_path.write_text(json.dumps(prd_data, indent=2, ensure_ascii=False))
            return {"status": "ok", "message": f"Story #{story_id} skipped"}

    raise HTTPException(404, "Project or story not found")


@router.post("/create")
async def create_project(request: CreateProjectRequest) -> dict[str, str | bool]:
    config = get_config()
    created = create_project_from_prd(
        config=config,
        prd=request.prd,
        project_name=request.project_name,
        project_path=request.project_path,
        priority=request.priority,
        launch=request.launch,
    )

    return {
        "status": "ok",
        "project_name": created.name,
        "project_path": str(created.path),
        "prd_path": str(created.prd_path),
        "launched": created.launched,
        "message": created.message,
        "log_path": str(created.log_path) if created.log_path else "",
    }
