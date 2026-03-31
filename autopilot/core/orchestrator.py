"""Main orchestrator for worker, gates, critic, and stuck detection."""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path
from typing import Callable

from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import AutopilotConfig
from autopilot.core.cost_accounting import merge_usage_records, summarize_invocation_usage
from autopilot.core.critic import run_review_plan
from autopilot.core.escalation import CompetingAttempt, AttemptPlan, attempt_strategy_label, build_attempt_plan, select_winning_attempt
from autopilot.core.gates import run_gates
from autopilot.core.loop_runner import (
    append_guardrail,
    check_git_diff_empty,
    get_last_commit_diff,
    read_quality_ratchet,
    run_ralph_iteration,
    run_retry_iteration,
    summarize_quality_regressions,
    update_quality_ratchet,
    write_critic_feedback,
)
from autopilot.core.models import IterationRecord, Profile
from autopilot.core.stuck_detector import StuckDetector

console = Console()


class StoryOutcome(StrEnum):
    APPROVED = "approved"
    GATE_FAILED = "gate_failed"
    QUALITY_REGRESSION = "quality_regression"
    CRITIC_REJECTED = "critic_rejected"
    RATE_LIMITED = "rate_limited"
    WORKER_FAILED = "worker_failed"
    STUCK = "stuck"
    ERROR = "error"


class Orchestrator:
    """Run the full loop for one project: worker -> gates -> critic."""

    def __init__(
        self,
        project_path: Path,
        config: AutopilotConfig,
        profiles_dir: Path,
        *,
        quality_regression_mode: str = "retry",
        quality_auto_revert: bool = False,
        max_task_attempts: int = 2,
    ):
        self.project_path = project_path
        self.config = config
        self.account_mgr = AccountManager(
            profiles_dir=profiles_dir,
            cooldown_base=config.cooldown_base_sec,
            config=config,
        )
        self.account_mgr.discover()
        self.stuck_detector = StuckDetector()
        self.iteration_history: list[IterationRecord] = []
        self.quality_regression_mode = quality_regression_mode if quality_regression_mode in {"retry", "quarantine"} else "retry"
        self.quality_auto_revert = bool(quality_auto_revert)
        self.max_task_attempts = max(1, int(max_task_attempts))

    def _run_worker_attempt(
        self,
        *,
        profile: Profile,
        env: dict[str, str],
        story_id: int,
        story_title: str,
        story_description: str,
        gates_config: list[dict],
        critic_profile: Profile,
        critic_env: dict[str, str],
        review_phases: list[str] | None,
        ralph_prd_path: str | None,
        progress_callback: Callable[[int, str], None] | None,
        iteration_number: int,
        attempt_plan: AttemptPlan,
        attempt_count: int,
    ) -> tuple[StoryOutcome, IterationRecord | None]:
        """Run one candidate attempt for the current task."""
        started_at = time.time()
        attempt_label = attempt_strategy_label(attempt_plan.strategy)
        if attempt_count > 1:
            console.print(
                f"  [blue]Worker[/blue] {profile.provider}/{profile.name} starting "
                f"attempt {attempt_plan.attempt}/{attempt_count} ({attempt_label})..."
            )
        else:
            console.print(f"  [blue]Worker[/blue] {profile.provider}/{profile.name} starting story #{story_id}...")

        if attempt_plan.strategy == "focused_retry":
            success, output, rate_limited = run_retry_iteration(
                self.project_path,
                env,
                profile.provider,
                story_id,
                story_title,
                story_description,
                self.config.codex_timeout_sec,
                on_progress=progress_callback,
                profile=profile,
            )
        else:
            success, output, rate_limited = run_ralph_iteration(
                self.project_path,
                env,
                self.config.codex_timeout_sec,
                prd_path=ralph_prd_path,
                on_progress=progress_callback,
            )

        worker_usage = summarize_invocation_usage(
            output,
            provider=profile.provider,
            role="worker",
        )

        if rate_limited:
            console.print(f"  [yellow]Rate limited[/yellow] - {profile.name}")
            return StoryOutcome.RATE_LIMITED, None

        if not success:
            diff_empty = check_git_diff_empty(self.project_path)
            failure_feedback = output.strip()[:2000] or "Worker execution failed before producing a usable result."
            write_critic_feedback(self.project_path, failure_feedback)
            append_guardrail(self.project_path, f"Worker failed on story #{story_id}: {failure_feedback[:200]}")
            console.print("  [red]Worker failed[/red]")
            return StoryOutcome.WORKER_FAILED, IterationRecord(
                story_id=story_id,
                iteration=iteration_number,
                profile_used=profile.name,
                provider=profile.provider,
                gates_passed=False,
                critic_feedback=failure_feedback,
                elapsed_sec=round(time.time() - started_at, 2),
                git_diff_empty=diff_empty,
                worker_usage=worker_usage,
            )

        diff_empty = check_git_diff_empty(self.project_path)
        gate_results = []
        if gates_config:
            console.print("  [blue]Gates[/blue] running...")
            all_passed, gate_results = run_gates(
                gates_config,
                self.project_path,
                quality_baseline=read_quality_ratchet(self.project_path),
                base_env=env,
            )
            update_quality_ratchet(self.project_path, gate_results)
            quality_regression = any(result.regression for result in gate_results if result.required)
            regression_summary = summarize_quality_regressions(gate_results)

            for gate_result in gate_results:
                status = "[green]PASS[/green]" if gate_result.passed else "[red]FAIL[/red]"
                regression_tag = " [yellow](regression)[/yellow]" if gate_result.regression else ""
                console.print(f"    {gate_result.name}: {status}{regression_tag}")

            if not all_passed:
                if quality_regression:
                    error_output = f"Quality regression detected:\n{regression_summary}"
                    append_guardrail(
                        self.project_path,
                        "Do not regress previously green required gates without restoring them to green.",
                    )
                else:
                    error_output = "\n".join(
                        f"- {gate_result.name}: {gate_result.output[:200]}"
                        for gate_result in gate_results
                        if not gate_result.passed
                    )
                write_critic_feedback(self.project_path, f"Gate failures:\n{error_output}")
                outcome = (
                    StoryOutcome.QUALITY_REGRESSION
                    if quality_regression and self.quality_regression_mode == "quarantine"
                    else StoryOutcome.GATE_FAILED
                )
                return outcome, IterationRecord(
                    story_id=story_id,
                    iteration=iteration_number,
                    profile_used=profile.name,
                    provider=profile.provider,
                    gates_passed=False,
                    critic_feedback=error_output,
                    elapsed_sec=round(time.time() - started_at, 2),
                    git_diff_empty=diff_empty,
                    gate_results=gate_results,
                    worker_usage=worker_usage,
                    quality_regression=quality_regression,
                    regression_summary=regression_summary,
                )

        review_label = ", ".join(review_phases or [])
        if review_label:
            console.print(
                f"  [blue]Critic[/blue] {critic_profile.provider}/{critic_profile.name} reviewing ({review_label})..."
            )
        else:
            console.print(f"  [blue]Critic[/blue] {critic_profile.provider}/{critic_profile.name} reviewing...")
        diff = get_last_commit_diff(self.project_path)
        critic_result = run_review_plan(
            story_title=story_title,
            story_description=story_description,
            diff=diff,
            provider=critic_profile.provider,
            env=critic_env,
            workdir=self.project_path,
            profile=critic_profile,
            review_phases=review_phases,
        )
        for review_result in critic_result.review_results:
            status = "[green]PASS[/green]" if review_result.approved else "[red]FAIL[/red]"
            console.print(f"    {review_result.phase}: {status}")

        record = IterationRecord(
            story_id=story_id,
            iteration=iteration_number,
            profile_used=profile.name,
            provider=profile.provider,
            gates_passed=True,
            critic_approved=critic_result.approved,
            critic_feedback=critic_result.feedback,
            elapsed_sec=round(time.time() - started_at, 2),
            git_diff_empty=diff_empty,
            gate_results=gate_results,
            worker_usage=worker_usage,
            critic_usage=critic_result.usage,
            review_phases=critic_result.review_phases,
            review_results=critic_result.review_results,
            quality_regression=any(result.regression for result in gate_results if result.required),
            regression_summary=summarize_quality_regressions(gate_results),
        )
        if critic_result.approved:
            console.print("  [green]APPROVED[/green]")
            return StoryOutcome.APPROVED, record

        write_critic_feedback(self.project_path, critic_result.feedback)
        console.print(f"  [yellow]NEEDS_WORK[/yellow]: {critic_result.feedback[:100]}...")
        return StoryOutcome.CRITIC_REJECTED, record

    def run_single_iteration(
        self,
        profile: Profile,
        env: dict[str, str],
        story_id: int,
        story_title: str,
        story_description: str,
        gates_config: list[dict],
        critic_profile: Profile,
        critic_env: dict[str, str],
        review_phases: list[str] | None = None,
        retry_only: bool = False,
        ralph_prd_path: str | None = None,
        progress_callback: Callable[[int, str], None] | None = None,
    ) -> StoryOutcome:
        """Execute one worker iteration followed by gates and critic review."""
        iteration_number = len(self.iteration_history) + 1
        attempt_plan = build_attempt_plan(
            profile.provider,
            retry_only=retry_only,
            max_attempts=self.max_task_attempts,
        )
        attempt_records: list[tuple[AttemptPlan, StoryOutcome, IterationRecord]] = []
        competing_attempts: list[CompetingAttempt] = []

        for planned_attempt in attempt_plan:
            outcome, record = self._run_worker_attempt(
                profile=profile,
                env=env,
                story_id=story_id,
                story_title=story_title,
                story_description=story_description,
                gates_config=gates_config,
                critic_profile=critic_profile,
                critic_env=critic_env,
                review_phases=review_phases,
                ralph_prd_path=ralph_prd_path,
                progress_callback=progress_callback,
                iteration_number=iteration_number,
                attempt_plan=planned_attempt,
                attempt_count=len(attempt_plan),
            )
            if outcome == StoryOutcome.RATE_LIMITED:
                return StoryOutcome.RATE_LIMITED
            if record is None:
                continue

            attempt_records.append((planned_attempt, outcome, record))
            competing_attempts.append(
                CompetingAttempt(
                    attempt=planned_attempt.attempt,
                    provider=planned_attempt.provider,
                    strategy=planned_attempt.strategy,
                    outcome=outcome.value,
                    valid=outcome == StoryOutcome.APPROVED,
                    gates_passed=record.gates_passed,
                    critic_approved=record.critic_approved,
                    quality_regression=record.quality_regression,
                    git_diff_empty=record.git_diff_empty,
                )
            )
            if outcome == StoryOutcome.APPROVED:
                break

        if not attempt_records:
            return StoryOutcome.ERROR

        winner = select_winning_attempt(competing_attempts)
        selected_plan, selected_outcome, selected_record = attempt_records[winner.attempt - 1]
        selected_record.elapsed_sec = round(sum(record.elapsed_sec for _, _, record in attempt_records), 2)

        merged_worker_usage = [
            record.worker_usage
            for _, _, record in attempt_records
            if record.worker_usage
        ]
        merged_critic_usage = [
            record.critic_usage
            for _, _, record in attempt_records
            if record.critic_usage
        ]
        selected_record.worker_usage = merge_usage_records(*merged_worker_usage) if merged_worker_usage else {}
        selected_record.critic_usage = merge_usage_records(*merged_critic_usage) if merged_critic_usage else {}

        self.stuck_detector.record_iteration(selected_record)
        self.iteration_history.append(selected_record)

        if len(attempt_records) > 1 and winner.valid:
            console.print(
                f"  [green]Winning attempt[/green] {winner.attempt}/{len(attempt_records)} "
                f"({attempt_strategy_label(selected_plan.strategy)}) selected by policy."
            )
        if selected_outcome == StoryOutcome.QUALITY_REGRESSION:
            console.print("  [red]QUALITY REGRESSION[/red] quarantined for manual attention.")
        return selected_outcome

    def check_stuck(self) -> bool:
        """Return whether the current story is considered stuck."""
        if self.stuck_detector.is_stuck():
            console.print(f"  [red]STUCK[/red]: {self.stuck_detector.summary()}")
            return True
        return False

    def reset_stuck(self) -> None:
        """Reset stuck detection for a new story or provider."""
        self.stuck_detector.reset()
