"""Tests for recurring maintenance scheduler helpers."""

from __future__ import annotations

from autopilot.core.scheduler import format_interval, parse_schedule_spec, run_scheduled_job


def test_parse_schedule_spec_supports_aliases_and_units() -> None:
    hourly = parse_schedule_spec("hourly")
    every_six_hours = parse_schedule_spec("6h", max_runs=3)

    assert hourly.interval_sec == 3600
    assert every_six_hours.interval_sec == 21600
    assert every_six_hours.max_runs == 3
    assert format_interval(every_six_hours.interval_sec) == "6h"


def test_run_scheduled_job_repeats_until_max_runs() -> None:
    now = 0.0
    sleeps: list[float] = []
    seen_runs: list[int] = []

    def monotonic() -> float:
        return now

    def sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    def runner(run_index: int) -> dict[str, object]:
        seen_runs.append(run_index)
        return {
            "kind": "run_all_summary",
            "timestamp": f"run-{run_index}",
            "exit_code": 0,
            "scheduled_run_index": run_index,
        }

    summary = run_scheduled_job(
        job_name="run-all",
        schedule=parse_schedule_spec("60s", max_runs=2),
        runner=runner,
        monotonic=monotonic,
        sleep=sleep,
    )

    assert seen_runs == [1, 2]
    assert sleeps == [60.0]
    assert summary["kind"] == "scheduled_run_summary"
    assert summary["run_count"] == 2
    assert summary["exit_code"] == 0
    assert summary["runs"][1]["scheduled_run_index"] == 2


def test_run_scheduled_job_marks_failure_if_any_run_fails() -> None:
    summary = run_scheduled_job(
        job_name="run",
        schedule=parse_schedule_spec("1s", max_runs=2),
        runner=lambda run_index: {
            "kind": "run_summary",
            "timestamp": f"run-{run_index}",
            "exit_code": 1 if run_index == 2 else 0,
            "scheduled_run_index": run_index,
        },
        monotonic=lambda: 0.0,
        sleep=lambda _seconds: None,
    )

    assert summary["exit_code"] == 1
    assert summary["failed_runs"] == [2]
