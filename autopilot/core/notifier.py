"""Telegram notification helpers for autopilot events."""

from __future__ import annotations

import asyncio
import os


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


class Notifier:
    """Send notifications via Telegram when credentials are configured."""

    def __init__(self, telegram_token: str | None = None, telegram_chat_id: str | None = None):
        self.token = telegram_token or os.environ.get("AUTOPILOT_TELEGRAM_TOKEN")
        self.chat_id = telegram_chat_id or os.environ.get("AUTOPILOT_TELEGRAM_CHAT_ID")

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    async def send(self, message: str) -> bool:
        """Send one Telegram message."""
        if not self.enabled:
            return False

        try:
            from telegram import Bot

            bot = Bot(token=self.token)
            await bot.send_message(chat_id=self.chat_id, text=message)
            return True
        except Exception:
            return False

    def send_sync(self, message: str) -> bool:
        """Synchronous wrapper around `send`."""
        if not self.enabled:
            return False
        try:
            return asyncio.run(self.send(message))
        except Exception:
            return False
