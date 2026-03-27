"""CLI command: `autopilot run <project-path>`."""

from __future__ import annotations

import json
import time
from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import load_config
from autopilot.core.orchestrator import Orchestrator, StoryOutcome

console = Console()


def load_prd_stories(project_path: Path, prd_path: str) -> list[dict]:
    """Load stories from a PRD JSON file."""
    full_path = project_path / prd_path
    if not full_path.exists():
        console.print(f"[red]PRD not found: {full_path}[/red]")
        raise typer.Exit(1)

    data = json.loads(full_path.read_text())
    return data.get("stories", [])


def find_next_open_story(stories: list[dict]) -> dict | None:
    """Return the next story with `open` status."""
    for story in stories:
        if story.get("status", "open") == "open":
            return story
    return None


def update_story_status(project_path: Path, prd_path: str, story_id: int, status: str) -> None:
    """Update the status of a story in the PRD file."""
    full_path = project_path / prd_path
    data = json.loads(full_path.read_text())
    for story in data.get("stories", []):
        if story["id"] == story_id:
            story["status"] = status
            break
    full_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="Path to PRD JSON file (relative to project)"),
) -> None:
    """Run the autopilot loop on one project until all stories are done."""
    project = Path(project_path).expanduser().resolve()
    if not project.exists():
        console.print(f"[red]Project not found: {project}[/red]")
        raise typer.Exit(1)

    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    account_mgr = AccountManager(profiles_dir=config.profiles_dir, cooldown_base=config.cooldown_base_sec)
    account_mgr.discover()

    if "codex" not in account_mgr.pools:
        console.print("[red]No Codex profiles found. Run: autopilot login codex[/red]")
        raise typer.Exit(1)

    gates_config: list[dict] = []
    project_config_path = Path.home() / ".autopilot" / "projects.yaml"
    if project_config_path.exists():
        import yaml

        projects_data = yaml.safe_load(project_config_path.read_text()) or {}
        for project_data in projects_data.get("projects", []):
            if Path(project_data["path"]).resolve() == project:
                gates_config = project_data.get("gates", [])
                break

    orchestrator = Orchestrator(
        project_path=project,
        config=config,
        profiles_dir=config.profiles_dir,
    )

    console.print(f"\n[bold]Autopilot[/bold] - running on [cyan]{project.name}[/cyan]\n")

    while True:
        stories = load_prd_stories(project, prd)
        story = find_next_open_story(stories)

        if story is None:
            console.print("[bold green]All stories complete![/bold green]")
            break

        story_id = story["id"]
        story_title = story.get("title", f"Story #{story_id}")
        story_desc = story.get("description", "")

        console.print(f"\n[bold]Story #{story_id}:[/bold] {story_title}")
        update_story_status(project, prd, story_id, "in_progress")
        orchestrator.reset_stuck()

        approved = False
        while not approved:
            worker_profile = account_mgr.get_next("codex")
            if worker_profile is None:
                console.print("[yellow]All worker accounts on cooldown. Waiting 60s...[/yellow]")
                time.sleep(60)
                continue

            worker_env = account_mgr.build_env(worker_profile)

            critic_profile = account_mgr.get_next("codex")
            if critic_profile is None:
                critic_profile = worker_profile
            critic_env = account_mgr.build_env(critic_profile)

            outcome = orchestrator.run_single_iteration(
                profile=worker_profile,
                env=worker_env,
                story_id=story_id,
                story_title=story_title,
                story_description=story_desc,
                gates_config=gates_config,
                critic_profile=critic_profile,
                critic_env=critic_env,
            )

            if outcome == StoryOutcome.APPROVED:
                update_story_status(project, prd, story_id, "done")
                account_mgr.mark_success("codex", worker_profile.name)
                approved = True
            elif outcome == StoryOutcome.RATE_LIMITED:
                account_mgr.mark_rate_limited("codex", worker_profile.name)
                continue
            elif outcome in (
                StoryOutcome.GATE_FAILED,
                StoryOutcome.CRITIC_REJECTED,
                StoryOutcome.WORKER_FAILED,
            ):
                if orchestrator.check_stuck():
                    console.print(f"[red]Story #{story_id} is stuck. Skipping.[/red]")
                    update_story_status(project, prd, story_id, "stuck")
                    break
                continue
            else:
                console.print(f"[red]Unexpected outcome: {outcome}[/red]")
                break

    console.print("\n[bold]Autopilot finished.[/bold]")
