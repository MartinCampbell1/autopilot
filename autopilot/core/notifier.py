"""Compatibility Telegram notifier wrapper."""

from __future__ import annotations

import asyncio

from autopilot.core.config import NotificationChannelConfig
from autopilot.core.notifiers import (
    channel_ready,
    NotificationEnvelope,
    deliver_channel_message,
    format_complete_message,
    format_escalation_message,
    format_stuck_message,
)

__all__ = [
    "Notifier",
    "format_complete_message",
    "format_escalation_message",
    "format_stuck_message",
]


class Notifier:
    """Send one-off Telegram notifications via the generalized notifier transport."""

    def __init__(self, telegram_token: str | None = None, telegram_chat_id: str | None = None):
        self.channel = NotificationChannelConfig(
            name="telegram",
            kind="telegram",
            token=telegram_token,
            token_env="AUTOPILOT_TELEGRAM_TOKEN",
            chat_id=telegram_chat_id,
            chat_id_env="AUTOPILOT_TELEGRAM_CHAT_ID",
            events=["*"],
        )

    @property
    def enabled(self) -> bool:
        return channel_ready(self.channel)

    async def send(self, message: str) -> bool:
        """Send one Telegram message."""
        if not self.enabled:
            return False
        envelope = NotificationEnvelope(
            event="manual_message",
            status="info",
            project_id="autopilot",
            project_name="Autopilot",
            project_path=None,
            timestamp="",
            message=message,
        )
        return await asyncio.to_thread(deliver_channel_message, self.channel, envelope, message)

    def send_sync(self, message: str) -> bool:
        """Synchronous wrapper around `send`."""
        if not self.enabled:
            return False
        try:
            return asyncio.run(self.send(message))
        except Exception:
            return False
