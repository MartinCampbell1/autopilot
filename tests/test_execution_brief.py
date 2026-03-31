"""Tests for execution-brief schema and rendering."""

from __future__ import annotations

from autopilot.core.execution_brief import ExecutionBrief, render_execution_brief_as_spec


def test_render_execution_brief_as_spec_includes_initiative_and_orchestration_sections() -> None:
    brief = ExecutionBrief(
        title="FounderOS Execution Plane",
        thesis="Turn research decisions into shipped execution loops.",
        initiative={
            "id": "init_1",
            "title": "Execution Plane",
            "stage": "mvp",
            "hypothesis_id": "hyp_1",
            "track": "core",
        },
        orchestration={
            "orchestrator": "founderos",
            "run_id": "run_1",
            "initiative_ref": "founderos/init_1",
            "project_ref": "founderos/proj_1",
            "requested_launch_preset": "parallel",
        },
        task_source={
            "source_kind": "execution_brief",
            "external_id": "init_1",
            "repo": "/tmp/founderos",
            "branch_policy": "isolated_worktree",
            "brief_ref": ".agents/tasks/execution-brief.json",
        },
    )

    rendered = render_execution_brief_as_spec(brief)

    assert "## Initiative" in rendered
    assert "- Initiative id: init_1" in rendered
    assert "## Orchestration Context" in rendered
    assert "- Orchestrator: founderos" in rendered
    assert "## Task Source" in rendered
    assert "- Branch policy: isolated_worktree" in rendered
    assert "- Use `blocked_by` when a story must wait for another story to complete." in rendered
