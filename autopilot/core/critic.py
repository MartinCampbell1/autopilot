"""Critic runner for evaluating worker output via AI provider CLIs."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from autopilot.core.models import CriticResult

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

DEFAULT_CRITIC_TEMPLATE = """You are a code reviewer. Your task is to evaluate the latest commit.

## Task from PRD
{story_title}: {story_description}

## Diff
{diff}

## Check
1. Does the code solve the task from the story?
2. No obvious bugs?
3. No hardcoded secrets?
4. Is the code readable?
5. Are there tests for new functionality?

## Response format
If everything is OK:
APPROVED

If there are issues:
NEEDS_WORK
- Issue 1: specific description
- Issue 2: specific description
"""


def parse_critic_output(raw_output: str) -> CriticResult:
    """Parse critic CLI output into a structured result."""
    if not raw_output.strip():
        return CriticResult(approved=False, feedback="Empty output from critic", raw_output=raw_output)

    upper = raw_output.upper()
    has_needs_work = "NEEDS_WORK" in upper
    has_approved = "APPROVED" in upper

    if has_needs_work:
        lines = raw_output.strip().split("\n")
        feedback_lines: list[str] = []
        capture = False
        for line in lines:
            if "NEEDS_WORK" in line.upper():
                capture = True
                continue
            if capture:
                feedback_lines.append(line)

        return CriticResult(
            approved=False,
            feedback="\n".join(feedback_lines).strip(),
            raw_output=raw_output,
        )

    if has_approved:
        return CriticResult(approved=True, feedback="", raw_output=raw_output)

    return CriticResult(approved=False, feedback=raw_output.strip(), raw_output=raw_output)


def build_critic_prompt(
    story_title: str,
    story_description: str,
    diff: str,
    template_path: Path | None = None,
) -> str:
    """Build a critic prompt from template and runtime values."""
    if template_path and template_path.exists():
        template = template_path.read_text()
    else:
        template = DEFAULT_CRITIC_TEMPLATE

    return template.format(
        story_title=story_title,
        story_description=story_description,
        diff=diff[:8000],
    )


def get_git_diff(workdir: Path) -> str:
    """Get the diff of the previous commit relative to HEAD."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~1"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def run_critic(
    prompt: str,
    provider: str,
    env: dict[str, str],
    workdir: Path,
    timeout: int = 600,
) -> CriticResult:
    """Run the configured provider CLI and parse the critic result."""
    started_at = time.time()

    if provider == "codex":
        cmd = ["codex", "exec", "--full-auto", prompt]
    elif provider == "claude":
        cmd = ["claude", "-p", prompt]
    elif provider == "gemini":
        cmd = ["gemini", "-p", prompt]
    else:
        return CriticResult(approved=False, feedback=f"Unknown provider: {provider}", raw_output="")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        raw_output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        raw_output = "TIMEOUT: critic did not respond within time limit"
    except Exception as exc:
        raw_output = f"ERROR: {exc}"

    parsed = parse_critic_output(raw_output)
    parsed.elapsed_sec = round(time.time() - started_at, 2)
    return parsed
