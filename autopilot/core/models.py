"""Core data models for Autopilot."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import Any, Mapping, Sequence


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


class StoryDependencyError(ValueError):
    """Raised when a story dependency graph is invalid."""


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
    baseline_passed: bool | None = None
    regression: bool = False


@dataclass
class CriticResult:
    """Result of critic evaluation."""

    approved: bool
    feedback: str
    raw_output: str
    profile_used: str = ""
    elapsed_sec: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    review_phases: list[str] = field(default_factory=list)
    review_results: list["ReviewPhaseResult"] = field(default_factory=list)


@dataclass
class ReviewPhaseResult:
    """Result of one focused review phase."""

    phase: str
    approved: bool
    feedback: str
    raw_output: str
    profile_used: str = ""
    elapsed_sec: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)


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
    worker_usage: dict[str, Any] = field(default_factory=dict)
    critic_usage: dict[str, Any] = field(default_factory=dict)
    review_phases: list[str] = field(default_factory=list)
    review_results: list[ReviewPhaseResult] = field(default_factory=list)
    quality_regression: bool = False
    regression_summary: str = ""


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

DEPENDENCY_SATISFIED_STATUSES = {
    StoryStatus.DONE.value,
    StoryStatus.SKIPPED.value,
}


def is_rate_limited(text: str) -> bool:
    """Check whether text contains rate limit indicators."""
    return any(pattern.search(text) for pattern in RATE_LIMIT_PATTERNS)


def normalize_story_blocked_by(value: Any, *, story_id: int) -> list[int]:
    """Normalize one story's `blocked_by` list."""
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise StoryDependencyError(f"Story {story_id} has invalid blocked_by; expected a list of story ids.")

    normalized: list[int] = []
    seen: set[int] = set()
    for raw in value:
        if isinstance(raw, bool):
            raise StoryDependencyError(f"Story {story_id} has invalid blocked_by reference: {raw!r}")
        try:
            dependency_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise StoryDependencyError(
                f"Story {story_id} has invalid blocked_by reference: {raw!r}"
            ) from exc
        if dependency_id == story_id:
            raise StoryDependencyError(f"Story {story_id} cannot depend on itself.")
        if dependency_id in seen:
            continue
        normalized.append(dependency_id)
        seen.add(dependency_id)
    return normalized


def validate_story_dependencies(stories: Sequence[Mapping[str, Any]]) -> dict[int, list[int]]:
    """Validate dependency references and reject cycles."""
    known_story_ids = {int(story["id"]) for story in stories}
    graph: dict[int, list[int]] = {}

    for story in stories:
        story_id = int(story["id"])
        blocked_by = normalize_story_blocked_by(story.get("blocked_by"), story_id=story_id)
        missing = [dependency_id for dependency_id in blocked_by if dependency_id not in known_story_ids]
        if missing:
            joined = ", ".join(str(dependency_id) for dependency_id in missing)
            raise StoryDependencyError(f"Story {story_id} depends on unknown stories: {joined}")
        graph[story_id] = blocked_by

    visiting: list[int] = []
    active: set[int] = set()
    visited: set[int] = set()

    def visit(story_id: int) -> None:
        if story_id in visited:
            return
        if story_id in active:
            cycle_start = visiting.index(story_id)
            cycle = visiting[cycle_start:] + [story_id]
            joined = " -> ".join(str(node) for node in cycle)
            raise StoryDependencyError(f"Story dependency cycle detected: {joined}")

        active.add(story_id)
        visiting.append(story_id)
        for dependency_id in graph.get(story_id, []):
            visit(dependency_id)
        visiting.pop()
        active.remove(story_id)
        visited.add(story_id)

    for story_id in graph:
        visit(story_id)
    return graph


def resolve_story_blocked_on(
    blocked_by: Sequence[int],
    story_state: Mapping[str | int, Mapping[str, Any]],
) -> list[int]:
    """Return unresolved dependency ids for one story."""
    blocked_on: list[int] = []
    for dependency_id in blocked_by:
        runtime = story_state.get(str(dependency_id)) or story_state.get(dependency_id) or {}
        status = str(runtime.get("status") or StoryStatus.OPEN.value)
        if status not in DEPENDENCY_SATISFIED_STATUSES:
            blocked_on.append(int(dependency_id))
    return blocked_on
