"""Always-on company shell builders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autopilot.core.company.channels import build_company_channels
from autopilot.core.company.goals import build_company_goals
from autopilot.core.company.live_events import build_company_live_events
from autopilot.core.company.routines import build_company_routines
from autopilot.core.company.secrets import build_company_secret_status
from autopilot.core.config import AutopilotConfig


def build_company_shell(
    config: AutopilotConfig,
    *,
    project: dict[str, Any],
    prd: dict[str, Any],
    stories: list[dict[str, Any]],
    state: dict[str, Any],
    delivery_status: dict[str, Any],
    latest_handoff: dict[str, Any] | None = None,
    bootstrap: dict[str, Any] | None = None,
    runtime_diagnostics: dict[str, Any] | None = None,
    runtime_control: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the always-on company shell payload for one project."""

    normalized_bootstrap = dict(bootstrap or {})
    normalized_runtime_diagnostics = dict(runtime_diagnostics or {})
    runtime_session_id = str(state.get("runtime_session_id") or "").strip()
    runtime_control_available = bool(
        runtime_session_id
        and str(state.get("status") or "").strip() == "running"
        and not bool(state.get("paused"))
    )
    channels = build_company_channels(
        config,
        project_id=str(project.get("id") or "").strip(),
        project_path=Path(str(project.get("path") or "")).expanduser(),
        runtime_session_id=runtime_session_id,
        runtime_control_available=runtime_control_available,
    )
    secrets = build_company_secret_status(config)
    goals = build_company_goals(project=project, prd=prd, stories=stories, state=state)
    routines = build_company_routines(
        project=project,
        state=state,
        delivery_status=delivery_status,
        latest_handoff=latest_handoff,
        bootstrap=normalized_bootstrap,
        runtime_diagnostics=normalized_runtime_diagnostics,
        runtime_control_available=runtime_control_available,
        channels=channels,
        secrets=secrets,
    )
    live_events = build_company_live_events(
        config,
        project_id=str(project.get("id") or "").strip(),
        state=state,
        runtime_session_id=runtime_session_id,
        runtime_control=runtime_control,
    )
    return {
        "status": {
            "always_on_ready": bool(goals.get("items")) and bool(routines.get("items")) and int(dict(channels.get("summary") or {}).get("ready_count") or 0) > 0,
            "runtime_wall_enforced": True,
            "runtime_control_available": runtime_control_available,
            "goal_count": int(dict(goals.get("summary") or {}).get("goal_count") or 0),
            "active_routine_count": int(dict(routines.get("summary") or {}).get("active_count") or 0),
            "ready_channel_count": int(dict(channels.get("summary") or {}).get("ready_count") or 0),
            "missing_secret_count": int(dict(secrets.get("summary") or {}).get("missing_count") or 0),
            "live_event_count": int(dict(live_events.get("summary") or {}).get("event_count") or 0),
        },
        "goals": goals,
        "routines": routines,
        "channels": channels,
        "secrets": secrets,
        "live_events": live_events,
    }


__all__ = ["build_company_shell"]

