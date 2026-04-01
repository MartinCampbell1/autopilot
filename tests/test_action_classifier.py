"""Tests for fail-closed projected tool-use classifier."""

from __future__ import annotations

from autopilot.core.action_classifier import (
    CLASSIFIER_MAX_USER_TEXT_CHARS,
    build_action_classifier_context,
    classify_tool_permission,
)
from autopilot.core.tool_contracts import ToolResult, build_tool


def test_classifier_allows_safe_explicit_read_intent() -> None:
    tool = build_tool(
        name="demo.read",
        description="Read demo payload.",
        approval_policy="ask",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )

    decision = classify_tool_permission(
        tool,
        {"path": "README.md"},
        permission_mode="default",
        context=build_action_classifier_context(
            {
                "enabled": True,
                "user_text": "Please inspect the README and show me the current contents.",
            }
        ),
    )

    assert decision is not None
    assert decision.behavior == "allow"
    assert decision.decision_id == "safe_explicit_intent"


def test_classifier_fails_closed_when_transcript_too_long() -> None:
    tool = build_tool(
        name="demo.read",
        description="Read demo payload.",
        approval_policy="ask",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )

    decision = classify_tool_permission(
        tool,
        {"path": "README.md"},
        permission_mode="default",
        context=build_action_classifier_context(
            {
                "enabled": True,
                "user_text": "x" * (CLASSIFIER_MAX_USER_TEXT_CHARS + 1),
            }
        ),
    )

    assert decision is not None
    assert decision.behavior == "ask"
    assert decision.decision_id == "transcript_too_long"


def test_classifier_denies_dangerous_projection_without_explicit_user_intent() -> None:
    tool = build_tool(
        name="shell_exec",
        description="Run shell command.",
        approval_policy="ask",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )

    decision = classify_tool_permission(
        tool,
        {"command": "rm -rf build"},
        permission_mode="default",
        context=build_action_classifier_context(
            {
                "enabled": True,
                "user_text": "Can you inspect the workspace and tell me what changed?",
            }
        ),
    )

    assert decision is not None
    assert decision.behavior == "deny"
    assert decision.decision_id == "dangerous_implicit_intent"


def test_classifier_can_return_pending_classifier_in_deferred_mode() -> None:
    tool = build_tool(
        name="demo.read",
        description="Read demo payload.",
        approval_policy="ask",
        execute=lambda tool_input, _: ToolResult(status="ok", payload=tool_input),
    )

    decision = classify_tool_permission(
        tool,
        {"path": "README.md"},
        permission_mode="default",
        context=build_action_classifier_context(
            {
                "enabled": True,
                "mode": "deferred",
                "user_text": "Please inspect the README and show me the current contents.",
            }
        ),
    )

    assert decision is not None
    assert decision.behavior == "pending_classifier"
    assert decision.decision_id == "deferred_classifier"
