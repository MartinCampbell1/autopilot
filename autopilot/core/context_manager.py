"""Context pressure helpers for prompt recovery and bounded feedback persistence."""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from autopilot.core.adapters import (
    AdapterExecutionRequest,
    AdapterExecutionResult,
    AdapterParsedOutput,
    LocalProviderAdapter,
)
from autopilot.core.session_memory import load_working_log, render_session_memory_context

PROMPT_TOO_LONG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"prompt(?:\s+is)?\s+too\s+long", re.IGNORECASE),
    re.compile(r"context(?:\s+window|\s+length)?\s+(?:was\s+)?(?:too\s+long|too\s+large|exceeded)", re.IGNORECASE),
    re.compile(r"(?:maximum|max)\s+(?:context|input)\s+(?:length|tokens).*(?:exceeded|reached)", re.IGNORECASE),
    re.compile(r"too\s+many\s+input\s+tokens", re.IGNORECASE),
    re.compile(r"context_window_exceeded", re.IGNORECASE),
    re.compile(r"prompt_too_long", re.IGNORECASE),
    re.compile(r"request\s+(?:body|payload).*(?:too\s+large|exceeds)", re.IGNORECASE),
)
MAX_INLINE_FEEDBACK_CHARS = 4000
FEEDBACK_HEAD_CHARS = 1800
FEEDBACK_TAIL_CHARS = 1200
COMPACT_PROMPT_MAX_CHARS = 2400
COMPACTION_STAGE_BUDGET = 3200


def _normalized_single_line(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def is_prompt_too_long_error(text: str) -> bool:
    """Return whether a provider/runtime response indicates context overflow."""

    normalized = _normalized_single_line(text)
    if not normalized:
        return False
    return any(pattern.search(normalized) for pattern in PROMPT_TOO_LONG_PATTERNS)


def _extract_prompt_line(prompt: str, prefix: str) -> str:
    for raw_line in str(prompt or "").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line
    return ""


def _trim_line(line: str, max_chars: int) -> str:
    normalized = line.strip()
    if len(normalized) <= max_chars:
        return normalized
    return f"{normalized[: max(0, max_chars - 3)].rstrip()}..."


def _trim_multiline(text: str, max_chars: int) -> str:
    normalized = str(text or "").strip()
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max(0, max_chars - 3)].rstrip() + "..."


def build_compact_recovery_prompt(prompt: str, *, max_chars: int = COMPACT_PROMPT_MAX_CHARS) -> str:
    """Build a smaller retry prompt that preserves the active story identity."""

    selected_story = _trim_line(_extract_prompt_line(prompt, "Selected story #"), 220)
    story_description = _trim_line(_extract_prompt_line(prompt, "Story description:"), 700)
    prd_snapshot = _trim_line(_extract_prompt_line(prompt, "PRD snapshot:"), 220)
    fallback_summary = _trim_line(_normalized_single_line(prompt), 900)

    lines = ["Context limit hit. Continue the same story."]
    if selected_story:
        lines.append(selected_story)
    elif fallback_summary:
        lines.append(f"Task: {fallback_summary}")
    if prd_snapshot:
        lines.append(prd_snapshot)
    if story_description and len(story_description) <= 180:
        lines.append(story_description)
    lines.extend(
        [
            "Read AGENTS.md, guardrails, critic feedback, and PRD from disk.",
            "Make the smallest verified fix, update .ralph/progress.md, and report blockers honestly.",
            'Output <promise>COMPLETE</promise> only when verified.',
        ]
    )
    compact_prompt = "\n".join(lines).strip()
    original_length = max(len(str(prompt or "").strip()), 0)
    target_chars = max_chars
    if original_length > 80:
        target_chars = min(target_chars, max(original_length - 1, 120))
    return _trim_line(compact_prompt, target_chars)


def _render_recent_working_log(project_path: Path, *, max_items: int = 4, max_chars: int = 900) -> str:
    entries = load_working_log(project_path, limit=max_items)
    if not entries:
        return ""
    lines = []
    for entry in entries:
        prefix = entry.kind.replace("_", " ")
        story = f" story #{entry.story_id}" if entry.story_id is not None else ""
        lines.append(f"- [{prefix}]{story} {entry.summary}")
    return _trim_multiline("\n".join(lines), max_chars)


def build_compaction_pipeline(
    project_path: Path,
    prompt: str,
    *,
    max_chars: int = COMPACTION_STAGE_BUDGET,
) -> dict[str, Any]:
    """Build a compact 4-stage context bundle for long-running prompts."""

    stage_identity = build_compact_recovery_prompt(prompt, max_chars=min(max_chars, 1200))
    critic_feedback = project_path / ".ralph" / "critic-feedback.md"
    stage_feedback = ""
    if critic_feedback.exists():
        stage_feedback = _trim_multiline(critic_feedback.read_text(), 900)
    stage_memory = render_session_memory_context(project_path, max_chars=900)
    stage_log = _render_recent_working_log(project_path, max_chars=900)
    stages = [
        {"stage": "identity", "content": stage_identity},
        {"stage": "feedback", "content": stage_feedback},
        {"stage": "memory", "content": stage_memory},
        {"stage": "working_log", "content": stage_log},
    ]
    rendered_sections = []
    for item in stages:
        content = str(item["content"] or "").strip()
        if content:
            rendered_sections.append(f"{item['stage'].replace('_', ' ').title()}:\n{content}")
    rendered = _trim_multiline("\n\n".join(rendered_sections), max_chars)
    return {
        "stages": stages,
        "rendered": rendered,
    }


def build_compacted_prompt(
    project_path: Path,
    prompt: str,
    *,
    max_chars: int = COMPACTION_STAGE_BUDGET,
) -> str:
    """Render the compacted prompt that preserves identity plus durable memory."""

    bundle = build_compaction_pipeline(project_path, prompt, max_chars=max_chars)
    rendered = str(bundle.get("rendered") or "").strip()
    return rendered or build_compact_recovery_prompt(prompt, max_chars=max_chars)


def _artifact_dir(project_path: Path) -> Path:
    return project_path / ".ralph" / "context"


def persist_context_artifact(project_path: Path, *, category: str, content: str) -> Path:
    """Persist a large context blob to a sidecar artifact file."""

    artifact_dir = _artifact_dir(project_path)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    artifact_path = artifact_dir / f"{category}-{int(time.time())}-{digest}.txt"
    artifact_path.write_text(content)
    return artifact_path


def render_bounded_feedback(project_path: Path, feedback: str, *, category: str = "critic-feedback") -> str:
    """Bound large feedback for future prompts while preserving a full artifact copy."""

    text = str(feedback or "")
    if len(text) <= MAX_INLINE_FEEDBACK_CHARS:
        return text

    artifact_path = persist_context_artifact(project_path, category=category, content=text)
    head = text[:FEEDBACK_HEAD_CHARS].rstrip()
    tail = text[-FEEDBACK_TAIL_CHARS :].lstrip()
    omitted_chars = max(len(text) - len(head) - len(tail), 0)
    summary = (
        f"{head}\n\n"
        f"[... omitted {omitted_chars} chars; full context stored at {artifact_path} ...]\n\n"
        f"{tail}"
    )
    return summary.strip()


def _render_execution_text(result: AdapterExecutionResult, parsed: AdapterParsedOutput) -> str:
    text = str(parsed.text or "").strip()
    if text:
        return text
    return str(result.output or result.stderr or result.stdout or "").strip()


def execute_with_context_recovery(
    adapter: LocalProviderAdapter,
    request: AdapterExecutionRequest,
) -> tuple[AdapterExecutionResult, AdapterParsedOutput]:
    """Execute once and retry automatically with a compact prompt on PTL errors."""

    result = adapter.execute(request)
    parsed = adapter.parse_output(result)
    rendered = _render_execution_text(result, parsed)
    if result.success or not is_prompt_too_long_error(rendered):
        return result, parsed

    compact_prompt = build_compact_recovery_prompt(request.prompt)
    if not compact_prompt or compact_prompt.strip() == str(request.prompt).strip():
        return result, parsed

    retry_request = replace(request, prompt=compact_prompt)
    retry_result = adapter.execute(retry_request)
    retry_parsed = adapter.parse_output(retry_result)
    retry_rendered = _render_execution_text(retry_result, retry_parsed)
    if retry_result.success or retry_rendered:
        return retry_result, retry_parsed
    return result, parsed


__all__ = [
    "build_compacted_prompt",
    "build_compaction_pipeline",
    "build_compact_recovery_prompt",
    "execute_with_context_recovery",
    "is_prompt_too_long_error",
    "persist_context_artifact",
    "render_bounded_feedback",
]
