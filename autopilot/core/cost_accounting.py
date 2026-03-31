"""Token and estimated cost accounting for runtime execution."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from autopilot.core.models import IterationRecord

_COUNT_PATTERNS = {
    "input_tokens": (
        re.compile(r"(?i)\binput tokens?\s*[:=]\s*([\d,]+)"),
        re.compile(r"(?i)\bprompt tokens?\s*[:=]\s*([\d,]+)"),
    ),
    "output_tokens": (
        re.compile(r"(?i)\boutput tokens?\s*[:=]\s*([\d,]+)"),
        re.compile(r"(?i)\bcompletion tokens?\s*[:=]\s*([\d,]+)"),
    ),
    "cached_tokens": (
        re.compile(r"(?i)\bcached(?: input)? tokens?\s*[:=]\s*([\d,]+)"),
    ),
    "total_tokens": (
        re.compile(r"(?i)\btotal tokens?\s*[:=]\s*([\d,]+)"),
        re.compile(r"(?i)\btokens used\s*[:=]\s*([\d,]+)"),
    ),
}
_NUMERIC_USAGE_KEYS = (
    "invocations",
    "tracked_invocations",
    "priced_invocations",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "total_tokens",
    "estimated_cost_usd",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_bucket() -> dict[str, Any]:
    return {
        "invocations": 0,
        "tracked_invocations": 0,
        "priced_invocations": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
    }


def default_cost_usage() -> dict[str, Any]:
    """Return the default cost-accounting state for one project."""
    return {
        "project": _empty_bucket(),
        "run": {"started_at": None, **_empty_bucket()},
        "stories": {},
        "agents": {},
        "last_recorded_at": None,
        "pricing_source": "unconfigured",
    }


def ensure_cost_state(state: dict[str, Any]) -> dict[str, Any]:
    """Ensure cost-accounting buckets exist in project runtime state."""
    usage = state.setdefault("cost_usage", default_cost_usage())
    usage.setdefault("project", _empty_bucket())
    usage.setdefault("run", {"started_at": None, **_empty_bucket()})
    usage.setdefault("stories", {})
    usage.setdefault("agents", {})
    usage.setdefault("last_recorded_at", None)
    usage.setdefault("pricing_source", "unconfigured")
    for key in ("project", "run"):
        bucket = usage.setdefault(key, _empty_bucket() if key == "project" else {"started_at": None, **_empty_bucket()})
        for numeric_key, default_value in _empty_bucket().items():
            bucket.setdefault(numeric_key, default_value)
        if key == "run":
            bucket.setdefault("started_at", None)
    return usage


def start_run_cost_bucket(state: dict[str, Any], *, started_at: str | None = None) -> dict[str, Any]:
    """Reset the current-run bucket while preserving project totals."""
    usage = ensure_cost_state(state)
    usage["run"] = {
        "started_at": started_at or _utcnow_iso(),
        **_empty_bucket(),
    }
    usage["last_recorded_at"] = usage["run"]["started_at"]
    return usage


def _parse_int(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    return int(match.group(1).replace(",", ""))


def _extract_count(text: str, patterns: tuple[re.Pattern[str], ...]) -> int | None:
    for pattern in patterns:
        match = pattern.search(text)
        if match is not None:
            return _parse_int(match)
    return None


def _load_pricing_table() -> tuple[dict[str, dict[str, float]], str]:
    raw = os.environ.get("AUTOPILOT_PRICING_JSON", "").strip()
    if not raw:
        return {}, "unconfigured"
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "invalid:AUTOPILOT_PRICING_JSON"
    if not isinstance(payload, dict):
        return {}, "invalid:AUTOPILOT_PRICING_JSON"

    pricing_table: dict[str, dict[str, float]] = {}
    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        pricing_table[key] = {}
        for rate_key in ("input_per_million_usd", "output_per_million_usd", "cached_input_per_million_usd"):
            raw_rate = value.get(rate_key)
            if raw_rate is None:
                continue
            try:
                pricing_table[key][rate_key] = float(raw_rate)
            except (TypeError, ValueError):
                continue
    return pricing_table, "env:AUTOPILOT_PRICING_JSON"


def _resolve_pricing(
    pricing_table: dict[str, dict[str, float]],
    *,
    provider: str,
    model: str | None,
) -> dict[str, float] | None:
    candidates = []
    if model:
        candidates.append(f"{provider}:{model}")
    candidates.append(provider)
    for key in candidates:
        pricing = pricing_table.get(key)
        if pricing:
            return pricing
    return None


def _estimate_cost_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int,
    pricing: dict[str, float] | None,
) -> float | None:
    if not pricing:
        return None
    input_rate = float(pricing.get("input_per_million_usd") or 0.0)
    output_rate = float(pricing.get("output_per_million_usd") or 0.0)
    cached_rate = float(pricing.get("cached_input_per_million_usd") or input_rate)
    uncached_input_tokens = max(input_tokens - cached_tokens, 0)
    cost = (
        (uncached_input_tokens / 1_000_000) * input_rate
        + (cached_tokens / 1_000_000) * cached_rate
        + (output_tokens / 1_000_000) * output_rate
    )
    return round(cost, 8)


def summarize_invocation_usage(
    output_text: str,
    *,
    provider: str,
    role: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Parse token usage from provider output and attach optional pricing."""
    input_tokens = _extract_count(output_text, _COUNT_PATTERNS["input_tokens"]) or 0
    output_tokens = _extract_count(output_text, _COUNT_PATTERNS["output_tokens"]) or 0
    cached_tokens = _extract_count(output_text, _COUNT_PATTERNS["cached_tokens"]) or 0
    total_tokens = _extract_count(output_text, _COUNT_PATTERNS["total_tokens"])
    tracked = any(
        pattern.search(output_text)
        for patterns in _COUNT_PATTERNS.values()
        for pattern in patterns
    )
    if total_tokens is None and tracked:
        total_tokens = input_tokens + output_tokens

    pricing_table, pricing_source = _load_pricing_table()
    pricing = _resolve_pricing(pricing_table, provider=provider, model=model)
    estimated_cost_usd = _estimate_cost_usd(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_tokens=cached_tokens,
        pricing=pricing,
    )

    return {
        "provider": provider,
        "model": model,
        "role": role,
        "pricing_source": pricing_source,
        "invocations": 1,
        "tracked_invocations": 1 if tracked else 0,
        "priced_invocations": 1 if estimated_cost_usd is not None else 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": int(total_tokens or 0),
        "estimated_cost_usd": float(estimated_cost_usd or 0.0),
    }


def merge_usage_records(*records: dict[str, Any]) -> dict[str, Any]:
    """Combine multiple usage records into one aggregate record."""
    merged = {
        "provider": None,
        "model": None,
        "role": None,
        "pricing_source": "unconfigured",
        **_empty_bucket(),
    }
    providers = {str(record.get("provider")) for record in records if record.get("provider")}
    models = {str(record.get("model")) for record in records if record.get("model")}
    roles = {str(record.get("role")) for record in records if record.get("role")}
    pricing_sources = {str(record.get("pricing_source")) for record in records if record.get("pricing_source")}
    merged["provider"] = providers.pop() if len(providers) == 1 else None
    merged["model"] = models.pop() if len(models) == 1 else None
    merged["role"] = roles.pop() if len(roles) == 1 else None
    merged["pricing_source"] = pricing_sources.pop() if len(pricing_sources) == 1 else "mixed"
    for record in records:
        for key in _NUMERIC_USAGE_KEYS:
            merged[key] = round(float(merged[key]) + float(record.get(key) or 0), 8) if key == "estimated_cost_usd" else int(merged[key]) + int(record.get(key) or 0)
    return merged


def _story_bucket(usage: dict[str, Any], story_id: int) -> dict[str, Any]:
    story_key = str(story_id)
    bucket = usage.setdefault("stories", {}).setdefault(story_key, _empty_bucket())
    for key, default_value in _empty_bucket().items():
        bucket.setdefault(key, default_value)
    return bucket


def _agent_bucket(usage: dict[str, Any], agent_label: str) -> dict[str, Any]:
    bucket = usage.setdefault("agents", {}).setdefault(agent_label, _empty_bucket())
    for key, default_value in _empty_bucket().items():
        bucket.setdefault(key, default_value)
    return bucket


def _accumulate_bucket(bucket: dict[str, Any], usage_record: dict[str, Any]) -> None:
    for key in _NUMERIC_USAGE_KEYS:
        if key == "estimated_cost_usd":
            bucket[key] = round(float(bucket.get(key) or 0.0) + float(usage_record.get(key) or 0.0), 8)
        else:
            bucket[key] = int(bucket.get(key) or 0) + int(usage_record.get(key) or 0)


def record_iteration_cost(
    state: dict[str, Any],
    *,
    story_id: int,
    worker_label: str,
    critic_label: str,
    iteration_record: IterationRecord,
) -> dict[str, Any]:
    """Accumulate one iteration's worker/critic usage into runtime state."""
    usage = ensure_cost_state(state)
    usage["pricing_source"] = (
        iteration_record.worker_usage.get("pricing_source")
        or iteration_record.critic_usage.get("pricing_source")
        or usage.get("pricing_source")
        or "unconfigured"
    )

    for usage_record, agent_label in (
        (iteration_record.worker_usage, worker_label),
        (iteration_record.critic_usage, critic_label),
    ):
        if not usage_record:
            continue
        _accumulate_bucket(usage["project"], usage_record)
        _accumulate_bucket(usage["run"], usage_record)
        _accumulate_bucket(_story_bucket(usage, story_id), usage_record)
        _accumulate_bucket(_agent_bucket(usage, agent_label), usage_record)

    usage["last_recorded_at"] = _utcnow_iso()
    return usage
