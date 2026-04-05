"""Adapters between shared Quorum contracts and local Autopilot models."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autopilot.core.execution_brief import (
    EvaluationContext,
    ExecutionBrief as InternalExecutionBrief,
    ExecutionContext,
    InitiativeContext,
    OrchestrationContext,
    ProvenanceContext,
    TaskSource,
)
from autopilot.core.shared_contract_codec import dump_shared_contract
from autopilot.core.shared_contracts import ExecutionBrief as SharedExecutionBrief

SHARED_EXECUTION_BRIEF_RELPATH = ".agents/tasks/shared-execution-brief.json"


def _compact_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if str(line).strip()]


def _shared_brief_summary(brief: SharedExecutionBrief) -> str:
    lines = _compact_lines(
        [
            brief.prd_summary,
            f"Acceptance criteria: {', '.join(brief.acceptance_criteria)}" if brief.acceptance_criteria else "",
            f"Recommended stack: {', '.join(brief.recommended_tech_stack)}" if brief.recommended_tech_stack else "",
            f"Judge summary: {brief.judge_summary}" if brief.judge_summary else "",
            f"Simulation summary: {brief.simulation_summary}" if brief.simulation_summary else "",
        ]
    )
    return "\n".join(lines).strip()


def shared_execution_brief_to_internal(brief: SharedExecutionBrief) -> InternalExecutionBrief:
    """Convert the shared cross-plane brief into the local execution-brief contract."""

    return InternalExecutionBrief(
        title=brief.title,
        thesis=brief.prd_summary.strip() or brief.title,
        summary=_shared_brief_summary(brief),
        tags=list(dict.fromkeys(str(item).strip() for item in brief.recommended_tech_stack if str(item).strip())),
        execution=ExecutionContext(
            mvp_scope=[story.title for story in brief.first_stories if str(story.title).strip()],
            required_capabilities=[
                str(item).strip()
                for item in brief.recommended_tech_stack
                if str(item).strip()
            ],
        ),
        evaluation=EvaluationContext(
            success_metrics=[str(item).strip() for item in brief.acceptance_criteria if str(item).strip()],
            major_risks=[
                (
                    f"[{risk.category}] {risk.description}"
                    + (f" Mitigation: {risk.mitigation}" if risk.mitigation else "")
                ).strip()
                for risk in brief.risks
                if str(risk.description).strip()
            ],
        ),
        initiative=InitiativeContext(
            id=brief.idea_id,
            title=brief.title,
            stage="brief_drafted",
            hypothesis_id=brief.brief_id,
            track="quorum_shared_contract",
        ),
        orchestration=OrchestrationContext(
            orchestrator="quorum",
            run_id=brief.brief_id,
            initiative_ref=brief.idea_id,
            project_ref=brief.brief_id,
            requested_launch_preset="",
        ),
        provenance=ProvenanceContext(
            source_system="quorum",
            source_session_id=brief.brief_id,
            source_mode="shared_contracts",
            ranking_rationale=str(brief.judge_summary or "").strip(),
        ),
        task_source=TaskSource(
            source_kind="execution_brief",
            external_id=brief.brief_id,
            repo="",
            branch_policy="isolated_worktree",
            brief_ref=SHARED_EXECUTION_BRIEF_RELPATH,
        ),
    )


def shared_execution_brief_path(project_root: Path, *, relpath: str = SHARED_EXECUTION_BRIEF_RELPATH) -> Path:
    """Resolve the raw shared-brief artifact path for one project root."""

    return (project_root / relpath).resolve()


def shared_execution_brief_payload(brief: SharedExecutionBrief) -> dict[str, Any]:
    """Return the JSON-safe shared brief payload."""

    return dump_shared_contract(brief)


def shared_execution_brief_metadata(brief: SharedExecutionBrief, *, brief_relpath: str) -> dict[str, Any]:
    """Build control-plane metadata that links a project to the shared brief."""

    evidence_payload = dump_shared_contract(brief.evidence) if brief.evidence is not None else None
    return {
        "brief_id": brief.brief_id,
        "idea_id": brief.idea_id,
        "title": brief.title,
        "relpath": brief_relpath,
        "confidence": brief.confidence.value,
        "effort": brief.effort.value,
        "urgency": brief.urgency.value,
        "budget_tier": brief.budget_tier.value,
        "acceptance_criteria": list(brief.acceptance_criteria),
        "recommended_tech_stack": list(brief.recommended_tech_stack),
        "first_story_titles": [story.title for story in brief.first_stories if str(story.title).strip()],
        "judge_summary": str(brief.judge_summary or "").strip(),
        "simulation_summary": str(brief.simulation_summary or "").strip(),
        "evidence": evidence_payload,
        "created_at": brief.created_at.isoformat(),
    }

