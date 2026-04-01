"""Permission state machine for runtime tool execution."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from autopilot.core.command_permissions import (
    check_projected_command_permission,
    command_rule_matches,
    normalize_permission_mode,
    normalize_serialized_permission_rules,
    parse_permission_rule,
    sanitize_permission_context_for_mode,
    serialize_permission_rule,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.permission_audit import append_permission_audit_entry
from autopilot.core.tool_contracts import ToolDef, ToolPermissionContext, get_empty_tool_permission_context

PermissionMode = Literal["default", "approved", "bypass_permissions", "dont_ask", "plan"]
PermissionBehavior = Literal["allow", "deny", "ask"]
PermissionRuleSource = Literal["command", "session", "project", "user", "managed", "env", "project_policy", "workspace_policy"]
PermissionUpdateDestination = Literal["session", "user", "project"]

RULE_SOURCE_ORDER: tuple[PermissionRuleSource, ...] = (
    "command",
    "session",
    "project",
    "user",
    "managed",
    "env",
    "project_policy",
    "workspace_policy",
)
DENIAL_BREAKER_THRESHOLD = 3
VALID_PERMISSION_RULE_SOURCES = set(RULE_SOURCE_ORDER)
ENV_PERMISSION_RULES_JSON = "AUTOPILOT_PERMISSION_RULES_JSON"


class PermissionRuleValue(BaseModel):
    """Rule target for one tool or one scoped tool variant."""

    tool_name: str
    rule_content: str | None = None


class PermissionRule(BaseModel):
    """One resolved permission rule."""

    source: PermissionRuleSource
    rule_behavior: PermissionBehavior
    rule_value: PermissionRuleValue


class PermissionDecision(BaseModel):
    """Result of one permission check."""

    behavior: PermissionBehavior
    message: str = ""
    reasons: list[str] = Field(default_factory=list)
    rule_source: PermissionRuleSource | None = None
    matched_rule: str | None = None
    updated_input: dict[str, Any] = Field(default_factory=dict)
    denial_count: int = 0
    escalation_required: bool = False


class PermissionUpdate(BaseModel):
    """One permission state mutation."""

    type: Literal["add_rules", "replace_rules", "remove_rules", "set_mode"]
    destination: PermissionUpdateDestination
    behavior: PermissionBehavior | None = None
    rules: list[PermissionRuleValue] = Field(default_factory=list)
    mode: PermissionMode | None = None
    project_id: str | None = None

    @model_validator(mode="after")
    def _validate_shape(self) -> "PermissionUpdate":
        if self.type == "set_mode":
            if self.mode is None:
                raise ValueError("set_mode updates require `mode`.")
            return self
        if self.behavior is None:
            raise ValueError(f"{self.type} updates require `behavior`.")
        if not self.rules:
            raise ValueError(f"{self.type} updates require at least one rule.")
        if self.destination == "project" and not str(self.project_id or "").strip():
            raise ValueError("Project-scoped permission updates require `project_id`.")
        return self


class PermissionScopeState(BaseModel):
    """Persisted rules for one scope."""

    mode: PermissionMode = "default"
    allow_rules: list[str] = Field(default_factory=list)
    deny_rules: list[str] = Field(default_factory=list)
    ask_rules: list[str] = Field(default_factory=list)


class PermissionContextOverlay(BaseModel):
    """Ephemeral permission overlay merged on top of persisted state."""

    mode: PermissionMode | None = None
    allow_rules: list[str] = Field(default_factory=list)
    deny_rules: list[str] = Field(default_factory=list)
    ask_rules: list[str] = Field(default_factory=list)
    tool_reasons: dict[str, list[str]] = Field(default_factory=dict)


class PersistedToolPermissionState(BaseModel):
    """File-backed permission state."""

    user: PermissionScopeState = Field(default_factory=PermissionScopeState)
    projects: dict[str, PermissionScopeState] = Field(default_factory=dict)


class PermissionDenialEntry(BaseModel):
    """Tracked denied attempts for one tool scope."""

    tool_name: str
    project_id: str = ""
    matched_rule: str = ""
    count: int = 0
    last_denied_at: str | None = None
    last_message: str = ""


class PersistedPermissionDenialState(BaseModel):
    """File-backed repeated-denial tracker."""

    entries: dict[str, PermissionDenialEntry] = Field(default_factory=dict)


class DenialBreakerDecision(BaseModel):
    """Resolved denial-breaker state."""

    count: int = 0
    threshold: int = DENIAL_BREAKER_THRESHOLD
    triggered: bool = False
    key: str = ""


def permission_state_path(config: AutopilotConfig) -> Path:
    """Return the persisted tool permission state path."""

    return config.tool_permissions_json_path


def permission_denial_state_path(config: AutopilotConfig) -> Path:
    """Return the persisted repeated-denial tracker path."""

    return config.tool_permission_denials_json_path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_serialized_rules(existing: list[str], additions: list[str]) -> list[str]:
    merged = normalize_serialized_permission_rules(list(existing))
    for item in normalize_serialized_permission_rules(list(additions)):
        if item not in merged:
            merged.append(item)
    return merged


def _merge_tool_reasons(
    existing: dict[str, list[str]],
    additions: dict[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    merged = {str(key): [str(reason) for reason in values] for key, values in existing.items()}
    for raw_key, raw_values in (additions or {}).items():
        key = str(raw_key or "").strip()
        if not key:
            continue
        current = [reason for reason in merged.get(key, []) if str(reason).strip()]
        for raw_reason in raw_values or []:
            reason = str(raw_reason or "").strip()
            if reason and reason not in current:
                current.append(reason)
        if current:
            merged[key] = current
    return merged


def _merge_permission_overlay(
    existing: PermissionContextOverlay | None,
    incoming: PermissionContextOverlay,
) -> PermissionContextOverlay:
    existing_overlay = existing or PermissionContextOverlay()
    return PermissionContextOverlay(
        mode=incoming.mode or existing_overlay.mode,
        allow_rules=_merge_serialized_rules(existing_overlay.allow_rules, incoming.allow_rules),
        deny_rules=_merge_serialized_rules(existing_overlay.deny_rules, incoming.deny_rules),
        ask_rules=_merge_serialized_rules(existing_overlay.ask_rules, incoming.ask_rules),
        tool_reasons=_merge_tool_reasons(existing_overlay.tool_reasons, incoming.tool_reasons),
    )


def _permission_overlay_from_payload(payload: Any) -> PermissionContextOverlay | None:
    if not isinstance(payload, dict):
        return None
    for key in ("tool_permissions", "permissions"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            payload = nested
            break
    normalized_payload: dict[str, Any] = {}
    for field_name in ("mode", "allow_rules", "deny_rules", "ask_rules", "tool_reasons"):
        if field_name in payload:
            normalized_payload[field_name] = payload[field_name]
    if not normalized_payload:
        return None
    try:
        overlay = PermissionContextOverlay.model_validate(normalized_payload)
    except Exception:
        return None
    return overlay


def _load_managed_permission_overlay(config: AutopilotConfig) -> tuple[PermissionContextOverlay | None, dict[str, Any]]:
    directory = config.managed_settings_fragments_dir
    metadata = {
        "directory": str(directory),
        "files": [],
        "warnings": [],
    }
    if not directory.exists():
        return None, metadata

    overlay = PermissionContextOverlay()
    for path in sorted(directory.glob("*.json")):
        metadata["files"].append(path.name)
        try:
            payload = json.loads(path.read_text())
        except Exception:
            metadata["warnings"].append(f"Failed to parse managed permission fragment `{path.name}`.")
            continue
        fragment = _permission_overlay_from_payload(payload)
        if fragment is None:
            metadata["warnings"].append(f"Managed permission fragment `{path.name}` did not contain a valid permission payload.")
            continue
        overlay = _merge_permission_overlay(overlay, fragment)

    if not any((overlay.allow_rules, overlay.deny_rules, overlay.ask_rules, overlay.tool_reasons, overlay.mode)):
        return None, metadata
    return overlay, metadata


def _load_env_permission_overlay() -> tuple[PermissionContextOverlay | None, dict[str, Any]]:
    metadata = {
        "env_var": ENV_PERMISSION_RULES_JSON,
        "loaded": False,
        "warnings": [],
    }
    raw_value = str(os.getenv(ENV_PERMISSION_RULES_JSON) or "").strip()
    if not raw_value:
        return None, metadata
    try:
        payload = json.loads(raw_value)
    except Exception:
        metadata["warnings"].append(f"Failed to parse `{ENV_PERMISSION_RULES_JSON}` as JSON.")
        return None, metadata
    overlay = _permission_overlay_from_payload(payload)
    if overlay is None:
        metadata["warnings"].append(f"`{ENV_PERMISSION_RULES_JSON}` did not contain a valid permission payload.")
        return None, metadata
    metadata["loaded"] = True
    return overlay, metadata


def _resolve_loaded_permission_mode(
    *,
    user_mode: str,
    project_mode: str,
    overlays: dict[str, PermissionContextOverlay] | None = None,
    explicit_mode: str | None = None,
) -> tuple[str, dict[str, Any]]:
    normalized_user_mode = normalize_permission_mode(user_mode or "default")
    resolved_mode = normalized_user_mode
    normalized_project_mode = normalize_permission_mode(project_mode or "default")
    overlay_modes: dict[str, str] = {}
    ignored_project_mode = ""

    if normalized_project_mode != "default" and normalized_project_mode != resolved_mode:
        ignored_project_mode = normalized_project_mode

    for source in ("command", "session", "project_policy", "workspace_policy"):
        overlay = (overlays or {}).get(source)
        if overlay is None or overlay.mode is None:
            continue
        normalized_mode = normalize_permission_mode(overlay.mode)
        overlay_modes[source] = normalized_mode
        resolved_mode = normalized_mode

    if explicit_mode is not None:
        resolved_mode = normalize_permission_mode(explicit_mode)

    return resolved_mode, {
        "user_mode": normalized_user_mode,
        "project_mode": normalized_project_mode,
        "ignored_project_mode": ignored_project_mode,
        "overlay_modes": overlay_modes,
        "explicit_mode": normalize_permission_mode(explicit_mode) if explicit_mode is not None else "",
        "resolved_mode": resolved_mode,
    }


def permission_rule_value_to_string(rule_value: PermissionRuleValue) -> str:
    """Serialize one rule to a stable string."""

    return serialize_permission_rule(rule_value.tool_name, rule_value.rule_content)


def permission_rule_value_from_string(rule: str) -> PermissionRuleValue:
    """Parse one serialized rule string."""

    tool_name, rule_content = parse_permission_rule(rule)
    return PermissionRuleValue(tool_name=tool_name, rule_content=rule_content or None)


def apply_permission_update(context: ToolPermissionContext, update: PermissionUpdate) -> ToolPermissionContext:
    """Apply one update to an in-memory permission context."""

    if update.type == "set_mode":
        return context.model_copy(update={"mode": update.mode})

    rule_field = {
        "allow": "always_allow_rules",
        "deny": "always_deny_rules",
        "ask": "always_ask_rules",
    }[str(update.behavior)]
    source_key = "project" if update.destination == "project" else update.destination
    existing = {
        key: normalize_serialized_permission_rules(list(values))
        for key, values in getattr(context, rule_field).items()
    }
    serialized = [permission_rule_value_to_string(rule) for rule in update.rules]
    current_values = normalize_serialized_permission_rules(list(existing.get(source_key, [])))

    if update.type == "add_rules":
        for item in serialized:
            if item not in current_values:
                current_values.append(item)
    elif update.type == "replace_rules":
        current_values = serialized
    elif update.type == "remove_rules":
        removals = set(serialized)
        current_values = [item for item in current_values if item not in removals]

    existing[source_key] = normalize_serialized_permission_rules(current_values)
    return context.model_copy(update={rule_field: existing})


def apply_permission_updates(
    context: ToolPermissionContext,
    updates: list[PermissionUpdate],
) -> ToolPermissionContext:
    """Apply multiple updates to an in-memory permission context."""

    updated = context
    for item in updates:
        updated = apply_permission_update(updated, item)
    return updated


def _load_persisted_state(config: AutopilotConfig) -> PersistedToolPermissionState:
    path = permission_state_path(config)
    if not path.exists():
        return PersistedToolPermissionState()
    try:
        return PersistedToolPermissionState.model_validate(json.loads(path.read_text()))
    except Exception:
        return PersistedToolPermissionState()


def _save_persisted_state(config: AutopilotConfig, state: PersistedToolPermissionState) -> PersistedToolPermissionState:
    path = permission_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state.model_dump(), indent=2, ensure_ascii=False))
    temp_path.replace(path)
    return state


def _load_permission_denials(config: AutopilotConfig) -> PersistedPermissionDenialState:
    path = permission_denial_state_path(config)
    if not path.exists():
        return PersistedPermissionDenialState()
    try:
        return PersistedPermissionDenialState.model_validate(json.loads(path.read_text()))
    except Exception:
        return PersistedPermissionDenialState()


def _save_permission_denials(
    config: AutopilotConfig,
    state: PersistedPermissionDenialState,
) -> PersistedPermissionDenialState:
    path = permission_denial_state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(state.model_dump(), indent=2, ensure_ascii=False))
    temp_path.replace(path)
    return state


def _denial_key(*, project_id: str, tool_name: str, matched_rule: str) -> str:
    normalized_project_id = str(project_id or "").strip() or "*"
    normalized_tool_name = str(tool_name or "").strip()
    normalized_rule = str(matched_rule or "").strip()
    return "::".join((normalized_project_id, normalized_tool_name, normalized_rule))


def _get_denial_count(
    config: AutopilotConfig,
    *,
    project_id: str,
    tool_name: str,
    matched_rule: str,
) -> DenialBreakerDecision:
    key = _denial_key(project_id=project_id, tool_name=tool_name, matched_rule=matched_rule)
    state = _load_permission_denials(config)
    entry = state.entries.get(key)
    count = int(entry.count) if entry is not None else 0
    return DenialBreakerDecision(
        count=count,
        threshold=DENIAL_BREAKER_THRESHOLD,
        triggered=count >= DENIAL_BREAKER_THRESHOLD,
        key=key,
    )


def _record_denial(
    config: AutopilotConfig,
    *,
    project_id: str,
    tool_name: str,
    matched_rule: str,
    message: str,
) -> DenialBreakerDecision:
    key = _denial_key(project_id=project_id, tool_name=tool_name, matched_rule=matched_rule)
    state = _load_permission_denials(config)
    entry = state.entries.get(key)
    if entry is None:
        entry = PermissionDenialEntry(
            tool_name=tool_name,
            project_id=str(project_id or "").strip(),
            matched_rule=str(matched_rule or "").strip(),
        )
    entry.count = int(entry.count) + 1
    entry.last_denied_at = _utcnow_iso()
    entry.last_message = str(message or "").strip()
    state.entries[key] = entry
    _save_permission_denials(config, state)
    return DenialBreakerDecision(
        count=entry.count,
        threshold=DENIAL_BREAKER_THRESHOLD,
        triggered=entry.count >= DENIAL_BREAKER_THRESHOLD,
        key=key,
    )


def reset_denial_breaker(
    config: AutopilotConfig,
    *,
    project_id: str,
    tool_name: str,
) -> None:
    """Clear tracked denials for one tool within one project scope."""

    state = _load_permission_denials(config)
    prefix = _denial_key(project_id=project_id, tool_name=tool_name, matched_rule="")
    removed = [key for key in state.entries if key == prefix or key.startswith(f"{prefix}::")]
    if not removed:
        return
    for key in removed:
        state.entries.pop(key, None)
    _save_permission_denials(config, state)


def _scope_for_update(state: PersistedToolPermissionState, update: PermissionUpdate) -> PermissionScopeState:
    if update.destination == "user":
        return state.user
    project_id = str(update.project_id or "").strip()
    if not project_id:
        raise ValueError("Project-scoped permission updates require `project_id`.")
    scope = state.projects.get(project_id)
    if scope is None:
        scope = PermissionScopeState()
        state.projects[project_id] = scope
    return scope


def persist_permission_update(config: AutopilotConfig, update: PermissionUpdate) -> PersistedToolPermissionState:
    """Persist one permission update when it targets disk-backed state."""

    if update.destination == "session":
        return _load_persisted_state(config)

    state = _load_persisted_state(config)
    scope = _scope_for_update(state, update)
    if update.type == "set_mode":
        scope.mode = str(update.mode or "default")  # type: ignore[assignment]
        return _save_persisted_state(config, state)

    field_name = {
        "allow": "allow_rules",
        "deny": "deny_rules",
        "ask": "ask_rules",
    }[str(update.behavior)]
    current_values = normalize_serialized_permission_rules(list(getattr(scope, field_name)))
    serialized = [permission_rule_value_to_string(rule) for rule in update.rules]

    if update.type == "add_rules":
        for item in serialized:
            if item not in current_values:
                current_values.append(item)
    elif update.type == "replace_rules":
        current_values = serialized
    elif update.type == "remove_rules":
        removals = set(serialized)
        current_values = [item for item in current_values if item not in removals]

    setattr(scope, field_name, normalize_serialized_permission_rules(current_values))
    return _save_persisted_state(config, state)


def persist_permission_updates(
    config: AutopilotConfig,
    updates: list[PermissionUpdate],
) -> PersistedToolPermissionState:
    """Persist multiple permission updates."""

    state = _load_persisted_state(config)
    for update in updates:
        if update.destination == "session":
            continue
        scope = _scope_for_update(state, update)
        if update.type == "set_mode":
            scope.mode = str(update.mode or "default")  # type: ignore[assignment]
            continue
        field_name = {
            "allow": "allow_rules",
            "deny": "deny_rules",
            "ask": "ask_rules",
        }[str(update.behavior)]
        current_values = normalize_serialized_permission_rules(list(getattr(scope, field_name)))
        serialized = [permission_rule_value_to_string(rule) for rule in update.rules]
        if update.type == "add_rules":
            for item in serialized:
                if item not in current_values:
                    current_values.append(item)
        elif update.type == "replace_rules":
            current_values = serialized
        elif update.type == "remove_rules":
            removals = set(serialized)
            current_values = [item for item in current_values if item not in removals]
        setattr(scope, field_name, normalize_serialized_permission_rules(current_values))
    return _save_persisted_state(config, state)


def load_tool_permission_context(
    config: AutopilotConfig,
    *,
    project_id: str | None = None,
    overlays: dict[str, PermissionContextOverlay] | None = None,
    mode: str | None = None,
) -> ToolPermissionContext:
    """Load the merged tool permission context for one project scope."""

    state = _load_persisted_state(config)
    managed_overlay, managed_metadata = _load_managed_permission_overlay(config)
    env_overlay, env_metadata = _load_env_permission_overlay()
    always_allow_rules = {"user": normalize_serialized_permission_rules(list(state.user.allow_rules))}
    always_deny_rules = {"user": normalize_serialized_permission_rules(list(state.user.deny_rules))}
    always_ask_rules = {"user": normalize_serialized_permission_rules(list(state.user.ask_rules))}
    metadata: dict[str, Any] = {
        "loader_sources": {
            "managed": managed_metadata,
            "env": env_metadata,
        }
    }
    project_mode = "default"

    normalized_project_id = str(project_id or "").strip()
    if normalized_project_id and normalized_project_id in state.projects:
        scope = state.projects[normalized_project_id]
        always_allow_rules["project"] = normalize_serialized_permission_rules(list(scope.allow_rules))
        always_deny_rules["project"] = normalize_serialized_permission_rules(list(scope.deny_rules))
        always_ask_rules["project"] = normalize_serialized_permission_rules(list(scope.ask_rules))
        project_mode = scope.mode

    normalized_overlays: dict[str, PermissionContextOverlay] = {}
    if managed_overlay is not None:
        normalized_overlays["managed"] = managed_overlay
    if env_overlay is not None:
        normalized_overlays["env"] = env_overlay
    for source, overlay in dict(overlays or {}).items():
        normalized_overlays[source] = _merge_permission_overlay(normalized_overlays.get(source), overlay)
    for source in normalized_overlays:
        if source not in VALID_PERMISSION_RULE_SOURCES:
            raise ValueError(f"Unsupported permission overlay source `{source}`.")
    for source, overlay in normalized_overlays.items():
        always_allow_rules[source] = _merge_serialized_rules(always_allow_rules.get(source, []), overlay.allow_rules)
        always_deny_rules[source] = _merge_serialized_rules(always_deny_rules.get(source, []), overlay.deny_rules)
        always_ask_rules[source] = _merge_serialized_rules(always_ask_rules.get(source, []), overlay.ask_rules)

    resolved_mode, mode_resolution = _resolve_loaded_permission_mode(
        user_mode=state.user.mode,
        project_mode=project_mode,
        overlays=normalized_overlays,
        explicit_mode=mode,
    )
    metadata["mode_resolution"] = mode_resolution
    tool_reasons: dict[str, list[str]] = {}
    for overlay in normalized_overlays.values():
        tool_reasons = _merge_tool_reasons(tool_reasons, overlay.tool_reasons)

    return get_empty_tool_permission_context().model_copy(
        update={
            "mode": resolved_mode,
            "always_allow_rules": always_allow_rules,
            "always_deny_rules": always_deny_rules,
            "always_ask_rules": always_ask_rules,
            "tool_reasons": tool_reasons,
            "metadata": metadata,
        }
    )


def _rules_for_behavior(
    context: ToolPermissionContext,
    behavior: PermissionBehavior,
) -> list[PermissionRule]:
    raw_map = {
        "allow": context.always_allow_rules,
        "deny": context.always_deny_rules,
        "ask": context.always_ask_rules,
    }[behavior]
    resolved: list[PermissionRule] = []
    for source in RULE_SOURCE_ORDER:
        for raw_rule in raw_map.get(source, []):
            resolved.append(
                PermissionRule(
                    source=source,
                    rule_behavior=behavior,
                    rule_value=permission_rule_value_from_string(raw_rule),
                )
            )
    return resolved


def create_permission_request_message(
    tool_name: str,
    reasons: list[str] | None = None,
    *,
    rule_source: PermissionRuleSource | None = None,
) -> str:
    """Build a concise approval request message."""

    reason_list = [str(item).strip() for item in (reasons or []) if str(item).strip()]
    if reason_list:
        return reason_list[0]
    if rule_source:
        return f"Tool `{tool_name}` requires approval under `{rule_source}`."
    return f"Tool `{tool_name}` requires approval."


def _rule_reasons(
    context: ToolPermissionContext,
    *,
    tool_name: str,
    matched_rule: str,
) -> list[str]:
    reasons = list(context.tool_reasons.get(tool_name) or [])
    if reasons:
        return reasons
    reasons = list(context.tool_reasons.get(matched_rule) or [])
    if reasons:
        return reasons
    return []


def _tool_matches_rule(tool: ToolDef, tool_input: dict[str, Any] | None, rule: PermissionRule) -> bool:
    pattern = str(rule.rule_value.tool_name or "").strip()
    if not pattern:
        return False
    if pattern.endswith("*"):
        matches_name = tool.name.startswith(pattern[:-1])
    else:
        matches_name = tool.name == pattern
    if not matches_name:
        return False
    rule_content = str(rule.rule_value.rule_content or "").strip()
    if not rule_content:
        return True
    if command_rule_matches(rule_content, tool=tool, tool_input=tool_input):
        return True
    candidates = {
        str(tool.metadata.get("command") or "").strip(),
        str(tool.metadata.get("project_id") or "").strip(),
        str(tool.metadata.get("rule_content") or "").strip(),
    }
    return rule_content in candidates


def check_rule_based_permissions(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    permission_context: ToolPermissionContext,
) -> PermissionDecision | None:
    """Evaluate explicit rule-based allow, ask, and deny decisions."""

    deny_rules = _rules_for_behavior(permission_context, "deny")
    for rule in deny_rules:
        if _tool_matches_rule(tool, tool_input, rule):
            serialized = permission_rule_value_to_string(rule.rule_value)
            reasons = _rule_reasons(permission_context, tool_name=tool.name, matched_rule=serialized)
            if not reasons:
                reasons = [f"Tool `{tool.name}` is blocked by `{rule.source}` permission rule `{serialized}`."]
            return PermissionDecision(
                behavior="deny",
                message=reasons[0],
                reasons=reasons,
                rule_source=rule.source,
                matched_rule=serialized,
            )

    projected_command_decision = check_projected_command_permission(tool, tool_input)
    if projected_command_decision is not None:
        matched_rule = f"{tool.name}(dangerous_pattern:{projected_command_decision.pattern_id})"
        reasons = list(projected_command_decision.reasons) or [projected_command_decision.message]
        return PermissionDecision(
            behavior=projected_command_decision.behavior,
            message=projected_command_decision.message,
            reasons=reasons,
            rule_source="workspace_policy",
            matched_rule=matched_rule,
        )

    ask_rules = _rules_for_behavior(permission_context, "ask")
    for rule in ask_rules:
        if _tool_matches_rule(tool, tool_input, rule):
            serialized = permission_rule_value_to_string(rule.rule_value)
            reasons = _rule_reasons(permission_context, tool_name=tool.name, matched_rule=serialized)
            return PermissionDecision(
                behavior="ask",
                message=create_permission_request_message(tool.name, reasons, rule_source=rule.source),
                reasons=reasons,
                rule_source=rule.source,
                matched_rule=serialized,
            )

    allow_rules = _rules_for_behavior(permission_context, "allow")
    for rule in allow_rules:
        if _tool_matches_rule(tool, tool_input, rule):
            serialized = permission_rule_value_to_string(rule.rule_value)
            return PermissionDecision(
                behavior="allow",
                rule_source=rule.source,
                matched_rule=serialized,
            )
    return None


def has_permissions_to_use_tool(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    permission_context: ToolPermissionContext,
) -> PermissionDecision:
    """Resolve the final permission decision for one tool use."""
    permission_context = sanitize_permission_context_for_mode(permission_context)

    if permission_context.mode == "bypass_permissions":
        return PermissionDecision(behavior="allow")

    rule_decision = check_rule_based_permissions(tool, tool_input, permission_context)
    if rule_decision is not None:
        if rule_decision.behavior == "ask" and permission_context.mode == "approved":
            return PermissionDecision(behavior="allow", reasons=rule_decision.reasons)
        if rule_decision.behavior == "ask" and permission_context.mode == "dont_ask":
            reasons = list(rule_decision.reasons)
            message = rule_decision.message or f"Tool `{tool.name}` requires approval, but prompts are disabled."
            if not reasons:
                reasons = [message]
            return PermissionDecision(
                behavior="deny",
                message=message,
                reasons=reasons,
                rule_source=rule_decision.rule_source,
                matched_rule=rule_decision.matched_rule,
            )
        return rule_decision

    approval_policy = str(tool.approval_policy or "").strip().lower()
    default_reasons = list(permission_context.tool_reasons.get(tool.name) or [])
    if approval_policy == "policy" and not default_reasons:
        return PermissionDecision(behavior="allow")
    if approval_policy in {"manual", "policy", "ask"}:
        if permission_context.mode == "approved":
            return PermissionDecision(behavior="allow", reasons=default_reasons)
        message = create_permission_request_message(tool.name, default_reasons)
        if permission_context.mode == "dont_ask":
            return PermissionDecision(
                behavior="deny",
                message=message,
                reasons=default_reasons or [message],
            )
        return PermissionDecision(
            behavior="ask",
            message=message,
            reasons=default_reasons,
        )

    return PermissionDecision(behavior="allow")


def resolve_tool_permission_decision(
    tool: ToolDef,
    tool_input: dict[str, Any] | None,
    permission_context: ToolPermissionContext,
    *,
    config: AutopilotConfig | None = None,
    project_id: str = "",
    record_denial: bool,
    actor: str = "",
    source: str = "",
) -> PermissionDecision:
    """Resolve one permission decision, including repeated-denial escalation."""

    decision = has_permissions_to_use_tool(tool, tool_input, permission_context)
    if config is None:
        return decision

    normalized_project_id = str(project_id or "").strip()
    if decision.behavior != "deny":
        reset_denial_breaker(config, project_id=normalized_project_id, tool_name=tool.name)
        final_decision = decision.model_copy(update={"denial_count": 0, "escalation_required": False})
        append_permission_audit_entry(
            config,
            project_id=normalized_project_id,
            tool=tool,
            tool_input=tool_input,
            decision=final_decision,
            actor=actor,
            source=source,
        )
        return final_decision

    tracker = (
        _record_denial(
            config,
            project_id=normalized_project_id,
            tool_name=tool.name,
            matched_rule=str(decision.matched_rule or "").strip(),
            message=decision.message,
        )
        if record_denial
        else _get_denial_count(
            config,
            project_id=normalized_project_id,
            tool_name=tool.name,
            matched_rule=str(decision.matched_rule or "").strip(),
        )
    )
    if not tracker.triggered:
        final_decision = decision.model_copy(update={"denial_count": tracker.count, "escalation_required": False})
        append_permission_audit_entry(
            config,
            project_id=normalized_project_id,
            tool=tool,
            tool_input=tool_input,
            decision=final_decision,
            actor=actor,
            source=source,
        )
        return final_decision

    escalation_message = (
        f"Tool `{tool.name}` hit the denial breaker after {tracker.count} denied attempts "
        "to break the denial loop and now requires explicit approval."
    )
    escalation_reasons = list(decision.reasons)
    if decision.message and decision.message not in escalation_reasons:
        escalation_reasons.append(decision.message)
    if escalation_message not in escalation_reasons:
        escalation_reasons.append(escalation_message)
    final_decision = PermissionDecision(
        behavior="ask",
        message=escalation_message,
        reasons=escalation_reasons,
        rule_source=decision.rule_source,
        matched_rule=decision.matched_rule,
        denial_count=tracker.count,
        escalation_required=True,
    )
    append_permission_audit_entry(
        config,
        project_id=normalized_project_id,
        tool=tool,
        tool_input=tool_input,
        decision=final_decision,
        actor=actor,
        source=source,
    )
    return final_decision
