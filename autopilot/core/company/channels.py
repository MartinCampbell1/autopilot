"""Channel builders for the always-on company shell."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig, NotificationChannelConfig
from autopilot.core.notifiers import channel_ready
from autopilot.core.runtime_control import build_runtime_control_channel_status
from autopilot.core.team_messages import load_team_messages, team_messages_path

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    normalized = _NON_ALNUM.sub("-", str(value or "").strip().lower()).strip("-")
    return normalized or "channel"


def _target_for_channel(channel: NotificationChannelConfig) -> str:
    kind = str(channel.kind or "").strip().lower()
    if kind == "telegram":
        return str(channel.chat_id or channel.chat_id_env or "telegram-chat").strip()
    if kind in {"slack_webhook", "webhook"}:
        return str(channel.webhook_url_env or channel.webhook_url or "configured-webhook").strip()
    if kind == "email":
        return ", ".join(channel.email_to) or str(channel.smtp_host or "email").strip()
    if kind == "script":
        return " ".join(channel.command[:2]) or "configured-script"
    return kind or "channel"


def _status_for_channel(channel: NotificationChannelConfig, ready: bool) -> str:
    if not channel.enabled:
        return "disabled"
    if ready:
        return "ready"
    return "needs_secret"


def build_company_channels(
    config: AutopilotConfig,
    *,
    project_id: str,
    project_path: Path | str,
    runtime_session_id: str = "",
    runtime_control_available: bool = False,
) -> dict[str, Any]:
    """Build company channels without introducing a side-channel runtime."""

    normalized_project_path = Path(project_path).expanduser().resolve()
    team_messages = load_team_messages(normalized_project_path)
    team_channel_path = team_messages_path(normalized_project_path)
    items: list[dict[str, Any]] = [
        {
            "id": "dashboard",
            "name": "Workspace dashboard",
            "kind": "dashboard",
            "enabled": True,
            "ready": True,
            "status": "ready",
            "target": f"/projects/{project_id}",
            "events": ["launch", "resume", "pause", "review", "ship"],
            "capabilities": ["interactive", "approvals", "quarantine_review"],
            "approval_capable": True,
            "wall_enforced": True,
            "message_count": 0,
            "note": "Primary interactive operator channel inside the existing dashboard shell.",
        },
        build_runtime_control_channel_status(
            project_id=project_id,
            runtime_session_id=runtime_session_id,
            runtime_control_available=runtime_control_available,
        ),
        {
            "id": "team_messages",
            "name": "Teammate channel",
            "kind": "workspace_file",
            "enabled": True,
            "ready": True,
            "status": "ready",
            "target": str(team_channel_path),
            "events": ["coordination"],
            "capabilities": ["worker_coordination"],
            "approval_capable": False,
            "wall_enforced": True,
            "message_count": len(team_messages),
            "note": "Explicit teammate-visible channel for persistent coworker coordination.",
        },
    ]

    for channel in config.notifications:
        ready = channel_ready(channel)
        items.append(
            {
                "id": f"notify-{_slug(channel.name)}",
                "name": str(channel.name or "Notification channel").strip() or "Notification channel",
                "kind": str(channel.kind or "").strip().lower() or "notification",
                "enabled": bool(channel.enabled),
                "ready": ready,
                "status": _status_for_channel(channel, ready),
                "target": _target_for_channel(channel),
                "events": list(channel.events or []),
                "capabilities": ["notify"],
                "approval_capable": False,
                "wall_enforced": True,
                "message_count": 0,
                "note": "Notification-only channel. Decisions still must flow through the dashboard or runtime-control wall.",
            }
        )

    ready_count = sum(1 for item in items if bool(item.get("ready")))
    approval_capable_count = sum(1 for item in items if bool(item.get("approval_capable")))
    interactive_count = sum(1 for item in items if str(item.get("kind") or "") in {"dashboard", "runtime_control"})
    return {
        "items": items,
        "summary": {
            "channel_count": len(items),
            "ready_count": ready_count,
            "approval_capable_count": approval_capable_count,
            "interactive_count": interactive_count,
        },
    }

