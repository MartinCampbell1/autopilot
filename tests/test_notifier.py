"""Tests for notification system."""

from autopilot.core.notifier import Notifier, format_complete_message, format_stuck_message


class TestNotifier:
    def test_format_stuck_message(self) -> None:
        msg = format_stuck_message(
            project_name="uptime-monitor",
            story_id=3,
            story_title="OAuth login",
            reason="Critic gave same feedback 3 times",
            last_feedback="callback URL is hardcoded",
        )
        assert "uptime-monitor" in msg
        assert "OAuth login" in msg
        assert "hardcoded" in msg

    def test_format_complete_message(self) -> None:
        msg = format_complete_message(
            project_name="uptime-monitor",
            stories_done=5,
            stories_total=6,
            stories_stuck=1,
        )
        assert "5/6" in msg
        assert "uptime-monitor" in msg

    def test_notifier_disabled_without_token(self) -> None:
        notifier = Notifier(telegram_token=None, telegram_chat_id=None)
        assert notifier.enabled is False
