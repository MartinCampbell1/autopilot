"""CLI command: `autopilot init <project-path>`."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.capability_store import (
    build_planning_context,
    load_connectors_registry,
    load_role_templates,
    load_skill_packs_registry,
)
from autopilot.core.config import load_config, save_config
from autopilot.core.intake import (
    IntakeSession,
    build_spec_bootstrap,
    generate_prd_from_session_bootstrap,
    save_spec_bootstrap,
)
from autopilot.core.loop_runner import (
    apply_autopilot_ralph_overrides,
    check_ralph_installed,
    init_ralph_project,
)
from autopilot.core.onboarding import detect_project_tooling
from autopilot.core.project_store import (
    ensure_project_state,
    register_project,
    save_project_prd,
    update_project_entry,
)

console = Console()


def init(
    project_path: str = typer.Argument(help="Path to the project directory"),
    idea: str = typer.Option("", "--idea", help="Natural-language project idea to bootstrap into a starter spec/PRD."),
    bootstrap_only: bool = typer.Option(False, "--bootstrap-only", help="Save only the generated spec bootstrap and skip PRD generation."),
) -> None:
    """Initialize a project for Autopilot and persist detected gate defaults."""
    project = Path(project_path).expanduser().resolve()

    if not project.exists():
        console.print(f"[red]Directory not found: {project}[/red]")
        raise typer.Exit(1)

    if not project.is_dir():
        console.print(f"[red]Not a directory: {project}[/red]")
        raise typer.Exit(1)

    config_path = Path.home() / ".autopilot" / "config.yaml"
    config = load_config(config_path)
    config_created = False
    if not config_path.exists():
        save_config(config, config_path)
        config_created = True

    ralph_installed = check_ralph_installed()
    ralph_initialized = init_ralph_project(project) if ralph_installed else False
    if not ralph_initialized:
        apply_autopilot_ralph_overrides(project)

    project_entry = register_project(
        config,
        name=project.name,
        project_path=project,
        prd_relpath=".agents/tasks/prd.json",
    )

    prd_created = False
    prd_path = project / ".agents" / "tasks" / "prd.json"

    bootstrap_path: Path | None = None
    if idea.strip():
        session = IntakeSession(session_id="init-bootstrap")
        session.add_user_message(idea.strip())
        session.spec_bootstrap = build_spec_bootstrap(session)
        if session.spec_bootstrap:
            bootstrap_path = save_spec_bootstrap(session.spec_bootstrap, project)

        if not bootstrap_only and session.spec_bootstrap:
            account_mgr = AccountManager(
                profiles_dir=config.profiles_dir,
                cooldown_base=config.cooldown_base_sec,
            )
            account_mgr.discover()
            profile = account_mgr.get_next("codex")
            if profile is None:
                console.print("[yellow]No available codex profile for PRD generation. Saved bootstrap spec only.[/yellow]")
            else:
                env = account_mgr.build_env(profile)
                planning_context = build_planning_context(
                    connectors=load_connectors_registry(config),
                    skill_packs=load_skill_packs_registry(config),
                    role_templates=load_role_templates(),
                )
                generated_prd = generate_prd_from_session_bootstrap(
                    session,
                    provider="codex",
                    env=env,
                    workdir=str(project),
                    planning_context=planning_context,
                    timeout_sec=min(config.codex_timeout_sec, 300),
                )
                save_project_prd(project_entry, generated_prd)
                prd_created = True

    if not prd_path.exists() and not prd_created:
        save_project_prd(
            project_entry,
            {
                "title": project.name,
                "description": "",
                "stories": [],
            },
        )
        prd_created = True

    tooling = detect_project_tooling(project)
    project_entry["gates"] = tooling.gates
    update_project_entry(config, project_entry)
    ensure_project_state(config, project_entry, seed_mode="migrate")

    console.print(f"[bold]Initialized Autopilot in {project}[/bold]")
    console.print(f"Project id: [cyan]{project_entry['id']}[/cyan]")
    if config_created:
        console.print(f"[green]Created config:[/green] {config_path}")
    else:
        console.print(f"Using config: {config_path}")

    if tooling.stacks:
        console.print(f"Detected stack: {', '.join(tooling.stacks)}")
    else:
        console.print("[yellow]No obvious project stack detected yet.[/yellow]")

    if tooling.gates:
        console.print("[green]Saved detected gates:[/green]")
        for gate in tooling.gates:
            console.print(f"  - {gate['name']}: {gate['cmd']}")
    else:
        console.print("[yellow]No build/test/lint commands were auto-detected.[/yellow]")

    if prd_created:
        console.print(f"[green]Created starter PRD:[/green] {prd_path}")
    if bootstrap_path is not None:
        console.print(f"[green]Created spec bootstrap:[/green] {bootstrap_path}")

    if ralph_installed and ralph_initialized:
        console.print("[green]Ralph is installed and project scaffolding was refreshed.[/green]")
    elif ralph_installed:
        console.print("[yellow]Ralph is installed, but Autopilot fell back to local overrides only.[/yellow]")
    else:
        console.print("[yellow]Ralph is not installed. Autopilot created local overrides, but `ralph install` is still recommended.[/yellow]")

    if tooling.notes:
        console.print("\nNotes:")
        for note in tooling.notes:
            console.print(f"  - {note}")

    console.print("\nNext steps:")
    console.print("  1. Run `autopilot doctor` to verify provider sessions and detected gates.")
    console.print(f"  2. Edit {prd_path} and add your stories.")
    console.print(f"  3. Run `autopilot run {project}` when the PRD is ready.")
