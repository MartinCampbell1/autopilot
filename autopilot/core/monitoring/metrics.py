"""Project observability snapshot helpers."""

from __future__ import annotations

from typing import Any


def _sorted_cost_rollups(scope: dict[str, Any], *, key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item_key, bucket in dict(scope or {}).items():
        record = dict(bucket or {})
        record[key] = item_key
        items.append(record)
    items.sort(
        key=lambda item: (
            float(item.get("estimated_cost_usd") or 0.0),
            int(item.get("total_tokens") or 0),
            str(item.get(key) or ""),
        ),
        reverse=True,
    )
    return items


def build_monitoring_snapshot(
    *,
    cost_usage: dict[str, Any],
    trace_monitor: dict[str, Any],
    feedback_summary: dict[str, Any],
    benchmark_summary: dict[str, Any],
) -> dict[str, Any]:
    """Build one operator-facing monitoring snapshot."""

    cost_usage = dict(cost_usage or {})
    project_cost = dict(cost_usage.get("project") or {})
    run_cost = dict(cost_usage.get("run") or {})
    top_stories = _sorted_cost_rollups(cost_usage.get("stories") or {}, key="story_id")[:5]
    top_agents = _sorted_cost_rollups(cost_usage.get("agents") or {}, key="agent_label")[:5]
    trace_comparison = dict(trace_monitor.get("comparison") or {})
    benchmark_comparison = dict(benchmark_summary.get("comparison") or {})
    latest_run = benchmark_summary.get("latest") or (trace_monitor.get("runs") or [None])[-1]
    regressions = {
        "cost": bool(benchmark_comparison.get("cost_regression") or trace_comparison.get("cost_regression")),
        "reliability": bool(
            benchmark_comparison.get("reliability_regression") or trace_comparison.get("reliability_regression")
        ),
    }
    return {
        "cost": {
            "project": project_cost,
            "run": run_cost,
            "pricing_source": str(cost_usage.get("pricing_source") or "unconfigured"),
            "top_stories": top_stories,
            "top_agents": top_agents,
        },
        "trace": {
            "runs": list(trace_monitor.get("runs") or [])[-5:],
            "recent_failures": list(trace_monitor.get("recent_failures") or [])[-5:],
            "comparison": trace_comparison,
        },
        "feedback": feedback_summary,
        "benchmarks": benchmark_summary,
        "latest_run": latest_run,
        "regressions": regressions,
    }


__all__ = ["build_monitoring_snapshot"]
