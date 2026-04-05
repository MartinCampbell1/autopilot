"""Live activity feed builders for the company shell."""

from __future__ import annotations

from typing import Any

from autopilot.core.audit_chain import read_jsonl_records
from autopilot.core.config import AutopilotConfig


def _kind(payload: dict[str, Any]) -> str:
    for key in ("event", "type", "kind"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    request = payload.get("request")
    if isinstance(request, dict):
        subtype = str(request.get("subtype") or "").strip()
        if subtype:
            return subtype
    return "event"


def _headline(payload: dict[str, Any]) -> str:
    message = str(payload.get("message") or "").strip()
    if message:
        return message[:160]
    kind = _kind(payload).replace("_", " ").strip()
    return kind.capitalize() if kind else "Event"


def _detail(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    story_id = payload.get("story_id")
    if story_id not in (None, ""):
        parts.append(f"Story #{story_id}")
    status = str(payload.get("status") or "").strip()
    if status:
        parts.append(status.replace("_", " "))
    source = str(payload.get("source") or "").strip()
    if source:
        parts.append(source)
    request = payload.get("request")
    if isinstance(request, dict):
        subtype = str(request.get("subtype") or "").strip()
        if subtype:
            parts.append(subtype.replace("_", " "))
    return " · ".join(parts) or "No additional detail."


def _normalize_live_event(payload: dict[str, Any], *, fallback_id: str) -> dict[str, Any]:
    return {
        "id": str(
            payload.get("request_id")
            or payload.get("event_id")
            or payload.get("id")
            or fallback_id
        ).strip(),
        "kind": _kind(payload),
        "timestamp": str(payload.get("timestamp") or "").strip(),
        "headline": _headline(payload),
        "detail": _detail(payload),
        "source": str(payload.get("source") or payload.get("type") or "events_log").strip() or "events_log",
        "story_id": payload.get("story_id"),
        "session_id": str(payload.get("session_id") or payload.get("runtime_session_id") or "").strip(),
    }


def build_company_live_events(
    config: AutopilotConfig,
    *,
    project_id: str,
    state: dict[str, Any],
    runtime_session_id: str = "",
    runtime_control: dict[str, Any] | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    """Build a project-scoped live event feed from the shared event log."""

    normalized_project_id = str(project_id or "").strip()
    normalized_session_id = str(runtime_session_id or "").strip()
    items: list[dict[str, Any]] = []

    for index, record in enumerate(reversed(read_jsonl_records(config.events_log_path)), start=1):
        record_project_id = str(record.get("project_id") or "").strip()
        record_session_id = str(record.get("session_id") or record.get("runtime_session_id") or "").strip()
        if normalized_project_id and record_project_id != normalized_project_id:
            if not normalized_session_id or record_session_id != normalized_session_id:
                continue
        items.append(_normalize_live_event(record, fallback_id=f"event-{index}"))
        if len(items) >= limit:
            break

    if len(items) < limit and runtime_control:
        for story in list(runtime_control.get("stories") or []):
            health = dict(story.get("health") or {})
            issues = [str(issue).strip() for issue in list(health.get("issues") or []) if str(issue).strip()]
            if not issues:
                continue
            items.append(
                {
                    "id": f"checkout-{story.get('story_id')}",
                    "kind": "checkout_health",
                    "timestamp": str(state.get("updated_at") or "").strip(),
                    "headline": f"Story #{story.get('story_id')} checkout {str(health.get('status') or 'degraded')}",
                    "detail": issues[0],
                    "source": "runtime_control",
                    "story_id": story.get("story_id"),
                    "session_id": normalized_session_id,
                }
            )
            if len(items) >= limit:
                break

    if not items:
        for index, event in enumerate(reversed(list(state.get("timeline") or [])[-limit:]), start=1):
            normalized_event = {
                "id": f"timeline-{index}",
                "kind": str(event.get("event") or "timeline_event").strip() or "timeline_event",
                "timestamp": str(event.get("timestamp") or "").strip(),
                "headline": str(event.get("message") or "").strip()[:160] or "Timeline event",
                "detail": str(event.get("status") or "").strip() or "timeline",
                "source": "timeline",
                "story_id": event.get("story_id"),
                "session_id": normalized_session_id,
            }
            items.append(normalized_event)

    return {
        "items": items,
        "summary": {
            "event_count": len(items),
            "latest_timestamp": items[0]["timestamp"] if items else "",
        },
    }

