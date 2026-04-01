"""Structured control handlers for headless runtime sessions."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autopilot.core.capability_store import load_connectors_registry
from autopilot.core.action_classifier import render_projected_tool_use
from autopilot.core.approval_runtime import annotate_approval_runtime, create_or_reuse_approval_runtime
from autopilot.core.command_permissions import (
    headless_permission_mode_allowed,
    normalize_permission_mode,
    sanitize_permission_context_for_mode,
)
from autopilot.core.config import AutopilotConfig
from autopilot.core.control_messages import (
    ControlRequestEnvelope,
    ControlResponseEnvelope,
    make_control_error_response,
    make_control_success_response,
)
from autopilot.core.plugin_loader import clear_plugin_cache
from autopilot.core.plugin_mcp import list_plugin_mcp_servers
from autopilot.core.plugins import resolve_loaded_plugins
from autopilot.core.plugin_storage import get_plugin_option_state
from autopilot.core.project_store import build_project_summary
from autopilot.core.structured_io import StructuredIO
from autopilot.core.tool_contracts import ToolResult, build_tool
from autopilot.core.tool_permission_runtime import (
    get_tool_permission_runtime,
    list_tool_permission_runtimes,
    resolve_tool_permission_runtime,
    serialize_tool_permission_runtime,
)
from autopilot.core.tool_permissions import (
    PermissionContextOverlay,
    load_tool_permission_context,
    resolve_tool_permission_decision,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _color_for_category(name: str) -> str:
    palette = {
        "runtime": "#2563eb",
        "project": "#0891b2",
        "stories": "#0f766e",
        "agents": "#7c3aed",
    }
    return palette.get(name, "#64748b")


@dataclass(slots=True)
class HeadlessControlSession:
    """Mutable runtime control session for one headless project run."""

    config: AutopilotConfig
    project_entry: dict[str, Any]
    session_id: str
    selected_model: str | None = None
    permission_mode: str | None = None
    output_style: str = "normal"
    available_output_styles: tuple[str, ...] = ("normal",)
    metadata: dict[str, Any] = field(default_factory=dict)
    _interrupt_request_id: str | None = None
    _interrupt_requested_at: str | None = None
    _interrupt_claimed: bool = False
    _lock: threading.RLock = field(default_factory=threading.RLock)

    @property
    def project_id(self) -> str:
        return str(self.project_entry["id"])

    @property
    def project_path(self) -> str:
        return str(self.project_entry["path"])

    def build_project_snapshot(self) -> dict[str, Any]:
        """Return the latest project summary for control replies."""

        return build_project_summary(self.config, self.project_entry)

    def current_model(self) -> str:
        """Return the currently selected runtime model/profile id."""

        with self._lock:
            if self.selected_model:
                return self.selected_model
        summary = self.build_project_snapshot()
        provider_config = dict(summary.get("provider_config") or {})
        launch_profile = dict(summary.get("launch_profile") or {})
        return (
            str(provider_config.get("id") or "").strip()
            or str(launch_profile.get("provider_config_id") or "").strip()
            or str(launch_profile.get("provider") or "").strip()
            or "autopilot"
        )

    def resolved_permission_mode(self) -> str:
        """Return the session-specific permission mode."""

        with self._lock:
            if self.permission_mode:
                return self.permission_mode
        return load_tool_permission_context(self.config, project_id=self.project_id).mode

    def _permission_context(self) -> Any:
        overlays = None
        if self.permission_mode:
            overlays = {"session": PermissionContextOverlay(mode=self.permission_mode)}
        context = load_tool_permission_context(
            self.config,
            project_id=self.project_id,
            overlays=overlays,
        )
        return sanitize_permission_context_for_mode(context)

    def _available_models(self) -> list[dict[str, Any]]:
        current_model = self.current_model()
        models: list[dict[str, Any]] = []
        for provider in self.config.resolved_provider_configs():
            models.append(
                {
                    "id": provider.id,
                    "family": provider.family,
                    "mode": provider.mode,
                    "transport": provider.transport,
                    "default": provider.id == current_model,
                }
            )
        if not models:
            models.append({"id": current_model, "family": current_model, "mode": "local", "transport": "cli", "default": True})
        return models

    def initialize_payload(self) -> dict[str, Any]:
        """Build the initialize control payload for one headless session."""

        summary = self.build_project_snapshot()
        provider_config = dict(summary.get("provider_config") or {})
        runtime_profile = dict(summary.get("runtime_profile") or {})
        return {
            "commands": [],
            "agents": [],
            "output_style": self.output_style,
            "available_output_styles": list(self.available_output_styles),
            "models": self._available_models(),
            "account": {
                "provider_family": str(provider_config.get("family") or ""),
                "provider_config_id": str(provider_config.get("id") or ""),
                "runtime_profile_id": str(runtime_profile.get("id") or ""),
            },
            "pid": os.getpid(),
            "session": {
                "session_id": self.session_id,
                "project_id": self.project_id,
                "project_name": str(summary.get("name") or self.project_entry.get("name") or ""),
                "project_path": self.project_path,
                "permission_mode": self.resolved_permission_mode(),
                "model": self.current_model(),
            },
        }

    def context_usage_payload(self) -> dict[str, Any]:
        """Build a minimal context-usage payload from current cost state."""

        summary = self.build_project_snapshot()
        cost_usage = dict(summary.get("cost_usage") or {})
        run_usage = dict(cost_usage.get("run") or {})
        run_tokens = int(run_usage.get("total_tokens") or 0)
        max_tokens = max(run_tokens, 1)
        categories = [
            {
                "name": "runtime",
                "tokens": run_tokens,
                "color": _color_for_category("runtime"),
            }
        ]
        if not run_tokens:
            categories[0]["tokens"] = 0
        return {
            "categories": categories,
            "totalTokens": run_tokens,
            "maxTokens": max_tokens,
            "rawMaxTokens": max_tokens,
            "percentage": 0 if run_tokens == 0 else round((run_tokens / max_tokens) * 100, 2),
            "gridRows": [],
            "model": self.current_model(),
            "memoryFiles": [],
            "mcpTools": [],
            "agents": [],
            "project": {
                "project_id": self.project_id,
                "project_name": str(summary.get("name") or self.project_entry.get("name") or ""),
                "status": str(summary.get("status") or ""),
                "runtime_profile": (summary.get("runtime_profile") or {}),
            },
        }

    def _materialize_pending_permission_runtime(
        self,
        *,
        tool: Any,
        request: Any,
        decision: Any,
        stage: str,
        specific_message_type: str,
        source: str,
    ) -> str:
        """Create or update one explicit pending permission runtime for bridge clients."""

        tool_use_id = str(request.tool_use_id or "").strip()
        agent_id = str(request.agent_id or "").strip()
        if not tool_use_id or not agent_id:
            return ""
        approval_runtime = create_or_reuse_approval_runtime(
            self.config,
            key=f"tool-permission:{self.project_id}:{tool.name}:{tool_use_id}",
            project_id=self.project_id,
            runtime_agent_ids=[agent_id],
            metadata={
                "kind": "tool_permission_request",
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
                "source": source,
            },
            publish_pending=True,
            pending_message_type="tool_permission_pending",
            pending_payload={
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
                "message": decision.message,
                "behavior": decision.behavior,
            },
        )
        annotate_approval_runtime(
            self.config,
            approval_runtime_id=approval_runtime.id,
            metadata_updates={
                "pending": {
                    "stage": stage,
                    "tool_name": tool.name,
                    "tool_use_id": tool_use_id,
                }
            },
            payload_updates={
                stage: {
                    "tool_name": tool.name,
                    "tool_use_id": tool_use_id,
                    "message": decision.message,
                    "matched_rule": decision.matched_rule,
                    "reasons": list(decision.reasons),
                }
            },
            mailbox_message_type=specific_message_type,
            mailbox_payload={
                "tool_name": tool.name,
                "tool_use_id": tool_use_id,
                "message": decision.message,
                "behavior": decision.behavior,
                "matched_rule": decision.matched_rule,
            },
        )
        return approval_runtime.id

    def can_use_tool_payload(self, request: Any) -> dict[str, Any]:
        """Evaluate a can_use_tool request under the current permission context."""

        tool = build_tool(
            name=str(request.tool_name),
            description=str(request.description or request.display_name or request.title or request.tool_name),
            approval_policy="ask",
            execute=lambda tool_input, _: ToolResult(status="ok", payload=dict(tool_input)),
            metadata={
                "command": str((request.input or {}).get("command") or "").strip(),
                "project_id": self.project_id,
                "rule_content": str((request.input or {}).get("rule_content") or "").strip(),
            },
        )
        decision = resolve_tool_permission_decision(
            tool,
            dict(request.input or {}),
            self._permission_context(),
            classifier_context={
                "enabled": bool(request.classifier_enabled),
                "user_text": str(request.user_text or ""),
                "decision_reason": str(request.decision_reason or ""),
                "mode": str(request.classifier_mode or "sync"),
                "fail_open": bool(request.classifier_fail_open),
            },
            config=self.config,
            project_id=self.project_id,
            record_denial=True,
            actor="headless_control",
            source="headless_control.can_use_tool",
        )
        approval_runtime_id = ""
        if decision.behavior == "pending_classifier":
            approval_runtime_id = self._materialize_pending_permission_runtime(
                tool=tool,
                request=request,
                decision=decision,
                stage="pending_classifier",
                specific_message_type="tool_permission_classifier_pending",
                source="headless_control.classifier",
            )
            if approval_runtime_id:
                annotate_approval_runtime(
                    self.config,
                    approval_runtime_id=approval_runtime_id,
                    metadata_updates={
                        "classifier": {
                            "stage": "pending_classifier",
                            "mode": str(request.classifier_mode or "deferred"),
                            "tool_name": tool.name,
                            "tool_use_id": str(request.tool_use_id).strip(),
                        }
                    },
                    payload_updates={
                        "classifier": {
                            "message": decision.message,
                            "matched_rule": decision.matched_rule,
                            "projected_tool_use": render_projected_tool_use(tool, dict(request.input or {})),
                            "user_text": str(request.user_text or ""),
                            "decision_reason": str(request.decision_reason or ""),
                        }
                    },
                )
        elif decision.behavior == "ask":
            pending_user_decision = decision.model_copy(update={"behavior": "pending_user"})
            approval_runtime_id = self._materialize_pending_permission_runtime(
                tool=tool,
                request=request,
                decision=pending_user_decision,
                stage="pending_user",
                specific_message_type="tool_permission_user_pending",
                source="headless_control.user",
            )
            if approval_runtime_id:
                decision = pending_user_decision
        return {
            "behavior": decision.behavior,
            "message": decision.message,
            "reasons": list(decision.reasons),
            "rule_source": decision.rule_source,
            "matched_rule": decision.matched_rule,
            "denial_count": decision.denial_count,
            "escalation_required": decision.escalation_required,
            "tool_use_id": str(request.tool_use_id),
            "tool_name": str(request.tool_name),
            "permission_mode": self.resolved_permission_mode(),
            "approval_runtime_id": approval_runtime_id,
        }

    def interrupt_status_payload(self) -> dict[str, Any]:
        """Return the current structured interrupt state for the runtime."""

        with self._lock:
            requested = self._interrupt_requested_at is not None
            return {
                "requested": requested,
                "claimed": self._interrupt_claimed,
                "request_id": self._interrupt_request_id,
                "requested_at": self._interrupt_requested_at,
                "applies_at": "next_safe_checkpoint",
            }

    def request_interrupt(self, request_id: str) -> dict[str, Any]:
        """Mark one structured interrupt request for later application."""

        normalized = str(request_id or "").strip() or None
        with self._lock:
            already_requested = self._interrupt_requested_at is not None
            if not already_requested:
                self._interrupt_request_id = normalized
                self._interrupt_requested_at = _utcnow_iso()
                self._interrupt_claimed = False
            payload = self.interrupt_status_payload()
        return {
            "accepted": True,
            "already_requested": already_requested,
            "project_id": self.project_id,
            "project_path": self.project_path,
            "interrupt": payload,
        }

    def interrupt_requested(self) -> bool:
        """Return whether the session has a pending interrupt request."""

        with self._lock:
            return self._interrupt_requested_at is not None

    def take_interrupt(self) -> dict[str, str] | None:
        """Claim the first pending interrupt request, if any."""

        with self._lock:
            if self._interrupt_requested_at is None or self._interrupt_claimed:
                return None
            self._interrupt_claimed = True
            return {
                "request_id": self._interrupt_request_id or "",
                "requested_at": self._interrupt_requested_at,
            }

    def mcp_status_payload(self) -> dict[str, Any]:
        """Return live plugin/MCP runtime state for structured control clients."""

        plugins = resolve_loaded_plugins(self.config)
        option_states = {
            plugin.plugin_id: get_plugin_option_state(self.config, plugin)
            for plugin in plugins
        }
        mcp_servers = list_plugin_mcp_servers(self.config)
        managed_connectors = [
            connector
            for connector in load_connectors_registry(self.config)
            if connector.managed and connector.origin_plugin_id
        ]
        plugin_payloads: list[dict[str, Any]] = []
        for plugin in plugins:
            option_state = option_states[plugin.plugin_id]
            related_servers = [server for server in mcp_servers if server.plugin_id == plugin.plugin_id]
            invalid_server_count = sum(1 for server in related_servers if server.validation_status != "valid")
            plugin_payloads.append(
                {
                    "plugin_id": plugin.plugin_id,
                    "display_name": plugin.display_name or plugin.name,
                    "enabled": plugin.enabled,
                    "validation_status": plugin.validation_status,
                    "validation_errors": list(plugin.validation_errors),
                    "configured_option_keys": list(option_state.configured_keys),
                    "unconfigured_option_keys": list(option_state.unconfigured_keys),
                    "option_validation_errors": dict(option_state.validation_errors),
                    "mcp_server_count": len(related_servers),
                    "invalid_mcp_server_count": invalid_server_count,
                }
            )
        plugin_payloads.sort(key=lambda item: (str(item["display_name"]).lower(), str(item["plugin_id"])))
        connector_payloads = [
            {
                "id": connector.id,
                "name": connector.name,
                "enabled": connector.enabled,
                "transport": connector.transport,
                "validation_status": connector.validation_status,
                "origin_plugin_id": connector.origin_plugin_id,
                "origin_server_name": connector.origin_server_name,
            }
            for connector in managed_connectors
        ]
        connector_payloads.sort(key=lambda item: (str(item["origin_plugin_id"]), str(item["origin_server_name"]), str(item["id"])))
        invalid_server_count = sum(1 for server in mcp_servers if server.validation_status != "valid")
        return {
            "summary": {
                "plugin_count": len(plugins),
                "enabled_plugin_count": sum(1 for plugin in plugins if plugin.enabled),
                "invalid_plugin_count": sum(1 for plugin in plugins if plugin.validation_status != "valid"),
                "mcp_server_count": len(mcp_servers),
                "invalid_mcp_server_count": invalid_server_count,
                "managed_connector_count": len(connector_payloads),
            },
            "plugins": plugin_payloads,
            "mcp_servers": [server.model_dump() for server in mcp_servers],
            "managed_connectors": connector_payloads,
        }

    def reload_plugins_payload(self) -> dict[str, Any]:
        """Force one plugin rescan and return refreshed runtime state."""

        clear_plugin_cache()
        return {
            "reloaded_at": _utcnow_iso(),
            **self.mcp_status_payload(),
        }

    def list_tool_permission_runtimes_payload(self, request: Any) -> dict[str, Any]:
        """List tool-permission runtimes scoped to the current headless project."""

        runtimes = [
            serialize_tool_permission_runtime(record)
            for record in list_tool_permission_runtimes(
                self.config,
                project_id=self.project_id,
                runtime_agent_id=str(request.runtime_agent_id or "").strip() or None,
                status=str(request.status or "").strip() or None,
                pending_stage=str(request.pending_stage or "").strip() or None,
            )
        ]
        return {
            "summary": {
                "count": len(runtimes),
                "pending_count": sum(1 for runtime in runtimes if str(runtime.get("status") or "") == "pending"),
            },
            "runtimes": runtimes,
        }

    def get_tool_permission_runtime_payload(self, request: Any) -> dict[str, Any]:
        """Return one tool-permission runtime for the current headless project."""

        runtime = get_tool_permission_runtime(self.config, str(request.approval_runtime_id or "").strip())
        if runtime is None or runtime.project_id != self.project_id:
            raise KeyError(str(request.approval_runtime_id or "").strip())
        return {"runtime": serialize_tool_permission_runtime(runtime)}

    def resolve_tool_permission_runtime_payload(self, request: Any) -> dict[str, Any]:
        """Resolve one tool-permission runtime through the structured control channel."""

        runtime = get_tool_permission_runtime(self.config, str(request.approval_runtime_id or "").strip())
        if runtime is None or runtime.project_id != self.project_id:
            raise KeyError(str(request.approval_runtime_id or "").strip())
        resolved = resolve_tool_permission_runtime(
            self.config,
            runtime.id,
            outcome=request.outcome,
            actor=str(request.actor or "human"),
            note=str(request.note or ""),
            source=request.source,
        )
        return {"runtime": serialize_tool_permission_runtime(resolved)}

    def handle_request(self, request: ControlRequestEnvelope | dict[str, Any]) -> ControlResponseEnvelope:
        """Resolve one inbound control request for the headless runtime."""

        if not isinstance(request, ControlRequestEnvelope):
            request = ControlRequestEnvelope.model_validate(request)
        subtype = request.request.subtype
        if subtype == "initialize":
            return make_control_success_response(
                request.request_id,
                response=self.initialize_payload(),
                session_id=self.session_id,
            )
        if subtype == "get_context_usage":
            return make_control_success_response(
                request.request_id,
                response=self.context_usage_payload(),
                session_id=self.session_id,
            )
        if subtype == "interrupt":
            return make_control_success_response(
                request.request_id,
                response=self.request_interrupt(request.request_id),
                session_id=self.session_id,
            )
        if subtype == "set_model":
            with self._lock:
                self.selected_model = request.request.model
            return make_control_success_response(
                request.request_id,
                response={"model": self.current_model()},
                session_id=self.session_id,
            )
        if subtype == "set_permission_mode":
            try:
                normalized_mode = normalize_permission_mode(str(request.request.mode))
            except ValueError as exc:
                return make_control_error_response(
                    request.request_id,
                    error=str(exc),
                    session_id=self.session_id,
                )
            if not headless_permission_mode_allowed(normalized_mode):
                return make_control_error_response(
                    request.request_id,
                    error=f"Permission mode `{normalized_mode}` is not available from structured headless control.",
                    session_id=self.session_id,
                )
            with self._lock:
                self.permission_mode = normalized_mode
            sanitized = self._permission_context()
            transition = dict(sanitized.metadata.get("mode_transition") or {})
            return make_control_success_response(
                request.request_id,
                response={
                    "mode": self.resolved_permission_mode(),
                    "stripped_allow_rules": list(transition.get("stripped_allow_rules") or []),
                },
                session_id=self.session_id,
            )
        if subtype == "can_use_tool":
            return make_control_success_response(
                request.request_id,
                response=self.can_use_tool_payload(request.request),
                session_id=self.session_id,
            )
        if subtype == "mcp_status":
            return make_control_success_response(
                request.request_id,
                response=self.mcp_status_payload(),
                session_id=self.session_id,
            )
        if subtype == "reload_plugins":
            return make_control_success_response(
                request.request_id,
                response=self.reload_plugins_payload(),
                session_id=self.session_id,
            )
        if subtype == "list_tool_permission_runtimes":
            return make_control_success_response(
                request.request_id,
                response=self.list_tool_permission_runtimes_payload(request.request),
                session_id=self.session_id,
            )
        if subtype == "get_tool_permission_runtime":
            try:
                payload = self.get_tool_permission_runtime_payload(request.request)
            except KeyError:
                return make_control_error_response(
                    request.request_id,
                    error=f"Tool-permission runtime `{request.request.approval_runtime_id}` was not found in this session.",
                    session_id=self.session_id,
                )
            return make_control_success_response(
                request.request_id,
                response=payload,
                session_id=self.session_id,
            )
        if subtype == "resolve_tool_permission_runtime":
            try:
                payload = self.resolve_tool_permission_runtime_payload(request.request)
            except KeyError:
                return make_control_error_response(
                    request.request_id,
                    error=f"Tool-permission runtime `{request.request.approval_runtime_id}` was not found in this session.",
                    session_id=self.session_id,
                )
            except RuntimeError as exc:
                return make_control_error_response(
                    request.request_id,
                    error=str(exc),
                    session_id=self.session_id,
                )
            return make_control_success_response(
                request.request_id,
                response=payload,
                session_id=self.session_id,
            )
        return make_control_error_response(
            request.request_id,
            error=f"Headless runtime does not handle control_request subtype: {subtype}",
            session_id=self.session_id,
        )


def attach_headless_control_handlers(
    runtime: StructuredIO,
    session: HeadlessControlSession,
) -> HeadlessControlSession:
    """Attach synchronous control handlers to one structured headless runtime."""

    def _on_control_request(request: ControlRequestEnvelope) -> None:
        try:
            response = session.handle_request(request)
        except Exception as exc:
            response = make_control_error_response(
                request.request_id,
                error=str(exc),
                session_id=session.session_id,
            )
        runtime.emit_control_response(response)

    runtime.set_on_control_request_received(_on_control_request)
    return session


def create_headless_control_session(
    config: AutopilotConfig,
    *,
    project_entry: dict[str, Any],
    session_id: str,
) -> HeadlessControlSession:
    """Create one default headless control session for a project run."""

    summary = build_project_summary(config, project_entry)
    provider_config = dict(summary.get("provider_config") or {})
    permission_context = load_tool_permission_context(config, project_id=str(project_entry["id"]))
    return HeadlessControlSession(
        config=config,
        project_entry=project_entry,
        session_id=session_id,
        selected_model=str(provider_config.get("id") or "").strip() or None,
        permission_mode=permission_context.mode,
        metadata={"project_path": str(Path(project_entry["path"]).expanduser())},
    )


__all__ = [
    "HeadlessControlSession",
    "attach_headless_control_handlers",
    "create_headless_control_session",
]
