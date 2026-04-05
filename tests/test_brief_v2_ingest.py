"""Tests for the BriefV2 → Autopilot planning context adapter."""
from __future__ import annotations

from founderos_contracts.brief_v2 import (
    ApprovalPolicy,
    BudgetPolicy,
    EvidenceBundle,
    EvidenceItem,
    ExecutionBriefV2,
    RiskItem,
    StoryDecompositionSeed,
)
from founderos_contracts.citations import Citation

from autopilot.core.brief_v2_adapter import brief_v2_to_planning_context, should_deduplicate_brief


def _make_v2_brief() -> ExecutionBriefV2:
    return ExecutionBriefV2(
        schema_version="2.0",
        brief_id="brief-001",
        revision_id="rev-001",
        initiative_id="init-001",
        option_id="opt-001",
        decision_id="dec-001",
        title="Launch MVP Dashboard",
        initiative_summary="Build a founder-facing dashboard for tracking key metrics.",
        winner_rationale="This option balances speed and scope.",
        research_summary="Market research shows demand for real-time founder dashboards.",
        assumptions=["Founders have existing data sources", "API integrations available"],
        constraints=["Must ship in 4 weeks", "No external DB vendor"],
        success_criteria=["DAU > 100 within 30 days", "P95 latency < 200ms"],
        budget_policy=BudgetPolicy(
            tier="medium",
            max_run_cost_usd=50.0,
            max_total_cost_usd=500.0,
            max_runtime_minutes=120,
        ),
        approval_policy=ApprovalPolicy(
            founder_approval_required=True,
            auto_launch_allowed=False,
            required_approvers=["founder@example.com"],
        ),
        recommended_tech_stack=["python", "fastapi", "react"],
        story_breakdown=[
            StoryDecompositionSeed(
                title="User authentication",
                description="Implement OAuth2 login flow.",
                acceptance_criteria=["Login works", "Session persists"],
                effort="medium",
            ),
            StoryDecompositionSeed(
                title="Metrics overview page",
                description="Show key KPIs on landing page.",
                acceptance_criteria=["KPIs visible", "Data refreshes every 5 min"],
                effort="large",
            ),
        ],
        risks=[
            RiskItem(
                category="technical",
                description="OAuth provider downtime.",
                level="medium",
                mitigation="Add fallback email login.",
            )
        ],
        repo_dna_snapshot={
            "primary_language": "python",
            "frameworks": ["fastapi"],
            "test_coverage": 0.72,
        },
        repo_instruction_refs=["AGENTS.md", "CLAUDE.md"],
        citations=[
            Citation(
                citation_id="cit-001",
                title="Founder Dashboard Benchmark",
                url="https://example.com/benchmark",
                note="Industry baseline metrics.",
            )
        ],
        evidence=EvidenceBundle(
            bundle_id="evb-001",
            parent_id="init-001",
            items=[
                EvidenceItem(
                    evidence_id="ev-001",
                    kind="web_research",
                    summary="Demand confirmed via survey.",
                    confidence=0.85,
                )
            ],
            overall_confidence=0.85,
        ),
        source_pack_ref="pack-001",
        brief_approval_status="approved",
    )


def test_v2_brief_to_planning_context_preserves_stories() -> None:
    brief = _make_v2_brief()
    ctx = brief_v2_to_planning_context(brief)

    assert len(ctx["stories"]) == 2
    story = ctx["stories"][0]
    assert story["title"] == "User authentication"
    assert story["description"] == "Implement OAuth2 login flow."
    assert "Login works" in story["acceptance_criteria"]
    assert story["effort"] == "medium"


def test_v2_brief_to_planning_context_includes_repo_dna() -> None:
    brief = _make_v2_brief()
    ctx = brief_v2_to_planning_context(brief)

    assert ctx["repo_dna_snapshot"] is not None
    assert ctx["repo_dna_snapshot"]["primary_language"] == "python"
    assert ctx["repo_dna_snapshot"]["test_coverage"] == 0.72


def test_v2_brief_to_planning_context_includes_budget_policy() -> None:
    brief = _make_v2_brief()
    ctx = brief_v2_to_planning_context(brief)

    budget = ctx["budget_policy"]
    assert budget["tier"] == "medium"
    assert budget["max_total_cost_usd"] == 500.0


def test_v2_brief_to_planning_context_includes_evidence() -> None:
    brief = _make_v2_brief()
    ctx = brief_v2_to_planning_context(brief)

    assert ctx["evidence"] is not None
    assert len(ctx["evidence"]["items"]) == 1
    assert ctx["evidence"]["items"][0]["kind"] == "web_research"


def test_v2_brief_urgency_not_mapped_to_stage() -> None:
    """Regression: the old adapter mapped urgency → initiative.stage (semantic error).

    The V2 planning context must not contain a 'stage' field that mirrors budget tier.
    """
    brief = _make_v2_brief()
    ctx = brief_v2_to_planning_context(brief)

    # No 'stage' key at the top level — urgency is not in V2, budget tier is separate
    assert "stage" not in ctx
    # Budget tier must not be confused with lifecycle stage
    assert ctx["budget_policy"]["tier"] == "medium"
    # Verify no key called 'stage' sneaked in anywhere at the top level
    for key in ctx:
        assert key != "stage", f"'stage' field found in planning context under key '{key}'"


def test_should_deduplicate_brief_true() -> None:
    result = should_deduplicate_brief(
        brief_id="brief-001",
        existing_project_id="proj-abc",
    )
    assert result is True


def test_should_deduplicate_brief_false_when_new() -> None:
    result = should_deduplicate_brief(
        brief_id="brief-001",
        existing_project_id=None,
    )
    assert result is False


def test_should_deduplicate_brief_false_when_allowed() -> None:
    result = should_deduplicate_brief(
        brief_id="brief-001",
        existing_project_id="proj-abc",
        allow_duplicate=True,
    )
    assert result is False


# ---------------------------------------------------------------------------
# Approval gate tests
# ---------------------------------------------------------------------------


def test_approval_gate_blocks_unapproved_launch() -> None:
    """Brief with founder_approval_required=True and status != approved must block launch."""
    import pytest
    from datetime import datetime, timezone

    from autopilot.core.execution_plane import _check_brief_approval_gate

    brief = ExecutionBriefV2(
        schema_version="2.0",
        brief_id="test-block",
        revision_id="rev-001",
        initiative_id="init-001",
        title="Should Block",
        initiative_summary="Unapproved brief.",
        budget_policy=BudgetPolicy(tier="low"),
        approval_policy=ApprovalPolicy(founder_approval_required=True),
        brief_approval_status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with pytest.raises(ValueError, match="Brief must be approved"):
        _check_brief_approval_gate(brief, launch=True)


def test_approval_gate_allows_approved_launch() -> None:
    """Brief with approved status should not raise."""
    from datetime import datetime, timezone

    from autopilot.core.execution_plane import _check_brief_approval_gate

    brief = ExecutionBriefV2(
        schema_version="2.0",
        brief_id="test-allow",
        revision_id="rev-001",
        initiative_id="init-001",
        title="Should Allow",
        initiative_summary="Approved brief.",
        budget_policy=BudgetPolicy(tier="low"),
        approval_policy=ApprovalPolicy(founder_approval_required=True),
        brief_approval_status="approved",
        approved_by="founder",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Should not raise
    _check_brief_approval_gate(brief, launch=True)


def test_approval_gate_skips_legacy_briefs() -> None:
    """Legacy briefs without approval_policy should not be gated."""
    from autopilot.core.execution_plane import _check_brief_approval_gate

    class LegacyBrief:
        title = "Legacy"

    # Should not raise — no approval_policy attribute
    _check_brief_approval_gate(LegacyBrief(), launch=True)


def test_approval_gate_skips_when_not_launching() -> None:
    """No gate check needed if launch=False."""
    from datetime import datetime, timezone

    from autopilot.core.execution_plane import _check_brief_approval_gate

    brief = ExecutionBriefV2(
        schema_version="2.0",
        brief_id="test-no-launch",
        revision_id="rev-001",
        initiative_id="init-001",
        title="No Launch",
        initiative_summary="Not launching.",
        budget_policy=BudgetPolicy(tier="low"),
        approval_policy=ApprovalPolicy(founder_approval_required=True),
        brief_approval_status="pending",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Should not raise — launch=False
    _check_brief_approval_gate(brief, launch=False)
