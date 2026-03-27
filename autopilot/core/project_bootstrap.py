"""Project creation and launch helpers for the dashboard."""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from autopilot.core.config import AutopilotConfig
from autopilot.core.loop_runner import check_ralph_installed


@dataclass
class CreatedProject:
    name: str
    path: Path
    prd_path: Path
    launched: bool
    message: str
    log_path: Path | None = None


def slugify_project_name(name: str) -> str:
    """Convert a project name into a safe filesystem slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def normalize_prd(prd: dict) -> dict:
    """Ensure the PRD has a stable shape and sequential story ids."""
    title = str(prd.get("title") or "Untitled Project").strip()
    description = str(prd.get("description") or "").strip()
    stories = prd.get("stories") or []

    normalized_stories: list[dict] = []
    for index, story in enumerate(stories, start=1):
        normalized_stories.append(
            {
                "id": story.get("id", index),
                "title": str(story.get("title") or f"Story {index}").strip(),
                "description": str(story.get("description") or "").strip(),
                "status": story.get("status", "open"),
            }
        )

    return {
        "title": title,
        "description": description,
        "stories": normalized_stories,
    }


def _load_projects(projects_yaml: Path) -> dict:
    if not projects_yaml.exists():
        return {"projects": []}
    return yaml.safe_load(projects_yaml.read_text()) or {"projects": []}


def _unique_project_name(existing: set[str], requested_name: str) -> str:
    if requested_name not in existing:
        return requested_name

    index = 2
    while f"{requested_name} {index}" in existing:
        index += 1
    return f"{requested_name} {index}"


def _unique_project_dir(base_dir: Path) -> Path:
    if not base_dir.exists():
        return base_dir

    index = 2
    while True:
        candidate = base_dir.parent / f"{base_dir.name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def ensure_project_registered(
    projects_yaml: Path,
    name: str,
    project_path: Path,
    prd_relpath: str = ".agents/tasks/prd.json",
    priority: str = "normal",
) -> None:
    """Create or update a project entry in projects.yaml."""
    data = _load_projects(projects_yaml)
    projects = data.setdefault("projects", [])

    existing = next((project for project in projects if Path(project["path"]).resolve() == project_path.resolve()), None)
    entry = {
        "name": name,
        "path": str(project_path),
        "priority": priority,
        "prd": prd_relpath,
    }

    if existing is None:
        projects.append(entry)
    else:
        existing.update(entry)

    projects_yaml.parent.mkdir(parents=True, exist_ok=True)
    projects_yaml.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))


def create_project_from_prd(
    config: AutopilotConfig,
    prd: dict,
    project_name: str | None = None,
    project_path: str | None = None,
    priority: str = "normal",
    launch: bool = True,
) -> CreatedProject:
    """Create a new local project directory from a PRD and optionally launch it."""
    normalized_prd = normalize_prd(prd)
    projects_data = _load_projects(config.projects_yaml_path)
    existing_names = {str(project["name"]) for project in projects_data.get("projects", [])}

    requested_name = (project_name or normalized_prd["title"] or "Untitled Project").strip()
    final_name = _unique_project_name(existing_names, requested_name)

    if project_path:
        root_dir = Path(project_path).expanduser().resolve()
    else:
        base_dir = config.autopilot_home / "projects" / slugify_project_name(final_name)
        root_dir = _unique_project_dir(base_dir).resolve()

    root_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / ".agents" / "tasks").mkdir(parents=True, exist_ok=True)
    (root_dir / ".ralph").mkdir(parents=True, exist_ok=True)

    prd_path = root_dir / ".agents" / "tasks" / "prd.json"
    prd_path.write_text(json.dumps(normalized_prd, indent=2, ensure_ascii=False))

    progress_path = root_dir / ".ralph" / "progress.md"
    if not progress_path.exists():
        progress_path.write_text("# Progress\n\n")

    guardrails_path = root_dir / ".ralph" / "guardrails.md"
    if not guardrails_path.exists():
        guardrails_path.write_text("# Guardrails\n\nDo not repeat these mistakes:\n\n")

    readme_path = root_dir / "README.md"
    if not readme_path.exists():
        readme_path.write_text(f"# {final_name}\n\n{normalized_prd['description']}\n")

    if not (root_dir / ".git").exists():
        subprocess.run(["git", "init"], cwd=str(root_dir), capture_output=True, text=True)

    ensure_project_registered(
        config.projects_yaml_path,
        final_name,
        root_dir,
        prd_relpath=".agents/tasks/prd.json",
        priority=priority,
    )

    launched = False
    message = "Project created."
    log_path: Path | None = None

    if launch:
        launched, log_path, launch_message = launch_project_run(root_dir)
        message = launch_message

    return CreatedProject(
        name=final_name,
        path=root_dir,
        prd_path=prd_path,
        launched=launched,
        message=message,
        log_path=log_path,
    )


def launch_project_run(project_path: Path, prd_relpath: str = ".agents/tasks/prd.json") -> tuple[bool, Path | None, str]:
    """Run `autopilot run` in the background for a project."""
    logs_dir = Path.home() / ".autopilot" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{project_path.name}.log"

    if not check_ralph_installed():
        return False, None, "Project created, but Ralph is not installed. Install Ralph before launching."

    with log_path.open("a", encoding="utf-8") as log_file:
        init_cmd = f"{shlex.quote(sys.executable)} -m autopilot init {shlex.quote(str(project_path))}"
        run_cmd = (
            f"{shlex.quote(sys.executable)} -m autopilot run "
            f"{shlex.quote(str(project_path))} --prd {shlex.quote(prd_relpath)}"
        )
        subprocess.Popen(
            ["/bin/sh", "-lc", f"{init_cmd} && {run_cmd}"],
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    return True, log_path, "Project created and background launch started."
