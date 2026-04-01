"""Tests for disk-backed tool result storage."""

from pathlib import Path

from autopilot.core.config import AutopilotConfig
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
    stored_path = Path(stored.payload["stored_result_path"])
    assert stored_path.exists()
    assert stored.metadata["stored_result_bytes"] > config.tool_result_inline_bytes_limit
    assert '"rows"' in stored_path.read_text()
