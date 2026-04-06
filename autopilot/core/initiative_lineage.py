"""Cross-plane initiative lineage — aggregate read model.

Tracks the full lifecycle of an initiative across Quorum (discovery) and
Autopilot (execution).  Persisted as a JSON file per initiative_id under
``{autopilot_home}/initiative-lineage/{initiative_id}.json``.

This is deliberately a simple file-based store.  It can be upgraded to a
database-backed store later without changing the API surface.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from founderos_contracts.lifecycle import (
    InitiativeLineage,
)

from autopilot.core.atomic_io import atomic_write_json
from autopilot.core.config import AutopilotConfig


def _lineage_dir(config: AutopilotConfig) -> Path:
    return Path(config.autopilot_home) / "initiative-lineage"


def _lineage_path(config: AutopilotConfig, initiative_id: str) -> Path:
    return _lineage_dir(config) / f"{initiative_id}.json"


def load_initiative_lineage(
    config: AutopilotConfig, initiative_id: str
) -> InitiativeLineage | None:
    """Load a persisted lineage record, or None if it doesn't exist."""
    path = _lineage_path(config, initiative_id)
    if not path.exists():
        return None
    try:
        return InitiativeLineage.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def persist_initiative_lineage(
    config: AutopilotConfig, lineage: InitiativeLineage
) -> Path:
    """Create or overwrite a lineage record."""
    lineage.updated_at = datetime.now(timezone.utc)
    path = _lineage_path(config, lineage.initiative_id)
    atomic_write_json(path, lineage.model_dump(mode="json"))
    return path


def upsert_initiative_lineage(
    config: AutopilotConfig,
    initiative_id: str,
    **updates: Any,
) -> InitiativeLineage:
    """Load-or-create a lineage record and apply partial updates.

    Accepted keyword arguments correspond to ``InitiativeLineage`` fields
    (e.g. ``brief_id``, ``project_id``, ``lifecycle_state``).
    """
    existing = load_initiative_lineage(config, initiative_id)
    if existing is None:
        existing = InitiativeLineage(initiative_id=initiative_id)

    # Apply updates via model_copy for immutability
    lineage = existing.model_copy(update=updates)
    persist_initiative_lineage(config, lineage)
    return lineage


def build_initiative_aggregate(
    config: AutopilotConfig, initiative_id: str
) -> dict[str, Any] | None:
    """Build a founder-facing aggregate view of one initiative.

    Returns a dict combining lineage metadata with project detail (if available)
    and outcome summary (if available).  Returns None if no lineage exists.
    """
    lineage = load_initiative_lineage(config, initiative_id)
    if lineage is None:
        return None

    aggregate: dict[str, Any] = {
        "initiative_id": lineage.initiative_id,
        "lifecycle_state": lineage.lifecycle_state.value,
        "current_mode": lineage.current_mode.value,
        "lineage": lineage.model_dump(mode="json"),
    }

    # Enrich with project detail if linked
    if lineage.project_id:
        try:
            from autopilot.core.project_store import build_project_detail
            project = build_project_detail(config, lineage.project_id)
            if project:
                aggregate["project"] = project
        except Exception:
            pass

    # Enrich with outcome bundle if available
    if lineage.brief_id:
        try:
            from autopilot.core.execution_outcomes import load_execution_outcome_bundle
            outcome = load_execution_outcome_bundle(config, lineage.brief_id)
            if outcome is not None:
                from autopilot.core.shared_contract_codec import dump_shared_contract
                aggregate["outcome"] = dump_shared_contract(outcome)
        except Exception:
            pass

    return aggregate


def list_initiative_lineages(config: AutopilotConfig) -> list[InitiativeLineage]:
    """List all persisted lineage records."""
    lineage_dir = _lineage_dir(config)
    if not lineage_dir.exists():
        return []
    records: list[InitiativeLineage] = []
    for path in sorted(lineage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            records.append(InitiativeLineage.model_validate(json.loads(path.read_text())))
        except Exception:
            continue
    return records
