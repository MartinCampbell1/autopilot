"""Config-driven notification routing for runtime events."""

from __future__ import annotations

import json
import os
import smtplib
import subprocess
import urllib.request
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any

from autopilot.core.config import AutopilotConfig, NotificationChannelConfig

DEFAULT_NOTIFICATION_EVENTS = frozenset(
    {
        "story_stuck",
        "story_merge_blocked",
        "story_quality_regression",
        "connector_activation_failed",
        "run_blocked",
        "run_failed",
        "run_completed",
        "project_error",
        "project_complete",
        "github_ci_failure",
        "github_review_feedback",
        "github_changes_requested",
        "github_approved_and_green",
    }
)


def format_stuck_message(
    project_name: str,
    story_id: int,
    story_title: str,
    reason: str,
    last_feedback: str,
) -> str:
    return (
        f"STUCK - {project_name}\n\n"
        f"Story #{story_id}: {story_title}\n"
        f"Reason: {reason}\n\n"
        f"Last feedback:\n{last_feedback[:500]}"
    )


def format_complete_message(
    project_name: str,
    stories_done: int,
    stories_total: int,
    stories_stuck: int,
) -> str:
    status = "COMPLETE" if stories_stuck == 0 else "PARTIAL"
    return (
        f"{status} - {project_name}\n\n"
        f"Stories: {stories_done}/{stories_total} done\n"
        f"Stuck: {stories_stuck}"
    )


def format_escalation_message(
    project_name: str,
    story_id: int,
    from_provider: str,
    to_provider: str,
) -> str:
    return f"ESCALATION - {project_name}\n\nStory #{story_id}: {from_provider} -> {to_provider}"


@dataclass
class NotificationEnvelope:
    event: str
    status: str
    project_id: str
    project_name: str
    project_path: str | None
    timestamp: str
    message: str
    story_id: int | None = None
    story_title: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    story_counts: dict[str, int] = field(default_factory=dict)


def _resolve_value(value: str | None, env_name: str | None) -> str | None:
    if value:
        return value
    if env_name:
        return os.getenv(env_name)
    return None


def _resolve_events(channel: NotificationChannelConfig) -> set[str]:
    return {event.strip() for event in (channel.events or list(DEFAULT_NOTIFICATION_EVENTS)) if event.strip()}


def _channel_ready(channel: NotificationChannelConfig) -> bool:
    if not channel.enabled:
        return False
    kind = channel.kind.strip().lower()
    if kind == "telegram":
        return bool(
            _resolve_value(channel.token, channel.token_env or "AUTOPILOT_TELEGRAM_TOKEN")
            and _resolve_value(channel.chat_id, channel.chat_id_env or "AUTOPILOT_TELEGRAM_CHAT_ID")
        )
    if kind in {"slack_webhook", "webhook"}:
        return bool(_resolve_value(channel.webhook_url, channel.webhook_url_env))
    if kind == "email":
        return bool(
            channel.smtp_host
            and channel.email_to
            and (channel.email_from or channel.smtp_username)
            and (channel.smtp_username is None or _resolve_value(channel.smtp_password, channel.smtp_password_env))
        )
    if kind == "script":
        return bool(channel.command)
    return False


def channel_ready(channel: NotificationChannelConfig) -> bool:
    """Public helper for readiness checks without dispatch side effects."""
    return _channel_ready(channel)


def load_notification_channels(config: AutopilotConfig) -> list[NotificationChannelConfig]:
    channels = [channel for channel in config.notifications if _channel_ready(channel)]
    if channels:
        return channels
    fallback = NotificationChannelConfig(
        name="telegram",
        kind="telegram",
        token_env="AUTOPILOT_TELEGRAM_TOKEN",
        chat_id_env="AUTOPILOT_TELEGRAM_CHAT_ID",
    )
    return [fallback] if _channel_ready(fallback) else []


def build_notification_envelope(
    *,
    project_entry: dict[str, Any],
    state: dict[str, Any],
    event_record: dict[str, Any],
    story_title: str | None,
) -> NotificationEnvelope:
    story_states = list((state.get("story_state") or {}).values())
    stories_done = sum(1 for item in story_states if item.get("status") in {"done", "skipped"})
    stories_stuck = sum(1 for item in story_states if item.get("status") in {"stuck", "merge_blocked"})
    return NotificationEnvelope(
        event=str(event_record.get("event") or ""),
        status=str(event_record.get("status") or "info"),
        project_id=str(event_record.get("project_id") or project_entry["id"]),
        project_name=str(project_entry.get("name") or project_entry["id"]),
        project_path=str(project_entry.get("path")) if project_entry.get("path") else None,
        timestamp=str(event_record.get("timestamp") or ""),
        message=str(event_record.get("message") or ""),
        story_id=event_record.get("story_id"),
        story_title=story_title,
        extra={
            key: value
            for key, value in event_record.items()
            if key not in {"event", "status", "project_id", "story_id", "message", "timestamp"}
        },
        story_counts={
            "done": stories_done,
            "total": len(story_states),
            "stuck": stories_stuck,
        },
    )


def _generic_notification_message(envelope: NotificationEnvelope) -> str:
    title = envelope.event.replace("_", " ").upper()
    lines = [f"{title} - {envelope.project_name}", ""]
    if envelope.story_id is not None:
        story_label = envelope.story_title or f"Story {envelope.story_id}"
        lines.append(f"Story #{envelope.story_id}: {story_label}")
    lines.append(f"Status: {envelope.status}")
    lines.append(f"Message: {envelope.message}")
    last_feedback = envelope.extra.get("critic_feedback") or envelope.extra.get("stuck_summary")
    if last_feedback:
        lines.extend(["", f"Details:\n{str(last_feedback)[:500]}"])
    return "\n".join(lines)


def format_notification_message(envelope: NotificationEnvelope) -> str:
    if envelope.event == "story_stuck" and envelope.story_id is not None:
        return format_stuck_message(
            project_name=envelope.project_name,
            story_id=envelope.story_id,
            story_title=envelope.story_title or f"Story {envelope.story_id}",
            reason=envelope.message,
            last_feedback=str(envelope.extra.get("critic_feedback") or envelope.extra.get("stuck_summary") or envelope.message),
        )
    if envelope.event in {"run_completed", "project_complete"}:
        counts = envelope.story_counts
        return format_complete_message(
            project_name=envelope.project_name,
            stories_done=int(counts.get("done", 0)),
            stories_total=int(counts.get("total", 0)),
            stories_stuck=int(counts.get("stuck", 0)),
        )
    if envelope.event == "provider_escalated" and envelope.story_id is not None:
        return format_escalation_message(
            project_name=envelope.project_name,
            story_id=envelope.story_id,
            from_provider=str(envelope.extra.get("from_provider") or "unknown"),
            to_provider=str(envelope.extra.get("to_provider") or "unknown"),
        )
    return _generic_notification_message(envelope)


def notification_subject(envelope: NotificationEnvelope, subject_prefix: str | None = None) -> str:
    subject = f"{envelope.project_name}: {envelope.event.replace('_', ' ')}"
    if subject_prefix:
        return f"{subject_prefix} {subject}".strip()
    return subject


def _post_json(url: str, payload: dict[str, Any]) -> bool:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            return 200 <= int(status) < 300
    except Exception:
        return False


def _send_telegram(channel: NotificationChannelConfig, message: str) -> bool:
    token = _resolve_value(channel.token, channel.token_env or "AUTOPILOT_TELEGRAM_TOKEN")
    chat_id = _resolve_value(channel.chat_id, channel.chat_id_env or "AUTOPILOT_TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    return _post_json(
        f"https://api.telegram.org/bot{token}/sendMessage",
        {"chat_id": chat_id, "text": message},
    )


def _send_slack(channel: NotificationChannelConfig, message: str) -> bool:
    webhook_url = _resolve_value(channel.webhook_url, channel.webhook_url_env)
    if not webhook_url:
        return False
    return _post_json(webhook_url, {"text": message})


def _send_webhook(channel: NotificationChannelConfig, envelope: NotificationEnvelope, message: str) -> bool:
    webhook_url = _resolve_value(channel.webhook_url, channel.webhook_url_env)
    if not webhook_url:
        return False
    return _post_json(
        webhook_url,
        {
            "event": envelope.event,
            "status": envelope.status,
            "project_id": envelope.project_id,
            "project_name": envelope.project_name,
            "project_path": envelope.project_path,
            "story_id": envelope.story_id,
            "story_title": envelope.story_title,
            "timestamp": envelope.timestamp,
            "message": envelope.message,
            "formatted_message": message,
            "extra": envelope.extra,
            "story_counts": envelope.story_counts,
        },
    )


def _send_email(channel: NotificationChannelConfig, envelope: NotificationEnvelope, message: str) -> bool:
    if not channel.smtp_host or not channel.email_to:
        return False
    email_message = EmailMessage()
    email_message["Subject"] = notification_subject(envelope, channel.subject_prefix)
    email_message["From"] = channel.email_from or channel.smtp_username or "autopilot@localhost"
    email_message["To"] = ", ".join(channel.email_to)
    email_message.set_content(message)
    password = _resolve_value(channel.smtp_password, channel.smtp_password_env)
    try:
        with smtplib.SMTP(channel.smtp_host, channel.smtp_port, timeout=10) as client:
            client.ehlo()
            if channel.smtp_use_tls:
                client.starttls()
                client.ehlo()
            if channel.smtp_username:
                client.login(channel.smtp_username, password or "")
            client.send_message(email_message)
        return True
    except Exception:
        return False


def _send_script(channel: NotificationChannelConfig, envelope: NotificationEnvelope, message: str) -> bool:
    if not channel.command:
        return False
    payload = {
        "event": envelope.event,
        "status": envelope.status,
        "project_id": envelope.project_id,
        "project_name": envelope.project_name,
        "story_id": envelope.story_id,
        "story_title": envelope.story_title,
        "timestamp": envelope.timestamp,
        "message": envelope.message,
        "formatted_message": message,
        "extra": envelope.extra,
        "story_counts": envelope.story_counts,
    }
    env = {
        **os.environ,
        "AUTOPILOT_NOTIFICATION_EVENT": envelope.event,
        "AUTOPILOT_NOTIFICATION_PROJECT_ID": envelope.project_id,
        "AUTOPILOT_NOTIFICATION_STATUS": envelope.status,
    }
    try:
        completed = subprocess.run(
            channel.command,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=30,
            env=env,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def deliver_channel_message(channel: NotificationChannelConfig, envelope: NotificationEnvelope, message: str) -> bool:
    kind = channel.kind.strip().lower()
    if kind == "telegram":
        return _send_telegram(channel, message)
    if kind == "slack_webhook":
        return _send_slack(channel, message)
    if kind == "webhook":
        return _send_webhook(channel, envelope, message)
    if kind == "email":
        return _send_email(channel, envelope, message)
    if kind == "script":
        return _send_script(channel, envelope, message)
    return False


class NotificationManager:
    """Dispatch one event notification to zero or more configured channels."""

    def __init__(self, channels: list[NotificationChannelConfig]):
        self.channels = channels

    @property
    def enabled(self) -> bool:
        return any(_channel_ready(channel) for channel in self.channels)

    def notify(self, envelope: NotificationEnvelope) -> bool:
        message = format_notification_message(envelope)
        delivered = False
        for channel in self.channels:
            if not _channel_ready(channel):
                continue
            events = _resolve_events(channel)
            if "*" not in events and envelope.event not in events:
                continue
            delivered = deliver_channel_message(channel, envelope, message) or delivered
        return delivered


def build_notification_manager(config: AutopilotConfig) -> NotificationManager:
    return NotificationManager(load_notification_channels(config))


def dispatch_project_event_notification(
    config: AutopilotConfig,
    *,
    project_entry: dict[str, Any],
    state: dict[str, Any],
    event_record: dict[str, Any],
    story_title: str | None = None,
) -> bool:
    manager = build_notification_manager(config)
    if not manager.enabled:
        return False
    envelope = build_notification_envelope(
        project_entry=project_entry,
        state=state,
        event_record=event_record,
        story_title=story_title,
    )
    return manager.notify(envelope)
