"""GitHub PR sync and reaction ingestion for story-scoped control-plane state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from autopilot.core.config import AutopilotConfig
from autopilot.core.control_plane_issues import GITHUB_ISSUE_CATEGORIES_BY_EVENT
from autopilot.core.github_prs import normalize_story_github_pr
from autopilot.core.orchestrator_sessions import get_orchestrator_session, link_orchestrator_session_entities
from autopilot.core.project_store import (
    emit_project_event,
    ensure_project_state,
    get_project_entry,
    load_project_prd,
    load_project_state,
    resume_project_run,
    update_story_runtime,
)
from autopilot.core.runtime_agents import resolve_story_runtime_agent_id

SUPPORTED_GITHUB_REACTION_TYPES = {
    "ci_failed",
    "review_comment_received",
    "changes_requested",
    "approved_and_green",
}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_project_and_story(
    config: AutopilotConfig,
    project_id: str,
    story_id: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    project = get_project_entry(config, project_id=project_id, include_archived=True)
    if project is None:
        raise KeyError(project_id)
    state = ensure_project_state(config, project, seed_mode="migrate")
    story = next(
        (item for item in load_project_prd(project, seed_mode="migrate").get("stories", []) if int(item["id"]) == int(story_id)),
        None,
    )
    if story is None:
        raise KeyError(story_id)
    runtime_story = (state.get("story_state") or {}).get(str(story_id))
    if runtime_story is None:
        raise KeyError(story_id)
    return project, story, runtime_story


def _resolve_runtime_agent_id(
    project_id: str,
    story_id: int,
    story: dict[str, Any],
    runtime_story: dict[str, Any],
    explicit_runtime_agent_id: str = "",
) -> str:
    if explicit_runtime_agent_id.strip():
        return explicit_runtime_agent_id.strip()
    return (
        resolve_story_runtime_agent_id(
            project_id,
            story_id,
            role="worker",
            team_members=runtime_story.get("team_members") or [],
            runtime_label=str(runtime_story.get("agent") or "").strip() or None,
        )
        or ""
    )


def _github_event_extra(
    github_pr: dict[str, Any],
    *,
    reaction_type: str = "",
    actor: str,
    orchestrator_session_id: str,
    agent_action_run_id: str,
    runtime_agent_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extra = {
        "github_pr": github_pr,
        "github_pr_number": github_pr.get("number"),
        "github_pr_url": github_pr.get("url"),
        "github_pr_state": github_pr.get("state"),
        "github_pr_head_branch": github_pr.get("head_branch"),
        "github_pr_base_branch": github_pr.get("base_branch"),
        "github_ci_status": github_pr.get("ci_status"),
        "github_review_status": github_pr.get("review_status"),
        "github_handoff_status": github_pr.get("handoff_status"),
        "github_merge_state": github_pr.get("merge_state"),
        "github_reaction_type": reaction_type,
        "actor": actor,
    }
    if orchestrator_session_id.strip():
        extra["orchestrator_session_id"] = orchestrator_session_id.strip()
    if agent_action_run_id.strip():
        extra["agent_action_run_id"] = agent_action_run_id.strip()
        extra["run_id"] = agent_action_run_id.strip()
    if runtime_agent_id.strip():
        extra["runtime_agent_id"] = runtime_agent_id.strip()
        extra["runtime_agent_ids"] = [runtime_agent_id.strip()]
    if details:
        extra.update(details)
    return extra


def _link_session_entities(
    config: AutopilotConfig,
    session_id: str,
    *,
    project_id: str,
    runtime_agent_id: str = "",
    issue_ids: list[str] | None = None,
    approval_ids: list[str] | None = None,
) -> None:
    normalized_session_id = session_id.strip()
    if not normalized_session_id:
        return
    if get_orchestrator_session(config, normalized_session_id) is None:
        raise KeyError(normalized_session_id)
    link_orchestrator_session_entities(
        config,
        normalized_session_id,
        project_ids=[project_id],
        linked_issue_ids=list(issue_ids or []),
        linked_approval_ids=list(approval_ids or []),
        linked_runtime_agent_ids=[runtime_agent_id] if runtime_agent_id else [],
    )


def sync_story_github_pr(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    payload: dict[str, Any],
    actor: str = "github",
    orchestrator_session_id: str = "",
    agent_action_run_id: str = "",
    runtime_agent_id: str = "",
    emit_event_record: bool = True,
) -> dict[str, Any]:
    """Persist story-scoped GitHub PR metadata and optionally emit a sync event."""

    project, story, runtime_story = _load_project_and_story(config, project_id, story_id)
    github_pr = normalize_story_github_pr(
        project["name"],
        story,
        existing=runtime_story.get("github_pr") or {},
        incoming={**payload, "updated_at": payload.get("updated_at") or _utcnow_iso()},
    )
    update_story_runtime(config, project_id, story_id, github_pr=github_pr)

    resolved_runtime_agent_id = _resolve_runtime_agent_id(
        project_id,
        story_id,
        story,
        runtime_story,
        explicit_runtime_agent_id=runtime_agent_id,
    )
    if emit_event_record:
        event_name = "github_pr_merged" if github_pr.get("state") == "merged" else "github_pr_synced"
        pr_number = github_pr.get("number")
        message_target = f"PR #{pr_number}" if pr_number else github_pr.get("head_branch") or f"story {story_id}"
        emit_project_event(
            config,
            project_id,
            event=event_name,
            status="ok" if github_pr.get("merge_state") != "blocked" else "warning",
            message=f"GitHub {message_target} synced for story {story_id}.",
            story_id=story_id,
            extra=_github_event_extra(
                github_pr,
                actor=actor,
                orchestrator_session_id=orchestrator_session_id,
                agent_action_run_id=agent_action_run_id,
                runtime_agent_id=resolved_runtime_agent_id,
            ),
        )
    _link_session_entities(
        config,
        orchestrator_session_id,
        project_id=project_id,
        runtime_agent_id=resolved_runtime_agent_id,
    )
    return github_pr


def _reaction_payload(reaction_type: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    details = dict(details or {})
    payload: dict[str, Any] = {
        "latest_event": reaction_type,
        "updated_at": _utcnow_iso(),
    }
    payload.update({key: value for key, value in details.items() if key in {
        "number",
        "url",
        "title",
        "state",
        "base_branch",
        "head_branch",
        "draft",
        "author",
        "labels",
        "comment_count",
        "review_comment_count",
        "last_commit_sha",
        "checks_url",
        "opened_at",
        "merged_at",
        "closed_at",
    }})
    if reaction_type == "ci_failed":
        payload.update({"ci_status": "red", "merge_state": "blocked"})
    elif reaction_type == "review_comment_received":
        payload.update({"review_status": "commented"})
    elif reaction_type == "changes_requested":
        payload.update(
            {
                "review_status": "changes_requested",
                "handoff_status": "changes_requested",
                "merge_state": "blocked",
            }
        )
    elif reaction_type == "approved_and_green":
        payload.update(
            {
                "ci_status": "green",
                "review_status": "approved",
                "handoff_status": "approved_and_green",
                "merge_state": "ready",
            }
        )
    return payload


def _reaction_message(reaction_type: str, github_pr: dict[str, Any], summary: str) -> tuple[str, str]:
    pr_number = github_pr.get("number")
    target = f"PR #{pr_number}" if pr_number else github_pr.get("head_branch") or "story handoff"
    if summary.strip():
        message = summary.strip()
    elif reaction_type == "ci_failed":
        message = f"GitHub CI failed for {target}."
    elif reaction_type == "review_comment_received":
        message = f"GitHub review comment received for {target}."
    elif reaction_type == "changes_requested":
        message = f"GitHub review requested changes for {target}."
    else:
        message = f"GitHub {target} is approved and green."
    status = "error" if reaction_type == "ci_failed" else "warning" if reaction_type in {"review_comment_received", "changes_requested"} else "ok"
    return message, status


def _matching_story_issue_ids(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    reaction_type: str,
) -> list[str]:
    from autopilot.core.control_plane_issues import list_issues

    categories = GITHUB_ISSUE_CATEGORIES_BY_EVENT.get(reaction_type) or []
    if not categories:
        return []
    return [
        issue.id
        for issue in list_issues(config, project_id=project_id)
        if issue.story_id == story_id and issue.category in categories
    ]


def ingest_story_github_reaction(
    config: AutopilotConfig,
    *,
    project_id: str,
    story_id: int,
    reaction_type: str,
    summary: str = "",
    actor: str = "github",
    details: dict[str, Any] | None = None,
    orchestrator_session_id: str = "",
    agent_action_run_id: str = "",
    runtime_agent_id: str = "",
) -> dict[str, Any]:
    """Ingest one GitHub CI/review reaction back into the control plane."""

    normalized_reaction = str(reaction_type or "").strip().lower()
    if normalized_reaction not in SUPPORTED_GITHUB_REACTION_TYPES:
        raise ValueError(
            f"Unsupported GitHub reaction type `{reaction_type}`. "
            f"Expected one of {sorted(SUPPORTED_GITHUB_REACTION_TYPES)}."
        )

    project, story, runtime_story = _load_project_and_story(config, project_id, story_id)
    resolved_runtime_agent_id = _resolve_runtime_agent_id(
        project_id,
        story_id,
        story,
        runtime_story,
        explicit_runtime_agent_id=runtime_agent_id,
    )
    github_pr = normalize_story_github_pr(
        project["name"],
        story,
        existing=runtime_story.get("github_pr") or {},
        incoming=_reaction_payload(normalized_reaction, details),
    )
    update_story_runtime(config, project_id, story_id, github_pr=github_pr)

    message, status = _reaction_message(normalized_reaction, github_pr, summary)
    emit_project_event(
        config,
        project_id,
        event=f"github_{normalized_reaction}",
        status=status,
        message=message,
        story_id=story_id,
        extra=_github_event_extra(
            github_pr,
            reaction_type=normalized_reaction,
            actor=actor,
            orchestrator_session_id=orchestrator_session_id,
            agent_action_run_id=agent_action_run_id,
            runtime_agent_id=resolved_runtime_agent_id,
            details=dict(details or {}),
        ),
    )

    approval: dict[str, Any] | None = None
    issue: dict[str, Any] | None = None
    auto_resumed = False

    state = load_project_state(config, project_id)
    if normalized_reaction == "approved_and_green" and bool(state.get("paused", False)):
        from autopilot.core.execution_plane import (
            create_execution_command_approval,
            create_execution_command_issue,
            load_project_command_policy,
        )

        policy = load_project_command_policy(config, project_id)
        if bool(policy.get("github_approved_and_green_auto_resume", False)):
            resumed, _, message_text = resume_project_run(config, project_id)
            auto_resumed = bool(resumed)
            emit_project_event(
                config,
                project_id,
                event="github_auto_resumed",
                status="ok" if resumed else "warning",
                message=message_text,
                story_id=story_id,
                extra=_github_event_extra(
                    github_pr,
                    reaction_type=normalized_reaction,
                    actor=actor,
                    orchestrator_session_id=orchestrator_session_id,
                    agent_action_run_id=agent_action_run_id,
                    runtime_agent_id=resolved_runtime_agent_id,
                ),
            )
        else:
            policy_reason = "GitHub approved-and-green auto-resume is disabled by project policy."
            issue = create_execution_command_issue(
                config,
                project_id=project_id,
                command="resume",
                requested_by=actor,
                reason="GitHub PR is approved and green, but project resume still requires operator approval.",
                policy_reasons=[policy_reason],
                runtime_agent_ids=[resolved_runtime_agent_id] if resolved_runtime_agent_id else [],
            )
            approval = create_execution_command_approval(
                config,
                project_id=project_id,
                command="resume",
                requested_by=actor,
                reason="GitHub PR is approved and green.",
                issue_id=str(issue["id"]),
                runtime_agent_ids=[resolved_runtime_agent_id] if resolved_runtime_agent_id else [],
                policy_reasons=[policy_reason],
            )
            issue["approval_id"] = approval["id"]
            emit_project_event(
                config,
                project_id,
                event="github_auto_resume_approval_requested",
                status="pending_approval",
                message="GitHub approved-and-green resume was escalated for approval.",
                story_id=story_id,
                extra={
                    **_github_event_extra(
                        github_pr,
                        reaction_type=normalized_reaction,
                        actor=actor,
                        orchestrator_session_id=orchestrator_session_id,
                        agent_action_run_id=agent_action_run_id,
                        runtime_agent_id=resolved_runtime_agent_id,
                    ),
                    "issue_id": issue["id"],
                    "approval_id": approval["id"],
                },
            )

    linked_issue_ids = _matching_story_issue_ids(
        config,
        project_id=project_id,
        story_id=story_id,
        reaction_type=f"github_{normalized_reaction}",
    )
    if issue is not None:
        linked_issue_ids.append(str(issue["id"]))
    linked_approval_ids = [str(approval["id"])] if approval is not None else []
    _link_session_entities(
        config,
        orchestrator_session_id,
        project_id=project_id,
        runtime_agent_id=resolved_runtime_agent_id,
        issue_ids=sorted(set(linked_issue_ids)),
        approval_ids=linked_approval_ids,
    )

    return {
        "status": "ok",
        "project_id": project_id,
        "story_id": story_id,
        "reaction_type": normalized_reaction,
        "github_pr": github_pr,
        "auto_resumed": auto_resumed,
        "issue": issue,
        "approval": approval,
    }
