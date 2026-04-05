"""Permission-mode transitions and command-oriented safety helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from autopilot.core.bash_ast import BashParseError, parse_bash_command
from autopilot.core.command_safety import validate_command_safety
from autopilot.core.tool_contracts import ToolDef
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
PERMISSION_RULE_COLON_PATTERN = re.compile(r"^(?P<tool>[A-Za-z0-9._*-]+)\s*:\s*(?P<content>.+)$")
SHELL_INTERPRETERS = {"bash", "sh", "zsh", "ksh"}
INLINE_CODE_TOOLS = {"python", "python3", "node", "ruby", "perl"}
REMOTE_ACCESS_TOOLS = {"ssh", "scp", "sftp"}
CLOUD_CONTROL_TOOLS = {"kubectl", "aws", "gcloud", "terraform"}


@dataclass(frozen=True)
class ProjectedCommandPermission:
    """Permission-stage decision for one projected shell-like command."""

    behavior: Literal["ask", "deny"]
    source: str
    pattern_id: str
    message: str
    reasons: tuple[str, ...] = ()


def _normalize_projected_command_reason(reason: str) -> str:
    normalized = " ".join(str(reason or "").strip().split())
    if not normalized:
        return "Projected shell command is not trusted."
    if normalized.startswith("Gate command "):
        return "Projected shell command " + normalized[len("Gate command ") :]
    if normalized.startswith("Shell command "):
        return "Projected shell command " + normalized[len("Shell command ") :]
    return normalized


def _check_fail_closed_command_safety(raw_command: str) -> ProjectedCommandPermission | None:
    try:
        ast = parse_bash_command(raw_command)
    except BashParseError as exc:
        message = _normalize_projected_command_reason(str(exc))
        return ProjectedCommandPermission(
            behavior="deny",
            source="workspace_policy",
            pattern_id="command_safety_parse_error",
            message=message,
            reasons=(message,),
        )

    violations = validate_command_safety(raw_command, ast=ast)
    if not violations:
        return None

    first = violations[0]
    message = _normalize_projected_command_reason(first.reason)
    return ProjectedCommandPermission(
        behavior="deny",
        source="workspace_policy",
        pattern_id=f"command_safety_{first.kind}",
        message=message,
        reasons=(message,),
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


def normalize_tool_pattern(tool_name: str) -> str:
    """Return a canonical tool-name pattern or raise for malformed grammar."""

    normalized = " ".join(str(tool_name or "").strip().split())
    if not normalized:
        raise ValueError("Permission rules require `tool_name`.")
    if any(char.isspace() for char in normalized):
        raise ValueError("Permission rule tool patterns cannot contain whitespace.")
    if ":" in normalized:
        raise ValueError("Permission rule tool patterns cannot contain `:` separators.")
    if "(" in normalized or ")" in normalized:
        raise ValueError("Permission rule tool patterns cannot contain parentheses.")
    if "*" in normalized[:-1]:
        raise ValueError("Permission rule tool patterns only support a trailing `*` wildcard.")
    if normalized.endswith("**"):
        normalized = normalized.rstrip("*") + "*"
    return normalized


def _command_candidates(tool: ToolDef, tool_input: dict[str, Any] | None) -> list[str]:
    payload = dict(tool_input or {})
    candidates = [
        str(payload.get("command") or "").strip(),
        str(payload.get("cmd") or "").strip(),
        str(tool.metadata.get("command") or "").strip(),
        str(tool.metadata.get("rule_content") or "").strip(),
    ]
    return [item for item in candidates if item]


def normalize_shell_command(command: str) -> str:
    """Return a normalized shell command string for exact/prefix matching."""

    raw_value = str(command or "").strip()
    if not raw_value:
        return ""
    try:
        ast = parse_bash_command(raw_value)
    except BashParseError:
        return " ".join(raw_value.split())
    if not ast.executable_argv:
        return ""
    return " ".join(ast.executable_argv)


def normalize_rule_content(rule_content: str | None) -> str:
    """Return canonical rule-content text for persistence and matching."""

    raw_value = str(rule_content or "").strip()
    if not raw_value:
        return ""
    normalized = normalize_shell_command(raw_value)
    return normalized or " ".join(raw_value.split())


def normalize_permission_rule(tool_name: str, rule_content: str | None = None) -> tuple[str, str]:
    """Return canonical permission rule components."""

    return normalize_tool_pattern(tool_name), normalize_rule_content(rule_content)


def parse_permission_rule(rule: str) -> tuple[str, str]:
    """Parse and normalize one serialized permission rule."""

    normalized = str(rule or "").strip()
    if normalized.endswith(")") and "(" in normalized:
        tool_name, raw_content = normalized[:-1].split("(", 1)
        return normalize_permission_rule(tool_name, raw_content)
    colon_match = PERMISSION_RULE_COLON_PATTERN.match(normalized)
    if colon_match is not None:
        return normalize_permission_rule(colon_match.group("tool"), colon_match.group("content"))
    return normalize_permission_rule(normalized, "")


def serialize_permission_rule(tool_name: str, rule_content: str | None = None) -> str:
    """Serialize one canonical permission rule string."""

    normalized_tool_name, normalized_rule_content = normalize_permission_rule(tool_name, rule_content)
    if not normalized_rule_content:
        return normalized_tool_name
    return f"{normalized_tool_name}({normalized_rule_content})"


def normalize_serialized_permission_rules(rules: list[str]) -> list[str]:
    """Normalize and dedupe serialized permission rules while preserving order."""

    normalized_rules: list[str] = []
    for raw_rule in rules:
        try:
            serialized = serialize_permission_rule(*parse_permission_rule(raw_rule))
        except ValueError:
            continue
        if serialized not in normalized_rules:
            normalized_rules.append(serialized)
    return normalized_rules


def command_rule_matches(
    rule_content: str,
    *,
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
) -> bool:
    """Return whether a permission rule matches the projected command exactly or by prefix."""

    normalized_rule = normalize_shell_command(rule_content)
    if not normalized_rule:
        return False
    wildcard = normalized_rule.endswith("*")
    if wildcard:
        normalized_rule = normalized_rule[:-1].rstrip()
    if not normalized_rule:
        return False

    for candidate in _command_candidates(tool, tool_input):
        normalized_candidate = normalize_shell_command(candidate)
        if not normalized_candidate:
            continue
        if normalized_candidate == normalized_rule or normalized_candidate.startswith(f"{normalized_rule} "):
            return True
        if wildcard and normalized_candidate.startswith(normalized_rule):
            return True
    return False


def check_projected_command_permission(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
) -> ProjectedCommandPermission | None:
    """Return a permission-stage decision for dangerous projected shell commands."""

    candidates = _command_candidates(tool, tool_input)
    if not candidates:
        return None
    raw_command = candidates[0]
    normalized_command = normalize_shell_command(raw_command)

    try:
        ast = parse_bash_command(raw_command)
        tokens = list(ast.executable_argv)
    except BashParseError:
        tokens = normalized_command.split()
    if not tokens:
        return None

    command_name = Path(tokens[0]).name
    args = tokens[1:]
    lower_tokens = [token.lower() for token in tokens]
    lower_command = normalized_command.lower()

    if command_name in {"curl", "wget"} and "|" in raw_command and any(item in lower_tokens for item in SHELL_INTERPRETERS):
        message = "Projected shell command downloads remote content and pipes it into a shell interpreter."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id="curl_pipe_shell",
            message=message,
            reasons=(message,),
        )

    safety_decision = _check_fail_closed_command_safety(raw_command)
    if safety_decision is not None:
        return safety_decision

    if not normalized_command:
        return None

    if command_name in SHELL_INTERPRETERS and any(arg in {"-c", "-lc"} for arg in args):
        message = "Projected shell command delegates execution to a nested shell interpreter."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id="nested_shell",
            message=message,
            reasons=(message,),
        )

    if command_name in INLINE_CODE_TOOLS and any(arg in {"-c", "-e", "--eval"} for arg in args):
        message = f"Projected command `{command_name}` uses inline code execution and requires explicit approval."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id=f"{command_name}_eval",
            message=message,
            reasons=(message,),
        )

    if command_name == "sudo":
        message = "Projected shell command requests privilege escalation via `sudo`."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id="sudo",
            message=message,
            reasons=(message,),
        )

    if command_name in REMOTE_ACCESS_TOOLS:
        message = f"Projected shell command `{command_name}` targets remote access and requires explicit approval."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id=command_name,
            message=message,
            reasons=(message,),
        )

    if command_name == "rsync" and ":" in lower_command:
        message = "Projected shell command `rsync` appears to target a remote host and requires explicit approval."
        return ProjectedCommandPermission(
            behavior="ask",
            source="workspace_policy",
            pattern_id="rsync_remote",
            message=message,
            reasons=(message,),
        )

    if command_name in CLOUD_CONTROL_TOOLS:
        if command_name != "terraform" or (args and args[0] in {"apply", "destroy"}):
            message = f"Projected shell command `{command_name}` targets infrastructure or cloud control and requires explicit approval."
            return ProjectedCommandPermission(
                behavior="ask",
                source="workspace_policy",
                pattern_id=command_name,
                message=message,
                reasons=(message,),
            )

    return None


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
