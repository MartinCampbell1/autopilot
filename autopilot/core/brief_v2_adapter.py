"""Adapter from canonical ExecutionBriefV2 to Autopilot planning context.

Replaces the lossy shared_execution_brief_to_internal(). Instead of converting
to an intermediate Pydantic model with field losses, produces a rich planning
context dict directly from V2.
"""
from __future__ import annotations

from founderos_contracts.brief_v2 import ExecutionBriefV2


def brief_v2_to_planning_context(brief: ExecutionBriefV2) -> dict:
    """Build a planning-ready context from the canonical brief.

    Every field in the brief is preserved and available to the planner/PRD generator.
    """
    return {
        "brief_id": brief.brief_id,
        "revision_id": brief.revision_id,
        "initiative_id": brief.initiative_id,
        "option_id": brief.option_id,
        "decision_id": brief.decision_id,
        "title": brief.title,
        "initiative_summary": brief.initiative_summary,
        "winner_rationale": brief.winner_rationale,
        "research_summary": brief.research_summary,
        "assumptions": brief.assumptions,
        "constraints": brief.constraints,
        "success_criteria": brief.success_criteria,
        "budget_policy": brief.budget_policy.model_dump(),
        "approval_policy": brief.approval_policy.model_dump(),
        "recommended_tech_stack": brief.recommended_tech_stack,
        "stories": [
            {
                "title": s.title,
                "description": s.description,
                "acceptance_criteria": list(s.acceptance_criteria),
                "effort": s.effort,
            }
            for s in brief.story_breakdown
        ],
        "risks": [
            {
                "category": r.category,
                "description": r.description,
                "level": r.level,
                "mitigation": r.mitigation,
            }
            for r in brief.risks
        ],
        "repo_dna_snapshot": brief.repo_dna_snapshot,
        "repo_instruction_refs": brief.repo_instruction_refs,
        "citations": [c.model_dump() for c in brief.citations],
        "evidence": brief.evidence.model_dump() if brief.evidence else None,
        "source_pack_ref": brief.source_pack_ref,
        "brief_approval_status": brief.brief_approval_status,
    }


def should_deduplicate_brief(
    brief_id: str,
    existing_project_id: str | None,
    allow_duplicate: bool = False,
) -> bool:
    """Return True if this brief has already been ingested and should be deduped."""
    if allow_duplicate:
        return False
    return existing_project_id is not None
