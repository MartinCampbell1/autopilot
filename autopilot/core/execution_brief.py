"""Execution brief schema and rendering helpers for portfolio-to-build handoff."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FounderContext(BaseModel):
    """Founder-specific constraints and advantages that should shape execution."""

    mode: str = Field(default="solo_ai_augmented")
    strengths: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    unfair_advantages: list[str] = Field(default_factory=list)
    available_capital_usd: int | None = None
    weekly_hours: int | None = None


class MarketContext(BaseModel):
    """Commercial framing for the opportunity."""

    icp: str = ""
    pain: str = ""
    why_now: str = ""
    wedge: str = ""


class ExecutionContext(BaseModel):
    """Practical build constraints and resources for the MVP."""

    mvp_scope: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    required_connectors: list[str] = Field(default_factory=list)
    existing_repos: list[str] = Field(default_factory=list)


class MonetizationContext(BaseModel):
    """How the brief expects to get to first dollars."""

    revenue_model: str = ""
    pricing_hint: str = ""
    time_to_first_dollar: str = ""


class EvaluationContext(BaseModel):
    """Success metrics and stopping rules for execution."""

    success_metrics: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    major_risks: list[str] = Field(default_factory=list)


class ProvenanceContext(BaseModel):
    """Optional metadata about how this brief was produced."""

    source_system: str = ""
    source_session_id: str = ""
    source_mode: str = ""
    ranking_rationale: str = ""


class InitiativeContext(BaseModel):
    """Optional upstream initiative mapping from FounderOS/Quorum."""

    id: str = ""
    title: str = ""
    stage: str = ""
    hypothesis_id: str = ""
    track: str = ""


class OrchestrationContext(BaseModel):
    """Optional external orchestrator metadata for execution-plane handoff."""

    orchestrator: str = ""
    run_id: str = ""
    initiative_ref: str = ""
    project_ref: str = ""
    requested_launch_preset: str = ""


class ExecutionBrief(BaseModel):
    """Typed handoff object from research/orchestration into execution."""

    version: str = Field(default="1.0")
    title: str
    thesis: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    founder: FounderContext = Field(default_factory=FounderContext)
    market: MarketContext = Field(default_factory=MarketContext)
    execution: ExecutionContext = Field(default_factory=ExecutionContext)
    monetization: MonetizationContext = Field(default_factory=MonetizationContext)
    evaluation: EvaluationContext = Field(default_factory=EvaluationContext)
    initiative: InitiativeContext = Field(default_factory=InitiativeContext)
    orchestration: OrchestrationContext = Field(default_factory=OrchestrationContext)
    provenance: ProvenanceContext = Field(default_factory=ProvenanceContext)


def _render_list(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    lines = [f"## {title}"]
    lines.extend(f"- {item}" for item in items if str(item).strip())
    lines.append("")
    return lines


def render_execution_brief_as_spec(brief: ExecutionBrief) -> str:
    """Render the brief into a planner-friendly spec for PRD generation."""

    lines: list[str] = [
        f"# {brief.title}",
        "",
        "## Core Thesis",
        brief.thesis.strip(),
        "",
    ]

    if brief.summary.strip():
        lines.extend(
            [
                "## Summary",
                brief.summary.strip(),
                "",
            ]
        )

    if brief.tags:
        lines.extend(
            [
                "## Tags",
                ", ".join(tag for tag in brief.tags if tag.strip()),
                "",
            ]
        )

    founder = brief.founder
    lines.extend(
        [
            "## Founder Context",
            f"- Operating mode: {founder.mode}",
        ]
    )
    if founder.available_capital_usd is not None:
        lines.append(f"- Available capital: ${founder.available_capital_usd}")
    if founder.weekly_hours is not None:
        lines.append(f"- Weekly time budget: {founder.weekly_hours} hours")
    lines.append("")
    lines.extend(_render_list("Founder Strengths", founder.strengths))
    lines.extend(_render_list("Founder Interests", founder.interests))
    lines.extend(_render_list("Founder Constraints", founder.constraints))
    lines.extend(_render_list("Founder Unfair Advantages", founder.unfair_advantages))

    market = brief.market
    if any((market.icp, market.pain, market.why_now, market.wedge)):
        lines.extend(["## Market Context"])
        if market.icp.strip():
            lines.append(f"- ICP: {market.icp.strip()}")
        if market.pain.strip():
            lines.append(f"- Pain: {market.pain.strip()}")
        if market.why_now.strip():
            lines.append(f"- Why now: {market.why_now.strip()}")
        if market.wedge.strip():
            lines.append(f"- Distribution wedge: {market.wedge.strip()}")
        lines.append("")

    execution = brief.execution
    lines.extend(_render_list("MVP Scope", execution.mvp_scope))
    lines.extend(_render_list("Non Goals", execution.non_goals))
    lines.extend(_render_list("Required Capabilities", execution.required_capabilities))
    lines.extend(_render_list("Required Connectors", execution.required_connectors))
    lines.extend(_render_list("Existing Repositories", execution.existing_repos))

    monetization = brief.monetization
    if any((monetization.revenue_model, monetization.pricing_hint, monetization.time_to_first_dollar)):
        lines.extend(["## Monetization"])
        if monetization.revenue_model.strip():
            lines.append(f"- Revenue model: {monetization.revenue_model.strip()}")
        if monetization.pricing_hint.strip():
            lines.append(f"- Pricing hint: {monetization.pricing_hint.strip()}")
        if monetization.time_to_first_dollar.strip():
            lines.append(f"- Time to first dollar: {monetization.time_to_first_dollar.strip()}")
        lines.append("")

    evaluation = brief.evaluation
    lines.extend(_render_list("Success Metrics", evaluation.success_metrics))
    lines.extend(_render_list("Kill Criteria", evaluation.kill_criteria))
    lines.extend(_render_list("Open Questions", evaluation.open_questions))
    lines.extend(_render_list("Major Risks", evaluation.major_risks))

    initiative = brief.initiative
    if any((initiative.id, initiative.title, initiative.stage, initiative.hypothesis_id, initiative.track)):
        lines.extend(["## Initiative"])
        if initiative.id.strip():
            lines.append(f"- Initiative id: {initiative.id.strip()}")
        if initiative.title.strip():
            lines.append(f"- Initiative title: {initiative.title.strip()}")
        if initiative.stage.strip():
            lines.append(f"- Initiative stage: {initiative.stage.strip()}")
        if initiative.hypothesis_id.strip():
            lines.append(f"- Hypothesis id: {initiative.hypothesis_id.strip()}")
        if initiative.track.strip():
            lines.append(f"- Track: {initiative.track.strip()}")
        lines.append("")

    orchestration = brief.orchestration
    if any((orchestration.orchestrator, orchestration.run_id, orchestration.initiative_ref, orchestration.project_ref, orchestration.requested_launch_preset)):
        lines.extend(["## Orchestration Context"])
        if orchestration.orchestrator.strip():
            lines.append(f"- Orchestrator: {orchestration.orchestrator.strip()}")
        if orchestration.run_id.strip():
            lines.append(f"- Orchestrator run id: {orchestration.run_id.strip()}")
        if orchestration.initiative_ref.strip():
            lines.append(f"- Initiative ref: {orchestration.initiative_ref.strip()}")
        if orchestration.project_ref.strip():
            lines.append(f"- Upstream project ref: {orchestration.project_ref.strip()}")
        if orchestration.requested_launch_preset.strip():
            lines.append(f"- Requested launch preset: {orchestration.requested_launch_preset.strip()}")
        lines.append("")

    provenance = brief.provenance
    if any((provenance.source_system, provenance.source_session_id, provenance.source_mode, provenance.ranking_rationale)):
        lines.extend(["## Provenance"])
        if provenance.source_system.strip():
            lines.append(f"- Source system: {provenance.source_system.strip()}")
        if provenance.source_session_id.strip():
            lines.append(f"- Source session: {provenance.source_session_id.strip()}")
        if provenance.source_mode.strip():
            lines.append(f"- Source mode: {provenance.source_mode.strip()}")
        if provenance.ranking_rationale.strip():
            lines.append(f"- Ranking rationale: {provenance.ranking_rationale.strip()}")
        lines.append("")

    lines.extend(
        [
            "## Planning Instructions",
            "- Convert this brief into a phased execution PRD.",
            "- Preserve the founder constraints and commercial framing.",
            "- Keep the MVP narrow and ship-oriented.",
            "- Reflect required connectors, repos, and external systems in the story metadata.",
        ]
    )
    return "\n".join(lines).strip() + "\n"
