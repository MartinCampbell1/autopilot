"""Tests for escalation chain."""

from autopilot.core.escalation import EscalationChain, EscalationResult


class TestEscalationChain:
    def test_initial_provider(self) -> None:
        chain = EscalationChain(providers=["codex", "claude", "gemini"], max_attempts_per_provider=3)
        assert chain.current_provider == "codex"
        assert chain.is_exhausted() is False

    def test_advance_after_max_attempts(self) -> None:
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=3)
        for _ in range(3):
            chain.record_failure("same issue")
        assert chain.current_provider == "claude"

    def test_exhausted_after_all_providers(self) -> None:
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        for _ in range(2):
            chain.record_failure("issue")
        assert chain.current_provider == "claude"
        for _ in range(2):
            chain.record_failure("issue")
        assert chain.is_exhausted() is True

    def test_reset(self) -> None:
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        for _ in range(2):
            chain.record_failure("issue")
        chain.reset()
        assert chain.current_provider == "codex"
        assert chain.is_exhausted() is False

    def test_build_context_summary(self) -> None:
        chain = EscalationChain(providers=["codex", "claude"], max_attempts_per_provider=2)
        chain.record_failure("callback URL hardcoded")
        chain.record_failure("still hardcoded")
        summary = chain.context_summary()
        assert "codex" in summary.lower()
        assert "hardcoded" in summary

    def test_try_fresh_account_first(self) -> None:
        chain = EscalationChain(
            providers=["codex", "claude"],
            max_attempts_per_provider=3,
            try_fresh_account_first=True,
        )
        for _ in range(3):
            chain.record_failure("issue")
        assert chain.attempts_on_current >= 3


def test_escalation_result_dataclass() -> None:
    result = EscalationResult(exhausted=False, current_provider="codex", context_summary="summary")
    assert result.current_provider == "codex"
