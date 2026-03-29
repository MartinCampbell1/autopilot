"""Core data models for Autopilot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
import re


class StoryStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    STUCK = "stuck"
    SKIPPED = "skipped"
    MERGE_BLOCKED = "merge_blocked"


class Provider(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    GEMINI = "gemini"


@dataclass
class Profile:
    """One CLI account/profile."""

    name: str
    provider: str
    path: str
    adapter_id: str | None = None
    is_available: bool = True
    requests_made: int = 0
    last_used: float = 0.0
    cooldown_until: float = 0.0
    consecutive_errors: int = 0

    @property
    def resolved_adapter_id(self) -> str:
        """Return the concrete runtime adapter to use for this profile."""
        if self.adapter_id:
            return self.adapter_id
        if self.provider.endswith("_local"):
            return self.provider
        return f"{self.provider}_local"

    def mark_rate_limited(self, cooldown_base: int = 300) -> None:
        """Mark profile as rate-limited with exponential backoff."""
        self.is_available = False
        self.consecutive_errors += 1
        backoff = min(self.consecutive_errors * 60, 1800)
        self.cooldown_until = time.time() + cooldown_base + backoff

    def mark_success(self) -> None:
        """Reset error counter on success."""
        self.consecutive_errors = 0

    def check_available(self) -> bool:
        """Check if cooldown has expired and restore availability."""
        if not self.is_available and time.time() >= self.cooldown_until:
            self.is_available = True
            self.consecutive_errors = 0
        return self.is_available


@dataclass
class GateResult:
    """Result of running one auto-gate."""

    name: str
    cmd: str
    passed: bool
    output: str
    required: bool = True
    elapsed_sec: float = 0.0


@dataclass
class CriticResult:
    """Result of critic evaluation."""

    approved: bool
    feedback: str
    raw_output: str
    profile_used: str = ""
    elapsed_sec: float = 0.0


@dataclass
class IterationRecord:
    """Record of one worker iteration."""

    story_id: int
    iteration: int
    profile_used: str
    provider: str
    gates_passed: bool
    critic_approved: bool | None = None
    critic_feedback: str = ""
    elapsed_sec: float = 0.0
    timestamp: float = field(default_factory=time.time)
    git_diff_empty: bool = False
    gate_results: list[GateResult] = field(default_factory=list)


@dataclass
class ProjectConfig:
    """Configuration for one managed project."""

    name: str
    path: str
    prd: str = ".agents/tasks/prd.json"
    priority: str = "normal"
    gates: list[dict] = field(default_factory=list)
    providers: list[str] = field(default_factory=lambda: ["codex"])


RATE_LIMIT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"resource has been exhausted", re.IGNORECASE),
    re.compile(r"resource_exhausted", re.IGNORECASE),
    re.compile(r"\brate limit(?:ed)?\b", re.IGNORECASE),
    re.compile(r"rate_limit", re.IGNORECASE),
    re.compile(r"quota exceeded", re.IGNORECASE),
    re.compile(r"quota_exceeded", re.IGNORECASE),
    re.compile(r"\b429\b", re.IGNORECASE),
    re.compile(r"too many requests", re.IGNORECASE),
    re.compile(r"insufficient_quota", re.IGNORECASE),
    re.compile(r"\bat capacity\b", re.IGNORECASE),
    re.compile(r"\boverloaded\b", re.IGNORECASE),
    re.compile(r"try again later", re.IGNORECASE),
]


def is_rate_limited(text: str) -> bool:
    """Check whether text contains rate limit indicators."""
    return any(pattern.search(text) for pattern in RATE_LIMIT_PATTERNS)
