"""Secret-readiness summaries for company channels."""

from __future__ import annotations

import os
from typing import Any

from autopilot.core.config import AutopilotConfig, NotificationChannelConfig


def _secret_refs(channel: NotificationChannelConfig) -> list[tuple[str, str, bool]]:
    kind = str(channel.kind or "").strip().lower()
    refs: list[tuple[str, str, bool]] = []

    if kind == "telegram":
        refs.append(("telegram_token", channel.token_env or "AUTOPILOT_TELEGRAM_TOKEN", bool(channel.token)))
        refs.append(("telegram_chat_id", channel.chat_id_env or "AUTOPILOT_TELEGRAM_CHAT_ID", bool(channel.chat_id)))
    elif kind in {"slack_webhook", "webhook"}:
        refs.append(("webhook_url", channel.webhook_url_env or "AUTOPILOT_WEBHOOK_URL", bool(channel.webhook_url)))
    elif kind == "email" and channel.smtp_username:
        refs.append(("smtp_password", channel.smtp_password_env or "AUTOPILOT_SMTP_PASSWORD", bool(channel.smtp_password)))

    return refs


def build_company_secret_status(config: AutopilotConfig) -> dict[str, Any]:
    """Summarize secret readiness without exposing any secret values."""

    items: list[dict[str, Any]] = []
    for channel in config.notifications:
        refs = _secret_refs(channel)
        if not refs:
            continue

        required_keys: list[str] = []
        resolved_keys: list[str] = []
        missing_keys: list[str] = []
        for _, env_name, inline_present in refs:
            label = str(env_name or "").strip() or "inline"
            required_keys.append(label)
            if inline_present or os.getenv(env_name):
                resolved_keys.append(label)
            else:
                missing_keys.append(label)

        ready = len(missing_keys) == 0
        items.append(
            {
                "id": str(channel.name or channel.kind or "secret").strip().lower().replace(" ", "-"),
                "channel_name": str(channel.name or channel.kind or "channel").strip() or "channel",
                "kind": str(channel.kind or "").strip().lower(),
                "ready": ready,
                "status": "ready" if ready else "missing",
                "required_keys": required_keys,
                "resolved_keys": resolved_keys,
                "missing_keys": missing_keys,
            }
        )

    missing_count = sum(len(item["missing_keys"]) for item in items)
    resolved_count = sum(len(item["resolved_keys"]) for item in items)
    return {
        "items": items,
        "summary": {
            "secret_group_count": len(items),
            "ready_count": sum(1 for item in items if bool(item.get("ready"))),
            "missing_count": missing_count,
            "resolved_count": resolved_count,
        },
    }

