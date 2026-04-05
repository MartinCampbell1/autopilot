"""Export routes for shared execution outcome bundles."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from autopilot.api.deps import get_config
from autopilot.core.execution_outcomes import (
    build_execution_proof_bundle,
    execution_outcome_path,
    find_project_by_execution_brief_id,
    load_execution_outcome_bundle,
    refresh_execution_outcome_bundle,
)
from autopilot.core.shared_contract_codec import dump_shared_contract

router = APIRouter()


@router.get("/{brief_id}")
async def get_execution_outcome(brief_id: str) -> dict[str, object]:
    config = get_config()
    bundle = load_execution_outcome_bundle(config, brief_id)
    if bundle is None:
        bundle = refresh_execution_outcome_bundle(config, brief_id)
    if bundle is None:
        raise HTTPException(404, f"Execution outcome for brief {brief_id} not found")

    project = find_project_by_execution_brief_id(config, brief_id)
    return {
        "status": "ok",
        "brief_id": brief_id,
        "project_id": str((project or {}).get("id") or ""),
        "path": str(execution_outcome_path(config, brief_id)),
        "bundle": dump_shared_contract(bundle),
    }


@router.get("/{brief_id}/proof")
async def get_execution_proof_bundle(brief_id: str) -> dict[str, object]:
    """Return a founder-grade proof bundle aggregating outcomes, tests, CI, approvals."""
    config = get_config()
    proof = build_execution_proof_bundle(config, brief_id)
    if proof is None:
        raise HTTPException(404, f"Proof bundle for brief {brief_id} not found")
    return {"status": "ok", "proof_bundle": proof}

