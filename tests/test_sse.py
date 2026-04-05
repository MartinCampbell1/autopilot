"""Tests for the in-memory SSE broadcaster."""

from __future__ import annotations

from autopilot.api.sse import SSEBroadcaster


async def test_sse_broadcaster_injects_sequence_and_replay_id() -> None:
    broadcaster = SSEBroadcaster(replay_capacity=8)

    await broadcaster.broadcast("project_created", {"project_id": "proj_1"})

    replayed = broadcaster._select_replay_events(from_sequence=0)

    assert len(replayed) == 1
    assert replayed[0].event == "project_created"
    assert replayed[0].sequence == 1
    assert replayed[0].event_id == "evt_1"
    assert replayed[0].data["event_id"] == "evt_1"
    assert replayed[0].data["sequence"] == 1


async def test_sse_broadcaster_replays_only_items_after_sequence_cursor() -> None:
    broadcaster = SSEBroadcaster(replay_capacity=8)

    await broadcaster.broadcast("project_created", {"project_id": "proj_1"})
    await broadcaster.broadcast("run_started", {"project_id": "proj_1"})

    replayed = broadcaster._select_replay_events(from_sequence=1)

    assert [item.event for item in replayed] == ["run_started"]
    assert replayed[0].sequence == 2


async def test_sse_broadcaster_replays_only_items_after_evt_cursor() -> None:
    broadcaster = SSEBroadcaster(replay_capacity=8)

    await broadcaster.broadcast("project_created", {"project_id": "proj_1"})
    await broadcaster.broadcast("run_started", {"project_id": "proj_1"})
    await broadcaster.broadcast("run_finished", {"project_id": "proj_1"})

    replayed = broadcaster._select_replay_events(last_event_id="evt_2")

    assert [item.event for item in replayed] == ["run_finished"]
    assert replayed[0].sequence == 3
