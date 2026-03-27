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
Start by asking: "What do you want to build?"
"""


def run_intake_turn(
    session: IntakeSession,
    user_message: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
) -> str:
    """Run one intake conversation turn and update the session."""
    session.add_user_message(user_message)

    conversation = f"[System]: {INTAKE_SYSTEM_PROMPT}\n\n"
    for message in session.messages:
        role = "User" if message["role"] == "user" else "Assistant"
        conversation += f"[{role}]: {message['content']}\n\n"
    conversation += "[Assistant]:"

    if provider == "codex":
        cmd = ["codex", "exec", "--full-auto", conversation]
    elif provider == "claude":
        cmd = ["claude", "-p", conversation]
    else:
        cmd = ["codex", "exec", "--full-auto", conversation]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=workdir,
            env=env,
        )
        response = result.stdout.strip()
    except Exception as exc:
        response = f"Error: {exc}"

    session.add_agent_message(response)

    try:
        prd = json.loads(response)
        if "stories" in prd:
            session.prd = prd
    except (json.JSONDecodeError, TypeError):
        pass

    return response


def save_prd(prd: dict, project_path: Path) -> Path:
    """Save a generated PRD into the project's tasks directory."""
    tasks_dir = project_path / ".agents" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    slug = prd.get("title", "project").lower().replace(" ", "-")[:30]
    prd_path = tasks_dir / f"prd-{slug}.json"
    prd_path.write_text(json.dumps(prd, indent=2, ensure_ascii=False))
    return prd_path
