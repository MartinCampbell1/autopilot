"""Benchmark snapshots for run-to-run observability and regression detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autopilot.core.config import AutopilotConfig


def benchmark_path(config: AutopilotConfig, project_id: str) -> Path:
    return config.autopilot_home / "evals" / "benchmarks" / f"{project_id}.jsonl"


def read_benchmark_runs(
    config: AutopilotConfig,
    project_id: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    path = benchmark_path(config, project_id)
    if not path.exists():
        return []
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if limit is not None and limit > 0:
        return records[-limit:]
    return records


def append_benchmark_run(
    config: AutopilotConfig,
    project_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    records = read_benchmark_runs(config, project_id)
    run_id = str(payload.get("run_id") or "").strip()
    if run_id and any(str(record.get("run_id") or "") == run_id for record in records):
        return payload
    path = benchmark_path(config, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"project_id": project_id, **payload}, ensure_ascii=False) + "\n")
    return payload


def build_benchmark_run_snapshot(
    run_summary: dict[str, Any],
    *,
    feedback_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    feedback_records = list(feedback_records or [])
    cost = dict(run_summary.get("cost") or {})
    judge_outcomes: dict[str, int] = {}
    for record in feedback_records:
        verdict = str(record.get("judge_verdict") or "").strip().upper()
        if not verdict:
            continue
        judge_outcomes[verdict] = int(judge_outcomes.get(verdict) or 0) + 1
    return {
        "run_id": str(run_summary.get("run_id") or ""),
        "run_sequence": int(run_summary.get("run_sequence") or 0),
        "status": str(run_summary.get("status") or ""),
        "started_at": run_summary.get("started_at"),
        "finished_at": run_summary.get("finished_at"),
        "story_ids": list(run_summary.get("story_ids") or []),
        "entry_count": int(run_summary.get("entry_count") or 0),
        "iteration_count": int(run_summary.get("iteration_count") or 0),
        "failure_count": int(run_summary.get("failure_count") or 0),
        "critic_rejection_count": int(run_summary.get("critic_rejection_count") or 0),
        "quality_regression_count": int(run_summary.get("quality_regression_count") or 0),
        "cost": cost,
        "judge_outcomes": judge_outcomes or dict(run_summary.get("judge_outcomes") or {}),
        "feedback_count": len(feedback_records),
        "blocking_feedback_count": sum(1 for record in feedback_records if str(record.get("severity") or "") == "error"),
    }


def build_benchmark_summary(runs: list[dict[str, Any]]) -> dict[str, Any]:
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
                float(latest_cost.get("estimated_cost_usd") or 0.0)
                - float(previous_cost.get("estimated_cost_usd") or 0.0),
                8,
            ),
            "total_tokens_delta": int(latest_cost.get("total_tokens") or 0) - int(previous_cost.get("total_tokens") or 0),
            "failure_delta": int(latest.get("failure_count") or 0) - int(previous.get("failure_count") or 0),
            "quality_regression_delta": int(latest.get("quality_regression_count") or 0)
            - int(previous.get("quality_regression_count") or 0),
            "cost_regression": float(latest_cost.get("estimated_cost_usd") or 0.0)
            > float(previous_cost.get("estimated_cost_usd") or 0.0),
            "reliability_regression": int(latest.get("failure_count") or 0) > int(previous.get("failure_count") or 0)
            or int(latest.get("quality_regression_count") or 0) > int(previous.get("quality_regression_count") or 0),
        }
    return {
        "count": len(runs),
        "latest": latest,
        "previous": previous,
        "comparison": comparison,
        "history": runs[-10:],
    }


__all__ = [
    "append_benchmark_run",
    "benchmark_path",
    "build_benchmark_run_snapshot",
    "build_benchmark_summary",
    "read_benchmark_runs",
]
