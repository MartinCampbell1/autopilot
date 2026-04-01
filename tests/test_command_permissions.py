"""Tests for permission-mode transition safety helpers."""

from autopilot.core.command_permissions import normalize_permission_mode, sanitize_permission_context_for_mode
from autopilot.core.tool_contracts import ToolPermissionContext


def test_normalize_permission_mode_rejects_unknown_mode() -> None:
    try:
        normalize_permission_mode("godmode")
    except ValueError as exc:
        assert "unsupported permission mode" in str(exc).lower()
    else:
        raise AssertionError("Expected invalid permission mode to raise.")


def test_sanitize_permission_context_for_plan_mode_strips_dangerous_allow_rules() -> None:
    context = ToolPermissionContext(
        mode="plan",
        always_allow_rules={
            "user": [
                "execution.archive",
                "execution.pause",
            ]
        },
    )

    sanitized = sanitize_permission_context_for_mode(context)

    assert sanitized.always_allow_rules["user"] == ["execution.pause"]
    assert "execution.archive" in sanitized.always_ask_rules["project_policy"]
    assert "execution.archive" in sanitized.metadata["mode_transition"]["stripped_allow_rules"]
    assert any("requires approval" in reason.lower() for reason in sanitized.tool_reasons["execution.archive"])
