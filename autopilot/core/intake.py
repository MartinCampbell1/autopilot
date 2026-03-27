"""Intake agent backend for brainstorming and PRD generation."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from autopilot.core.project_store import normalize_prd


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
3. Execution context (existing repo vs greenfield, external systems, MCP/data/tool needs)
4. Key phases and deliverables
5. Any constraints or requirements

If the user already described what they want to build, do not repeat "What do you want to build?".
Instead, ask the next most useful clarifying question immediately.

After you have enough information, generate a PRD in this JSON format:
```json
{
  "title": "Project Name",
  "description": "One paragraph description",
  "phases": [
    {"id": "phase-1", "title": "Foundation", "goal": "What this phase proves"}
  ],
  "stories": [
    {
      "id": 1,
      "phase_id": "phase-1",
      "phase_title": "Foundation",
      "title": "Small concrete task",
      "description": "What exactly to build",
      "acceptance_criteria": ["Concrete verification item"],
      "tags": ["backend", "api"],
      "role": "backend_worker",
      "skill_packs": ["fastapi-backend"],
      "connectors": ["shell_exec", "python_exec", "web_docs"],
      "status": "open"
    }
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
- First decide project complexity: low, medium, high, or very_high.
- Use that complexity to size the plan:
  - low: 1-2 phases, 3-8 stories
  - medium: 2-4 phases, 8-18 stories
  - high: 4-6 phases, 18-35 stories
  - very_high: 5-8 phases, 30-60 stories
- Prefer more smaller stories over fewer broad stories.
- Each story must be narrow enough for one focused worker iteration and one clear review.
- Group stories into phases with explicit goals.
- Add execution metadata for each story:
  - tags
  - role
  - skill_packs
  - connectors
- If the project mentions existing repos, external APIs, graphs, databases, browsers, design systems, or research, reflect that in story metadata.
- Output ONLY valid JSON with this shape:
{
  "title": "Project Name",
  "description": "One paragraph description",
  "phases": [
    {"id": "phase-1", "title": "Foundation", "goal": "What this phase proves"}
  ],
  "stories": [
    {
      "id": 1,
      "phase_id": "phase-1",
      "phase_title": "Foundation",
      "title": "Concrete implementation task",
      "description": "Exactly what to build",
      "acceptance_criteria": ["Concrete verification item"],
      "tags": ["backend", "api"],
      "role": "backend_worker",
      "skill_packs": ["fastapi-backend"],
      "connectors": ["shell_exec", "python_exec", "web_docs"],
      "status": "open"
    }
  ]
}
"""

PLAN_REFINEMENT_PROMPT = """You are refining an implementation plan because the initial PRD is too coarse for execution.

Take the current PRD and rewrite it into a more detailed phased implementation plan.

Rules:
- Preserve the original product intent.
- Keep the existing title unless it is obviously broken.
- Keep or improve the description.
- Expand broad stories into smaller, concrete stories.
- Each story must be scoped for one focused worker implementation + one critic review.
- Maintain explicit phases with goals.
- Use the target complexity and story range below as hard guidance.
- Include execution metadata for every story:
  - phase_id
  - phase_title
  - acceptance_criteria
  - tags
  - role
  - skill_packs
  - connectors
- Output ONLY valid JSON with the same schema as the original PRD.
"""

COMPLEXITY_RANGES: dict[str, tuple[int, int]] = {
    "low": (3, 8),
    "medium": (8, 18),
    "high": (18, 35),
    "very_high": (30, 60),
}

COMPLEXITY_SIGNALS: dict[str, tuple[str, ...]] = {
    "medium": ("dashboard", "auth", "payment", "integration", "postgres", "queue", "telegram", "worker"),
    "high": ("multi-agent", "gateway", "orchestration", "trading", "solana", "graph", "neo4j", "analytics"),
    "very_high": ("exchange", "autotrading", "multi-tenant", "market making", "distributed", "real-time"),
}


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


def _estimate_complexity(text: str) -> str:
    lowered = text.lower()
    score = 0

    text_length = len(lowered)
    if text_length > 5000:
        score += 4
    elif text_length > 2500:
        score += 3
    elif text_length > 1000:
        score += 2
    elif text_length > 250:
        score += 1

    line_count = len([line for line in lowered.splitlines() if line.strip()])
    if line_count > 25:
        score += 2
    elif line_count > 10:
        score += 1

    for level, keywords in COMPLEXITY_SIGNALS.items():
        matches = sum(1 for keyword in keywords if keyword in lowered)
        if matches == 0:
            continue
        if level == "medium":
            score += min(matches, 2)
        elif level == "high":
            score += min(matches, 3)
        else:
            score += min(matches, 4)

    if score >= 7:
        return "very_high"
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def _plan_needs_expansion(prd: dict, source_text: str) -> tuple[bool, str]:
    complexity = _estimate_complexity(source_text)
    if complexity == "low":
        return False, complexity

    stories = prd.get("stories") or []
    phases = prd.get("phases") or []
    min_stories, _ = COMPLEXITY_RANGES[complexity]

    if len(stories) < min_stories:
        return True, complexity
    if complexity in {"high", "very_high"} and len(phases) < 3:
        return True, complexity
    return False, complexity


def _refine_prd_if_needed(
    prd: dict,
    *,
    source_text: str,
    provider: str,
    env: dict[str, str],
    workdir: str,
    planning_context: str,
) -> dict:
    needs_expansion, complexity = _plan_needs_expansion(prd, source_text)
    if not needs_expansion:
        return normalize_prd(prd, seed_mode="new")

    min_stories, max_stories = COMPLEXITY_RANGES[complexity]
    prompt = (
        f"{PLAN_REFINEMENT_PROMPT}\n\n"
        f"Target complexity: {complexity}\n"
        f"Target story range: {min_stories}-{max_stories}\n"
    )
    if planning_context.strip():
        prompt += f"\n[Planning Catalog]\n{planning_context.strip()}\n"
    prompt += (
        f"\n[Original Product Intent]\n{source_text.strip()}\n"
        f"\n[Current PRD]\n{json.dumps(prd, ensure_ascii=False, indent=2)}\n"
    )

    response = _run_provider_prompt(prompt, provider, env, workdir)
    try:
        refined = json.loads(_extract_json_blob(response))
    except json.JSONDecodeError:
        return normalize_prd(prd, seed_mode="new")

    if not isinstance(refined, dict) or "stories" not in refined:
        return normalize_prd(prd, seed_mode="new")
    return normalize_prd(refined, seed_mode="new")


def run_intake_turn(
    session: IntakeSession,
    user_message: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
    planning_context: str = "",
) -> str:
    """Run one intake conversation turn and update the session."""
    session.add_user_message(user_message)

    introduction = INTAKE_SYSTEM_PROMPT
    if planning_context.strip():
        introduction += f"\n\nUse this planning catalog when assigning roles, skill packs, and connectors:\n{planning_context.strip()}\n"
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
            session.prd = _refine_prd_if_needed(
                prd,
                source_text="\n".join(message["content"] for message in session.messages),
                provider=provider,
                env=env,
                workdir=workdir,
                planning_context=planning_context,
            )
    except (json.JSONDecodeError, TypeError):
        pass

    return response


def generate_prd_from_spec(
    spec_text: str,
    provider: str,
    env: dict[str, str],
    workdir: str = "/tmp",
    planning_context: str = "",
) -> dict:
    """Convert an uploaded specification into a PRD JSON document."""
    spec = spec_text.strip()
    if not spec:
        raise ValueError("Spec text is empty")

    try:
        parsed = json.loads(spec)
        if isinstance(parsed, dict) and "stories" in parsed:
            return normalize_prd(parsed, seed_mode="new")
    except json.JSONDecodeError:
        pass

    prompt = SPEC_TO_PRD_PROMPT
    if planning_context.strip():
        prompt += f"\n\n[Planning Catalog]\n{planning_context.strip()}\n"
    prompt += f"\n[Specification]\n{spec}\n"
    response = _run_provider_prompt(prompt, provider, env, workdir)

    try:
        parsed = json.loads(_extract_json_blob(response))
    except json.JSONDecodeError as exc:
        raise ValueError(response.strip() or "Provider did not return valid JSON") from exc

    if not isinstance(parsed, dict) or "stories" not in parsed:
        raise ValueError("Provider response did not contain a valid PRD")

    return _refine_prd_if_needed(
        parsed,
        source_text=spec,
        provider=provider,
        env=env,
        workdir=workdir,
        planning_context=planning_context,
    )


def save_prd(prd: dict, project_path: Path) -> Path:
    """Save a generated PRD into the project's tasks directory."""
    tasks_dir = project_path / ".agents" / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    slug = prd.get("title", "project").lower().replace(" ", "-")[:30]
    prd_path = tasks_dir / f"prd-{slug}.json"
    prd_path.write_text(json.dumps(prd, indent=2, ensure_ascii=False))
    return prd_path
