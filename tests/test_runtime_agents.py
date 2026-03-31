"""Tests for runtime-agent pipeline helpers."""

from autopilot.core.runtime_agents import build_runtime_agents, build_story_pipeline_state, update_pipeline_stage_state


def test_build_story_pipeline_state_assigns_members_by_stage() -> None:
    state = build_story_pipeline_state(
        ["research", "implement", "review"],
        [
            {"member_id": "specialist", "label": "Research Specialist", "execution_role": "specialist", "pipeline_stage": "research"},
            {"member_id": "primary", "label": "Primary Worker", "execution_role": "primary_worker", "pipeline_stage": "implement"},
            {"member_id": "critic", "label": "Critic", "execution_role": "critic", "pipeline_stage": "review"},
        ],
    )

    assert [entry["stage"] for entry in state] == ["research", "implement", "review"]
    assert state[0]["member_id"] == "specialist"
    assert state[1]["role"] == "worker"
    assert state[2]["role"] == "critic"


def test_update_pipeline_stage_state_marks_stage_complete() -> None:
    initial = [
        {"stage": "research", "order": 1, "role": "specialist", "member_id": "specialist", "label": "Research Specialist", "status": "pending"},
        {"stage": "implement", "order": 2, "role": "worker", "member_id": "primary", "label": "Primary Worker", "status": "pending"},
    ]

    updated = update_pipeline_stage_state(
        initial,
        stage="research",
        status="completed",
        timestamp="2026-03-31T00:00:00Z",
        detail="Research finished.",
    )

    assert updated[0]["status"] == "completed"
    assert updated[0]["completed_at"] == "2026-03-31T00:00:00Z"
    assert updated[0]["detail"] == "Research finished."


def test_build_runtime_agents_uses_pipeline_state_for_specialist_status() -> None:
    agents = build_runtime_agents(
        "proj_demo",
        [
            {
                "id": 7,
                "title": "Build dashboard",
                "status": "in_progress",
                "team_members": [
                    {
                        "member_id": "specialist",
                        "label": "Research Specialist",
                        "execution_role": "specialist",
                        "pipeline_stage": "research",
                        "pipeline_order": 1,
                        "specialist": True,
                    },
                    {
                        "member_id": "primary",
                        "label": "Primary Worker",
                        "execution_role": "primary_worker",
                        "pipeline_stage": "implement",
                        "pipeline_order": 2,
                    },
                    {
                        "member_id": "critic",
                        "label": "Critic",
                        "execution_role": "critic",
                        "pipeline_stage": "review",
                        "pipeline_order": 3,
                    },
                ],
                "story_pipeline": ["research", "implement", "review"],
                "pipeline_state": [
                    {"stage": "research", "order": 1, "role": "specialist", "member_id": "specialist", "label": "Research Specialist", "status": "completed"},
                    {"stage": "implement", "order": 2, "role": "worker", "member_id": "primary", "label": "Primary Worker", "status": "active"},
                    {"stage": "review", "order": 3, "role": "critic", "member_id": "critic", "label": "Critic", "status": "pending"},
                ],
                "agent": "codex/worker-1",
                "critic": "codex/critic-1",
            }
        ],
    )

    specialist = next(agent for agent in agents if agent["role"] == "specialist")
    worker = next(agent for agent in agents if agent["role"] == "worker")

    assert specialist["pipeline_status"] == "completed"
    assert specialist["status"] == "done"
    assert worker["pipeline_status"] == "active"
    assert worker["status"] == "active"
