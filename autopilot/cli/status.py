"""CLI command: `autopilot status`."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import load_config

console = Console()


def status() -> None:
    """Show status of configured accounts and projects."""
    config = load_config(Path.home() / ".autopilot" / "config.yaml")
    account_mgr = AccountManager(profiles_dir=config.profiles_dir, config=config)
    account_mgr.discover()

    console.print(Panel("[bold]Account Status[/bold]"))
    for provider in account_mgr.pools:
        profiles = account_mgr.pools.get(provider, [])
        if not profiles:
            continue

        table = Table(title=f"{provider} ({len(profiles)} accounts)")
        table.add_column("Name")
        table.add_column("Available")
        table.add_column("Requests")
        table.add_column("Cooldown")

        for pool_item in account_mgr.pool_status(provider):
            available = "[green]yes[/green]" if pool_item["available"] else "[red]no[/red]"
            cooldown = (
                f"{pool_item['cooldown_remaining_sec']}s"
                if pool_item["cooldown_remaining_sec"] > 0
                else "-"
            )
            table.add_row(pool_item["name"], available, str(pool_item["requests_made"]), cooldown)

        console.print(table)

    projects_path = config.projects_yaml_path
    if projects_path.exists():
        import yaml

        data = yaml.safe_load(projects_path.read_text()) or {}
        projects = data.get("projects", [])

        if projects:
            console.print(Panel("[bold]Projects[/bold]"))
            table = Table()
            table.add_column("Name")
            table.add_column("Path")
            table.add_column("Priority")
            table.add_column("Stories")

            for project in projects:
                prd_path = Path(project["path"]) / project.get("prd", ".agents/tasks/prd.json")
                story_count = "-"
                if prd_path.exists():
                    try:
                        prd_data = json.loads(prd_path.read_text())
                        stories = prd_data.get("stories", [])
                        done = sum(1 for story in stories if story.get("status") == "done")
                        total = len(stories)
                        story_count = f"{done}/{total}"
                    except Exception:
                        pass

                table.add_row(
                    project["name"],
                    project["path"],
                    project.get("priority", "normal"),
                    story_count,
                )

            console.print(table)
