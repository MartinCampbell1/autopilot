"""CLI command: `autopilot run <project-path>`."""

from __future__ import annotations

import concurrent.futures
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.capability_store import normalize_launch_profile, resolve_story_runtime_plan
from autopilot.core.config import load_config
from autopilot.core.orchestrator import Orchestrator, StoryOutcome
from autopilot.core.loop_runner import apply_autopilot_ralph_overrides, run_prompt_iteration
from autopilot.core.project_store import (
    auto_pause_project_run,
    emit_project_event,
    ensure_project_state,
    get_project_entry,
    load_project_prd,
    load_projects_registry,
    load_project_state,
    requeue_recoverable_stuck_stories,
    register_project,
    save_project_state,
    update_project_runtime,
    update_story_runtime,
)
from autopilot.core.runtime_agents import resolve_story_runtime_agent_id
from autopilot.core.runtime_budgets import consume_iteration_budget
from autopilot.core.runtime_control import (
    RuntimeAgentRole,
    WorkItemLeaseConflict,
    claim_work_item_lease,
    refresh_work_item_lease,
    release_work_item_lease,
)
from autopilot.core.worktree import create_worktree, merge_worktree, remove_worktree, worktree_path

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


def _write_ralph_story_snapshot(project_entry: dict, story_id: int) -> str:
    prd = load_project_prd(project_entry, seed_mode="migrate")
    snapshot = {
        "title": prd.get("title", project_entry["name"]),
        "description": prd.get("description", ""),
        "phases": prd.get("phases", []),
        "stories": [],
    }
    for story in prd.get("stories", []):
        snapshot["stories"].append(
            {
                "id": story["id"],
                "title": story.get("title", f"Story {story['id']}"),
                "description": story.get("description", ""),
                "position": story.get("position", 0),
                "phase_id": story.get("phase_id"),
                "phase_title": story.get("phase_title"),
                "phase_goal": story.get("phase_goal"),
                "acceptance_criteria": story.get("acceptance_criteria", []),
                "tags": story.get("tags", []),
                "role": story.get("role"),
                "skill_packs": story.get("skill_packs", []),
                "connectors": story.get("connectors", []),
                "required_connectors": story.get("required_connectors", []),
                "preferred_connectors": story.get("preferred_connectors", []),
                "forbidden_connectors": story.get("forbidden_connectors", []),
                "status": "open" if story["id"] == story_id else "done",
            }
        )

    tmp_dir = Path(project_entry["path"]) / ".ralph" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = tmp_dir / f"autopilot-story-{story_id}.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    return str(snapshot_path)


def _write_team_context(project_path: Path, runtime_plan: dict[str, Any]) -> None:
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    context_path = ralph_dir / "team-context.json"
    context_path.write_text(json.dumps(runtime_plan, indent=2))


def _write_specialist_notes(project_path: Path, specialist_output: str) -> None:
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    notes_path = ralph_dir / "specialist-notes.md"
    notes_path.write_text(specialist_output.strip() or "No specialist notes generated.")


def _is_git_worktree_ready(project_path: Path) -> bool:
    return (project_path / ".git").exists()


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


def _serialize_gate_results(gate_results: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "name": gate_result.name,
            "cmd": gate_result.cmd,
            "passed": gate_result.passed,
            "output": gate_result.output,
            "required": gate_result.required,
            "elapsed_sec": gate_result.elapsed_sec,
        }
        for gate_result in gate_results
    ]


def _last_iteration_extra(orchestrator: Orchestrator) -> dict[str, Any]:
    if not orchestrator.iteration_history:
        return {}
    last_record = orchestrator.iteration_history[-1]
    return {
        "iteration": last_record.iteration,
        "profile_used": last_record.profile_used,
        "provider": last_record.provider,
        "gates_passed": last_record.gates_passed,
        "critic_approved": last_record.critic_approved,
        "critic_feedback": last_record.critic_feedback,
        "elapsed_sec": last_record.elapsed_sec,
        "git_diff_empty": last_record.git_diff_empty,
        "gate_failures": [
            gate
            for gate in _serialize_gate_results(last_record.gate_results)
            if not gate["passed"]
        ],
    }


def _story_agent_event_extra(
    project_id: str,
    story_id: int,
    runtime_plan: dict[str, Any],
    *,
    worker_label: str | None = None,
    critic_label: str | None = None,
    primary_role: str | None = None,
) -> dict[str, Any]:
    team_members = runtime_plan.get("team_members") or []
    worker_runtime_agent_id = resolve_story_runtime_agent_id(
        project_id,
        story_id,
        role="worker",
        team_members=team_members,
        runtime_label=worker_label,
    )
    critic_runtime_agent_id = resolve_story_runtime_agent_id(
        project_id,
        story_id,
        role="critic",
        team_members=team_members,
        runtime_label=critic_label,
    )
    specialist_runtime_agent_id = resolve_story_runtime_agent_id(
        project_id,
        story_id,
        role="specialist",
        team_members=team_members,
    )
    runtime_agent_ids = [
        agent_id
        for agent_id in (
            worker_runtime_agent_id,
            critic_runtime_agent_id,
            specialist_runtime_agent_id,
        )
        if agent_id
    ]
    extra: dict[str, Any] = {
        "runtime_agent_ids": runtime_agent_ids,
    }
    if worker_runtime_agent_id:
        extra["worker_runtime_agent_id"] = worker_runtime_agent_id
    if critic_runtime_agent_id:
        extra["critic_runtime_agent_id"] = critic_runtime_agent_id
    if specialist_runtime_agent_id:
        extra["specialist_runtime_agent_id"] = specialist_runtime_agent_id

    primary_agent_id = ""
    if primary_role == "worker":
        primary_agent_id = worker_runtime_agent_id or ""
    elif primary_role == "critic":
        primary_agent_id = critic_runtime_agent_id or ""
    elif primary_role == "specialist":
        primary_agent_id = specialist_runtime_agent_id or ""
    if primary_agent_id:
        extra["runtime_agent_id"] = primary_agent_id
    return extra


def _emit_worker_progress(
    config,
    project_id: str,
    story_id: int,
    iteration: int,
    runtime_plan: dict[str, Any],
    worker_label: str,
    critic_label: str,
    elapsed_sec: int,
    detail: str,
) -> None:
    detail = detail.strip() or "Worker is still running."
    message = f"Worker running for {elapsed_sec}s. Last Ralph activity: {detail}"
    update_project_runtime(
        config,
        project_id,
        status="running",
        paused=False,
        current_story_id=story_id,
        current_iteration=iteration,
        active_worker=worker_label,
        active_critic=critic_label,
        last_error=None,
    )
    emit_project_event(
        config,
        project_id,
        event="worker_progress",
        status="running",
        message=message,
        story_id=story_id,
        extra={
            "iteration": iteration,
            "worker": worker_label,
            "critic": critic_label,
            "elapsed_sec": elapsed_sec,
            **_story_agent_event_extra(
                project_id,
                story_id,
                runtime_plan,
                worker_label=worker_label,
                critic_label=critic_label,
                primary_role="worker",
            ),
        },
    )


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
            "parallel_story_ids": [],
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
    launch_profile = normalize_launch_profile(state.get("launch_profile"))
    state_lock = threading.Lock()
    account_lock = threading.Lock()

    if launch_profile.project_concurrency_mode == "parallel" and not _is_git_worktree_ready(project):
        launch_profile = normalize_launch_profile({"preset": "team"})
        update_project_runtime(
            config,
            project_id,
            launch_profile=launch_profile.model_dump(),
        )
        emit_project_event(
            config,
            project_id,
            event="parallel_fallback",
            status="paused",
            message="Parallel mode requested, but the repo is not git-ready. Falling back to Team mode.",
        )

    if not state.get("pid"):
        update_project_runtime(
            config,
            project_id,
            pid=None,
            status="running",
            paused=False,
            finished_at=None,
            started_at=state.get("started_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            launch_profile=launch_profile.model_dump(),
        )
        emit_project_event(
            config,
            project_id,
            event="run_started",
            status="running",
            message="Run started from CLI.",
        )
    else:
        update_project_runtime(
            config,
            project_id,
            status="running",
            paused=False,
            finished_at=None,
            launch_profile=launch_profile.model_dump(),
        )

    gates_config: list[dict] = []
    projects = load_projects_registry(config, include_archived=True)
    for project_data in projects:
        if project_data["id"] == project_id:
            gates_config = project_data.get("gates", [])
            break

    console.print(f"\n[bold]Autopilot[/bold] - running on [cyan]{project.name}[/cyan]\n")

    def sync_project(**fields: Any) -> dict[str, Any]:
        with state_lock:
            return update_project_runtime(config, project_id, **fields)

    def sync_story(story_id: int, **fields: Any) -> dict[str, Any]:
        with state_lock:
            return update_story_runtime(config, project_id, story_id, **fields)

    def sync_event(*, event: str, status: str, message: str, story_id: int | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        with state_lock:
            return emit_project_event(
                config,
                project_id,
                event=event,
                status=status,
                message=message,
                story_id=story_id,
                extra=extra,
            )

    def reserve_profiles() -> tuple[Any, Any] | None:
        with account_lock:
            worker_profile = account_mgr.get_next("codex")
            if worker_profile is None:
                return None
            critic_profile = account_mgr.get_next("codex") or worker_profile
            return worker_profile, critic_profile

    def reserve_specialist_profile() -> Any | None:
        with account_lock:
            return account_mgr.get_next("codex")

    def mark_profile_success(profile: Any) -> None:
        with account_lock:
            account_mgr.mark_success(profile.provider, profile.name)

    def mark_profile_rate_limited(profile: Any) -> None:
        with account_lock:
            account_mgr.mark_rate_limited(profile.provider, profile.name)

    def reserve_iteration_budget(story_id: int, worker_label: str, critic_label: str) -> tuple[bool, str | None]:
        with state_lock:
            state = load_project_state(config, project_id)
            allowed, reason = consume_iteration_budget(
                state,
                worker_label=worker_label,
                critic_label=critic_label,
            )
            save_project_state(config, project_id, state)
            if allowed:
                return True, None

            story_state = state.setdefault("story_state", {}).get(str(story_id))
            if story_state is not None:
                story_state["status"] = "open"
                story_state["agent"] = None
                story_state["critic"] = None
                story_state["last_error"] = reason
                save_project_state(config, project_id, state)
            return False, reason

    def register_parallel_story(story_id: int | None) -> None:
        current_state = load_project_state(config, project_id)
        active_ids = list(current_state.get("parallel_story_ids") or [])
        if story_id is not None and story_id not in active_ids:
            active_ids.append(story_id)
        sync_project(
            parallel_story_ids=active_ids,
            current_story_id=active_ids[0] if active_ids else story_id,
        )

    def unregister_parallel_story(story_id: int) -> None:
        current_state = load_project_state(config, project_id)
        active_ids = [active_story_id for active_story_id in (current_state.get("parallel_story_ids") or []) if active_story_id != story_id]
        sync_project(
            parallel_story_ids=active_ids,
            current_story_id=active_ids[0] if active_ids else None,
        )

    def run_specialist_preflight(
        execution_path: Path,
        story: dict[str, Any],
        runtime_plan: dict[str, Any],
    ) -> None:
        specialist = next(
            (member for member in runtime_plan.get("team_members", []) if member.get("execution_role") == "specialist"),
            None,
        )
        if not specialist:
            return

        specialist_profile = reserve_specialist_profile()
        if specialist_profile is None:
            sync_event(
                event="specialist_skipped",
                status="warning",
                message="No specialist account available; proceeding without specialist preflight.",
                story_id=story["id"],
                extra=_story_agent_event_extra(
                    project_id,
                    int(story["id"]),
                    runtime_plan,
                    primary_role="specialist",
                ),
            )
            return

        specialist_env = account_mgr.build_env(specialist_profile)
        prompt = (
            f"You are the {specialist['label']} for story #{story['id']}.\n\n"
            f"Story title: {story.get('title', '')}\n"
            f"Story description: {story.get('description', '')}\n"
            f"Tags: {', '.join(story.get('tags', [])) or 'none'}\n"
            f"Acceptance criteria: {json.dumps(story.get('acceptance_criteria', []), ensure_ascii=False)}\n"
            f"Planned connectors: {json.dumps(specialist.get('planned_connectors', []), ensure_ascii=False)}\n\n"
            "Do not edit files. Return only concise, actionable implementation notes for the primary worker."
        )
        success, output, rate_limited = run_prompt_iteration(
            execution_path,
            specialist_env,
            specialist_profile.provider,
            prompt,
            timeout=min(900, config.codex_timeout_sec),
            profile=specialist_profile,
        )
        if rate_limited:
            mark_profile_rate_limited(specialist_profile)
            sync_event(
                event="specialist_rate_limited",
                status="warning",
                message="Specialist preflight was rate limited; continuing without specialist notes.",
                story_id=story["id"],
                extra=_story_agent_event_extra(
                    project_id,
                    int(story["id"]),
                    runtime_plan,
                    primary_role="specialist",
                ),
            )
            return

        if success:
            mark_profile_success(specialist_profile)
            _write_specialist_notes(execution_path, output)
            sync_event(
                event="specialist_ready",
                status="ok",
                message=f"{specialist['label']} prepared implementation notes.",
                story_id=story["id"],
                extra=_story_agent_event_extra(
                    project_id,
                    int(story["id"]),
                    runtime_plan,
                    primary_role="specialist",
                ),
            )
            return

        _write_specialist_notes(execution_path, output)
        sync_event(
            event="specialist_failed",
            status="warning",
            message="Specialist preflight failed; primary worker will continue without specialist confidence.",
            story_id=story["id"],
            extra=_story_agent_event_extra(
                project_id,
                int(story["id"]),
                runtime_plan,
                primary_role="specialist",
            ),
        )

    def execute_story(story: dict[str, Any], *, parallel_slot: bool = False) -> str:
        story_id = story["id"]
        story_title = story.get("title", f"Story #{story_id}")
        story_desc = story.get("description", "")
        started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        runtime_plan = resolve_story_runtime_plan(story, launch_profile=launch_profile, provider="codex")

        execution_path = project
        branch_name: str | None = None
        lease_owner = f"run:{os.getpid()}:story:{story_id}"
        planned_checkout_path = project
        planned_checkout_mode = "shared_main"
        story_lease = None

        if parallel_slot and launch_profile.project_concurrency_mode == "parallel":
            branch_name = f"story-{story_id}"
            planned_checkout_path = worktree_path(project, story_id)
            planned_checkout_mode = "worktree"

        try:
            story_lease = claim_work_item_lease(
                config,
                project_id=project_id,
                story_id=story_id,
                role=RuntimeAgentRole.COORDINATOR,
                owner=lease_owner,
                runtime_pid=os.getpid(),
                project_path=project,
                checkout_path=planned_checkout_path,
                branch_name=branch_name,
            )
        except WorkItemLeaseConflict as exc:
            message = str(exc)
            sync_story(
                story_id,
                last_error=message,
                team_mode=runtime_plan["team_mode"],
                team_members=runtime_plan["team_members"],
                connector_activation=runtime_plan["active_connectors"],
                activation_errors=runtime_plan["activation_errors"],
                ownership={
                    "role": exc.lease.role,
                    "owner": exc.lease.owner,
                    "acquired_at": exc.lease.acquired_at,
                },
                checkout={
                    "mode": "worktree" if exc.lease.branch_name else "shared_main",
                    "path": exc.lease.checkout_path or exc.lease.project_path,
                    "branch_name": exc.lease.branch_name,
                },
            )
            sync_event(
                event="story_lease_conflict",
                status="warning",
                message=message,
                story_id=story_id,
                extra={
                    "role": exc.lease.role,
                    "owner": exc.lease.owner,
                    "checkout_path": exc.lease.checkout_path or exc.lease.project_path,
                    "project_path": exc.lease.project_path,
                    "branch_name": exc.lease.branch_name,
                    **_story_agent_event_extra(
                        project_id,
                        story_id,
                        runtime_plan,
                        primary_role="worker",
                    ),
                },
            )
            raise RuntimeError(message) from exc

        if parallel_slot and launch_profile.project_concurrency_mode == "parallel":
            try:
                execution_path = create_worktree(project, story_id)
                apply_autopilot_ralph_overrides(execution_path)
            except Exception as exc:
                sync_story(
                    story_id,
                    status="stuck",
                    completed_at=started_at,
                    last_error=f"Failed to create story worktree: {exc}",
                    team_mode=runtime_plan["team_mode"],
                    team_members=runtime_plan["team_members"],
                    connector_activation=runtime_plan["active_connectors"],
                    activation_errors=[f"Failed to create worktree: {exc}"],
                    ownership={
                        "role": story_lease.role,
                        "owner": story_lease.owner,
                        "acquired_at": story_lease.acquired_at,
                    } if story_lease is not None else None,
                    checkout={
                        "mode": planned_checkout_mode,
                        "path": str(planned_checkout_path),
                        "branch_name": branch_name,
                    },
                )
                sync_event(
                    event="story_stuck",
                    status="stuck",
                    message=f"Failed to create story worktree: {exc}",
                    story_id=story_id,
                    extra={
                        "error": str(exc),
                        "checkout_mode": planned_checkout_mode,
                        "checkout_path": str(planned_checkout_path),
                        "branch_name": branch_name,
                        **_story_agent_event_extra(
                            project_id,
                            story_id,
                            runtime_plan,
                            primary_role="worker",
                        ),
                    },
                )
                release_work_item_lease(
                    config,
                    project_id=project_id,
                    story_id=story_id,
                    owner=lease_owner,
                )
                sync_story(story_id, ownership=None, checkout=None)
                return "stuck"

        register_parallel_story(story_id if parallel_slot else None)
        sync_story(
            story_id,
            status="in_progress",
            started_at=started_at,
            completed_at=None,
            last_error=None,
            team_mode=runtime_plan["team_mode"],
            team_members=runtime_plan["team_members"],
            connector_activation=runtime_plan["active_connectors"],
            activation_errors=runtime_plan["activation_errors"],
            worktree_path=str(execution_path) if execution_path != project else None,
            branch_name=branch_name,
            ownership={
                "role": story_lease.role,
                "owner": story_lease.owner,
                "acquired_at": story_lease.acquired_at,
            } if story_lease is not None else None,
            checkout={
                "mode": planned_checkout_mode,
                "path": str(execution_path),
                "branch_name": branch_name,
            },
        )
        sync_project(
            status="running",
            paused=False,
            current_story_id=story_id if not parallel_slot else load_project_state(config, project_id).get("current_story_id"),
            current_iteration=0,
            active_worker=None,
            active_critic=None,
            last_error=None,
            activation_errors=runtime_plan["activation_errors"],
        )
        sync_event(
            event="story_started",
            status="in_progress",
            message=story_title,
            story_id=story_id,
            extra={
                "team_mode": runtime_plan["team_mode"],
                "team_members": runtime_plan["team_members"],
                "connector_activation": runtime_plan["active_connectors"],
                "activation_errors": runtime_plan["activation_errors"],
                "checkout": {
                    "mode": planned_checkout_mode,
                    "path": str(execution_path),
                    "branch_name": branch_name,
                },
                **_story_agent_event_extra(
                    project_id,
                    story_id,
                    runtime_plan,
                ),
            },
        )

        def touch_story_lease(*, status: str | None = None) -> None:
            refresh_work_item_lease(
                config,
                project_id=project_id,
                story_id=story_id,
                owner=lease_owner,
                status=status,
                checkout_path=execution_path,
                branch_name=branch_name,
            )

        _write_team_context(execution_path, runtime_plan)
        if runtime_plan["activation_errors"]:
            message = "Required connectors could not be activated: " + "; ".join(runtime_plan["activation_errors"])
            sync_story(
                story_id,
                status="stuck",
                completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                last_error=message,
                ownership=None,
                checkout=None if execution_path != project else {
                    "mode": planned_checkout_mode,
                    "path": str(execution_path),
                    "branch_name": branch_name,
                },
            )
            sync_project(last_error=message)
            sync_event(
                event="connector_activation_failed",
                status="stuck",
                message=message,
                story_id=story_id,
                extra={
                    "activation_errors": runtime_plan["activation_errors"],
                    "connector_activation": runtime_plan["active_connectors"],
                    "team_mode": runtime_plan["team_mode"],
                    "team_members": runtime_plan["team_members"],
                    "checkout": {
                        "mode": planned_checkout_mode,
                        "path": str(execution_path),
                        "branch_name": branch_name,
                    },
                    **_story_agent_event_extra(
                        project_id,
                        story_id,
                        runtime_plan,
                        primary_role="worker",
                    ),
                },
            )
            unregister_parallel_story(story_id)
            release_work_item_lease(
                config,
                project_id=project_id,
                story_id=story_id,
                owner=lease_owner,
            )
            sync_story(story_id, ownership=None, checkout=None)
            return "stuck"

        story_project_entry = {**project_entry, "path": str(execution_path)}
        story_orchestrator = Orchestrator(
            project_path=execution_path,
            config=config,
            profiles_dir=config.profiles_dir,
        )
        story_orchestrator.reset_stuck()

        if launch_profile.story_execution_mode == "team":
            run_specialist_preflight(execution_path, story, runtime_plan)

        approved = False
        try:
            while not approved:
                current_state = load_project_state(config, project_id)
                iteration = int(current_state.get("story_state", {}).get(str(story_id), {}).get("iteration", 0)) + 1

                reserved = reserve_profiles()
                if reserved is None:
                    console.print("[yellow]All worker accounts on cooldown. Waiting 60s...[/yellow]")
                    time.sleep(60)
                    continue
                worker_profile, critic_profile = reserved
                worker_env = account_mgr.build_env(worker_profile)
                critic_env = account_mgr.build_env(critic_profile)
                worker_label = f"{worker_profile.provider}/{worker_profile.name}"
                critic_label = f"{critic_profile.provider}/{critic_profile.name}"
                allowed_budget, budget_reason = reserve_iteration_budget(story_id, worker_label, critic_label)
                if not allowed_budget:
                    auto_pause_project_run(
                        config,
                        project_id,
                        message=budget_reason or "Runtime budget exhausted.",
                        story_id=story_id,
                        extra={
                            "worker": worker_label,
                            "critic": critic_label,
                            **_story_agent_event_extra(
                                project_id,
                                story_id,
                                runtime_plan,
                                worker_label=worker_label,
                                critic_label=critic_label,
                                primary_role="worker",
                            ),
                        },
                    )
                    sync_story(
                        story_id,
                        last_error=budget_reason,
                    )
                    unregister_parallel_story(story_id)
                    return "paused"

                sync_story(
                    story_id,
                    iteration=iteration,
                    agent=worker_label,
                    critic=critic_label,
                    team_mode=runtime_plan["team_mode"],
                    team_members=runtime_plan["team_members"],
                    connector_activation=runtime_plan["active_connectors"],
                    activation_errors=runtime_plan["activation_errors"],
                )
                sync_project(
                    current_iteration=iteration,
                    active_worker=worker_label,
                    active_critic=critic_label,
                )
                touch_story_lease(status="active")

                ralph_prd_path = _write_ralph_story_snapshot(story_project_entry, story_id)
                sync_event(
                    event="iteration_started",
                    status="in_progress",
                    message=f"Iteration {iteration} started.",
                    story_id=story_id,
                    extra={
                        "iteration": iteration,
                        "worker": worker_label,
                        "critic": critic_label,
                        **_story_agent_event_extra(
                            project_id,
                            story_id,
                            runtime_plan,
                            worker_label=worker_label,
                            critic_label=critic_label,
                            primary_role="worker",
                        ),
                    },
                )

                outcome = story_orchestrator.run_single_iteration(
                    profile=worker_profile,
                    env=worker_env,
                    story_id=story_id,
                    story_title=story_title,
                    story_description=story_desc,
                    gates_config=gates_config,
                    critic_profile=critic_profile,
                    critic_env=critic_env,
                    retry_only=iteration > 1,
                    ralph_prd_path=ralph_prd_path,
                    progress_callback=lambda elapsed_sec, detail, *, _story_id=story_id, _iteration=iteration, _worker=worker_label, _critic=critic_label: (
                        touch_story_lease(status="active"),
                        _emit_worker_progress(
                            config,
                            project_id,
                            _story_id,
                            _iteration,
                            runtime_plan,
                            _worker,
                            _critic,
                            elapsed_sec,
                            detail,
                        ),
                    )[-1],
                )
                touch_story_lease(status="active")

                if outcome == StoryOutcome.APPROVED:
                    timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    mark_profile_success(worker_profile)
                    mark_profile_success(critic_profile)
                    if execution_path != project and branch_name:
                        merged = merge_worktree(project, execution_path, branch_name)
                        if not merged:
                            message = f"Approved in worktree, but merge back into main failed for `{branch_name}`."
                            sync_story(
                                story_id,
                                status="merge_blocked",
                                completed_at=timestamp,
                                last_error=message,
                                ownership=None,
                            )
                            sync_project(
                                current_iteration=0,
                                active_worker=None,
                                active_critic=None,
                                last_error=message,
                            )
                            sync_event(
                                event="story_merge_blocked",
                                status="merge_blocked",
                                message=message,
                                story_id=story_id,
                                extra={
                                    "branch_name": branch_name,
                                    "worktree_path": str(execution_path),
                                    "merge_target_path": str(project),
                                    **_story_agent_event_extra(
                                        project_id,
                                        story_id,
                                        runtime_plan,
                                        worker_label=worker_label,
                                        critic_label=critic_label,
                                        primary_role="worker",
                                    ),
                                    **_last_iteration_extra(story_orchestrator),
                                },
                            )
                            touch_story_lease(status="merge_blocked")
                            unregister_parallel_story(story_id)
                            return "merge_blocked"

                    sync_story(
                        story_id,
                        status="done",
                        completed_at=timestamp,
                        worktree_path=None,
                        branch_name=None,
                        ownership=None,
                        checkout=None,
                    )
                    sync_project(
                        current_story_id=None if not parallel_slot else load_project_state(config, project_id).get("current_story_id"),
                        current_iteration=0,
                        active_worker=None,
                        active_critic=None,
                        last_error=None,
                    )
                    sync_event(
                        event="story_done",
                        status="done",
                        message=story_title,
                        story_id=story_id,
                        extra={
                            "branch_name": branch_name,
                            **_story_agent_event_extra(
                                project_id,
                                story_id,
                                runtime_plan,
                                worker_label=worker_label,
                                critic_label=critic_label,
                                primary_role="worker",
                            ),
                            **_last_iteration_extra(story_orchestrator),
                        },
                    )
                    touch_story_lease(status="completed")
                    unregister_parallel_story(story_id)
                    approved = True
                    continue

                if outcome == StoryOutcome.RATE_LIMITED:
                    mark_profile_rate_limited(worker_profile)
                    continue

                if outcome in (
                    StoryOutcome.GATE_FAILED,
                    StoryOutcome.CRITIC_REJECTED,
                    StoryOutcome.WORKER_FAILED,
                ):
                    message = _iteration_message(outcome, story_orchestrator)
                    iteration_extra = {
                        "outcome": outcome.value,
                        **_last_iteration_extra(story_orchestrator),
                    }
                    if outcome == StoryOutcome.GATE_FAILED:
                        event_name = "story_gate_failed"
                        iteration_extra["gate_failure_count"] = len(iteration_extra.get("gate_failures", []))
                        iteration_extra.update(
                            _story_agent_event_extra(
                                project_id,
                                story_id,
                                runtime_plan,
                                worker_label=worker_label,
                                critic_label=critic_label,
                                primary_role="worker",
                            )
                        )
                    elif outcome == StoryOutcome.CRITIC_REJECTED:
                        event_name = "critic_rejected"
                        iteration_extra.update(
                            _story_agent_event_extra(
                                project_id,
                                story_id,
                                runtime_plan,
                                worker_label=worker_label,
                                critic_label=critic_label,
                                primary_role="critic",
                            )
                        )
                    else:
                        event_name = "worker_failed"
                        iteration_extra["worker_error"] = message
                        iteration_extra.update(
                            _story_agent_event_extra(
                                project_id,
                                story_id,
                                runtime_plan,
                                worker_label=worker_label,
                                critic_label=critic_label,
                                primary_role="worker",
                            )
                        )
                    sync_event(
                        event=event_name,
                        status="error",
                        message=message,
                        story_id=story_id,
                        extra=iteration_extra,
                    )
                    sync_project(last_error=message)
                    sync_story(story_id, last_error=message)
                    touch_story_lease(status="active")
                    if story_orchestrator.check_stuck():
                        stuck_message = story_orchestrator.stuck_detector.summary()
                        console.print(f"[red]Story #{story_id} is stuck. Skipping.[/red]")
                        sync_story(
                            story_id,
                            status="stuck",
                            completed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            last_error=stuck_message,
                            ownership=None,
                            checkout=None,
                        )
                        sync_project(
                            current_iteration=0,
                            active_worker=None,
                            active_critic=None,
                            last_error=stuck_message,
                        )
                        sync_event(
                            event="story_stuck",
                            status="stuck",
                            message=stuck_message,
                            story_id=story_id,
                            extra={
                                "stuck_summary": stuck_message,
                                **_story_agent_event_extra(
                                    project_id,
                                    story_id,
                                    runtime_plan,
                                    worker_label=worker_label,
                                    critic_label=critic_label,
                                    primary_role="worker",
                                ),
                                **_last_iteration_extra(story_orchestrator),
                            },
                        )
                        touch_story_lease(status="stuck")
                        unregister_parallel_story(story_id)
                        return "stuck"
                    continue

                message = f"Unexpected outcome: {outcome}"
                console.print(f"[red]{message}[/red]")
                sync_project(status="failed", last_error=message)
                sync_event(
                    event="run_failed",
                    status="failed",
                    message=message,
                    story_id=story_id,
                    extra={
                        "outcome": str(outcome),
                        **_story_agent_event_extra(
                            project_id,
                            story_id,
                            runtime_plan,
                            worker_label=worker_label,
                            critic_label=critic_label,
                            primary_role="worker",
                        ),
                        **_last_iteration_extra(story_orchestrator),
                    },
                )
                unregister_parallel_story(story_id)
                return "failed"
        finally:
            if execution_path != project and branch_name:
                story_state = load_project_state(config, project_id).get("story_state", {}).get(str(story_id), {})
                if story_state.get("status") != "merge_blocked":
                    remove_worktree(project, execution_path)
            if story_lease is not None:
                release_work_item_lease(
                    config,
                    project_id=project_id,
                    story_id=story_id,
                    owner=lease_owner,
                )
                story_state = load_project_state(config, project_id).get("story_state", {}).get(str(story_id), {})
                checkout_update = {} if story_state.get("status") == "merge_blocked" else {"checkout": None}
                sync_story(story_id, ownership=None, **checkout_update)

        return "done"

    try:
        while True:
            state = ensure_project_state(config, project_entry, seed_mode="migrate")
            if state.get("paused"):
                console.print("[yellow]Project paused.[/yellow]")
                break
            reopened_story_ids = requeue_recoverable_stuck_stories(config, project_id)
            if reopened_story_ids:
                for reopened_story_id in reopened_story_ids:
                    sync_event(
                        event="story_requeued",
                        status="open",
                        message="Story reopened after later completed work may have resolved the blocker.",
                        story_id=reopened_story_id,
                    )
                state = ensure_project_state(config, project_entry, seed_mode="migrate")

            open_stories = []
            for candidate in _story_definitions(project_entry):
                runtime = state.get("story_state", {}).get(str(candidate["id"]), {})
                if runtime.get("status", "open") == "open":
                    open_stories.append(candidate)

            if not open_stories:
                stories = state.get("story_state", {}).values()
                has_stuck = any(
                    story_state.get("status") in {"stuck", "merge_blocked"} for story_state in stories
                )
                console.print("[bold green]All stories complete![/bold green]")
                _mark_run_finished(
                    config,
                    project_id,
                    failed=has_stuck,
                    message="Run finished with stuck stories." if has_stuck else "All stories completed.",
                )
                break

            if launch_profile.project_concurrency_mode == "parallel":
                batch = open_stories[: launch_profile.max_parallel_stories]
                with concurrent.futures.ThreadPoolExecutor(max_workers=len(batch)) as executor:
                    futures = [executor.submit(execute_story, story, parallel_slot=True) for story in batch]
                    for future in concurrent.futures.as_completed(futures):
                        future.result()
                continue

            result = execute_story(open_stories[0], parallel_slot=False)
            if result == "paused":
                break
    except Exception as exc:  # pragma: no cover - defensive top-level sync
        update_project_runtime(config, project_id, status="failed", last_error=str(exc), pid=None)
        emit_project_event(
            config,
            project_id,
            event="run_failed",
            status="failed",
            message=str(exc),
            extra={"exception_type": type(exc).__name__},
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
