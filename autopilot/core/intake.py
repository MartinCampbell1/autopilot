"""Intake agent backend for brainstorming and PRD generation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class IntakeSession:
    session_id: str
    messages: list[dict] = field(default_factory=list)
    prd: dict | None = None
    project_name: str = ""

    def add_user_message(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def add_agent_message(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})


INTAKE_SYSTEM_PROMPT = """You are a project intake agent. Your job is to help the user define a software project.

Ask clarifying questions ONE AT A TIME to understand:
1. What the project does
2. Tech stack (language, framework, deployment)
3. Key features (3-8 stories)
4. Any constraints or requirements

If the user already described what they want to build, do not repeat "What do you want to build?".
Instead, ask the next most useful clarifying question immediately.

After you have enough information, generate a PRD in this JSON format:
```json
{
  "title": "Project Name",
  "description": "One paragraph description",
  "stories": [
    {"id": 1, "title": "Story title", "description": "What to build", "status": "open"},
    {"id": 2, "title": "Story title", "description": "What to build", "status": "open"}
  ]
}
```

Output ONLY the JSON when you're ready. No markdown fences, no explanation.
If the user has not provided a project description yet, start by asking: "What do you want to build?"
"""

SPEC_TO_PRD_PROMPT = """You are a project planner.

You will receive a project specification. Convert it into a PRD JSON document.

Rules:
- Preserve the user's actual intent.
- Keep the title concise.
- Write a one-paragraph description.
- Produce 3-8 implementation stories.
- Output ONLY valid JSON with this shape:
{
  "title": "Project Name",
  "description": "One paragraph description",
  "stories": [
    {"id": 1, "title": "Story title", "description": "What to build", "status": "open"}
  ]
}
"""


def _extract_json_blob(text: str) -> str:
    """Extract the first top-level JSON object from model output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.replace("json\n", "", 1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _run_provider_prompt(
    prompt: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
) -> str:
    """Run one provider prompt and return stdout or a surfaced error."""
    if provider == "codex":
        cmd = ["codex", "exec", "--full-auto", "--skip-git-repo-check", prompt]
    elif provider == "claude":
        cmd = ["claude", "-p", prompt]
    else:
        cmd = ["codex", "exec", "--full-auto", "--skip-git-repo-check", prompt]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=workdir,
            env=env,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode == 0 and stdout:
            return stdout
        if stderr:
            return stderr
        if stdout:
            return stdout
        return f"Command failed with exit code {result.returncode}"
    except Exception as exc:
        return f"Error: {exc}"


def run_intake_turn(
    session: IntakeSession,
    user_message: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
) -> str:
    """Run one intake conversation turn and update the session."""
    session.add_user_message(user_message)

    introduction = INTAKE_SYSTEM_PROMPT
    if len(session.messages) == 1 and user_message.strip():
        introduction += (
            "\n\nThe user already provided the initial project description in their first message. "
            "Do not repeat the generic opening question."
        )

    conversation = f"[System]: {introduction}\n\n"
    for message in session.messages:
        role = "User" if message["role"] == "user" else "Assistant"
        conversation += f"[{role}]: {message['content']}\n\n"
    conversation += "[Assistant]:"

    response = _run_provider_prompt(conversation, provider, env, workdir)

    session.add_agent_message(response)

    try:
        prd = json.loads(_extract_json_blob(response))
        if "stories" in prd:
            session.prd = prd
    except (json.JSONDecodeError, TypeError):
        pass

    return response


def generate_prd_from_spec(
    spec_text: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
) -> dict:
    """Convert an uploaded specification into a PRD JSON document."""
    spec = spec_text.strip()
    if not spec:
        raise ValueError("Spec text is empty")

    try:
        parsed = json.loads(spec)
        if isinstance(parsed, dict) and "stories" in parsed:
            return parsed
    except json.JSONDecodeError:
        pass

    prompt = f"{SPEC_TO_PRD_PROMPT}\n\n[Specification]\n{spec}\n"
    response = _run_provider_prompt(prompt, provider, env, workdir)

    try:
        parsed = json.loads(_extract_json_blob(response))
    except json.JSONDecodeError as exc:
        raise ValueError(response.strip() or "Provider did not return valid JSON") from exc

    if not isinstance(parsed, dict) or "stories" not in parsed:
        raise ValueError("Provider response did not contain a valid PRD")

    return parsed


def save_prd(prd: dict, project_path: Path) -> Path:
    """Save a generated PRD into the project's tasks directory."""
    tasks_dir = project_path / ".agents" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    slug = prd.get("title", "project").lower().replace(" ", "-")[:30]
    prd_path = tasks_dir / f"prd-{slug}.json"
    prd_path.write_text(json.dumps(prd, indent=2, ensure_ascii=False))
    return prd_path
