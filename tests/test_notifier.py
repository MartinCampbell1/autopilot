"""Tests for notification system."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from autopilot.core.config import AutopilotConfig, NotificationChannelConfig
from autopilot.core.notifier import Notifier, format_complete_message, format_stuck_message
from autopilot.core.notifiers import (
    build_notification_envelope,
    build_notification_manager,
    dispatch_project_event_notification,
    format_notification_message,
)


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


def test_notification_manager_uses_env_fallback(monkeypatch) -> None:
    monkeypatch.setenv("AUTOPILOT_TELEGRAM_TOKEN", "token")
    monkeypatch.setenv("AUTOPILOT_TELEGRAM_CHAT_ID", "chat")

    manager = build_notification_manager(AutopilotConfig())

    assert manager.enabled is True
    assert manager.channels[0].kind == "telegram"


def test_format_notification_message_uses_complete_summary() -> None:
    envelope = build_notification_envelope(
        project_entry={"id": "demo", "name": "Demo", "path": "/tmp/demo"},
        state={
            "story_state": {
                "1": {"status": "done"},
                "2": {"status": "stuck"},
            }
        },
        event_record={
            "event": "run_completed",
            "status": "done",
            "project_id": "demo",
            "message": "All stories complete!",
            "timestamp": "2026-03-31T00:00:00Z",
        },
        story_title=None,
    )

    message = format_notification_message(envelope)

    assert "PARTIAL - Demo" in message
    assert "Stories: 1/2 done" in message


def test_dispatch_project_event_notification_posts_webhook(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        notifications=[
            NotificationChannelConfig(
                name="ops-webhook",
                kind="webhook",
                events=["story_stuck"],
                webhook_url="https://example.test/hooks/autopilot",
            )
        ],
    )
    project_dir = tmp_path / "project"
    project_dir.mkdir(parents=True)
    project_entry = {"id": "proj_demo", "name": "Demo", "path": str(project_dir)}
    event_record = {
        "event": "story_stuck",
        "status": "stuck",
        "project_id": "proj_demo",
        "story_id": 7,
        "message": "Gate kept failing.",
        "timestamp": "2026-03-31T00:00:00Z",
        "stuck_summary": "Gate kept failing.",
    }
    state = {"story_state": {"7": {"status": "stuck"}}}
    captured: dict[str, object] = {}

    class _Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    def fake_urlopen(request, timeout=10):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    delivered = dispatch_project_event_notification(
        config,
        project_entry=project_entry,
        state=state,
        event_record=event_record,
        story_title="Build dashboard",
    )

    assert delivered is True
    assert captured["url"] == "https://example.test/hooks/autopilot"
    assert captured["payload"]["event"] == "story_stuck"
    assert captured["payload"]["story_title"] == "Build dashboard"


def test_dispatch_project_event_notification_runs_script(monkeypatch, tmp_path: Path) -> None:
    config = AutopilotConfig(
        notifications=[
            NotificationChannelConfig(
                name="script",
                kind="script",
                events=["story_stuck"],
                command=["/bin/echo", "notify"],
            )
        ]
    )
    event_record = {
        "event": "story_stuck",
        "status": "stuck",
        "project_id": "proj_demo",
        "story_id": 2,
        "message": "Blocked.",
        "timestamp": "2026-03-31T00:00:00Z",
    }
    called = MagicMock(return_value=MagicMock(returncode=0))
    monkeypatch.setattr("subprocess.run", called)

    delivered = dispatch_project_event_notification(
        config,
        project_entry={"id": "proj_demo", "name": "Demo", "path": str(tmp_path / "project")},
        state={"story_state": {"2": {"status": "stuck"}}},
        event_record=event_record,
        story_title="Fix auth",
    )

    assert delivered is True
    payload = json.loads(called.call_args.kwargs["input"])
    assert payload["event"] == "story_stuck"
    assert payload["story_title"] == "Fix auth"
