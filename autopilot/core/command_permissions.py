"""Permission-mode transitions and command-oriented safety helpers."""

from __future__ import annotations

from autopilot.core.tool_contracts import ToolPermissionContext


VALID_PERMISSION_MODES = {
    "default",
    "approved",
    "bypass_permissions",
    "dont_ask",
    "plan",
}
HEADLESS_DISALLOWED_PERMISSION_MODES = {"bypass_permissions"}
AUTO_STRIP_PERMISSION_MODES = {"dont_ask", "plan"}
DANGEROUS_ALLOW_TOOL_PATTERNS = (
    "execution.launch",
    "execution.archive",
    "execution.update_budget_policy",
    "shell*",
    "shell_exec*",
    "python_exec*",
)


def normalize_permission_mode(mode: str) -> str:
    """Normalize and validate one permission mode."""

    normalized = str(mode or "").strip()
    if normalized not in VALID_PERMISSION_MODES:
        raise ValueError(
            f"Unsupported permission mode `{normalized}`. Expected one of {sorted(VALID_PERMISSION_MODES)}."
        )
    return normalized


def headless_permission_mode_allowed(mode: str) -> bool:
    """Return whether one permission mode can be set via structured headless control."""

    return normalize_permission_mode(mode) not in HEADLESS_DISALLOWED_PERMISSION_MODES


def _tool_matches_pattern(tool_name: str, pattern: str) -> bool:
    if pattern.endswith("*"):
        return tool_name.startswith(pattern[:-1])
    return tool_name == pattern


def _is_dangerous_auto_allow_tool(tool_name: str) -> bool:
    return any(_tool_matches_pattern(tool_name, pattern) for pattern in DANGEROUS_ALLOW_TOOL_PATTERNS)


def _serialized_rule_tool_name(rule: str) -> str:
    normalized = str(rule or "").strip()
    if normalized.endswith(")") and "(" in normalized:
        return normalized[:-1].split("(", 1)[0].strip()
    return normalized


def _append_reason(tool_reasons: dict[str, list[str]], key: str, reason: str) -> None:
    if not key:
        return
    values = list(tool_reasons.get(key) or [])
    if reason not in values:
        values.append(reason)
    tool_reasons[key] = values


def sanitize_permission_context_for_mode(context: ToolPermissionContext) -> ToolPermissionContext:
    """Apply safe mode-transition semantics to one permission context."""

    mode = normalize_permission_mode(context.mode)
    if mode not in AUTO_STRIP_PERMISSION_MODES:
        metadata = dict(context.metadata or {})
        metadata["mode_transition"] = {"mode": mode, "stripped_allow_rules": []}
        return context.model_copy(update={"mode": mode, "metadata": metadata})

    allow_rules = {key: list(values) for key, values in context.always_allow_rules.items()}
    ask_rules = {key: list(values) for key, values in context.always_ask_rules.items()}
    tool_reasons = {key: list(values) for key, values in context.tool_reasons.items()}
    project_policy_ask_rules = list(ask_rules.get("project_policy", []))
    stripped_rules: list[str] = []

    for source, rules in list(allow_rules.items()):
        kept_rules: list[str] = []
        for raw_rule in rules:
            tool_name = _serialized_rule_tool_name(raw_rule)
            if not _is_dangerous_auto_allow_tool(tool_name):
                kept_rules.append(raw_rule)
                continue
            stripped_rules.append(raw_rule)
            if raw_rule not in project_policy_ask_rules:
                project_policy_ask_rules.append(raw_rule)
            reason = f"Permission mode `{mode}` strips dangerous allow rule `{raw_rule}` and now requires approval."
            _append_reason(tool_reasons, tool_name, reason)
            _append_reason(tool_reasons, raw_rule, reason)
        allow_rules[source] = kept_rules

    ask_rules["project_policy"] = project_policy_ask_rules
    metadata = dict(context.metadata or {})
    metadata["mode_transition"] = {
        "mode": mode,
        "stripped_allow_rules": stripped_rules,
    }
    return context.model_copy(
        update={
            "mode": mode,
            "always_allow_rules": allow_rules,
            "always_ask_rules": ask_rules,
            "tool_reasons": tool_reasons,
            "metadata": metadata,
        }
    )
