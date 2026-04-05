"""Unified runtime budget and watchdog enforcement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from autopilot.core.run_watchdog import check_runtime_watchdog
from autopilot.core.runtime_budgets import consume_iteration_budget


@dataclass(frozen=True)
class BudgetEnforcementDecision:
    """One normalized runtime-enforcement outcome."""

    allowed: bool
    kind: Literal["ok", "budget", "watchdog"] = "ok"
    reason: str = ""
    scope: Literal["run", "story"] | None = None
    story_id: int | None = None
    elapsed_seconds: int = 0
    limit_seconds: int = 0

    @property
    def triggered(self) -> bool:
        return not self.allowed

    def as_event_extra(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}
        if self.scope is not None:
            extra["scope"] = self.scope
        if self.kind == "watchdog":
            extra["elapsed_seconds"] = self.elapsed_seconds
            extra["limit_seconds"] = self.limit_seconds
        return extra


def _allowed_decision() -> BudgetEnforcementDecision:
    return BudgetEnforcementDecision(allowed=True)


def check_budget_enforcement(
    state: dict[str, Any],
    *,
    story_id: int | None = None,
    now: datetime | None = None,
) -> BudgetEnforcementDecision:
    """Check runtime watchdogs and normalize the result."""

    watchdog = check_runtime_watchdog(state, story_id=story_id, now=now)
    if not watchdog.triggered:
        return _allowed_decision()
    return BudgetEnforcementDecision(
        allowed=False,
        kind="watchdog",
        reason=watchdog.reason,
        scope=watchdog.scope,
        story_id=watchdog.story_id,
        elapsed_seconds=watchdog.elapsed_seconds,
        limit_seconds=watchdog.limit_seconds,
    )


def reserve_iteration_with_budget_enforcement(
    state: dict[str, Any],
    *,
    story_id: int | None = None,
    worker_label: str,
    critic_label: str,
    now: datetime | None = None,
) -> BudgetEnforcementDecision:
    """Reserve one iteration only if watchdogs and budgets still allow it."""

    decision = check_budget_enforcement(state, story_id=story_id, now=now)
    if decision.triggered:
        return decision

    allowed, reason = consume_iteration_budget(
        state,
        story_id=story_id,
        worker_label=worker_label,
        critic_label=critic_label,
    )
    if allowed:
        return _allowed_decision()
    return BudgetEnforcementDecision(
        allowed=False,
        kind="budget",
        reason=str(reason or "Runtime budget exhausted."),
        story_id=story_id,
    )


__all__ = [
    "BudgetEnforcementDecision",
    "check_budget_enforcement",
    "reserve_iteration_with_budget_enforcement",
]
