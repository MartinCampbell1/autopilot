"""Shared runtime-agent helpers for execution-plane and issue enrichment."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RuntimeAgentSnapshot(BaseModel):
    """Stable runtime agent snapshot derived from story/runtime state."""

    agent_id: str
    role: str
    label: str
    provider: str | None = None
    profile_name: str | None = None
    member_id: str | None = None
    role_id: str | None = None
    specialist: bool = False
    status: str = "planned"
    story_id: int | None = None
    story_title: str | None = None
    story_status: str = "open"
    ownership: dict[str, Any] | None = None
    checkout: dict[str, Any] | None = None
    skill_packs: list[str] = Field(default_factory=list)
    planned_connectors: list[str] = Field(default_factory=list)
    active_connectors: list[dict[str, Any]] = Field(default_factory=list)


class RuntimeAgentRef(BaseModel):
    """Parsed stable runtime-agent identifier."""

    project_id: str
    story_id: int
    role: str
    token: str


def normalize_runtime_agent_role(execution_role: str) -> str:
    """Normalize provider/runtime role labels into stable control-plane roles."""

    normalized = str(execution_role or "").strip().lower()
    if normalized in {"primary_worker", "worker"}:
        return "worker"
    return normalized or "worker"


def parse_runtime_agent_identity(
    label: str | None,
    fallback_provider: str | None = None,
) -> tuple[str | None, str | None]:
    """Split `<provider>/<profile>` labels when available."""

    if label and "/" in label:
        provider, profile_name = label.split("/", 1)
        return provider or fallback_provider, profile_name or None
    return fallback_provider, None


def runtime_agent_id(
    project_id: str,
    story_id: int,
    role: str,
    *,
    member_id: str | None = None,
    role_id: str | None = None,
    runtime_label: str | None = None,
) -> str:
    """Build the stable runtime-agent identifier."""

    normalized_role = normalize_runtime_agent_role(role)
    token = str(member_id or role_id or runtime_label or "agent").strip() or "agent"
    return f"{project_id}:{story_id}:{normalized_role}:{token}"


def parse_runtime_agent_id(value: str) -> RuntimeAgentRef | None:
    """Parse a stable runtime-agent identifier into its parts."""

    raw = str(value or "").strip()
    if not raw:
        return None
    parts = raw.split(":", 3)
    if len(parts) != 4:
        return None
    project_id, story_id_raw, role, token = parts
    try:
        story_id = int(story_id_raw)
    except ValueError:
        return None
    if not project_id or not role or not token:
        return None
    return RuntimeAgentRef(
        project_id=project_id,
        story_id=story_id,
        role=normalize_runtime_agent_role(role),
        token=token,
    )


def runtime_agent_status(story_status: str, *, runtime_label: str | None) -> str:
    """Map story/runtime state into a stable per-agent status."""

    if story_status == "in_progress":
        return "active" if runtime_label else "planned"
    if story_status == "merge_blocked":
        return "blocked"
    if story_status == "stuck":
        return "stuck"
    if story_status in {"done", "skipped"}:
        return story_status
    return "planned"


def resolve_story_runtime_agent_id(
    project_id: str,
    story_id: int,
    *,
    role: str,
    team_members: list[dict[str, Any]] | None = None,
    runtime_label: str | None = None,
) -> str | None:
    """Resolve the stable runtime agent id for one story/role pair."""

    normalized_role = normalize_runtime_agent_role(role)
    for member in team_members or []:
        member_role = normalize_runtime_agent_role(
            str(member.get("execution_role") or member.get("role_id") or normalized_role)
        )
        if member_role != normalized_role:
            continue
        return runtime_agent_id(
            project_id,
            story_id,
            normalized_role,
            member_id=str(member.get("member_id") or "") or None,
            role_id=str(member.get("role_id") or "") or None,
            runtime_label=runtime_label,
        )

    if runtime_label:
        return runtime_agent_id(
            project_id,
            story_id,
            normalized_role,
            runtime_label=runtime_label,
        )
    return None


def build_runtime_agents(
    project_id: str,
    stories: list[dict[str, Any]],
    *,
    leases_by_story: dict[int, Any] | None = None,
) -> list[dict[str, Any]]:
    """Build runtime-agent snapshots from merged story/runtime data."""

    leases_by_story = leases_by_story or {}
    agents: list[dict[str, Any]] = []

    for story in stories:
        story_id = int(story["id"])
        story_status = str(story.get("status") or "open")
        lease = leases_by_story.get(story_id)
        ownership = story.get("ownership")
        checkout = story.get("checkout")
        if lease is not None:
            ownership = ownership or {
                "role": lease.role,
                "owner": lease.owner,
                "acquired_at": lease.acquired_at,
                "updated_at": lease.updated_at,
                "runtime_pid": lease.runtime_pid,
                "status": lease.status,
            }
            checkout = checkout or {
                "mode": "worktree" if lease.branch_name else "shared_main",
                "path": lease.checkout_path or lease.project_path,
                "branch_name": lease.branch_name,
            }

        team_members = story.get("team_members") or []
        for member in team_members:
            role = normalize_runtime_agent_role(
                str(member.get("execution_role") or member.get("role_id") or "worker")
            )
            runtime_label = (
                story.get("agent")
                if role == "worker"
                else story.get("critic")
                if role == "critic"
                else None
            )
            provider, profile_name = parse_runtime_agent_identity(
                runtime_label,
                str(member.get("provider") or "") or None,
            )
            agents.append(
                RuntimeAgentSnapshot(
                    agent_id=runtime_agent_id(
                        project_id,
                        story_id,
                        role,
                        member_id=str(member.get("member_id") or "") or None,
                        role_id=str(member.get("role_id") or "") or None,
                        runtime_label=runtime_label,
                    ),
                    role=role,
                    label=str(runtime_label or member.get("label") or role.title()),
                    provider=provider,
                    profile_name=profile_name,
                    member_id=str(member.get("member_id") or "") or None,
                    role_id=str(member.get("role_id") or "") or None,
                    specialist=bool(member.get("specialist", False)),
                    status=runtime_agent_status(story_status, runtime_label=runtime_label),
                    story_id=story_id,
                    story_title=str(story.get("title") or ""),
                    story_status=story_status,
                    ownership=ownership if role in {"worker", "specialist"} else None,
                    checkout=checkout if role in {"worker", "specialist"} else None,
                    skill_packs=list(member.get("skill_packs") or []),
                    planned_connectors=list(member.get("planned_connectors") or []),
                    active_connectors=list(member.get("active_connectors") or []),
                ).model_dump()
            )

        if not team_members:
            for role, runtime_label in (("worker", story.get("agent")), ("critic", story.get("critic"))):
                if not runtime_label:
                    continue
                provider, profile_name = parse_runtime_agent_identity(str(runtime_label))
                agents.append(
                    RuntimeAgentSnapshot(
                        agent_id=runtime_agent_id(
                            project_id,
                            story_id,
                            role,
                            runtime_label=str(runtime_label),
                        ),
                        role=role,
                        label=str(runtime_label),
                        provider=provider,
                        profile_name=profile_name,
                        status=runtime_agent_status(story_status, runtime_label=str(runtime_label)),
                        story_id=story_id,
                        story_title=str(story.get("title") or ""),
                        story_status=story_status,
                        ownership=ownership if role == "worker" else None,
                        checkout=checkout if role == "worker" else None,
                    ).model_dump()
                )

    agents.sort(
        key=lambda item: (
            item["status"] != "active",
            item["story_status"] not in {"in_progress", "merge_blocked", "stuck"},
            item["story_id"] or 0,
            item["role"],
            item["label"].lower(),
        )
    )
    return agents
