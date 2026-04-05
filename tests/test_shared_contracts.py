"""Tests for shared Quorum/Autopilot contracts and adapters."""

from __future__ import annotations

from autopilot.core.shared_contract_adapters import shared_execution_brief_to_internal
from autopilot.core.shared_contract_codec import dump_shared_contract, load_shared_execution_brief


def _shared_brief_payload() -> dict[str, object]:
    return {
        "brief_id": "brief_demo_1",
        "idea_id": "idea_demo_1",
        "title": "FounderOS Shared Brief",
        "prd_summary": "Turn Quorum-ranked ideas into execution-ready projects.",
        "acceptance_criteria": ["Bridge shared brief ingestion", "Export outcome bundle"],
        "risks": [
            {
                "category": "technical",
                "description": "Contract drift between planes",
                "level": "high",
                "mitigation": "Use identical shared dataclasses",
            }
        ],
        "recommended_tech_stack": ["python", "fastapi", "pydantic"],
        "first_stories": [
            {
                "title": "Add shared contracts",
                "description": "Land the cross-seam types",
                "acceptance_criteria": ["Types compile", "Routes can parse them"],
                "effort": "small",
            }
        ],
        "judge_summary": "Shared seam is implementation-ready.",
        "simulation_summary": "Expected to integrate cleanly with existing execution-plane APIs.",
        "confidence": "high",
        "effort": "small",
        "urgency": "this_week",
        "budget_tier": "low",
        "created_at": "2026-04-02T09:00:00+00:00",
    }


def test_shared_execution_brief_round_trips_through_codec() -> None:
    brief = load_shared_execution_brief(_shared_brief_payload())

    dumped = dump_shared_contract(brief)

    assert dumped["brief_id"] == "brief_demo_1"
    assert dumped["confidence"] == "high"
    assert dumped["risks"][0]["level"] == "high"
    assert dumped["created_at"] == "2026-04-02T09:00:00+00:00"


def test_shared_execution_brief_adapter_preserves_cross_plane_ids() -> None:
    brief = load_shared_execution_brief(_shared_brief_payload())

    internal = shared_execution_brief_to_internal(brief)

    assert internal.title == brief.title
    assert internal.thesis == brief.prd_summary
    assert internal.initiative.id == brief.idea_id
    assert internal.initiative.hypothesis_id == brief.brief_id
    assert internal.orchestration.project_ref == brief.brief_id
    assert internal.provenance.source_system == "quorum"
    assert internal.task_source.source_kind == "execution_brief"
    assert internal.task_source.external_id == brief.brief_id
    assert "Acceptance criteria" in internal.summary
