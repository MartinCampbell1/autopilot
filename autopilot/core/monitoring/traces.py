"""Trace aggregation helpers for run comparison and forensic replay."""

from __future__ import annotations

from collections import Counter
from typing import Any

from autopilot.core.cost_accounting import merge_usage_records

RUN_START_EVENTS = {"run_started", "run_resumed", "resumed"}
RUN_END_EVENTS = {
    "budget_paused",
    "interrupt_paused",
    "paused",
    "run_completed",
    "run_failed",
    "run_finished",
    "run_paused",
    "timeout_paused",
}
FAILURE_EVENTS = {
    "critic_rejected",
    "run_failed",
    "story_gate_failed",
    "story_quality_regression",
    "story_stuck",
    "worker_failed",
}


def _coerce_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _usage_record(entry: dict[str, Any]) -> dict[str, Any]:
    usage = entry.get("iteration_usage")
    if isinstance(usage, dict) and usage:
        return usage
    worker_usage = entry.get("worker_usage")
    critic_usage = entry.get("critic_usage")
    records = [record for record in (worker_usage, critic_usage) if isinstance(record, dict) and record]
    if not records:
        return {}
    return merge_usage_records(*records)


def annotate_trace_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign a stable derived run id/sequence to trace entries when one is missing."""

    annotated: list[dict[str, Any]] = []
    known_sequences: dict[str, int] = {}
    next_sequence = 0
    current_run_id = ""
    current_sequence = 0

    for entry in entries:
        record = dict(entry)
        event = str(record.get("event") or "")
        run_id = str(record.get("run_id") or "").strip()

        if run_id:
            if run_id not in known_sequences:
                next_sequence += 1
                known_sequences[run_id] = next_sequence
            current_run_id = run_id
            current_sequence = known_sequences[run_id]
        elif event in RUN_START_EVENTS or not current_run_id:
            next_sequence += 1
            current_run_id = f"run-{next_sequence}"
            known_sequences[current_run_id] = next_sequence
            current_sequence = next_sequence
            run_id = current_run_id
        else:
            run_id = current_run_id

        record["run_id"] = run_id
        record["run_sequence"] = current_sequence
        annotated.append(record)

        if event in RUN_END_EVENTS and current_run_id == run_id:
            current_run_id = ""
            current_sequence = 0

    return annotated


def build_trace_replay(
    entries: list[dict[str, Any]],
    *,
    story_id: int | None = None,
    run_id: str | None = None,
    limit: int | None = 100,
) -> dict[str, Any]:
    """Build a readable chronological replay payload."""

    annotated = annotate_trace_entries(entries)
    filtered = [
        entry
        for entry in annotated
        if (story_id is None or _coerce_int(entry.get("story_id")) == int(story_id))
        and (run_id is None or str(entry.get("run_id") or "") == str(run_id))
    ]
    if limit is not None and limit > 0:
        filtered = filtered[-limit:]

    replay_entries = [
        {
            "timestamp": entry.get("timestamp"),
            "run_id": entry.get("run_id"),
            "run_sequence": entry.get("run_sequence"),
            "kind": str(entry.get("kind") or "unknown"),
            "event": str(entry.get("event") or ""),
            "status": str(entry.get("status") or ""),
            "story_id": entry.get("story_id"),
            "story_title": str(entry.get("story_title") or ""),
            "iteration": entry.get("iteration"),
            "prompt_type": str(entry.get("prompt_type") or ""),
            "attempt_strategy": str(entry.get("attempt_strategy") or ""),
            "provider": str(entry.get("provider") or ""),
            "adapter_id": str(entry.get("adapter_id") or ""),
            "profile_used": str(entry.get("profile_used") or ""),
            "worker": str(entry.get("worker") or ""),
            "critic": str(entry.get("critic") or ""),
            "critic_approved": entry.get("critic_approved"),
            "critic_feedback": str(entry.get("critic_feedback") or ""),
            "quality_regression": bool(entry.get("quality_regression")),
            "regression_summary": str(entry.get("regression_summary") or ""),
            "judge_verdict": str(entry.get("judge_verdict") or ""),
            "judge_pack": str(entry.get("judge_pack") or ""),
            "elapsed_sec": _coerce_float(entry.get("elapsed_sec")),
            "message": str(entry.get("message") or ""),
            "gate_results": list(entry.get("gate_results") or []),
            "review_results": list(entry.get("review_results") or []),
            "verification_checks": list(entry.get("verification_checks") or []),
            "iteration_usage": _usage_record(entry),
        }
        for entry in filtered
    ]
    run_ids = list(dict.fromkeys(str(entry.get("run_id") or "") for entry in replay_entries if entry.get("run_id")))
    return {
        "entry_count": len(replay_entries),
        "first_timestamp": replay_entries[0]["timestamp"] if replay_entries else None,
        "last_timestamp": replay_entries[-1]["timestamp"] if replay_entries else None,
        "run_ids": run_ids,
        "entries": replay_entries,
    }


def build_trace_monitor(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate trace entries into run/story summaries and regression hints."""

    annotated = annotate_trace_entries(entries)
    by_kind = Counter(str(entry.get("kind") or "unknown") for entry in annotated)
    story_map: dict[str, dict[str, Any]] = {}
    run_map: dict[str, dict[str, Any]] = {}
    recent_failures: list[dict[str, Any]] = []

    for entry in annotated:
        run_key = str(entry.get("run_id") or "")
        run = run_map.setdefault(
            run_key,
            {
                "run_id": run_key,
                "run_sequence": _coerce_int(entry.get("run_sequence")),
                "started_at": entry.get("run_started_at") or entry.get("timestamp"),
                "finished_at": None,
                "last_timestamp": entry.get("timestamp"),
                "status": str(entry.get("status") or entry.get("event") or ""),
                "entry_count": 0,
                "iteration_count": 0,
                "failure_count": 0,
                "critic_rejection_count": 0,
                "quality_regression_count": 0,
                "story_ids": [],
                "judge_outcomes": {},
                "cost": {},
            },
        )
        run["entry_count"] += 1
        run["last_timestamp"] = entry.get("timestamp")
        run["status"] = str(entry.get("status") or entry.get("event") or run["status"])
        if str(entry.get("event") or "") in RUN_END_EVENTS:
            run["finished_at"] = entry.get("timestamp")

        story_id = entry.get("story_id")
        if story_id not in (None, ""):
            story_key = str(story_id)
            story = story_map.setdefault(
                story_key,
                {
                    "story_id": story_id,
                    "story_title": str(entry.get("story_title") or ""),
                    "entry_count": 0,
                    "iteration_count": 0,
                    "failure_count": 0,
                    "latest_status": None,
                    "last_timestamp": None,
                    "run_ids": [],
                },
            )
            story["entry_count"] += 1
            story["latest_status"] = str(entry.get("status") or entry.get("event") or "")
            story["last_timestamp"] = entry.get("timestamp")
            if run_key and run_key not in story["run_ids"]:
                story["run_ids"].append(run_key)
            if str(entry.get("kind") or "") == "iteration_record":
                story["iteration_count"] += 1
            if str(entry.get("event") or "") in FAILURE_EVENTS or str(entry.get("status") or "") in {
                "critic_rejected",
                "gate_failed",
                "quality_regression",
                "worker_failed",
            }:
                story["failure_count"] += 1
            if story_id not in run["story_ids"]:
                run["story_ids"].append(story_id)

        if str(entry.get("kind") or "") == "iteration_record":
            run["iteration_count"] += 1
            if bool(entry.get("quality_regression")):
                run["quality_regression_count"] += 1
            if entry.get("critic_approved") is False:
                run["critic_rejection_count"] += 1
            judge_verdict = str(entry.get("judge_verdict") or "").strip().upper()
            if judge_verdict:
                judge_counts = dict(run.get("judge_outcomes") or {})
                judge_counts[judge_verdict] = _coerce_int(judge_counts.get(judge_verdict)) + 1
                run["judge_outcomes"] = judge_counts
            usage = _usage_record(entry)
            if usage:
                existing_cost = run.get("cost") or {}
                run["cost"] = merge_usage_records(existing_cost, usage) if existing_cost else dict(usage)

        event = str(entry.get("event") or "")
        if event in FAILURE_EVENTS:
            run["failure_count"] += 1
            recent_failures.append(
                {
                    "timestamp": entry.get("timestamp"),
                    "run_id": run_key,
                    "story_id": entry.get("story_id"),
                    "event": event,
                    "status": str(entry.get("status") or ""),
                    "message": str(entry.get("message") or entry.get("critic_feedback") or ""),
                }
            )

    runs = sorted(run_map.values(), key=lambda item: (_coerce_int(item.get("run_sequence")), str(item.get("started_at") or "")))
    latest = runs[-1] if runs else None
    previous = runs[-2] if len(runs) > 1 else None
    comparison: dict[str, Any] = {}
    if latest and previous:
        latest_cost = dict(latest.get("cost") or {})
        previous_cost = dict(previous.get("cost") or {})
        comparison = {
            "latest_run_id": latest.get("run_id"),
            "previous_run_id": previous.get("run_id"),
            "cost_delta_usd": round(
                _coerce_float(latest_cost.get("estimated_cost_usd")) - _coerce_float(previous_cost.get("estimated_cost_usd")),
                8,
            ),
            "total_tokens_delta": _coerce_int(latest_cost.get("total_tokens")) - _coerce_int(previous_cost.get("total_tokens")),
            "failure_delta": _coerce_int(latest.get("failure_count")) - _coerce_int(previous.get("failure_count")),
            "iteration_delta": _coerce_int(latest.get("iteration_count")) - _coerce_int(previous.get("iteration_count")),
            "quality_regression_delta": _coerce_int(latest.get("quality_regression_count"))
            - _coerce_int(previous.get("quality_regression_count")),
            "cost_regression": _coerce_float(latest_cost.get("estimated_cost_usd"))
            > _coerce_float(previous_cost.get("estimated_cost_usd")),
            "reliability_regression": _coerce_int(latest.get("failure_count")) > _coerce_int(previous.get("failure_count"))
            or _coerce_int(latest.get("quality_regression_count")) > _coerce_int(previous.get("quality_regression_count")),
        }

    return {
        "entry_count": len(annotated),
        "by_kind": dict(by_kind),
        "runs": runs,
        "stories": sorted(story_map.values(), key=lambda item: _coerce_int(item.get("story_id"))),
        "recent_failures": recent_failures[-10:],
        "comparison": comparison,
        "first_timestamp": annotated[0]["timestamp"] if annotated else None,
        "last_timestamp": annotated[-1]["timestamp"] if annotated else None,
    }
