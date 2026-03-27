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
