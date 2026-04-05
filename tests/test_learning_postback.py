"""Tests for LearningPostback — outcome postback to Quorum."""
from __future__ import annotations

from autopilot.core.learning_postback import LearningPostback, PostbackConfig


def test_postback_config_defaults() -> None:
    config = PostbackConfig()

    assert config.quorum_feedback_base_url is None
    assert config.retry_max == 3
    assert config.idempotency_enabled is True


def test_postback_skips_when_no_quorum_url() -> None:
    import asyncio

    config = PostbackConfig(quorum_feedback_base_url=None)
    postback = LearningPostback(config)

    result = asyncio.run(
        postback.maybe_post_outcome(
            idea_id="idea-001",
            outcome={"outcome_id": "out-001"},
            project_id="proj-001",
            project_name="test",
        )
    )

    assert result["sent"] is False
    assert result["reason"] == "no_quorum_url"


def test_postback_sends_to_correct_endpoint() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    config = PostbackConfig(quorum_feedback_base_url="http://localhost:8000/api/orchestrate")
    postback = LearningPostback(config)
    captured = {}

    async def mock_post(url, **kwargs):
        captured["url"] = url
        captured["payload"] = kwargs.get("json")
        resp = AsyncMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        resp.json.return_value = {"status": "ok"}
        return resp

    async def _run():
        with patch("autopilot.core.learning_postback.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = mock_post
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client
            return await postback.maybe_post_outcome(
                idea_id="idea-001",
                outcome={"outcome_id": "out-001"},
                project_id="proj-001",
                project_name="test",
            )

    result = asyncio.run(_run())
    assert result["sent"] is True
    assert "/discovery/ideas/idea-001/execution-feedback" in captured["url"]


def test_postback_idempotency_prevents_duplicate() -> None:
    import asyncio
    from unittest.mock import AsyncMock, patch

    config = PostbackConfig(quorum_feedback_base_url="http://localhost:8000/api/orchestrate")
    postback = LearningPostback(config)

    async def mock_post(url, **kwargs):
        resp = AsyncMock()
        resp.status_code = 200
        resp.raise_for_status = lambda: None
        resp.json.return_value = {"status": "ok"}
        return resp

    async def _run_first():
        with patch("autopilot.core.learning_postback.httpx.AsyncClient") as mock_cls:
            client = AsyncMock()
            client.post = mock_post
            client.__aenter__ = AsyncMock(return_value=client)
            client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = client
            return await postback.maybe_post_outcome(
                idea_id="idea-001",
                outcome={"outcome_id": "out-001"},
                project_id="proj-001",
                project_name="test",
            )

    async def _run_second():
        return await postback.maybe_post_outcome(
            idea_id="idea-001",
            outcome={"outcome_id": "out-001"},
            project_id="proj-001",
            project_name="test",
        )

    first = asyncio.run(_run_first())
    assert first["sent"] is True

    second = asyncio.run(_run_second())
    assert second["sent"] is False
    assert second["reason"] == "already_sent"
    assert "idempotency_key" in second


import threading
from unittest.mock import AsyncMock, patch


def test_dispatch_from_sync_context_no_runtime_warning():
    """dispatch_learning_postback from sync context must not leave unawaited coroutines."""
    import time
    from autopilot.core.learning_postback import dispatch_learning_postback

    with patch(
        "autopilot.core.learning_postback.auto_post_learning_outcome",
        new=AsyncMock(return_value={"sent": True}),
    ):
        dispatch_learning_postback(
            idea_id="test-idea",
            outcome={"outcome_id": "o1"},
            project_id="proj-1",
            project_name="Test",
        )
    time.sleep(0.5)


def test_dispatch_calls_on_success_callback():
    """on_success callback fires when postback succeeds."""
    from autopilot.core.learning_postback import dispatch_learning_postback

    success_called = threading.Event()

    with patch(
        "autopilot.core.learning_postback.auto_post_learning_outcome",
        new=AsyncMock(return_value={"sent": True}),
    ):
        dispatch_learning_postback(
            idea_id="test-idea",
            outcome={"outcome_id": "o1"},
            project_id="proj-1",
            project_name="Test",
            on_success=lambda: success_called.set(),
        )
        assert success_called.wait(timeout=3.0), "on_success was not called within timeout"
