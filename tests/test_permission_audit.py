"""Tests for permission audit trail helpers."""

from __future__ import annotations

from pathlib import Path

from autopilot.core.config import AutopilotConfig
from autopilot.core.permission_audit import (
    append_permission_audit_entry,
    build_permission_audit_summary,
    read_permission_audit_entries,
)
from autopilot.core.tool_contracts import ToolResult, build_tool
from autopilot.core.tool_permissions import PermissionDecision


def test_append_and_read_permission_audit_entries(tmp_path: Path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    tool = build_tool(
        name="shell_exec",
        description="Run shell commands.",
        approval_policy="policy",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=dict(tool_input)),
        metadata={"command": "git status"},
    )

    append_permission_audit_entry(
        config,
        project_id="proj_demo",
        tool=tool,
        tool_input={"command": "git status --short", "cwd": "/tmp/demo"},
        decision=PermissionDecision(
            behavior="ask",
            message="Approval required.",
            reasons=["Approval required."],
            rule_source="workspace_policy",
            matched_rule="shell_exec(git status)",
        ),
        actor="tester",
        source="unit_test",
    )

    entries = read_permission_audit_entries(config, "proj_demo")
    summary = build_permission_audit_summary(entries)

    assert len(entries) == 1
    assert entries[0]["projected_command"] == "git status --short"
    assert entries[0]["input_keys"] == ["command", "cwd"]
    assert entries[0]["actor"] == "tester"
    assert summary["by_behavior"]["ask"] == 1
    assert summary["by_source"]["workspace_policy"] == 1
