"""Loop runner that wraps Ralph for one worker iteration."""

from __future__ import annotations

import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Callable

from autopilot.core.adapters import AdapterExecutionRequest, AdapterMode, get_adapter
from autopilot.core.models import Profile, is_rate_limited

IGNORED_PREFIXES = (".agents/", ".ralph/")
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"
RALPH_BUILD_TEMPLATE_PATH = TEMPLATE_DIR / "ralph-build-prompt.md"
RETRY_TEMPLATE_PATH = TEMPLATE_DIR / "retry-prompt.md"
DEFAULT_PROJECT_AGENTS = """# AGENTS.md

This repository was bootstrapped by Autopilot from a PRD.

## Operational Rules
- Work only on the currently selected story.
- For non-documentation stories, a README-only or docs-only change is incomplete.
- If the repository is greenfield, create the smallest real scaffold needed to satisfy the story.
- If the story depends on an existing app, gateway, or file that is not present here, record the exact blocker in `.ralph/errors.log` and `.ralph/guardrails.md`, then stop without claiming success.
- Treat transient verification artifacts such as `__pycache__/`, `.pytest_cache/`, and `*.egg-info/` as disposable. Prefer `.gitignore` over manual recursive cleanup.
- Prefer the lightest verification that still proves the story works.
- If you discover repeatable build/test commands, keep this file updated with concise operational notes.

## Verification Guidance
- Python: prefer `pytest`, then targeted smoke checks or import checks.
- Node: prefer `npm test`, `npm run lint`, or `npm run build` when available.
- If no tooling exists yet, add the smallest meaningful verification artifact you can run and document it in `.ralph/progress.md`.
"""
DEFAULT_STATE_FILES = {
    "progress.md": "# Progress\n\n",
    "guardrails.md": "# Guardrails\n\nDo not repeat these mistakes:\n\n",
    "errors.log": "# Error Log\n\n> Failures and repeated issues. Use this to add guardrails.\n",
    "activity.log": "# Activity Log\n\n## Run Summary\n\n## Events\n",
    "critic-feedback.md": "",
}
RALPH_LOOP_REPLACE_OLD = '    src = src.replace("{{" + k + "}}", v)\n'
RALPH_LOOP_REPLACE_NEW = '    src = src.replace("{{" + k + "}}", str(v))\n'
AUTOPILOT_CONFIG_MARKER = "# Autopilot overrides"
AUTOPILOT_CONFIG_BLOCK = """# Autopilot overrides
ACTIVITY_CMD=".agents/ralph/log-activity.sh"
AGENTS_PATH="AGENTS.md"
PROMPT_BUILD=".agents/ralph/PROMPT_build.md"
"""
DEFAULT_PROGRESS_INTERVAL_SEC = 15


def check_ralph_installed() -> bool:
    """Return whether the Ralph CLI is available."""
    return shutil.which("ralph") is not None


def apply_autopilot_ralph_overrides(project_path: Path) -> None:
    """Install Autopilot-specific Ralph prompt and support files into a project."""
    agents_dir = project_path / ".agents" / "ralph"
    agents_dir.mkdir(parents=True, exist_ok=True)

    if RALPH_BUILD_TEMPLATE_PATH.exists():
        (agents_dir / "PROMPT_build.md").write_text(RALPH_BUILD_TEMPLATE_PATH.read_text())

    loop_script = agents_dir / "loop.sh"
    if loop_script.exists():
        loop_contents = loop_script.read_text()
        if RALPH_LOOP_REPLACE_OLD in loop_contents and RALPH_LOOP_REPLACE_NEW not in loop_contents:
            loop_script.write_text(loop_contents.replace(RALPH_LOOP_REPLACE_OLD, RALPH_LOOP_REPLACE_NEW))

    config_script = agents_dir / "config.sh"
    if config_script.exists():
        config_contents = config_script.read_text()
        if AUTOPILOT_CONFIG_MARKER not in config_contents:
            config_script.write_text(f"{config_contents.rstrip()}\n\n{AUTOPILOT_CONFIG_BLOCK}")

    agents_doc = project_path / "AGENTS.md"
    if not agents_doc.exists():
        agents_doc.write_text(DEFAULT_PROJECT_AGENTS)

    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(parents=True, exist_ok=True)
    for filename, default_contents in DEFAULT_STATE_FILES.items():
        file_path = ralph_dir / filename
        if not file_path.exists():
            file_path.write_text(default_contents)


def init_ralph_project(project_path: Path) -> bool:
    """Run `ralph install` in the project directory and apply Autopilot overrides."""
    agents_dir = project_path / ".agents" / "ralph"
    try:
        result = subprocess.run(
            ["ralph", "install", "--force"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            apply_autopilot_ralph_overrides(project_path)
            return True
        if agents_dir.exists():
            apply_autopilot_ralph_overrides(project_path)
            return True
        return False
    except Exception:
        if agents_dir.exists():
            apply_autopilot_ralph_overrides(project_path)
            return True
        return False


def _last_nonempty_content_line(path: Path) -> str:
    if not path.exists():
        return ""

    for raw_line in reversed(path.read_text().splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    return ""


def _latest_worker_activity(project_path: Path) -> str:
    activity_line = _last_nonempty_content_line(project_path / ".ralph" / "activity.log")
    if activity_line:
        if "] " in activity_line:
            return activity_line.split("] ", 1)[1].strip()
        return activity_line

    progress_line = _last_nonempty_content_line(project_path / ".ralph" / "progress.md")
    if progress_line:
        return progress_line.lstrip("- ").strip()

    return "Worker is still running."


def _run_command_with_progress(
    cmd: list[str],
    *,
    project_path: Path,
    env: dict[str, str],
    timeout: int,
    on_progress: Callable[[int, str], None] | None,
    progress_interval: int,
) -> tuple[bool, str, bool]:
    tmp_dir = project_path / ".ralph" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_dir / f"autopilot-worker-{uuid.uuid4().hex}.log"

    started_at = time.monotonic()
    next_progress_at = started_at + max(1, progress_interval)

    with output_path.open("w", encoding="utf-8") as output_file:
        process = subprocess.Popen(
            cmd,
            cwd=str(project_path),
            stdout=output_file,
            stderr=subprocess.STDOUT,
            text=True,
            env=env,
        )

        timed_out = False
        while True:
            returncode = process.poll()
            if returncode is not None:
                break

            elapsed = int(time.monotonic() - started_at)
            if elapsed >= timeout:
                timed_out = True
                process.kill()
                process.wait(timeout=5)
                break

            now = time.monotonic()
            if on_progress is not None and now >= next_progress_at:
                try:
                    on_progress(elapsed, _latest_worker_activity(project_path))
                except Exception:
                    pass
                next_progress_at = now + max(1, progress_interval)
            time.sleep(1)

    output = output_path.read_text(encoding="utf-8").strip() if output_path.exists() else ""
    output_path.unlink(missing_ok=True)
    if timed_out:
        return False, f"Timeout after {timeout}s", False

    success = process.returncode == 0
    rate_limited = is_rate_limited(output)
    return success, output, rate_limited


def _infer_runtime_profile(provider: str, env: dict[str, str], profile: Profile | None = None) -> Profile:
    if profile is not None:
        return profile

    adapter = get_adapter(provider)
    if adapter.provider_family == "codex":
        runtime_path = env.get("CODEX_HOME", "")
    else:
        runtime_home = env.get("HOME", "")
        runtime_path = str(Path(runtime_home).parent) if runtime_home else ""

    return Profile(
        name="runtime",
        provider=adapter.provider_family,
        adapter_id=adapter.adapter_id,
        path=runtime_path or ".",
    )


def run_ralph_iteration(
    project_path: Path,
    env: dict[str, str],
    timeout: int = 1800,
    prd_path: str | None = None,
    on_progress: Callable[[int, str], None] | None = None,
    progress_interval: int = DEFAULT_PROGRESS_INTERVAL_SEC,
) -> tuple[bool, str, bool]:
    """Run one Ralph build iteration and report success/output/rate-limit state."""
    cmd = ["ralph", "build", "1"]
    if prd_path:
        cmd.extend(["--prd", prd_path])

    if on_progress is not None:
        return _run_command_with_progress(
            cmd,
            project_path=project_path,
            env=env,
            timeout=timeout,
            on_progress=on_progress,
            progress_interval=progress_interval,
        )

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = f"{result.stdout}\n{result.stderr}".strip()
        success = result.returncode == 0
        rate_limited = is_rate_limited(output)
        return success, output, rate_limited
    except subprocess.TimeoutExpired:
        return False, f"Timeout after {timeout}s", False
    except Exception as exc:
        return False, str(exc), False


def build_retry_prompt(
    story_id: int,
    story_title: str,
    story_description: str,
    template_path: Path | None = None,
) -> str:
    """Build a focused retry prompt for follow-up iterations."""
    resolved_template = template_path or RETRY_TEMPLATE_PATH
    template = resolved_template.read_text() if resolved_template.exists() else (
        "Continue story #{story_id}: {story_title}\n\n"
        "Story details:\n{story_description}\n\n"
        "Read .ralph/critic-feedback.md, .ralph/progress.md, and .ralph/guardrails.md.\n"
        "Fix only the outstanding issues from the previous attempt.\n"
    )
    return template.format(
        story_id=story_id,
        story_title=story_title,
        story_description=story_description,
    )


def run_retry_iteration(
    project_path: Path,
    env: dict[str, str],
    provider: str,
    story_id: int,
    story_title: str,
    story_description: str,
    timeout: int = 1800,
    on_progress: Callable[[int, str], None] | None = None,
    progress_interval: int = DEFAULT_PROGRESS_INTERVAL_SEC,
    profile: Profile | None = None,
) -> tuple[bool, str, bool]:
    """Run a focused retry prompt after a failed or rejected iteration."""
    prompt = build_retry_prompt(story_id, story_title, story_description)
    runtime_profile = _infer_runtime_profile(provider, env, profile)
    adapter = get_adapter(runtime_profile.resolved_adapter_id)
    result = adapter.execute(
        AdapterExecutionRequest(
            profile=runtime_profile,
            prompt=prompt,
            workdir=project_path,
            env=env,
            timeout=timeout,
            mode=AdapterMode.EXEC,
            on_progress=on_progress,
            progress_interval=progress_interval,
            progress_message=lambda: _latest_worker_activity(project_path),
        )
    )
    parsed = adapter.parse_output(result)
    return result.success, parsed.text, parsed.rate_limited


def run_prompt_iteration(
    project_path: Path,
    env: dict[str, str],
    provider: str,
    prompt: str,
    timeout: int = 1800,
    on_progress: Callable[[int, str], None] | None = None,
    progress_interval: int = DEFAULT_PROGRESS_INTERVAL_SEC,
    profile: Profile | None = None,
) -> tuple[bool, str, bool]:
    """Run one generic provider prompt without invoking Ralph build mode."""
    runtime_profile = _infer_runtime_profile(provider, env, profile)
    adapter = get_adapter(runtime_profile.resolved_adapter_id)
    result = adapter.execute(
        AdapterExecutionRequest(
            profile=runtime_profile,
            prompt=prompt,
            workdir=project_path,
            env=env,
            timeout=timeout,
            mode=AdapterMode.EXEC,
            on_progress=on_progress,
            progress_interval=progress_interval,
            progress_message=lambda: _latest_worker_activity(project_path),
        )
    )
    parsed = adapter.parse_output(result)
    return result.success, parsed.text, parsed.rate_limited


def read_progress(project_path: Path) -> str:
    """Read `.ralph/progress.md` if it exists."""
    progress_file = project_path / ".ralph" / "progress.md"
    if progress_file.exists():
        return progress_file.read_text()
    return ""


def write_critic_feedback(project_path: Path, feedback: str) -> None:
    """Write critic feedback to `.ralph/critic-feedback.md`."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    feedback_file = ralph_dir / "critic-feedback.md"
    feedback_file.write_text(feedback)


def append_guardrail(project_path: Path, guardrail: str) -> None:
    """Append one guardrail entry to `.ralph/guardrails.md`."""
    ralph_dir = project_path / ".ralph"
    ralph_dir.mkdir(exist_ok=True)
    guardrails_file = ralph_dir / "guardrails.md"
    existing = guardrails_file.read_text() if guardrails_file.exists() else ""
    guardrails_file.write_text(f"{existing}\n- {guardrail}\n")


def _run_capture(project_path: Path, args: list[str], timeout: int = 30) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip()
    except Exception:
        return 1, ""


def _git_has_revision(project_path: Path, revision: str) -> bool:
    code, _ = _run_capture(project_path, ["git", "rev-parse", "--verify", revision], timeout=10)
    return code == 0


def _pathspec() -> list[str]:
    return ["--", ".", ":(exclude).agents", ":(exclude).ralph"]


def _committed_diff(project_path: Path) -> str:
    if not _git_has_revision(project_path, "HEAD"):
        return ""

    if _git_has_revision(project_path, "HEAD~1"):
        _, output = _run_capture(
            project_path,
            ["git", "diff", "HEAD~1", "HEAD", *_pathspec()],
        )
        return output

    _, output = _run_capture(
        project_path,
        ["git", "show", "--format=", "HEAD", *_pathspec()],
    )
    return output


def _working_tree_diff(project_path: Path) -> str:
    chunks: list[str] = []

    _, staged = _run_capture(project_path, ["git", "diff", "--cached", *_pathspec()])
    if staged:
        chunks.append(staged)

    _, unstaged = _run_capture(project_path, ["git", "diff", *_pathspec()])
    if unstaged:
        chunks.append(unstaged)

    _, untracked_raw = _run_capture(
        project_path,
        ["git", "ls-files", "--others", "--exclude-standard"],
    )
    for relative_path in untracked_raw.splitlines():
        relative_path = relative_path.strip()
        if not relative_path or relative_path.startswith(IGNORED_PREFIXES):
            continue
        file_path = project_path / relative_path
        if not file_path.is_file():
            continue
        _, file_diff = _run_capture(
            project_path,
            ["git", "diff", "--no-index", "--", "/dev/null", relative_path],
        )
        if file_diff:
            chunks.append(file_diff)

    return "\n".join(chunk for chunk in chunks if chunk).strip()


def check_git_diff_empty(project_path: Path) -> bool:
    """Return whether the latest relevant workspace changes are empty."""
    return get_last_commit_diff(project_path).strip() == ""


def get_last_commit_diff(project_path: Path) -> str:
    """Return the latest relevant changes for critic review.

    Prefer the current working tree if Ralph left changes uncommitted.
    Fall back to the latest commit diff when the tree is clean.
    """
    worktree_diff = _working_tree_diff(project_path)
    if worktree_diff:
        return worktree_diff
    return _committed_diff(project_path)
