"""CLI command: `autopilot run <project-path>`."""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import load_config
from autopilot.core.orchestrator import Orchestrator, StoryOutcome
from autopilot.core.project_store import (
    emit_project_event,
    ensure_project_state,
    get_project_entry,
    load_project_prd,
    load_projects_registry,
    load_project_state,
    register_project,
    save_project_state,
    update_project_runtime,
    update_story_runtime,
)

console = Console()


def _load_or_register_project(config, project_path: Path, project_id: str | None, prd_path: str) -> dict:
    project_entry = get_project_entry(
        config,
        project_id=project_id,
        project_path=project_path,
        include_archived=True,
    )
    if project_entry is not None:
        return project_entry

    prd_data = load_project_prd(
        {
            "name": project_path.name,
            "path": str(project_path),
            "prd": prd_path,
        },
        seed_mode="migrate",
    )
    return register_project(
        config,
        name=prd_data.get("title") or project_path.name,
        project_path=project_path,
        prd_relpath=prd_path,
    )


def _story_definitions(project_entry: dict) -> list[dict]:
    return load_project_prd(project_entry, seed_mode="migrate").get("stories", [])


def _next_open_story(project_entry: dict, state: dict) -> dict | None:
    current_story_id = state.get("current_story_id")
    if current_story_id is not None:
        current_runtime = state.get("story_state", {}).get(str(current_story_id), {})
        if current_runtime.get("status") == "in_progress":
            return next(
                (story for story in _story_definitions(project_entry) if story["id"] == current_story_id),
                None,
            )

    story_state = state.get("story_state", {})
    for story in _story_definitions(project_entry):
        runtime = story_state.get(str(story["id"]), {})
        if runtime.get("status", "open") == "open":
            return story
    return None


def _iteration_message(outcome: StoryOutcome, orchestrator: Orchestrator) -> str:
    last_record = orchestrator.iteration_history[-1] if orchestrator.iteration_history else None
    if outcome == StoryOutcome.CRITIC_REJECTED and last_record:
        return last_record.critic_feedback or "Critic requested changes."
    if outcome == StoryOutcome.GATE_FAILED and last_record:
        return last_record.critic_feedback or "Quality gates failed."
    if outcome == StoryOutcome.WORKER_FAILED:
        return "Worker iteration failed."
    return "Iteration completed."


def _mark_run_finished(config, project_id: str, *, failed: bool, message: str) -> None:
    state = load_project_state(config, project_id)
    state.update(
        {
            "pid": None,
            "paused": False,
            "active_worker": None,
            "active_critic": None,
            "current_story_id": None,
            "current_iteration": 0,
            "status": "failed" if failed else "completed",
            "finished_at": state.get("finished_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    )
    save_project_state(config, project_id, state)
    emit_project_event(
        config,
        project_id,
        event="run_failed" if failed else "run_finished",
        status="failed" if failed else "completed",
        message=message,
    )


def run(
    project_path: str = typer.Argument(help="Path to the project directory"),
    prd: str = typer.Option(".agents/tasks/prd.json", help="Path to PRD JSON file (relative to project)"),
    project_id: str | None = typer.Option(None, help="Stable project id from the dashboard"),
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

    project_entry = _load_or_register_project(config, project, project_id, prd)
    project_id = project_entry["id"]
    state = ensure_project_state(config, project_entry, seed_mode="migrate")
    if not state.get("pid"):
        update_project_runtime(
            config,
            project_id,
            pid=None,
            status="running",
            paused=False,
            finished_at=None,
            started_at=state.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        emit_project_event(
            config,
            project_id,
            event="run_started",
            status="running",
            message="Run started from CLI.",
        )
    else:
        update_project_runtime(config, project_id, status="running", paused=False, finished_at=None)

    gates_config: list[dict] = []
    projects = load_projects_registry(config, include_archived=True)
    for project_data in projects:
        if project_data["id"] == project_id:
            gates_config = project_data.get("gates", [])
            break

    orchestrator = Orchestrator(
        project_path=project,
        config=config,
        profiles_dir=config.profiles_dir,
    )

    console.print(f"\n[bold]Autopilot[/bold] - running on [cyan]{project.name}[/cyan]\n")

    try:
        while True:
            state = ensure_project_state(config, project_entry, seed_mode="migrate")
            story = _next_open_story(project_entry, state)

            if story is None:
                stories = state.get("story_state", {}).values()
                has_stuck = any(story_state.get("status") == "stuck" for story_state in stories)
                console.print("[bold green]All stories complete![/bold green]")
                _mark_run_finished(
                    config,
                    project_id,
                    failed=has_stuck,
                    message="Run finished with stuck stories." if has_stuck else "All stories completed.",
                )
                break

            story_id = story["id"]
            story_title = story.get("title", f"Story #{story_id}")
            story_desc = story.get("description", "")
            story_runtime = state["story_state"][str(story_id)]
            resuming_story = story_runtime.get("status") == "in_progress"

            console.print(f"\n[bold]Story #{story_id}:[/bold] {story_title}")
            update_story_runtime(
                config,
                project_id,
                story_id,
                status="in_progress",
                started_at=story_runtime.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                completed_at=None,
                last_error=None,
            )
            update_project_runtime(
                config,
                project_id,
                status="running",
                paused=False,
                current_story_id=story_id,
                current_iteration=story_runtime.get("iteration", 0) if resuming_story else 0,
                active_worker=None,
                active_critic=None,
                last_error=None,
            )
            if not resuming_story:
                emit_project_event(
                    config,
                    project_id,
                    event="story_started",
                    status="in_progress",
                    message=story_title,
                    story_id=story_id,
                )
            orchestrator.reset_stuck()

            approved = False
            while not approved:
                current_state = load_project_state(config, project_id)
                iteration = int(current_state.get("current_iteration", 0)) + 1

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

                update_story_runtime(
                    config,
                    project_id,
                    story_id,
                    iteration=iteration,
                    agent=f"{worker_profile.provider}/{worker_profile.name}",
                    critic=f"{critic_profile.provider}/{critic_profile.name}",
                )
                update_project_runtime(
                    config,
                    project_id,
                    current_iteration=iteration,
                    active_worker=f"{worker_profile.provider}/{worker_profile.name}",
                    active_critic=f"{critic_profile.provider}/{critic_profile.name}",
                )
                emit_project_event(
                    config,
                    project_id,
                    event="iteration_started",
                    status="in_progress",
                    message=f"Iteration {iteration} started.",
                    story_id=story_id,
                    extra={
                        "iteration": iteration,
                        "worker": f"{worker_profile.provider}/{worker_profile.name}",
                        "critic": f"{critic_profile.provider}/{critic_profile.name}",
                    },
                )

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
                    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    update_story_runtime(
                        config,
                        project_id,
                        story_id,
                        status="done",
                        completed_at=timestamp,
                    )
                    update_project_runtime(
                        config,
                        project_id,
                        current_story_id=None,
                        current_iteration=0,
                        active_worker=None,
                        active_critic=None,
                    )
                    emit_project_event(
                        config,
                        project_id,
                        event="story_done",
                        status="done",
                        message=story_title,
                        story_id=story_id,
                    )
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
                    message = _iteration_message(outcome, orchestrator)
                    emit_project_event(
                        config,
                        project_id,
                        event="critic_rejected" if outcome == StoryOutcome.CRITIC_REJECTED else "worker_failed",
                        status="error",
                        message=message,
                        story_id=story_id,
                    )
                    update_project_runtime(config, project_id, last_error=message)
                    update_story_runtime(config, project_id, story_id, last_error=message)
                    if orchestrator.check_stuck():
                        stuck_message = orchestrator.stuck_detector.summary()
                        console.print(f"[red]Story #{story_id} is stuck. Skipping.[/red]")
                        update_story_runtime(
                            config,
                            project_id,
                            story_id,
                            status="stuck",
                            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            last_error=stuck_message,
                        )
                        update_project_runtime(
                            config,
                            project_id,
                            current_story_id=None,
                            current_iteration=0,
                            active_worker=None,
                            active_critic=None,
                            last_error=stuck_message,
                        )
                        emit_project_event(
                            config,
                            project_id,
                            event="story_stuck",
                            status="stuck",
                            message=stuck_message,
                            story_id=story_id,
                        )
                        break
                    continue
                else:
                    message = f"Unexpected outcome: {outcome}"
                    console.print(f"[red]{message}[/red]")
                    update_project_runtime(config, project_id, status="failed", last_error=message)
                    emit_project_event(
                        config,
                        project_id,
                        event="run_failed",
                        status="failed",
                        message=message,
                        story_id=story_id,
                    )
                    break
    except Exception as exc:  # pragma: no cover - defensive top-level sync
        update_project_runtime(config, project_id, status="failed", last_error=str(exc), pid=None)
        emit_project_event(
            config,
            project_id,
            event="run_failed",
            status="failed",
            message=str(exc),
        )
        raise

    console.print("\n[bold]Autopilot finished.[/bold]")


def run_all() -> None:
    """Run autopilot on all configured projects in parallel."""
    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    projects = load_projects_registry(config, include_archived=False)

    if not projects:
        console.print("[red]No projects configured in projects.yaml[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Autopilot[/bold] - running {len(projects)} projects in parallel\n")

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(projects)) as executor:
        futures: dict[concurrent.futures.Future[None], str] = {}
        for project in projects:
            future = executor.submit(run, project["path"], project.get("prd", ".agents/tasks/prd.json"), project["id"])
            futures[future] = project["name"]

        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                future.result()
                console.print(f"[green]{name}: complete[/green]")
            except Exception as exc:
                console.print(f"[red]{name}: error - {exc}[/red]")
