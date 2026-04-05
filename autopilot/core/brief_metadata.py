"""Helpers for execution-brief control-plane metadata across project types."""

from __future__ import annotations

from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import load_projects_registry


def get_execution_brief_v2_metadata(project: dict[str, Any]) -> dict[str, Any]:
    """Return normalized V2 brief metadata from one project entry."""

    return dict((project.get("control_plane") or {}).get("execution_brief_v2") or {})


def get_execution_brief_project_metadata(project: dict[str, Any]) -> dict[str, Any]:
    """Return normalized brief metadata for either canonical V2 or legacy shared briefs."""

    control_plane = dict(project.get("control_plane") or {})

    v2 = dict(control_plane.get("execution_brief_v2") or {})
    brief_id = str(v2.get("brief_id") or "").strip()
    if brief_id:
        initiative_id = str(v2.get("initiative_id") or "").strip()
        return {
            "kind": "v2",
            "brief_id": brief_id,
            "idea_id": initiative_id,
            "initiative_id": initiative_id,
            "brief_approval_status": str(v2.get("brief_approval_status") or "").strip(),
            "founder_approval_required": bool(v2.get("founder_approval_required")),
        }

    shared = dict(control_plane.get("shared_execution_brief") or {})
    brief_id = str(shared.get("brief_id") or "").strip()
    if brief_id:
        idea_id = str(shared.get("idea_id") or "").strip()
        return {
            "kind": "shared",
            "brief_id": brief_id,
            "idea_id": idea_id,
            "initiative_id": idea_id,
            "brief_approval_status": "",
            "founder_approval_required": False,
        }

    return {}


def find_project_by_execution_brief_id(
    config: AutopilotConfig,
    brief_id: str,
) -> dict[str, Any] | None:
    """Locate one registered project by shared or V2 brief id."""

    normalized = str(brief_id or "").strip()
    if not normalized:
        return None
    for project in load_projects_registry(config, include_archived=True):
        metadata = get_execution_brief_project_metadata(project)
        if str(metadata.get("brief_id") or "").strip() == normalized:
            return project
    return None


def raise_if_founder_approval_missing_for_project(project: dict[str, Any]) -> None:
    """Block launch for V2 projects that still require founder approval."""

    metadata = get_execution_brief_v2_metadata(project)
    if not metadata:
        return

    approval_status = str(metadata.get("brief_approval_status") or "").strip()
    founder_required = bool(metadata.get("founder_approval_required"))
    if founder_required and approval_status != "approved":
        raise ValueError(
            "Brief must be approved by founder before launch. "
            f"Current status: {approval_status or 'unknown'}"
        )
