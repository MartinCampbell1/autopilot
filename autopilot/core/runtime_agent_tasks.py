"""File-backed async runtime-agent tasks for honest background lifecycle tracking."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from autopilot.core.config import AutopilotConfig
from autopilot.core.project_store import emit_project_event, ensure_project_state, get_project_entry
from autopilot.core.task_output import load_text_from_source, persist_task_output
from autopilot.core.task_transcript import persist_task_transcript

SUPPORTED_RUNTIME_AGENT_TASK_STATUSES = {
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
}
TERMINAL_RUNTIME_AGENT_TASK_STATUSES = {"completed", "failed", "cancelled"}
TASK_HISTORY_LIMIT = 100


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    temp_path.replace(path)


def _parse_iso(value: str | None) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _default_placeholder_result(command: str) -> str:
    normalized = str(command or "").strip().lower()
    if normalized in {"launch", "resume"}:
        return "Background run launched. Do not report completion until this task reaches a terminal status."
    return "Background work launched. Do not report completion until this task reaches a terminal status."


class RuntimeAgentTaskRecord(BaseModel):
    """Stable persisted background task for one runtime-agent-triggered async action."""

    id: str
    project_id: str
    orchestrator_session_id: str = ""
    agent_action_run_id: str = ""
    approval_id: str = ""
    issue_id: str = ""
    command: str = ""
    actor: str = ""
    reason: str = ""
    title: str = ""
    status: str = "queued"
    runtime_agent_id: str = ""
    runtime_agent_ids: list[str] = Field(default_factory=list)
    placeholder_result: str = ""
    result_summary: str = ""
    result_payload: dict[str, Any] = Field(default_factory=dict)
    output_path: str = ""
    output_artifact_id: str = ""
    output_preview: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None


def runtime_agent_task_path(config: AutopilotConfig, task_id: str) -> Path:
    """Return the persisted path for one runtime-agent task."""

    return config.control_plane_state_dir / "runtime_agent_tasks" / f"{task_id}.json"


def get_runtime_agent_task(
    config: AutopilotConfig,
    task_id: str,
) -> RuntimeAgentTaskRecord | None:
    """Load one persisted runtime-agent task if it exists."""

    path = runtime_agent_task_path(config, task_id)
    if not path.exists():
        return None
    try:
        return RuntimeAgentTaskRecord.model_validate(json.loads(path.read_text()))
    except Exception:
        return None


def save_runtime_agent_task(
    config: AutopilotConfig,
    task: RuntimeAgentTaskRecord,
) -> RuntimeAgentTaskRecord:
    """Persist one runtime-agent task."""

    task.updated_at = _utcnow_iso()
    _atomic_write_json(runtime_agent_task_path(config, task.id), task.model_dump())
    _persist_runtime_agent_task_transcript(config, task)
    return task


def _append_task_history(
    task: RuntimeAgentTaskRecord,
    *,
    event: str,
    status: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> RuntimeAgentTaskRecord:
    entries = list(task.history or [])
    entry = {
        "timestamp": _utcnow_iso(),
        "event": str(event or "").strip(),
        "status": str(status or "").strip(),
        "message": str(message or "").strip(),
        "extra": dict(extra or {}),
    }
    last = entries[-1] if entries else None
    if last and all(
        last.get(key) == entry.get(key)
        for key in ("event", "status", "message")
    ) and dict(last.get("extra") or {}) == entry["extra"]:
        return task
    task.history = entries[-TASK_HISTORY_LIMIT + 1 :] + [entry]
    return task


def _render_runtime_agent_task_transcript(task: RuntimeAgentTaskRecord) -> str:
    lines = [
        "# Runtime Agent Task Transcript",
        "",
        f"Task ID: {task.id}",
        f"Project ID: {task.project_id}",
        f"Command: {task.command}",
        f"Status: {task.status}",
        f"Actor: {task.actor or '-'}",
        f"Reason: {task.reason or '-'}",
        f"Created At: {task.created_at}",
        f"Started At: {task.started_at or '-'}",
        f"Completed At: {task.completed_at or '-'}",
        f"Orchestrator Session: {task.orchestrator_session_id or '-'}",
        f"Agent Action Run: {task.agent_action_run_id or '-'}",
        f"Approval ID: {task.approval_id or '-'}",
        f"Issue ID: {task.issue_id or '-'}",
        f"Runtime Agents: {', '.join(task.runtime_agent_ids) or '-'}",
        f"Output Artifact ID: {task.output_artifact_id or '-'}",
        f"Output Path: {task.output_path or '-'}",
        "",
        "## Result",
        f"Summary: {task.result_summary or task.placeholder_result or '-'}",
    ]
    if task.result_payload:
        lines.extend(
            [
                "",
                "```json",
                json.dumps(task.result_payload, indent=2, ensure_ascii=False),
                "```",
            ]
        )
    lines.extend(["", "## Timeline"])
    if not task.history:
        lines.append("- No lifecycle events recorded yet.")
    else:
        for item in task.history:
            timestamp = str(item.get("timestamp") or "").strip() or "-"
            status = str(item.get("status") or "").strip() or "unknown"
            event = str(item.get("event") or "").strip() or "event"
            message = str(item.get("message") or "").strip() or "-"
            lines.append(f"- [{timestamp}] {status} {event}: {message}")
            extra = dict(item.get("extra") or {})
            if extra:
                lines.extend(
                    [
                        "  ```json",
                        json.dumps(extra, indent=2, ensure_ascii=False),
                        "  ```",
                    ]
                )
    return "\n".join(lines).rstrip() + "\n"


def _persist_runtime_agent_task_transcript(
    config: AutopilotConfig,
    task: RuntimeAgentTaskRecord,
) -> None:
    persist_task_transcript(
        config,
        owner_kind="runtime_agent_task",
        owner_id=task.id,
        content=_render_runtime_agent_task_transcript(task),
        metadata={
            "project_id": task.project_id,
            "command": task.command,
            "status": task.status,
            "orchestrator_session_id": task.orchestrator_session_id,
            "agent_action_run_id": task.agent_action_run_id,
            "output_artifact_id": task.output_artifact_id,
        },
    )


def list_runtime_agent_tasks(
    config: AutopilotConfig,
    *,
    task_id: str | None = None,
    project_id: str | None = None,
    orchestrator_session_id: str | None = None,
    runtime_agent_id: str | None = None,
    status: str | None = None,
    command: str | None = None,
    agent_action_run_id: str | None = None,
) -> list[RuntimeAgentTaskRecord]:
    """List persisted runtime-agent tasks with lightweight filtering."""

    directory = config.control_plane_state_dir / "runtime_agent_tasks"
    if not directory.exists():
        return []

    records: list[RuntimeAgentTaskRecord] = []
    for path in sorted(directory.glob("*.json")):
        try:
            record = RuntimeAgentTaskRecord.model_validate(json.loads(path.read_text()))
        except Exception:
            continue
        if task_id and record.id != task_id:
            continue
        if project_id and record.project_id != project_id:
            continue
        if orchestrator_session_id and record.orchestrator_session_id != orchestrator_session_id:
            continue
        if runtime_agent_id and runtime_agent_id != record.runtime_agent_id and runtime_agent_id not in record.runtime_agent_ids:
            continue
        if status and record.status != status:
            continue
        if command and record.command != command:
            continue
        if agent_action_run_id and record.agent_action_run_id != agent_action_run_id:
            continue
        records.append(record)

    records.sort(key=lambda item: (item.created_at, item.id), reverse=True)
    return records


def _matching_active_task(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | None = None,
) -> RuntimeAgentTaskRecord | None:
    desired_runtime_agent_ids = {
        str(item).strip()
        for item in (runtime_agent_ids or [])
        if str(item).strip()
    }
    for record in list_runtime_agent_tasks(
        config,
        project_id=project_id,
        orchestrator_session_id=orchestrator_session_id or None,
        command=command,
    ):
        if record.status not in {"queued", "running"}:
            continue
        if desired_runtime_agent_ids and not desired_runtime_agent_ids.intersection(set(record.runtime_agent_ids or [])):
            continue
        return record
    return None


def _emit_runtime_agent_task_event(
    config: AutopilotConfig,
    task: RuntimeAgentTaskRecord,
    *,
    event: str,
    status: str,
    message: str,
) -> None:
    extra = {
        "runtime_agent_task_id": task.id,
        "orchestrator_session_id": task.orchestrator_session_id,
        "agent_action_run_id": task.agent_action_run_id,
        "approval_id": task.approval_id,
        "issue_id": task.issue_id,
        "command": task.command,
        "runtime_agent_id": task.runtime_agent_id,
        "runtime_agent_ids": list(task.runtime_agent_ids),
        "output_artifact_id": task.output_artifact_id,
    }
    emit_project_event(
        config,
        task.project_id,
        event=event,
        status=status,
        message=message,
        extra=extra,
    )


def create_or_reuse_runtime_agent_task(
    config: AutopilotConfig,
    *,
    project_id: str,
    command: str,
    actor: str = "",
    reason: str = "",
    orchestrator_session_id: str = "",
    runtime_agent_ids: list[str] | None = None,
    output_path: str = "",
    metadata: dict[str, Any] | None = None,
    approval_id: str = "",
    issue_id: str = "",
) -> RuntimeAgentTaskRecord:
    """Create or reuse one running runtime-agent task for background work."""

    normalized_project_id = str(project_id or "").strip()
    normalized_command = str(command or "").strip()
    normalized_session_id = str(orchestrator_session_id or "").strip()
    normalized_runtime_agent_ids = sorted(
        {
            str(item).strip()
            for item in (runtime_agent_ids or [])
            if str(item).strip()
        }
    )
    existing = _matching_active_task(
        config,
        project_id=normalized_project_id,
        command=normalized_command,
        orchestrator_session_id=normalized_session_id,
        runtime_agent_ids=normalized_runtime_agent_ids,
    )
    if existing is not None:
        changed = False
        if output_path and existing.output_path != output_path:
            existing.output_path = output_path
            changed = True
        if reason and existing.reason != reason:
            existing.reason = reason
            changed = True
        if actor and existing.actor != actor:
            existing.actor = actor
            changed = True
        if approval_id and existing.approval_id != approval_id:
            existing.approval_id = approval_id
            changed = True
        if issue_id and existing.issue_id != issue_id:
            existing.issue_id = issue_id
            changed = True
        if normalized_runtime_agent_ids and sorted(existing.runtime_agent_ids) != normalized_runtime_agent_ids:
            existing.runtime_agent_ids = normalized_runtime_agent_ids
            existing.runtime_agent_id = normalized_runtime_agent_ids[0]
            changed = True
        if metadata:
            next_metadata = dict(existing.metadata or {})
            for key, value in dict(metadata).items():
                if key not in next_metadata or next_metadata[key] != value:
                    next_metadata[key] = value
                    changed = True
            existing.metadata = next_metadata
        if changed:
            _append_task_history(
                existing,
                event="task_context_updated",
                status=existing.status,
                message="Task metadata was refreshed while background work was still in progress.",
            )
            return save_runtime_agent_task(config, existing)
        return existing

    created_at = _utcnow_iso()
    task = RuntimeAgentTaskRecord(
        id=f"rat_{uuid.uuid4().hex[:10]}",
        project_id=normalized_project_id,
        orchestrator_session_id=normalized_session_id,
        approval_id=str(approval_id or "").strip(),
        issue_id=str(issue_id or "").strip(),
        command=normalized_command,
        actor=str(actor or "").strip(),
        reason=str(reason or "").strip(),
        title=f"Background `{normalized_command}` task".strip(),
        status="running",
        runtime_agent_id=normalized_runtime_agent_ids[0] if normalized_runtime_agent_ids else "",
        runtime_agent_ids=normalized_runtime_agent_ids,
        placeholder_result=_default_placeholder_result(normalized_command),
        output_path=str(output_path or "").strip(),
        metadata=dict(metadata or {}),
        created_at=created_at,
        updated_at=created_at,
        started_at=created_at,
    )
    _append_task_history(
        task,
        event="task_started",
        status="running",
        message=f"Background task `{task.id}` started for `{task.command}`.",
        extra={"runtime_agent_ids": list(task.runtime_agent_ids)},
    )
    save_runtime_agent_task(config, task)
    _emit_runtime_agent_task_event(
        config,
        task,
        event="execution_plane_runtime_agent_task_started",
        status="running",
        message=f"Background task `{task.id}` started for `{task.command}`.",
    )
    return task


def link_runtime_agent_task_run(
    config: AutopilotConfig,
    task_id: str,
    *,
    agent_action_run_id: str,
) -> RuntimeAgentTaskRecord:
    """Attach one persisted agent-action run id to a runtime-agent task."""

    task = get_runtime_agent_task(config, task_id)
    if task is None:
        raise KeyError(task_id)
    normalized_run_id = str(agent_action_run_id or "").strip()
    if normalized_run_id and task.agent_action_run_id != normalized_run_id:
        task.agent_action_run_id = normalized_run_id
        _append_task_history(
            task,
            event="linked_agent_action_run",
            status=task.status,
            message=f"Linked runtime-agent task to action run `{normalized_run_id}`.",
            extra={"agent_action_run_id": normalized_run_id},
        )
        return save_runtime_agent_task(config, task)
    return task


def _state_is_newer_than_task(state: dict[str, Any], task: RuntimeAgentTaskRecord) -> bool:
    task_time = _parse_iso(task.started_at) or _parse_iso(task.created_at)
    if task_time is None:
        return False
    for key in ("finished_at", "updated_at", "started_at"):
        candidate = _parse_iso(state.get(key))
        if candidate is not None and candidate >= task_time:
            return True
    return False


def _terminal_task_update(
    config: AutopilotConfig,
    task: RuntimeAgentTaskRecord,
    *,
    status: str,
    summary: str,
    project_state: dict[str, Any],
) -> RuntimeAgentTaskRecord:
    output_source_path = str(project_state.get("log_path") or task.output_path or "").strip()
    source_output = load_text_from_source(output_source_path)
    fallback_output = "\n".join(
        [
            f"Task: {task.id}",
            f"Command: {task.command}",
            f"Status: {status}",
            f"Summary: {summary}",
            f"Project status: {str(project_state.get('status') or '')}",
            f"Finished at: {str(project_state.get('finished_at') or '')}",
            f"Last error: {str(project_state.get('last_error') or '')}",
            f"Log path: {output_source_path}",
        ]
    ).strip()
    output_record = persist_task_output(
        config,
        owner_kind="runtime_agent_task",
        owner_id=task.id,
        content=source_output or fallback_output,
        source_path=output_source_path,
        metadata={
            "project_id": task.project_id,
            "orchestrator_session_id": task.orchestrator_session_id,
            "agent_action_run_id": task.agent_action_run_id,
            "command": task.command,
            "status": status,
        },
    )

    task.status = status
    task.placeholder_result = ""
    task.result_summary = summary
    task.result_payload = {
        "project_status": str(project_state.get("status") or ""),
        "paused": bool(project_state.get("paused")),
        "finished_at": project_state.get("finished_at"),
        "last_error": project_state.get("last_error"),
        "log_path": project_state.get("log_path"),
        "output_artifact_id": output_record.id,
        "output_source_path": output_source_path,
    }
    task.output_artifact_id = output_record.id
    task.output_preview = output_record.preview
    task.completed_at = str(project_state.get("finished_at") or "").strip() or _utcnow_iso()
    _append_task_history(
        task,
        event=f"task_{status}",
        status=status,
        message=summary,
        extra={
            "output_artifact_id": output_record.id,
            "output_source_path": output_source_path,
            "project_status": str(project_state.get("status") or ""),
        },
    )
    return task


def refresh_runtime_agent_task(
    config: AutopilotConfig,
    task_or_id: RuntimeAgentTaskRecord | str,
) -> RuntimeAgentTaskRecord:
    """Sync one running task against the current project runtime state."""

    task = (
        task_or_id
        if isinstance(task_or_id, RuntimeAgentTaskRecord)
        else get_runtime_agent_task(config, str(task_or_id))
    )
    if task is None:
        raise KeyError(str(task_or_id))
    if task.status in TERMINAL_RUNTIME_AGENT_TASK_STATUSES:
        return task

    project = get_project_entry(config, project_id=task.project_id, include_archived=True)
    if project is None:
        return task

    project_state = ensure_project_state(config, project, seed_mode="migrate")
    changed = False
    output_path = str(project_state.get("log_path") or "").strip()
    if output_path and output_path != task.output_path:
        task.output_path = output_path
        changed = True

    if project_state.get("status") == "running" and not bool(project_state.get("paused")):
        if task.status != "running":
            task.status = "running"
            changed = True
        if task.started_at is None:
            task.started_at = str(project_state.get("started_at") or "").strip() or _utcnow_iso()
            changed = True
        if changed:
            return save_runtime_agent_task(config, task)
        return task

    if not _state_is_newer_than_task(project_state, task):
        if changed:
            return save_runtime_agent_task(config, task)
        return task

    transition: tuple[str, str, str] | None = None
    if bool(project_state.get("paused")) or project_state.get("status") == "paused":
        transition = (
            "cancelled",
            "cancelled",
            "Background run was paused before completion.",
        )
    elif project_state.get("status") == "completed":
        transition = (
            "completed",
            "ok",
            "Background run completed.",
        )
    elif project_state.get("status") == "failed":
        transition = (
            "failed",
            "error",
            str(project_state.get("last_error") or "Background run failed."),
        )

    if transition is None:
        if changed:
            return save_runtime_agent_task(config, task)
        return task

    next_status, event_status, summary = transition
    prior_status = task.status
    task = _terminal_task_update(
        config,
        task,
        status=next_status,
        summary=summary,
        project_state=project_state,
    )
    save_runtime_agent_task(config, task)
    if prior_status != next_status:
        _emit_runtime_agent_task_event(
            config,
            task,
            event=f"execution_plane_runtime_agent_task_{next_status}",
            status=event_status,
            message=summary,
        )
    return task
