"""Tests for benchmark snapshot storage and regression summaries."""

from __future__ import annotations

from autopilot.core.config import AutopilotConfig
from autopilot.core.evals.benchmarks import (
    append_benchmark_run,
    build_benchmark_run_snapshot,
    build_benchmark_summary,
    read_benchmark_runs,
)


def test_benchmark_summary_detects_cost_and_reliability_regression(tmp_path) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    append_benchmark_run(
        config,
        "proj-bench",
        build_benchmark_run_snapshot(
            {
                "run_id": "sess-1",
                "run_sequence": 1,
                "status": "run_completed",
                "iteration_count": 1,
                "failure_count": 0,
                "quality_regression_count": 0,
                "cost": {"estimated_cost_usd": 0.01, "total_tokens": 100},
            }
        ),
    )
    append_benchmark_run(
        config,
        "proj-bench",
        build_benchmark_run_snapshot(
            {
                "run_id": "sess-2",
                "run_sequence": 2,
                "status": "run_failed",
                "iteration_count": 2,
                "failure_count": 2,
                "quality_regression_count": 1,
                "cost": {"estimated_cost_usd": 0.03, "total_tokens": 250},
            }
        ),
    )

    summary = build_benchmark_summary(read_benchmark_runs(config, "proj-bench"))

    assert summary["count"] == 2
    assert summary["comparison"]["cost_regression"] is True
    assert summary["comparison"]["reliability_regression"] is True
