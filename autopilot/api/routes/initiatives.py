"""Initiative lineage routes — cross-plane aggregate read model."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from autopilot.api.deps import get_config
from autopilot.core.initiative_lineage import (
    build_initiative_aggregate,
    list_initiative_lineages,
    upsert_initiative_lineage,
)

router = APIRouter()


@router.get("/{initiative_id}")
async def get_initiative(initiative_id: str) -> dict[str, Any]:
    """Return the full aggregate view for one initiative.

    Combines lineage metadata, project detail, and outcome summary.
    """
    config = get_config()
    aggregate = build_initiative_aggregate(config, initiative_id)
    if aggregate is None:
        raise HTTPException(404, f"Initiative {initiative_id} not found")
    return {"status": "ok", "initiative": aggregate}


@router.get("/")
async def list_initiatives() -> dict[str, Any]:
    """List all tracked initiative lineages."""
    config = get_config()
    lineages = list_initiative_lineages(config)
    return {
        "status": "ok",
        "count": len(lineages),
        "initiatives": [lineage.model_dump(mode="json") for lineage in lineages],
    }


@router.patch("/{initiative_id}")
async def update_initiative_lineage(initiative_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Partially update a lineage record (e.g. advance lifecycle_state)."""
    config = get_config()

    allowed_fields = {
        "option_id", "decision_id", "brief_id", "project_id",
        "outcome_id", "lifecycle_state", "current_mode",
    }
    filtered = {k: v for k, v in updates.items() if k in allowed_fields}
    if not filtered:
        raise HTTPException(400, f"No updatable fields provided. Allowed: {sorted(allowed_fields)}")

    lineage = upsert_initiative_lineage(config, initiative_id, **filtered)
    return {"status": "ok", "lineage": lineage.model_dump(mode="json")}
