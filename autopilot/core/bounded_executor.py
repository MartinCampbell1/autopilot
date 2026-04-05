"""Bounded step-by-step executor for machine-readable execution blueprints."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel, Field

from autopilot.core.execution_blueprint import ExecutionBlueprint, StepNode, TerminalVerdict, TransitionGuard


class BoundedStepExecution(BaseModel):
    """One visited step in a bounded execution walk."""

    step_id: str
    binding_index: int
    status: str
    next_step_id: str | None = None
    terminal_verdict_id: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class BoundedExecutionResult(BaseModel):
    """Structured result of walking an execution blueprint."""

    visited_node_ids: list[str] = Field(default_factory=list)
    step_results: list[BoundedStepExecution] = Field(default_factory=list)
    terminal_verdict: TerminalVerdict
    stopped_early: bool = False
    continue_on_error: bool = True


def _sanitize_result(result: dict[str, Any], *, allowed_fields: list[str]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key in allowed_fields:
        if key in result:
            sanitized[str(key)] = result[key]
    if "status" not in sanitized:
        sanitized["status"] = str(result.get("status") or "unknown")
    return sanitized


def _find_transition(node: StepNode, status: str) -> TransitionGuard | None:
    for transition in node.transitions:
        if status in transition.statuses:
            return transition
    return None


def _resolve_terminal_verdict(
    blueprint: ExecutionBlueprint,
    *,
    step_results: list[BoundedStepExecution],
    forced_terminal_verdict_id: str | None = None,
) -> TerminalVerdict:
    verdicts = {verdict.id: verdict for verdict in blueprint.terminal_verdicts}
    if forced_terminal_verdict_id and forced_terminal_verdict_id in verdicts:
        return verdicts[forced_terminal_verdict_id]

    statuses = [step.status for step in step_results]
    if any(status == "error" for status in statuses):
        if any(status not in {"error"} for status in statuses):
            return verdicts.get("partial") or TerminalVerdict(id="partial", state="partial", reason="Bounded execution completed with at least one failing step.")
        return verdicts.get("error") or TerminalVerdict(id="error", state="error", reason="Bounded execution stopped on a failing step.")
    if any(status in {"pending_approval", "planned_request_approval"} for status in statuses):
        return verdicts.get("requires_approval") or TerminalVerdict(id="requires_approval", state="requires_approval", reason="Bounded execution produced an approval handoff.")
    return verdicts.get("completed") or TerminalVerdict(id="completed", state="completed", reason="Bounded execution completed successfully.")


def execute_bounded_execution_blueprint(
    blueprint: ExecutionBlueprint,
    *,
    actions: list[dict[str, Any]],
    step_executor: Callable[[StepNode, dict[str, Any]], dict[str, Any]],
    continue_on_error: bool,
) -> BoundedExecutionResult:
    """Walk a blueprint node-by-node and execute only the allowed step schema."""

    nodes = {node.id: node for node in blueprint.step_nodes}
    if blueprint.entry_step_id not in nodes:
        raise KeyError(f"Execution blueprint entry step `{blueprint.entry_step_id}` does not exist.")

    current_step_id = blueprint.entry_step_id
    visited_node_ids: list[str] = []
    step_results: list[BoundedStepExecution] = []
    forced_terminal_verdict_id: str | None = None
    stopped_early = False

    while current_step_id:
        node = nodes.get(current_step_id)
        if node is None:
            raise KeyError(f"Execution blueprint step `{current_step_id}` does not exist.")
        if node.binding_index < 0 or node.binding_index >= len(actions):
            raise IndexError(
                f"Execution blueprint step `{node.id}` points at action index `{node.binding_index}` outside the selected action set."
            )

        visited_node_ids.append(node.id)
        raw_result = dict(step_executor(node, dict(actions[node.binding_index])) or {})
        sanitized_result = _sanitize_result(raw_result, allowed_fields=list(node.allowed_result_fields))
        status = str(sanitized_result.get("status") or "unknown")
        transition = _find_transition(node, status)
        next_step_id = transition.next_step_id if transition is not None else None
        terminal_verdict_id = transition.terminal_verdict_id if transition is not None else None

        step_results.append(
            BoundedStepExecution(
                step_id=node.id,
                binding_index=node.binding_index,
                status=status,
                next_step_id=next_step_id,
                terminal_verdict_id=terminal_verdict_id,
                result=sanitized_result,
            )
        )

        if status == "error" and not continue_on_error:
            forced_terminal_verdict_id = "error"
            stopped_early = True
            break
        if terminal_verdict_id:
            forced_terminal_verdict_id = terminal_verdict_id
            break
        current_step_id = next_step_id

    terminal_verdict = _resolve_terminal_verdict(
        blueprint,
        step_results=step_results,
        forced_terminal_verdict_id=forced_terminal_verdict_id,
    )
    return BoundedExecutionResult(
        visited_node_ids=visited_node_ids,
        step_results=step_results,
        terminal_verdict=terminal_verdict,
        stopped_early=stopped_early,
        continue_on_error=continue_on_error,
    )


__all__ = [
    "BoundedExecutionResult",
    "BoundedStepExecution",
    "execute_bounded_execution_blueprint",
]
