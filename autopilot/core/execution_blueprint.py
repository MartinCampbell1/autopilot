"""Machine-readable execution blueprints for bounded execution-plane runs."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from autopilot.core.atomic_io import atomic_write_json as _shared_atomic_write_json
from autopilot.core.config import AutopilotConfig

_SUPPORTED_BLUEPRINT_ACTION_TYPES = {"suggested_command"}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _shared_atomic_write_json(path, payload)


class TransitionGuard(BaseModel):
    """One bounded transition from a step node based on observed status."""

    statuses: list[str] = Field(default_factory=list)
    next_step_id: str | None = None
    terminal_verdict_id: str | None = None


class StepNode(BaseModel):
    """One execution step bound by an allowed result schema and explicit transitions."""

    id: str
    index: int
    binding_index: int
    action_type: str = "suggested_command"
    command: str = ""
    planned_mode: str = "auto"
    allowed_result_fields: list[str] = Field(default_factory=list)
    transitions: list[TransitionGuard] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TerminalVerdict(BaseModel):
    """One explicit terminal outcome for a bounded execution graph."""

    id: str
    state: Literal["completed", "requires_approval", "partial", "error"]
    reason: str


class ExecutionBlueprint(BaseModel):
    """Execution graph that can be cached and rebound to compatible action selections."""

    id: str
    cache_key: str
    family_key: str
    task_family: str
    planner: dict[str, Any] = Field(default_factory=dict)
    follower: dict[str, Any] = Field(default_factory=dict)
    entry_step_id: str
    step_nodes: list[StepNode] = Field(default_factory=list)
    terminal_verdicts: list[TerminalVerdict] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ExecutionBlueprintPlan(BaseModel):
    """Planner result describing whether bounded execution can be used safely."""

    strategy: Literal["bounded_blueprint", "freeform"]
    blueprint: ExecutionBlueprint | None = None
    cache_hit: bool = False
    fallback_reason: str = ""
    route_policy: dict[str, Any] = Field(default_factory=dict)


def execution_blueprint_cache_path(config: AutopilotConfig, cache_key: str) -> Path:
    """Return the persisted cache path for one blueprint family."""

    return config.control_plane_state_dir / "execution_blueprints" / f"{cache_key}.json"


def get_execution_blueprint(config: AutopilotConfig, cache_key: str) -> ExecutionBlueprint | None:
    """Load one cached execution blueprint if present."""

    path = execution_blueprint_cache_path(config, cache_key)
    if not path.exists():
        return None
    try:
        return ExecutionBlueprint.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_execution_blueprint(
    config: AutopilotConfig,
    blueprint: ExecutionBlueprint,
) -> ExecutionBlueprint:
    """Persist one execution blueprint into the control-plane cache."""

    blueprint.updated_at = _utcnow_iso()
    _atomic_write_json(execution_blueprint_cache_path(config, blueprint.cache_key), blueprint.model_dump())
    return blueprint


def _normalized_action_signature(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "action_type": str(action.get("action_type") or "").strip(),
        "command": str(action.get("command") or "").strip(),
        "approval_required": bool(action.get("approval_required")),
        "project_id": str(action.get("project_id") or "").strip(),
        "runtime_agent_id": str(action.get("runtime_agent_id") or "").strip(),
    }


def derive_execution_blueprint_task_family(
    actions: list[dict[str, Any]],
    *,
    requested_mode: str,
    policy_profile: str,
) -> str:
    """Build a stable task-family key for action selections with the same shape."""

    digest = hashlib.sha1(
        json.dumps(
            {
                "requested_mode": str(requested_mode or "").strip(),
                "policy_profile": str(policy_profile or "").strip(),
                "actions": [_normalized_action_signature(action) for action in actions],
            },
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"action_batch_{digest}"


def derive_execution_blueprint_cache_key(
    actions: list[dict[str, Any]],
    *,
    requested_mode: str,
    policy_profile: str,
) -> str:
    """Build a stable cache key for one blueprint family."""

    return f"xbp_{derive_execution_blueprint_task_family(actions, requested_mode=requested_mode, policy_profile=policy_profile)}"


def _route_policy(
    *,
    requested_mode: str,
    selected_count: int,
    approval_required_count: int,
) -> dict[str, Any]:
    return {
        "planner": {
            "kind": "deterministic_blueprint_planner",
            "routing_tier": "stronger" if selected_count > 1 or approval_required_count > 0 else "default",
        },
        "follower": {
            "kind": "bounded_executor",
            "routing_tier": "cheaper",
            "requested_mode": str(requested_mode or "").strip() or "auto",
        },
    }


def _allowed_result_fields() -> list[str]:
    return [
        "status",
        "message",
        "action",
        "command_result",
        "approval",
        "issue",
        "policy_triggered",
        "policy_reasons",
        "project",
        "planned_mode",
        "async_task",
    ]


def _build_execution_blueprint(
    *,
    cache_key: str,
    task_family: str,
    requested_mode: str,
    actions: list[dict[str, Any]],
) -> ExecutionBlueprint:
    created_at = _utcnow_iso()
    step_nodes: list[StepNode] = []
    terminal_verdicts = [
        TerminalVerdict(id="completed", state="completed", reason="All bounded steps settled without requiring free-form recovery."),
        TerminalVerdict(id="requires_approval", state="requires_approval", reason="At least one bounded step requires an explicit approval handoff."),
        TerminalVerdict(id="partial", state="partial", reason="At least one bounded step failed but the executor completed the bounded walk."),
        TerminalVerdict(id="error", state="error", reason="A bounded step failed and execution stopped early."),
    ]
    for index, action in enumerate(actions, start=1):
        next_step_id = f"step_{index + 1}" if index < len(actions) else None
        step_nodes.append(
            StepNode(
                id=f"step_{index}",
                index=index,
                binding_index=index - 1,
                action_type=str(action.get("action_type") or ""),
                command=str(action.get("command") or ""),
                planned_mode=str(requested_mode or "").strip() or "auto",
                allowed_result_fields=_allowed_result_fields(),
                transitions=[
                    TransitionGuard(
                        statuses=[
                            "ok",
                            "planned_execute",
                            "planned_request_approval",
                            "pending_approval",
                            "pending_async",
                            "skipped",
                            "not_executable",
                        ],
                        next_step_id=next_step_id,
                        terminal_verdict_id="completed" if next_step_id is None else None,
                    ),
                    TransitionGuard(
                        statuses=["error"],
                        next_step_id=next_step_id,
                        terminal_verdict_id="partial" if next_step_id is None else None,
                    ),
                ],
                metadata={
                    "approval_required": bool(action.get("approval_required")),
                    "priority": str(action.get("priority") or "").strip(),
                    "runtime_agent_id": str(action.get("runtime_agent_id") or "").strip(),
                    "project_id": str(action.get("project_id") or "").strip(),
                },
            )
        )

    approval_required_count = sum(1 for action in actions if bool(action.get("approval_required")))
    return ExecutionBlueprint(
        id=f"xbp_{hashlib.sha1(cache_key.encode('utf-8')).hexdigest()[:10]}",
        cache_key=cache_key,
        family_key=task_family,
        task_family=task_family,
        planner={
            **_route_policy(
                requested_mode=requested_mode,
                selected_count=len(actions),
                approval_required_count=approval_required_count,
            )["planner"],
            "cached": True,
        },
        follower={
            **_route_policy(
                requested_mode=requested_mode,
                selected_count=len(actions),
                approval_required_count=approval_required_count,
            )["follower"],
            "allowed_result_fields": _allowed_result_fields(),
        },
        entry_step_id=step_nodes[0].id,
        step_nodes=step_nodes,
        terminal_verdicts=terminal_verdicts,
        metadata={
            "selected_count": len(actions),
            "approval_required_count": approval_required_count,
            "commands": [str(action.get("command") or "") for action in actions],
            "action_types": [str(action.get("action_type") or "") for action in actions],
        },
        created_at=created_at,
        updated_at=created_at,
    )


def _can_cover_with_blueprint(actions: list[dict[str, Any]]) -> str:
    if not actions:
        return "no_selected_actions"
    unsupported = sorted(
        {
            str(action.get("action_type") or "").strip() or "unknown"
            for action in actions
            if str(action.get("action_type") or "").strip() not in _SUPPORTED_BLUEPRINT_ACTION_TYPES
        }
    )
    if unsupported:
        return f"unsupported_action_types:{','.join(unsupported)}"
    missing_commands = any(not str(action.get("command") or "").strip() for action in actions)
    if missing_commands:
        return "missing_command"
    return ""


def plan_execution_blueprint(
    config: AutopilotConfig,
    *,
    actions: list[dict[str, Any]],
    requested_mode: str,
    policy_profile: str,
) -> ExecutionBlueprintPlan:
    """Return a cached or freshly planned execution blueprint when the selection is safely coverable."""

    fallback_reason = _can_cover_with_blueprint(actions)
    route_policy = _route_policy(
        requested_mode=requested_mode,
        selected_count=len(actions),
        approval_required_count=sum(1 for action in actions if bool(action.get("approval_required"))),
    )
    if fallback_reason:
        return ExecutionBlueprintPlan(
            strategy="freeform",
            fallback_reason=fallback_reason,
            route_policy=route_policy,
        )

    task_family = derive_execution_blueprint_task_family(
        actions,
        requested_mode=requested_mode,
        policy_profile=policy_profile,
    )
    cache_key = derive_execution_blueprint_cache_key(
        actions,
        requested_mode=requested_mode,
        policy_profile=policy_profile,
    )
    cached = get_execution_blueprint(config, cache_key)
    if cached is not None:
        return ExecutionBlueprintPlan(
            strategy="bounded_blueprint",
            blueprint=cached,
            cache_hit=True,
            route_policy=route_policy,
        )

    planned = _build_execution_blueprint(
        cache_key=cache_key,
        task_family=task_family,
        requested_mode=requested_mode,
        actions=actions,
    )
    save_execution_blueprint(config, planned)
    return ExecutionBlueprintPlan(
        strategy="bounded_blueprint",
        blueprint=planned,
        cache_hit=False,
        route_policy=route_policy,
    )


__all__ = [
    "ExecutionBlueprint",
    "ExecutionBlueprintPlan",
    "StepNode",
    "TerminalVerdict",
    "TransitionGuard",
    "derive_execution_blueprint_cache_key",
    "derive_execution_blueprint_task_family",
    "execution_blueprint_cache_path",
    "get_execution_blueprint",
    "plan_execution_blueprint",
    "save_execution_blueprint",
]
