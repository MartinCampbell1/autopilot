"""Tests for run CLI helpers."""

from __future__ import annotations

import json
from pathlib import Path

from autopilot.cli.run import _write_ralph_story_snapshot


def test_write_ralph_story_snapshot_selects_only_requested_story(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    prd_path = project_dir / ".agents" / "tasks" / "prd.json"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        json.dumps(
            {
                "title": "Demo",
                "description": "Demo project",
                "stories": [
                    {"id": 1, "title": "One", "description": "A", "position": 0, "status": "stuck"},
                    {"id": 2, "title": "Two", "description": "B", "position": 1, "status": "open"},
                    {"id": 3, "title": "Three", "description": "C", "position": 2, "status": "done"},
                ],
            }
        )
    )

    snapshot_path = _write_ralph_story_snapshot(
        {
            "name": "Demo",
            "path": str(project_dir),
            "prd": ".agents/tasks/prd.json",
        },
        2,
    )

    snapshot = json.loads(Path(snapshot_path).read_text())

    assert [story["status"] for story in snapshot["stories"]] == ["done", "open", "done"]
