"""Escalation chain for rotating providers when a story gets stuck."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderAttempt:
    provider: str
    failures: list[str] = field(default_factory=list)


@dataclass
class EscalationResult:
    exhausted: bool
    current_provider: str
    context_summary: str


@dataclass(frozen=True)
class AttemptPlan:
    """One bounded worker attempt for a task."""

    attempt: int
    provider: str
    strategy: str


@dataclass(frozen=True)
class CompetingAttempt:
    """One evaluated attempt competing to satisfy a task."""

    attempt: int
    provider: str
    strategy: str
    outcome: str
    valid: bool = False
    gates_passed: bool = False
    critic_approved: bool | None = None
    quality_regression: bool = False
    git_diff_empty: bool = False


_ATTEMPT_STRATEGY_PRIORITY = {
    "primary": 30,
    "focused_retry": 20,
    "fresh_build": 10,
}


def attempt_strategy_label(strategy: str) -> str:
    """Return a human-readable attempt label."""
    return {
        "primary": "primary build",
        "focused_retry": "focused retry",
        "fresh_build": "fresh build",
    }.get(strategy, strategy.replace("_", " "))


def build_attempt_plan(
    provider: str,
    *,
    retry_only: bool = False,
    max_attempts: int = 2,
) -> list[AttemptPlan]:
    """Build a bounded sequence of alternate worker attempts for one task."""
    attempt_cap = max(1, int(max_attempts))
    preferred = ["focused_retry", "fresh_build"] if retry_only else ["primary", "focused_retry"]
    fallback_cycle = ["fresh_build", "focused_retry", "primary"]

    strategies: list[str] = []
    seen: set[str] = set()
    for strategy in preferred:
        if strategy in seen:
            continue
        strategies.append(strategy)
        seen.add(strategy)
        if len(strategies) >= attempt_cap:
            break

    while len(strategies) < attempt_cap:
        for strategy in fallback_cycle:
            if strategy in seen:
                continue
            strategies.append(strategy)
            seen.add(strategy)
            break
        else:
            strategies.append(preferred[-1])

    return [
        AttemptPlan(attempt=index, provider=provider, strategy=strategy)
        for index, strategy in enumerate(strategies, 1)
    ]


def _valid_attempt_score(attempt: CompetingAttempt) -> tuple[int, int, int]:
    return (
        int(bool(attempt.gates_passed)),
        _ATTEMPT_STRATEGY_PRIORITY.get(attempt.strategy, 0),
        -attempt.attempt,
    )


def select_winning_attempt(attempts: list[CompetingAttempt]) -> CompetingAttempt:
    """Select the winning attempt by policy.

    Policy:
    - any valid attempt beats all invalid ones
    - among valid attempts, prefer cleaner earlier strategies over fallback attempts
    - if nothing is valid, the latest attempt wins so the worktree stays aligned
    """
    if not attempts:
        raise ValueError("attempts must not be empty")

    valid_attempts = [attempt for attempt in attempts if attempt.valid]
    if not valid_attempts:
        return attempts[-1]
    return max(valid_attempts, key=_valid_attempt_score)


class EscalationChain:
    """Manage provider escalation: codex -> claude -> gemini -> human."""

    def __init__(
        self,
        providers: list[str],
        max_attempts_per_provider: int = 3,
        try_fresh_account_first: bool = True,
    ):
        if not providers:
            raise ValueError("providers must not be empty")

        self.providers = providers
        self.max_attempts_per_provider = max_attempts_per_provider
        self.try_fresh_account_first = try_fresh_account_first
        self._provider_index = 0
        self._attempts: list[ProviderAttempt] = [ProviderAttempt(provider=providers[0])]
        self.attempts_on_current = 0

    @property
    def current_provider(self) -> str:
        return self.providers[self._provider_index]

    def record_failure(self, description: str) -> None:
        """Record one failure for the current provider."""
        self._attempts[-1].failures.append(description)
        self.attempts_on_current += 1

        if len(self._attempts[-1].failures) >= self.max_attempts_per_provider:
            self._advance()

    def _advance(self) -> None:
        """Move to the next provider in the escalation chain."""
        if self._provider_index + 1 < len(self.providers):
            self._provider_index += 1
            self._attempts.append(ProviderAttempt(provider=self.current_provider))

    def is_exhausted(self) -> bool:
        """Return whether every provider has already hit the max attempts."""
        if self._provider_index < len(self.providers) - 1:
            return False
        return len(self._attempts[-1].failures) >= self.max_attempts_per_provider

    def context_summary(self) -> str:
        """Summarize what failed on previous providers."""
        lines = ["## What was already tried"]
        for attempt in self._attempts:
            if attempt.failures:
                lines.append(f"\n### {attempt.provider} ({len(attempt.failures)} attempts)")
                for index, failure in enumerate(attempt.failures, 1):
                    lines.append(f"  {index}. {failure}")
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset the chain for a new story."""
        self._provider_index = 0
        self._attempts = [ProviderAttempt(provider=self.providers[0])]
        self.attempts_on_current = 0
