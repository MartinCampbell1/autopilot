"""Project creation helpers for the dashboard."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import (
    ensure_project_state,
    emit_project_event,
    launch_project_run,
    normalize_prd,
    register_project,
    save_project_prd,
    slugify_project_name,
)


@dataclass
class CreatedProject:
    project_id: str
    name: str
    path: Path
    prd_path: Path
    launched: bool
    message: str
    log_path: Path | None = None


def _unique_project_dir(base_dir: Path) -> Path:
    if not base_dir.exists():
        return base_dir

    index = 2
    while True:
        candidate = base_dir.parent / f"{base_dir.name}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def create_project_from_prd(
    config: AutopilotConfig,
    prd: dict,
    project_name: str | None = None,
    project_path: str | None = None,
    priority: str = "normal",
    launch: bool = False,
) -> CreatedProject:
    """Create a new local project directory from a PRD and optionally launch it."""
    normalized_prd = normalize_prd(prd, seed_mode="new")
    final_name = (project_name or normalized_prd["title"] or "Untitled Project").strip() or "Untitled Project"

    if project_path:
        root_dir = Path(project_path).expanduser().resolve()
    else:
        base_dir = config.autopilot_home / "projects" / slugify_project_name(final_name)
        root_dir = _unique_project_dir(base_dir).resolve()

    root_dir.mkdir(parents=True, exist_ok=True)
    (root_dir / ".agents" / "tasks").mkdir(parents=True, exist_ok=True)
    (root_dir / ".ralph").mkdir(parents=True, exist_ok=True)

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

    project_entry = register_project(
        config,
        name=final_name,
        project_path=root_dir,
        prd_relpath=".agents/tasks/prd.json",
        priority=priority,
    )
    prd_path = save_project_prd(project_entry, normalized_prd)
    ensure_project_state(config, project_entry, seed_mode="new")
    emit_project_event(
        config,
        project_entry["id"],
        event="project_created",
        status="idle",
        message="Project created from PRD.",
    )

    launched = False
    message = "Project created."
    log_path: Path | None = None
    if launch:
        launched, log_path, message = launch_project_run(config, project_entry["id"])

    return CreatedProject(
        project_id=project_entry["id"],
        name=project_entry["name"],
        path=root_dir,
        prd_path=prd_path,
        launched=launched,
        message=message,
        log_path=log_path,
    )
