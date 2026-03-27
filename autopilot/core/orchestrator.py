"""Main orchestrator for worker, gates, critic, and stuck detection."""

from __future__ import annotations

import time
from enum import StrEnum
from pathlib import Path

from rich.console import Console

from autopilot.core.account_manager import AccountManager
from autopilot.core.config import AutopilotConfig
from autopilot.core.critic import build_critic_prompt, run_critic
from autopilot.core.gates import run_gates
from autopilot.core.loop_runner import (
    append_guardrail,
    check_git_diff_empty,
    get_last_commit_diff,
    run_ralph_iteration,
    write_critic_feedback,
)
from autopilot.core.models import IterationRecord, Profile
from autopilot.core.stuck_detector import StuckDetector

console = Console()


class StoryOutcome(StrEnum):
    APPROVED = "approved"
    GATE_FAILED = "gate_failed"
    CRITIC_REJECTED = "critic_rejected"
    RATE_LIMITED = "rate_limited"
    WORKER_FAILED = "worker_failed"
    STUCK = "stuck"
    ERROR = "error"


class Orchestrator:
    """Run the full loop for one project: worker -> gates -> critic."""

    def __init__(self, project_path: Path, config: AutopilotConfig, profiles_dir: Path):
        self.project_path = project_path
        self.config = config
        self.account_mgr = AccountManager(profiles_dir=profiles_dir, cooldown_base=config.cooldown_base_sec)
        self.account_mgr.discover()
        self.stuck_detector = StuckDetector()
        self.iteration_history: list[IterationRecord] = []

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
    ) -> StoryOutcome:
        """Execute one worker iteration followed by gates and critic review."""
        started_at = time.time()

        console.print(f"  [blue]Worker[/blue] {profile.provider}/{profile.name} starting story #{story_id}...")
        success, output, rate_limited = run_ralph_iteration(
            self.project_path,
            env,
            self.config.codex_timeout_sec,
        )

        if rate_limited:
            console.print(f"  [yellow]Rate limited[/yellow] - {profile.name}")
            return StoryOutcome.RATE_LIMITED

        if not success:
            append_guardrail(self.project_path, f"Worker failed on story #{story_id}: {output[:200]}")
            record = IterationRecord(
                story_id=story_id,
                iteration=len(self.iteration_history) + 1,
                profile_used=profile.name,
                provider=profile.provider,
                gates_passed=False,
                elapsed_sec=round(time.time() - started_at, 2),
            )
            self.stuck_detector.record_iteration(record)
            self.iteration_history.append(record)
            console.print("  [red]Worker failed[/red]")
            return StoryOutcome.WORKER_FAILED

        diff_empty = check_git_diff_empty(self.project_path)

        gate_results = []
        if gates_config:
            console.print("  [blue]Gates[/blue] running...")
            all_passed, gate_results = run_gates(gates_config, self.project_path)

            for gate_result in gate_results:
                status = "[green]PASS[/green]" if gate_result.passed else "[red]FAIL[/red]"
                console.print(f"    {gate_result.name}: {status}")

            if not all_passed:
                error_output = "\n".join(
                    f"- {gate_result.name}: {gate_result.output[:200]}"
                    for gate_result in gate_results
                    if not gate_result.passed
                )
                write_critic_feedback(self.project_path, f"Gate failures:\n{error_output}")

                record = IterationRecord(
                    story_id=story_id,
                    iteration=len(self.iteration_history) + 1,
                    profile_used=profile.name,
                    provider=profile.provider,
                    gates_passed=False,
                    critic_feedback=error_output,
                    elapsed_sec=round(time.time() - started_at, 2),
                    git_diff_empty=diff_empty,
                    gate_results=gate_results,
                )
                self.stuck_detector.record_iteration(record)
                self.iteration_history.append(record)
                return StoryOutcome.GATE_FAILED

        console.print(f"  [blue]Critic[/blue] {critic_profile.provider}/{critic_profile.name} reviewing...")
        diff = get_last_commit_diff(self.project_path)
        critic_prompt = build_critic_prompt(story_title, story_description, diff)
        critic_result = run_critic(
            prompt=critic_prompt,
            provider=critic_profile.provider,
            env=critic_env,
            workdir=self.project_path,
        )

        record = IterationRecord(
            story_id=story_id,
            iteration=len(self.iteration_history) + 1,
            profile_used=profile.name,
            provider=profile.provider,
            gates_passed=True,
            critic_approved=critic_result.approved,
            critic_feedback=critic_result.feedback,
            elapsed_sec=round(time.time() - started_at, 2),
            git_diff_empty=diff_empty,
            gate_results=gate_results,
        )
        self.stuck_detector.record_iteration(record)
        self.iteration_history.append(record)

        if critic_result.approved:
            console.print("  [green]APPROVED[/green]")
            return StoryOutcome.APPROVED

        write_critic_feedback(self.project_path, critic_result.feedback)
        console.print(f"  [yellow]NEEDS_WORK[/yellow]: {critic_result.feedback[:100]}...")
        return StoryOutcome.CRITIC_REJECTED

    def check_stuck(self) -> bool:
        """Return whether the current story is considered stuck."""
        if self.stuck_detector.is_stuck():
            console.print(f"  [red]STUCK[/red]: {self.stuck_detector.summary()}")
            return True
        return False

    def reset_stuck(self) -> None:
        """Reset stuck detection for a new story or provider."""
        self.stuck_detector.reset()
