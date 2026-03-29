"""Critic runner for evaluating worker output via AI provider CLIs."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from autopilot.core.adapters import AdapterExecutionRequest, AdapterMode, get_adapter
from autopilot.core.models import CriticResult, Profile

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
ISSUE_PATTERN = re.compile(r"^\s*-\s*Issue\b.*", re.IGNORECASE)
PLACEHOLDER_ISSUE_PATTERN = re.compile(
    r"^\s*(?:-\s*)?(?:"
    r"Issue\s+\d+:\s*specific description|"
    r"<[^>]+>|"
    r"concrete issue\b.*|"
    r"second concrete issue\b.*|"
    r"Then list one or more bullet points with concrete blocking issues\.?|"
    r"Followed by one or more bullet points that each name a real blocking issue\.?"
    r")\s*$",
    re.IGNORECASE,
)
NON_ACTIONABLE_FEEDBACK = "Critic returned NEEDS_WORK without actionable issues."
STOP_MARKERS = (
    "openai codex",
    "claude code",
    "assistant",
    "user",
    "codex",
    "exec",
    "mcp:",
    "tokens used",
    "--------",
)

DEFAULT_CRITIC_TEMPLATE = """You are a code reviewer. Your task is to evaluate the latest relevant code changes in the workspace.

## Task from PRD
{story_title}: {story_description}

## Diff
{diff}

## Check
1. Does the code solve the task from the story?
2. No obvious bugs?
3. No hardcoded secrets?
4. Is the code readable?
5. Are there tests or meaningful verification for new functionality?
6. If the story is not documentation-only, reject README-only or docs-only changes.
7. If the story depends on an existing codebase or file that is missing, call out the exact blocker.

## Response format
If everything is OK:
APPROVED

If there are issues:
NEEDS_WORK
Then list one or more bullet points with concrete blocking issues.
"""

STRICT_CRITIC_TEMPLATE = """You are a code reviewer. Evaluate the latest relevant code changes in the workspace against the story.

## Task from PRD
{story_title}: {story_description}

## Diff
{diff}

## Review rules
1. Approve only if the change satisfies the story as written.
2. Reject only for concrete, code-backed issues you can point to in the diff or files.
3. Do not output placeholder bullet text or template fillers.
4. If you cannot identify at least one concrete blocking issue, respond with APPROVED.
5. If tests or verification are missing for required new behavior, call that out explicitly.

## Response format
Use exactly one of these formats:

APPROVED

or

NEEDS_WORK
Followed by one or more bullet points that each name a real blocking issue.
"""


def feedback_is_actionable(feedback: str) -> bool:
    stripped = feedback.strip()
    if not stripped or stripped == NON_ACTIONABLE_FEEDBACK:
        return False

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if not lines:
        return False

    if all(PLACEHOLDER_ISSUE_PATTERN.match(line) for line in lines):
        return False
    return True


def _extract_issue_lines(raw_output: str) -> list[str]:
    lines = [line.rstrip() for line in raw_output.splitlines()]
    needs_work_indexes = [index for index, line in enumerate(lines) if "NEEDS_WORK" in line.upper()]
    search_space = lines[needs_work_indexes[-1] + 1 :] if needs_work_indexes else lines

    issues: list[str] = []
    for line in search_space:
        stripped = line.strip()
        if not stripped:
            if issues:
                break
            continue
        if any(stripped.lower().startswith(marker) for marker in STOP_MARKERS):
            break
        if ISSUE_PATTERN.match(stripped):
            if PLACEHOLDER_ISSUE_PATTERN.match(stripped):
                continue
            issues.append(stripped)
            continue
        if issues:
            break

    if issues:
        deduped: list[str] = []
        for issue in issues:
            if issue not in deduped:
                deduped.append(issue)
        return deduped

    cleaned: list[str] = []
    for line in search_space:
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.lower().startswith(marker) for marker in STOP_MARKERS):
            break
        if stripped.upper() == "NEEDS_WORK":
            continue
        if PLACEHOLDER_ISSUE_PATTERN.match(stripped):
            continue
        cleaned.append(stripped)
        if len(cleaned) >= 8:
            break
    return cleaned


def parse_critic_output(raw_output: str) -> CriticResult:
    """Parse critic CLI output into a structured result."""
    if not raw_output.strip():
        return CriticResult(approved=False, feedback="Empty output from critic", raw_output=raw_output)

    upper = raw_output.upper()
    has_needs_work = "NEEDS_WORK" in upper
    has_approved = "APPROVED" in upper

    if has_needs_work:
        feedback_lines = _extract_issue_lines(raw_output)
        feedback = "\n".join(feedback_lines).strip()
        if not feedback:
            feedback = NON_ACTIONABLE_FEEDBACK

        return CriticResult(
            approved=False,
            feedback=feedback,
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
    *,
    strict: bool = False,
) -> str:
    """Build a critic prompt from template and runtime values."""
    if template_path and template_path.exists():
        template = template_path.read_text()
    else:
        template = STRICT_CRITIC_TEMPLATE if strict else DEFAULT_CRITIC_TEMPLATE

    return template.format(
        story_title=story_title,
        story_description=story_description,
        diff=diff[:8000],
    )


def get_git_diff(workdir: Path) -> str:
    """Return the latest committed diff for ad-hoc callers."""
    try:
        has_head = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode == 0
        if not has_head:
            return ""

        has_parent = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD~1"],
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=10,
        ).returncode == 0

        cmd = ["git", "diff", "HEAD~1", "HEAD"] if has_parent else ["git", "show", "--format=", "HEAD"]
        result = subprocess.run(
            cmd,
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
    profile: Profile | None = None,
) -> CriticResult:
    """Run the configured provider CLI and parse the critic result."""
    started_at = time.time()

    try:
        adapter = get_adapter(profile.resolved_adapter_id if profile is not None else provider)
    except ValueError:
        return CriticResult(approved=False, feedback=f"Unknown provider: {provider}", raw_output="")

    runtime_profile = profile
    if runtime_profile is None:
        if adapter.provider_family == "codex":
            runtime_path = env.get("CODEX_HOME", "")
        else:
            runtime_home = env.get("HOME", "")
            runtime_path = str(Path(runtime_home).parent) if runtime_home else ""
        runtime_profile = Profile(
            name="runtime",
            provider=adapter.provider_family,
            adapter_id=adapter.adapter_id,
            path=runtime_path or ".",
        )

    execution = adapter.execute(
        AdapterExecutionRequest(
            profile=runtime_profile,
            prompt=prompt,
            workdir=workdir,
            env=env,
            timeout=timeout,
            mode=AdapterMode.CRITIC,
        )
    )
    parsed_output = adapter.parse_output(execution)
    raw_output = parsed_output.text
    if execution.timed_out and not raw_output:
        raw_output = "TIMEOUT: critic did not respond within time limit"
    elif not raw_output and execution.stderr:
        raw_output = execution.stderr

    parsed = parse_critic_output(raw_output)
    parsed.elapsed_sec = round(time.time() - started_at, 2)
    return parsed
