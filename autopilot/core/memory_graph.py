"""Simple graph memory derived from distilled session memory."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json
from autopilot.core.session_memory import load_session_memory, memory_root


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_atomic_write_json(path, payload)


class MemoryGraphNode(BaseModel):
    node_id: str
    kind: str
    label: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryGraphEdge(BaseModel):
    source_id: str
    target_id: str
    relation: str


class MemoryGraph(BaseModel):
    version: int = 1
    updated_at: str = Field(default_factory=_utcnow_iso)
    nodes: list[MemoryGraphNode] = Field(default_factory=list)
    edges: list[MemoryGraphEdge] = Field(default_factory=list)


def memory_graph_path(project_path: Path) -> Path:
    return memory_root(project_path) / "memory-graph.json"


def load_memory_graph(project_path: Path) -> MemoryGraph:
    path = memory_graph_path(project_path)
    if not path.exists():
        return MemoryGraph()
    try:
        return MemoryGraph.model_validate_json(path.read_text())
    except Exception:
        return MemoryGraph()


def save_memory_graph(project_path: Path, graph: MemoryGraph) -> MemoryGraph:
    updated = graph.model_copy(update={"updated_at": _utcnow_iso()})
    _atomic_write_json(memory_graph_path(project_path), updated.model_dump())
    return updated


def rebuild_memory_graph(project_path: Path) -> MemoryGraph:
    """Rebuild a lightweight task/decision/tool/failure/fix graph from memory state."""

    state = load_session_memory(project_path)
    nodes: dict[str, MemoryGraphNode] = {}
    edges: dict[tuple[str, str, str], MemoryGraphEdge] = {}

    def ensure_node(node_id: str, kind: str, label: str, metadata: dict[str, Any] | None = None) -> None:
        nodes[node_id] = MemoryGraphNode(
            node_id=node_id,
            kind=kind,
            label=label,
            metadata=dict(metadata or {}),
        )

    def ensure_edge(source_id: str, target_id: str, relation: str) -> None:
        edges[(source_id, target_id, relation)] = MemoryGraphEdge(
            source_id=source_id,
            target_id=target_id,
            relation=relation,
        )

    for record in state.memories:
        node_kind = "memory"
        if "failure" in record.tags:
            node_kind = "failure"
        elif "verified_fix" in record.tags:
            node_kind = "verified_fix"
        elif "decision" in record.tags:
            node_kind = "decision"
        ensure_node(record.memory_id, node_kind, record.title, metadata=record.metadata)
        if record.story_id is not None:
            story_id = f"story-{record.story_id}"
            ensure_node(story_id, "task", f"Story #{record.story_id}")
            ensure_edge(record.memory_id, story_id, "about_story")
        tool_name = str(record.metadata.get("tool_name") or "").strip()
        if tool_name:
            tool_id = f"tool-{tool_name}"
            ensure_node(tool_id, "tool", tool_name)
            ensure_edge(record.memory_id, tool_id, "mentions_tool")

    for skill in state.skills:
        ensure_node(skill.skill_id, "skill", skill.label, metadata=skill.metadata)
        if skill.story_id is not None:
            story_id = f"story-{skill.story_id}"
            ensure_node(story_id, "task", f"Story #{skill.story_id}")
            ensure_edge(skill.skill_id, story_id, "learned_from_story")

    graph = MemoryGraph(nodes=list(nodes.values()), edges=list(edges.values()))
    return save_memory_graph(project_path, graph)


def build_memory_graph_snapshot(project_path: Path) -> dict[str, Any]:
    graph = load_memory_graph(project_path)
    kind_counts: dict[str, int] = {}
    for node in graph.nodes:
        kind_counts[node.kind] = kind_counts.get(node.kind, 0) + 1
    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "node_kind_counts": kind_counts,
        "updated_at": graph.updated_at,
    }


__all__ = [
    "MemoryGraph",
    "MemoryGraphEdge",
    "MemoryGraphNode",
    "build_memory_graph_snapshot",
    "load_memory_graph",
    "memory_graph_path",
    "rebuild_memory_graph",
    "save_memory_graph",
]
