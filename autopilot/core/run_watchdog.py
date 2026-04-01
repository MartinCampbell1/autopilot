"""Wall-clock watchdog checks for project runs and individual stories."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from autopilot.core.runtime_budgets import ensure_budget_state


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: Any) -> datetime | None:
    rendered = str(value or "").strip()
    if not rendered:
        return None
    try:
        return datetime.fromisoformat(rendered.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class RuntimeWatchdogDecision:
    triggered: bool
    scope: Literal["run", "story"] | None = None
    reason: str = ""
    elapsed_seconds: int = 0
    limit_seconds: int = 0
    story_id: int | None = None


def _build_timeout_reason(*, scope: Literal["run", "story"], elapsed_seconds: int, limit_seconds: int, story_id: int | None = None) -> str:
    if scope == "story" and story_id is not None:
        return (
            f"Story watchdog triggered for story {story_id}: "
            f"elapsed {elapsed_seconds}s exceeded limit {limit_seconds}s."
        )
    return f"Run watchdog triggered: elapsed {elapsed_seconds}s exceeded limit {limit_seconds}s."


def check_runtime_watchdog(
    state: dict[str, Any],
    *,
    story_id: int | None = None,
    now: datetime | None = None,
) -> RuntimeWatchdogDecision:
    """Return one timeout decision for the active run/story, if any."""

    now = now or _utcnow()
    policy, usage = ensure_budget_state(state)

    if story_id is not None:
        story_state = dict((state.get("story_state") or {}).get(str(story_id)) or {})
        story_started_at = _parse_iso(story_state.get("started_at"))
        story_limit_seconds = int(policy.get("story_max_runtime_seconds") or 0)
        if (
            story_limit_seconds > 0
            and story_started_at is not None
            and str(story_state.get("status") or "") in {"in_progress", "merge_blocked"}
        ):
            elapsed_seconds = max(int((now - story_started_at).total_seconds()), 0)
            if elapsed_seconds > story_limit_seconds:
                return RuntimeWatchdogDecision(
                    triggered=True,
                    scope="story",
                    reason=_build_timeout_reason(
                        scope="story",
                        elapsed_seconds=elapsed_seconds,
                        limit_seconds=story_limit_seconds,
                        story_id=story_id,
                    ),
                    elapsed_seconds=elapsed_seconds,
                    limit_seconds=story_limit_seconds,
                    story_id=story_id,
                )

    run_started_at = _parse_iso((usage.get("run") or {}).get("started_at"))
    run_limit_seconds = int(policy.get("run_max_runtime_seconds") or 0)
    if run_limit_seconds > 0 and run_started_at is not None:
        elapsed_seconds = max(int((now - run_started_at).total_seconds()), 0)
        if elapsed_seconds > run_limit_seconds:
            return RuntimeWatchdogDecision(
                triggered=True,
                scope="run",
                reason=_build_timeout_reason(
                    scope="run",
                    elapsed_seconds=elapsed_seconds,
                    limit_seconds=run_limit_seconds,
                ),
                elapsed_seconds=elapsed_seconds,
                limit_seconds=run_limit_seconds,
                story_id=story_id,
            )

    return RuntimeWatchdogDecision(triggered=False)


__all__ = [
    "RuntimeWatchdogDecision",
    "check_runtime_watchdog",
]
