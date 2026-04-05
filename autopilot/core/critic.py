"""Critic runner for evaluating worker output via AI provider CLIs."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

from autopilot.core.adapters import AdapterExecutionRequest, AdapterMode, get_adapter
from autopilot.core.capability_store import normalize_review_phases
from autopilot.core.cost_accounting import merge_usage_records, summarize_invocation_usage
from autopilot.core.evals.judges import build_critic_judge_context, evaluate_judge_pack
from autopilot.core.models import CriticResult, Profile, ReviewPhaseResult, VerificationCheck
from autopilot.core.shadow_audit import audit_verifier_output
from autopilot.core.verification_agent import NON_ACTIONABLE_VERIFICATION_FEEDBACK, VERDICT_PATTERN

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
ISSUE_PATTERN = re.compile(r"^\s*-\s*Issue\b.*", re.IGNORECASE)
CHECK_HEADER_PATTERN = re.compile(r"^###\s*Check:\s*(.+?)\s*$", re.IGNORECASE)
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
REVIEW_PHASE_FOCUS: dict[str, str] = {
    "security": (
        "Focus only on security-impacting defects: secrets exposure, auth/authz mistakes, unsafe command or "
        "file handling, injection risks, insecure defaults, and data leakage. Ignore non-security concerns."
    ),
    "architecture": (
        "Focus only on architecture and integration risks: broken boundaries, missing migrations or wiring, "
        "brittle coupling, invalid assumptions about existing modules, and changes that do not fit the current system shape."
    ),
    "tests": (
        "Focus only on verification quality: missing tests for new behavior, insufficient regression coverage, "
        "or claims of correctness without concrete validation."
    ),
}

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
VERIFICATION_CRITIC_APPENDIX = """

## Verification Contract
You are acting as a verification specialist, not a trust-the-code reviewer.
Your job is to try to break the change and approve it only when command-backed evidence supports that decision.

Required rules:
1. Do not modify project files, install packages, or run git write operations.
2. Treat passing tests as context, not proof.
3. Use concrete commands against the changed behavior whenever the environment allows it.
4. Include at least one adversarial probe relevant to the change: boundary input, invalid input, idempotency, regression, or similar.
5. Label that check title with the words `adversarial probe`, for example `### Check: adversarial probe - invalid token`.
6. If you cannot verify a claim because the environment blocks it, return `VERDICT: PARTIAL`, not PASS.
7. A PASS without command-backed evidence is invalid.

## Required Output Format
For each concrete check, use:

### Check: [what you verified]
**Command run:**
  [exact command you executed]
**Output observed:**
  [actual observed output or relevant excerpt]
**Result: PASS**

If a check fails, use `**Result: FAIL**` and include expected vs actual when relevant.

End with exactly one line:
VERDICT: PASS
or
VERDICT: FAIL
or
VERDICT: PARTIAL
"""
STRICT_VERIFICATION_APPENDIX = """

## Additional Strictness
- Do not return PASS unless at least one check block includes both a concrete command and observed output.
- If you cannot produce command-backed evidence, return `VERDICT: PARTIAL`.
- Reject vague concerns without reproduction. Use FAIL for reproduced issues and PARTIAL for environmental limits.
"""


def _starts_section(line: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()
    return bool(
        CHECK_HEADER_PATTERN.match(stripped)
        or VERDICT_PATTERN.match(stripped)
        or lowered.startswith("**command run:**")
        or lowered.startswith("**output observed:**")
        or lowered.startswith("**expected vs actual:**")
        or lowered.startswith("**result:")
    )


def _parse_result_line(line: str) -> tuple[str, str]:
    stripped = line.strip()
    match = re.match(r"^\*{0,2}Result:\s*(PASS|FAIL|PARTIAL)\*{0,2}\s*(.*)$", stripped, re.IGNORECASE)
    if not match:
        return "", ""
    status = match.group(1).upper()
    details = match.group(2).strip().strip("*").strip()
    return status, details


def _parse_verification_checks(raw_output: str) -> list[VerificationCheck]:
    checks: list[VerificationCheck] = []
    current: VerificationCheck | None = None
    current_section: str | None = None
    section_lines: list[str] = []

    def flush_section() -> None:
        nonlocal section_lines
        if current is None or current_section is None:
            section_lines = []
            return
        content = "\n".join(section_lines).strip()
        if current_section == "command":
            current.command = content
        elif current_section == "output":
            current.output = content
        elif current_section == "expected_vs_actual":
            current.expected_vs_actual = content
        section_lines = []

    def flush_check() -> None:
        nonlocal current, current_section, section_lines
        flush_section()
        if current is not None:
            checks.append(current)
        current = None
        current_section = None
        section_lines = []

    for raw_line in raw_output.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        check_match = CHECK_HEADER_PATTERN.match(stripped)
        if check_match:
            flush_check()
            current = VerificationCheck(name=check_match.group(1).strip())
            continue
        if current is None:
            continue
        if VERDICT_PATTERN.match(stripped):
            flush_check()
            break
        lowered = stripped.lower()
        if lowered.startswith("**command run:**"):
            flush_section()
            current_section = "command"
            inline = stripped.split(":", 1)[1].strip().strip("*").strip()
            section_lines = [inline] if inline else []
            continue
        if lowered.startswith("**output observed:**"):
            flush_section()
            current_section = "output"
            inline = stripped.split(":", 1)[1].strip().strip("*").strip()
            section_lines = [inline] if inline else []
            continue
        if lowered.startswith("**expected vs actual:**"):
            flush_section()
            current_section = "expected_vs_actual"
            inline = stripped.split(":", 1)[1].strip().strip("*").strip()
            section_lines = [inline] if inline else []
            continue
        if lowered.startswith("**result:"):
            flush_section()
            current_section = None
            status, details = _parse_result_line(stripped)
            current.status = status
            current.details = details
            continue
        if _starts_section(stripped):
            flush_section()
            current_section = None
            continue
        if current_section is not None:
            section_lines.append(line)

    flush_check()
    return checks


def _verification_feedback(checks: list[VerificationCheck], raw_output: str, *, verdict: str) -> str:
    failing_checks = [
        check for check in checks if check.status in {"FAIL", "PARTIAL"} or (verdict != "PASS" and not check.status)
    ]
    candidates = failing_checks or checks
    lines: list[str] = []
    for check in candidates:
        summary = (
            check.expected_vs_actual.strip()
            or check.details.strip()
            or next((line.strip() for line in check.output.splitlines() if line.strip()), "")
            or next((line.strip() for line in check.command.splitlines() if line.strip()), "")
        )
        if summary:
            lines.append(f"- {check.name}: {summary}")
        else:
            lines.append(f"- {check.name}: verification reported {check.status or verdict}.")
    if lines:
        return "\n".join(lines[:8]).strip()

    fallback_lines = [
        line.strip()
        for line in raw_output.splitlines()
        if line.strip() and not VERDICT_PATTERN.match(line.strip()) and not CHECK_HEADER_PATTERN.match(line.strip())
    ]
    if fallback_lines:
        return "\n".join(fallback_lines[-8:]).strip()
    return NON_ACTIONABLE_FEEDBACK

def feedback_is_actionable(feedback: str) -> bool:
    stripped = feedback.strip()
    if not stripped or stripped in {NON_ACTIONABLE_FEEDBACK, NON_ACTIONABLE_VERIFICATION_FEEDBACK}:
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

    verification_checks = _parse_verification_checks(raw_output)
    verdict, shadow_audit = audit_verifier_output(raw_output, verification_checks)
    if shadow_audit.action in {"retry", "quarantine", "escalate"}:
        return CriticResult(
            approved=False,
            feedback=shadow_audit.summary,
            raw_output=raw_output,
            verdict=verdict,
            verification_checks=verification_checks,
            shadow_audit_action=shadow_audit.action,
            shadow_audit_feedback=shadow_audit.summary,
            shadow_audit_findings=list(shadow_audit.findings),
        )
    if verdict:
        if verdict == "PASS":
            return CriticResult(
                approved=True,
                feedback="",
                raw_output=raw_output,
                verdict=verdict,
                verification_checks=verification_checks,
                shadow_audit_action=shadow_audit.action,
                shadow_audit_findings=list(shadow_audit.findings),
            )
        return CriticResult(
            approved=False,
            feedback=_verification_feedback(verification_checks, raw_output, verdict=verdict),
            raw_output=raw_output,
            verdict=verdict,
            verification_checks=verification_checks,
            shadow_audit_action=shadow_audit.action,
            shadow_audit_findings=list(shadow_audit.findings),
        )

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
            verification_checks=verification_checks,
        )

    if has_approved:
        return CriticResult(approved=True, feedback="", raw_output=raw_output, verification_checks=verification_checks)

    return CriticResult(approved=False, feedback=raw_output.strip(), raw_output=raw_output, verification_checks=verification_checks)


def build_critic_prompt(
    story_title: str,
    story_description: str,
    diff: str,
    template_path: Path | None = None,
    *,
    strict: bool = False,
    phase: str | None = None,
) -> str:
    """Build a critic prompt from template and runtime values."""
    if template_path and template_path.exists():
        template = template_path.read_text()
    else:
        template = STRICT_CRITIC_TEMPLATE if strict else DEFAULT_CRITIC_TEMPLATE

    prompt = template.format(
        story_title=story_title,
        story_description=story_description,
        diff=diff[:8000],
    )
    prompt += VERIFICATION_CRITIC_APPENDIX
    if strict:
        prompt += STRICT_VERIFICATION_APPENDIX
    focus = REVIEW_PHASE_FOCUS.get(str(phase or "").strip().lower())
    if focus:
        prompt += (
            "\n\n## Narrow review focus\n"
            f"This is a focused {phase.strip().lower()} review. {focus}\n"
            "Reject only for blocking issues in this focus area."
        )
    return prompt


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
    parsed.profile_used = runtime_profile.name
    parsed.elapsed_sec = round(time.time() - started_at, 2)
    parsed.usage = summarize_invocation_usage(
        raw_output,
        provider=runtime_profile.provider,
        role="critic",
    )
    return parsed


def _run_review_phase(
    *,
    story_title: str,
    story_description: str,
    diff: str,
    provider: str,
    env: dict[str, str],
    workdir: Path,
    timeout: int = 600,
    profile: Profile | None = None,
    phase: str | None = None,
) -> CriticResult:
    prompt = build_critic_prompt(
        story_title,
        story_description,
        diff,
        strict=False,
        phase=phase,
    )
    critic_result = run_critic(
        prompt=prompt,
        provider=provider,
        env=env,
        workdir=workdir,
        timeout=timeout,
        profile=profile,
    )
    critic_usage = critic_result.usage
    if not critic_result.approved and not feedback_is_actionable(critic_result.feedback):
        retry_result = run_critic(
            prompt=build_critic_prompt(
                story_title,
                story_description,
                diff,
                strict=True,
                phase=phase,
            ),
            provider=provider,
            env=env,
            workdir=workdir,
            timeout=timeout,
            profile=profile,
        )
        critic_usage = merge_usage_records(critic_usage, retry_result.usage)
        if retry_result.approved or feedback_is_actionable(retry_result.feedback):
            critic_result = retry_result
        else:
            critic_result.feedback = NON_ACTIONABLE_FEEDBACK
        critic_result.usage = critic_usage
    critic_result.review_phases = [phase] if phase else []
    if phase:
        critic_result.review_results = [_review_phase_result(phase, critic_result)]
    elif not getattr(critic_result, "review_results", None):
        critic_result.review_results = []
    return critic_result


def _review_phase_result(phase: str, result: CriticResult) -> ReviewPhaseResult:
    return ReviewPhaseResult(
        phase=phase,
        approved=result.approved,
        feedback=result.feedback,
        raw_output=result.raw_output,
        verdict=getattr(result, "verdict", ""),
        profile_used=result.profile_used,
        elapsed_sec=result.elapsed_sec,
        usage=dict(result.usage or {}),
        verification_checks=list(getattr(result, "verification_checks", []) or []),
        shadow_audit_action=str(getattr(result, "shadow_audit_action", "pass") or "pass"),
        shadow_audit_feedback=str(getattr(result, "shadow_audit_feedback", "") or ""),
        shadow_audit_findings=list(getattr(result, "shadow_audit_findings", []) or []),
    )


def _aggregate_review_feedback(review_results: list[ReviewPhaseResult]) -> str:
    feedback_lines: list[str] = []
    for review in review_results:
        if review.approved:
            continue
        raw_lines = [line.strip() for line in str(review.feedback or "").splitlines() if line.strip()]
        if not raw_lines:
            raw_lines = [NON_ACTIONABLE_FEEDBACK]
        for line in raw_lines:
            text = line[2:].strip() if line.startswith("- ") else line
            feedback_lines.append(f"- [{review.phase}] {text}")
    return "\n".join(feedback_lines).strip()


def _apply_judge_pack(
    result: CriticResult,
    *,
    judge_pack: str | None = None,
    judge_registry: dict[str, object] | None = None,
) -> CriticResult:
    normalized_pack = str(judge_pack or "").strip()
    if not normalized_pack:
        return result

    judge_result = evaluate_judge_pack(
        normalized_pack,
        build_critic_judge_context(result),
        registry=judge_registry,
    )
    result.judge_pack = judge_result.pack_id
    result.judge_verdict = judge_result.verdict
    result.judge_summary = judge_result.summary
    result.judge_findings = list(judge_result.findings)

    if result.approved and judge_result.verdict != "PASS":
        result.approved = False
        result.verdict = judge_result.verdict
        if not feedback_is_actionable(result.feedback):
            result.feedback = judge_result.summary
    elif not result.verdict:
        result.verdict = judge_result.verdict
    return result


def run_review_plan(
    *,
    story_title: str,
    story_description: str,
    diff: str,
    provider: str,
    env: dict[str, str],
    workdir: Path,
    timeout: int = 600,
    profile: Profile | None = None,
    review_phases: list[str] | None = None,
    judge_pack: str | None = None,
    judge_registry: dict[str, object] | None = None,
) -> CriticResult:
    """Run either one broad critic pass or a focused multi-phase review fan-out."""

    phases = normalize_review_phases(review_phases, default=[], story_execution_mode="solo")
    if not phases:
        return _apply_judge_pack(
            _run_review_phase(
                story_title=story_title,
                story_description=story_description,
                diff=diff,
                provider=provider,
                env=env,
                workdir=workdir,
                timeout=timeout,
                profile=profile,
                phase=None,
            ),
            judge_pack=judge_pack,
            judge_registry=judge_registry,
        )

    phase_results: list[ReviewPhaseResult] = []
    usage_records: list[dict[str, object]] = []
    raw_outputs: list[str] = []
    for phase in phases:
        result = _run_review_phase(
            story_title=story_title,
            story_description=story_description,
            diff=diff,
            provider=provider,
            env=env,
            workdir=workdir,
            timeout=timeout,
            profile=profile,
            phase=phase,
        )
        phase_results.append(_review_phase_result(phase, result))
        usage_records.append(result.usage)
        raw_outputs.append(f"[{phase}]\n{result.raw_output}".strip())

    approved = all(result.approved for result in phase_results)
    verdict = "PASS" if approved else ("PARTIAL" if any(result.verdict == "PARTIAL" for result in phase_results) else "FAIL")
    return _apply_judge_pack(
        CriticResult(
            approved=approved,
            feedback="" if approved else _aggregate_review_feedback(phase_results),
            raw_output="\n\n".join(raw_outputs).strip(),
            verdict=verdict,
            profile_used=profile.name if profile is not None else "",
            elapsed_sec=round(sum(result.elapsed_sec for result in phase_results), 2),
            usage=merge_usage_records(*usage_records),
            review_phases=phases,
            review_results=phase_results,
        ),
        judge_pack=judge_pack,
        judge_registry=judge_registry,
    )
