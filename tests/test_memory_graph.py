"""Tests for graph memory derived from session memory."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.knowledge_distiller import distill_session_memory
from autopilot.core.memory_graph import build_memory_graph_snapshot, load_memory_graph
from autopilot.core.session_memory import append_working_log


def test_memory_graph_tracks_tasks_tools_failures_and_verified_fixes(tmp_path: Path) -> None:
    append_working_log(
        tmp_path,
        kind="failure",
        summary="Smoke test failed against callback route.",
        story_id=9,
        metadata={"tool_name": "pytest"},
    )
    append_working_log(
        tmp_path,
        kind="verified_fix",
        summary="Verified callback route fix with pytest.",
        story_id=9,
        metadata={"tool_name": "pytest", "story_title": "Repair callback route"},
    )

    distill_session_memory(tmp_path)
    snapshot = build_memory_graph_snapshot(tmp_path)
    graph = load_memory_graph(tmp_path)

    assert snapshot["node_count"] >= 4
    assert snapshot["node_kind_counts"]["task"] >= 1
    assert snapshot["node_kind_counts"]["tool"] >= 1
    assert snapshot["node_kind_counts"]["failure"] >= 1
    assert snapshot["node_kind_counts"]["verified_fix"] >= 1
    assert any(edge.relation == "mentions_tool" for edge in graph.edges)
