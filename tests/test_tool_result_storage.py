"""Tests for disk-backed tool result storage."""

import json
from pathlib import Path

from autopilot.core.artifact_store import get_artifact, read_artifact_text
from autopilot.core.config import AutopilotConfig
from autopilot.core.orchestrator_sessions import create_orchestrator_session, get_orchestrator_session
from autopilot.core.tool_contracts import ToolResult, ToolUseContext
from autopilot.core.tool_result_storage import store_large_tool_result


def test_store_large_tool_result_keeps_small_payload_inline(tmp_path: Path) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        tool_result_inline_bytes_limit=4096,
    )
    result = ToolResult(status="ok", payload={"value": "small"})

    stored = store_large_tool_result("demo.small", result, ToolUseContext(config=config, project_id="proj_small"))

    assert stored.payload == {"value": "small"}
    assert stored.metadata == {}


def test_store_large_tool_result_writes_json_reference(tmp_path: Path) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        tool_result_inline_bytes_limit=128,
        tool_result_preview_chars=80,
    )
    result = ToolResult(
        status="ok",
        message="done",
        payload={"rows": ["y" * 60 for _ in range(8)]},
    )

    stored = store_large_tool_result("demo.big", result, ToolUseContext(config=config, project_id="proj_big"))

    assert stored.payload["stored_result"] is True
    assert stored.payload["stored_result_artifact_id"]
    stored_path = Path(stored.payload["stored_result_path"])
    manifest_path = Path(stored.payload["stored_result_manifest_path"])
    assert stored_path.exists()
    assert manifest_path.exists()
    assert stored.payload["stored_result_stage"] == "temporary"
    assert stored.metadata["stored_result_bytes"] > config.tool_result_inline_bytes_limit
    assert '"rows"' in stored_path.read_text()
    artifact = get_artifact(config, stored.payload["stored_result_artifact_id"])
    assert artifact is not None
    assert artifact.artifact_type == "tool_result"
    assert artifact.stage == "temporary"
    assert json.loads(read_artifact_text(config, artifact.id))["tool_name"] == "demo.big"


def test_store_large_tool_result_links_artifact_to_orchestrator_session(tmp_path: Path) -> None:
    config = AutopilotConfig(
        autopilot_home_override=str(tmp_path / ".autopilot"),
        tool_result_inline_bytes_limit=128,
    )
    session = create_orchestrator_session(
        config,
        orchestrator="founderos",
        actor="founderos",
        project_ids=["proj_big"],
        title="Tool artifacts",
    )
    result = ToolResult(status="ok", payload={"rows": ["z" * 60 for _ in range(8)]})

    stored = store_large_tool_result(
        "demo.big",
        result,
        ToolUseContext(config=config, project_id="proj_big", orchestrator_session_id=session.id, runtime_agent_ids=("agt_1",)),
    )
    linked = get_orchestrator_session(config, session.id)

    assert linked is not None
    assert stored.payload["stored_result_artifact_id"] in linked.linked_artifact_ids
