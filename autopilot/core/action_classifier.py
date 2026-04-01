"""Fail-closed projected tool-use classifier foundation."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from autopilot.core.tool_contracts import ToolDef

ClassifierBehavior = Literal["allow", "ask", "deny", "pending_classifier"]

CLASSIFIER_MAX_USER_TEXT_CHARS = 4000
SAFE_ACTION_KEYWORDS = {
    "cat",
    "check",
    "describe",
    "diff",
    "find",
    "inspect",
    "lint",
    "list",
    "log",
    "open",
    "read",
    "review",
    "search",
    "show",
    "status",
    "test",
    "view",
}
DANGEROUS_ACTION_KEYWORDS = {
    "apply",
    "delete",
    "deploy",
    "destroy",
    "drop",
    "edit",
    "kill",
    "modify",
    "overwrite",
    "publish",
    "push",
    "remove",
    "reset",
    "rewrite",
    "rm",
    "shutdown",
    "terminate",
    "write",
}
SAFE_PROJECTION_HINTS = SAFE_ACTION_KEYWORDS | {"build", "grep", "ls", "pytest", "rg"}
DANGEROUS_PROJECTION_HINTS = DANGEROUS_ACTION_KEYWORDS | {
    "bash",
    "curl",
    "gcloud",
    "kubectl",
    "node",
    "python",
    "sh",
    "ssh",
    "sudo",
    "terraform",
    "wget",
}


class ActionClassifierContext(BaseModel):
    """Context for one projected tool-use classification."""

    enabled: bool = False
    user_text: str = ""
    decision_reason: str = ""
    projected_tool_use: str = ""
    mode: Literal["sync", "deferred"] = "sync"
    fail_open: bool = False
    max_user_text_chars: int = CLASSIFIER_MAX_USER_TEXT_CHARS


class ActionClassifierDecision(BaseModel):
    """Result of one classifier pass."""

    behavior: ClassifierBehavior
    decision_id: str
    message: str = ""
    reasons: list[str] = Field(default_factory=list)
    explanation: str = ""
    projected_tool_use: str = ""


def build_action_classifier_context(raw: dict[str, Any] | None) -> ActionClassifierContext:
    """Normalize one raw classifier context payload."""

    return ActionClassifierContext.model_validate(dict(raw or {}))


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _tokenize(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9_./:-]+", _normalize_text(value)) if token}


def _contains_any(text: str, candidates: set[str]) -> bool:
    normalized = _normalize_text(text)
    return any(candidate in normalized for candidate in candidates)


def render_projected_tool_use(tool: ToolDef, tool_input: dict[str, Any] | None) -> str:
    """Render one compact projection of a tool call for classifier input."""

    normalized_input = dict(tool_input or {})
    command = str(normalized_input.get("command") or tool.metadata.get("command") or "").strip()
    lines = [
        f"tool={tool.name}",
        f"approval_policy={str(tool.approval_policy or '').strip().lower() or 'manual'}",
    ]
    if command:
        lines.append(f"command={command}")
    scalar_items: list[str] = []
    for key in sorted(normalized_input):
        if key in {"command", "user_text"}:
            continue
        value = normalized_input[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            scalar_items.append(f"{key}={value}")
    if scalar_items:
        lines.append("input=" + ", ".join(scalar_items[:8]))
    return " | ".join(lines)


def _fail_closed_decision(
    *,
    permission_mode: str,
    decision_id: str,
    message: str,
    explanation: str,
    projected_tool_use: str,
) -> ActionClassifierDecision:
    behavior: ClassifierBehavior = "deny" if str(permission_mode or "").strip() in {"dont_ask", "plan"} else "ask"
    reasons = [message]
    if explanation and explanation not in reasons:
        reasons.append(explanation)
    return ActionClassifierDecision(
        behavior=behavior,
        decision_id=decision_id,
        message=message,
        reasons=reasons,
        explanation=explanation,
        projected_tool_use=projected_tool_use,
    )


def classify_tool_permission(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    *,
    permission_mode: str,
    context: ActionClassifierContext,
) -> ActionClassifierDecision | None:
    """Classify one projected tool use with fail-closed defaults."""

    if not context.enabled:
        return None

    projected_tool_use = context.projected_tool_use.strip() or render_projected_tool_use(tool, tool_input)
    user_text = str(context.user_text or context.decision_reason or "").strip()
    if not user_text:
        if context.fail_open:
            return None
        return _fail_closed_decision(
            permission_mode=permission_mode,
            decision_id="missing_user_text",
            message="Permission classifier could not inspect user intent.",
            explanation="No user_text or decision_reason was provided for classifier evaluation.",
            projected_tool_use=projected_tool_use,
        )

    max_user_text_chars = max(int(context.max_user_text_chars or CLASSIFIER_MAX_USER_TEXT_CHARS), 1)
    if len(user_text) > max_user_text_chars:
        if context.fail_open:
            return None
        return _fail_closed_decision(
            permission_mode=permission_mode,
            decision_id="transcript_too_long",
            message="Permission classifier transcript was too long to classify safely.",
            explanation="The classifier failed closed because the user-intent transcript exceeded the configured limit.",
            projected_tool_use=projected_tool_use,
        )

    if context.mode == "deferred":
        return ActionClassifierDecision(
            behavior="pending_classifier",
            decision_id="deferred_classifier",
            message="Permission classifier delegated this tool use to runtime settlement.",
            reasons=[
                "Deferred classifier mode is enabled for this projected tool use.",
                "The classifier should settle through the shared approval runtime instead of silently allowing.",
            ],
            explanation="Deferred classifier mode materializes a pending classifier decision for external settlement.",
            projected_tool_use=projected_tool_use,
        )

    normalized_user_text = _normalize_text(user_text)
    projection_tokens = _tokenize(projected_tool_use)
    safe_projection = (
        bool(projection_tokens.intersection(SAFE_PROJECTION_HINTS))
        or _contains_any(projected_tool_use, SAFE_PROJECTION_HINTS)
    ) and not (
        bool(projection_tokens.intersection(DANGEROUS_PROJECTION_HINTS))
        or _contains_any(projected_tool_use, DANGEROUS_PROJECTION_HINTS)
    )
    dangerous_projection = bool(projection_tokens.intersection(DANGEROUS_PROJECTION_HINTS)) or _contains_any(
        projected_tool_use,
        DANGEROUS_PROJECTION_HINTS,
    )
    explicit_safe_intent = _contains_any(normalized_user_text, SAFE_ACTION_KEYWORDS)
    explicit_dangerous_intent = _contains_any(normalized_user_text, DANGEROUS_ACTION_KEYWORDS)

    if dangerous_projection:
        if explicit_dangerous_intent:
            return ActionClassifierDecision(
                behavior="ask",
                decision_id="dangerous_explicit_intent",
                message="Projected tool use matches dangerous intent and requires explicit approval.",
                reasons=[
                    "The projected tool use contains dangerous execution patterns.",
                    "User intent appears explicit, so this should route to approval instead of silent allow.",
                ],
                explanation="Dangerous projected actions never auto-allow through the classifier.",
                projected_tool_use=projected_tool_use,
            )
        return ActionClassifierDecision(
            behavior="deny",
            decision_id="dangerous_implicit_intent",
            message="Projected tool use looks dangerous and user intent was not explicit enough.",
            reasons=[
                "The projected tool use contains dangerous execution patterns.",
                "User intent did not clearly authorize the dangerous action.",
            ],
            explanation="The classifier failed closed on a dangerous projected tool use.",
            projected_tool_use=projected_tool_use,
        )

    if safe_projection and explicit_safe_intent:
        return ActionClassifierDecision(
            behavior="allow",
            decision_id="safe_explicit_intent",
            message="Projected tool use matches explicit safe user intent.",
            reasons=[
                "The projected tool use is read-oriented or verification-oriented.",
                "User intent explicitly requests a safe inspection/check action.",
            ],
            explanation="The classifier allowed a safe projected tool use because the user request was explicit and non-mutating.",
            projected_tool_use=projected_tool_use,
        )

    return ActionClassifierDecision(
        behavior="ask",
        decision_id="ambiguous_projection",
        message="Projected tool use could not be auto-classified safely.",
        reasons=[
            "The classifier did not see enough explicit safe intent to auto-allow.",
            "Fallback is explicit approval rather than silent allow.",
        ],
        explanation="Ambiguous classifier results fall back to approval.",
        projected_tool_use=projected_tool_use,
    )


__all__ = [
    "ActionClassifierContext",
    "ActionClassifierDecision",
    "CLASSIFIER_MAX_USER_TEXT_CHARS",
    "build_action_classifier_context",
    "classify_tool_permission",
    "render_projected_tool_use",
]
