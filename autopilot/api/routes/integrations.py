"""Integration-trigger routes for inbound tracker events."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autopilot.api.deps import get_config
from autopilot.core.plugins import resolve_tracker_plugins
from autopilot.core.project_bootstrap import create_project_from_prd
from autopilot.core.project_store import (
    attach_tracker_reference,
    build_project_detail,
    emit_project_event,
    find_project_by_tracker_reference,
    get_project_entry,
    normalize_tracker_reference,
)

router = APIRouter()


class GitHubRepositoryRequest(BaseModel):
    id: int | None = None
    name: str = ""
    full_name: str = ""
    html_url: str = ""
    url: str = ""


class GitHubLabelRequest(BaseModel):
    name: str = ""


class GitHubIssueRequest(BaseModel):
    id: int | None = None
    number: int
    title: str
    body: str = ""
    html_url: str = ""
    state: str = "open"
    labels: list[GitHubLabelRequest] = Field(default_factory=list)


class GitHubIssueTriggerRequest(BaseModel):
    action: str = "opened"
    repository: GitHubRepositoryRequest
    issue: GitHubIssueRequest
    project_id: str | None = None
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False


class TrackerRepositoryRequest(BaseModel):
    id: int | None = None
    name: str = ""
    full_name: str = ""
    url: str = ""


class TrackerItemRequest(BaseModel):
    external_id: str
    title: str
    body: str = ""
    url: str = ""
    state: str = "open"
    labels: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrackerItemTriggerRequest(BaseModel):
    tracker_id: str
    action: str = "opened"
    item_kind: str = "item"
    repository: TrackerRepositoryRequest = Field(default_factory=TrackerRepositoryRequest)
    item: TrackerItemRequest
    project_id: str | None = None
    project_name: str | None = None
    project_path: str | None = None
    priority: str = "normal"
    launch: bool = False


def _acceptance_criteria_from_markdown(body: str) -> list[str]:
    criteria: list[str] = []
    for line in str(body or "").splitlines():
        match = re.match(r"^\s*[-*]\s*\[[ xX]\]\s*(.+?)\s*$", line)
        if match:
            criteria.append(match.group(1).strip())
    return criteria


def _github_issue_prd(request: GitHubIssueTriggerRequest) -> dict[str, Any]:
    repo_name = request.repository.full_name or request.repository.name or "GitHub Issue"
    labels = [label.name for label in request.issue.labels if label.name]
    body = request.issue.body.strip()
    return {
        "title": request.project_name or f"{repo_name} #{request.issue.number}",
        "description": body or request.issue.title,
        "stories": [
            {
                "id": 1,
                "title": request.issue.title,
                "description": body or request.issue.title,
                "acceptance_criteria": _acceptance_criteria_from_markdown(body),
                "tags": labels,
            }
        ],
    }


def _tracker_item_prd(request: TrackerItemTriggerRequest, tracker_display_name: str) -> dict[str, Any]:
    repo_name = request.repository.full_name or request.repository.name or tracker_display_name
    body = request.item.body.strip()
    acceptance = [item for item in request.item.acceptance_criteria if item] or _acceptance_criteria_from_markdown(body)
    return {
        "title": request.project_name or f"{repo_name} #{request.item.external_id}",
        "description": body or request.item.title,
        "stories": [
            {
                "id": 1,
                "title": request.item.title,
                "description": body or request.item.title,
                "acceptance_criteria": acceptance,
                "tags": [label for label in request.item.labels if label],
            }
        ],
    }


def _github_issue_task_source(request: GitHubIssueTriggerRequest) -> dict[str, str]:
    return {
        "source_kind": "github_issue",
        "external_id": str(request.issue.id or request.issue.number),
        "repo": request.repository.full_name or request.repository.name or "",
        "branch_policy": "isolated_worktree",
        "brief_ref": "",
    }


def _tracker_item_task_source(request: TrackerItemTriggerRequest) -> dict[str, str]:
    return {
        "source_kind": "tracker_item",
        "external_id": request.item.external_id,
        "repo": request.repository.full_name or request.repository.name or "",
        "branch_policy": "isolated_worktree",
        "brief_ref": "",
    }


@router.post("/github/issues")
async def ingest_github_issue_trigger(request: GitHubIssueTriggerRequest) -> dict[str, Any]:
    config = get_config()
    tracker_ref = normalize_tracker_reference(
        provider="github",
        kind="issue",
        external_id=str(request.issue.id or request.issue.number),
        title=request.issue.title,
        url=request.issue.html_url,
        event=request.action,
        repository=request.repository.model_dump(),
        metadata={
            "number": request.issue.number,
            "state": request.issue.state,
            "labels": [label.name for label in request.issue.labels if label.name],
        },
    )

    project = (
        get_project_entry(config, project_id=request.project_id, include_archived=True)
        if request.project_id
        else find_project_by_tracker_reference(config, tracker_ref)
    )
    created = False
    launched = False
    message = ""
    log_path = ""

    if request.project_id and project is None:
        raise HTTPException(404, f"Project {request.project_id} not found")

    if project is None:
        created_project = create_project_from_prd(
            config,
            _github_issue_prd(request),
            project_name=request.project_name,
            project_path=request.project_path,
            priority=request.priority,
            launch=request.launch,
            task_source=_github_issue_task_source(request),
        )
        project = get_project_entry(config, project_id=created_project.project_id, include_archived=True)
        created = True
        launched = created_project.launched
        message = created_project.message
        log_path = str(created_project.log_path) if created_project.log_path else ""
        if project is None:
            raise HTTPException(500, "Project was created but could not be loaded")
    else:
        message = "Tracker trigger linked to existing project."

    attach_tracker_reference(config, project["id"], tracker_ref)
    emit_project_event(
        config,
        project["id"],
        event="tracker_trigger_ingested",
        status="running" if launched else "idle",
        story_id=1 if created else None,
        message=f"Linked GitHub issue #{request.issue.number}: {request.issue.title}",
        extra={
            "tracker_ref": tracker_ref,
            "tracker_provider": "github",
            "tracker_kind": "issue",
            "tracker_event": request.action,
        },
    )

    return {
        "status": "ok",
        "created": created,
        "launched": launched,
        "message": message,
        "log_path": log_path,
        "tracker_ref": tracker_ref,
        "project": build_project_detail(config, project["id"]),
    }


@router.post("/tracker-items")
async def ingest_tracker_item_trigger(request: TrackerItemTriggerRequest) -> dict[str, Any]:
    config = get_config()
    tracker = next((item for item in resolve_tracker_plugins(config) if item.tracker_id == request.tracker_id), None)
    if tracker is None:
        raise HTTPException(404, f"Tracker {request.tracker_id} is not registered")
    if not bool((tracker.metadata or {}).get("supports_ingest", False)):
        raise HTTPException(400, f"Tracker {request.tracker_id} does not support inbound item ingestion")

    tracker_ref = normalize_tracker_reference(
        provider=request.tracker_id,
        kind=request.item_kind,
        external_id=request.item.external_id,
        title=request.item.title,
        url=request.item.url,
        event=request.action,
        repository=request.repository.model_dump(),
        metadata={
            "state": request.item.state,
            "labels": [label for label in request.item.labels if label],
            "tracker_display_name": tracker.display_name,
            **dict(request.item.metadata),
        },
    )

    project = (
        get_project_entry(config, project_id=request.project_id, include_archived=True)
        if request.project_id
        else find_project_by_tracker_reference(config, tracker_ref)
    )
    created = False
    launched = False
    message = ""
    log_path = ""

    if request.project_id and project is None:
        raise HTTPException(404, f"Project {request.project_id} not found")

    if project is None:
        created_project = create_project_from_prd(
            config,
            _tracker_item_prd(request, tracker.display_name),
            project_name=request.project_name,
            project_path=request.project_path,
            priority=request.priority,
            launch=request.launch,
            task_source=_tracker_item_task_source(request),
        )
        project = get_project_entry(config, project_id=created_project.project_id, include_archived=True)
        created = True
        launched = created_project.launched
        message = created_project.message
        log_path = str(created_project.log_path) if created_project.log_path else ""
        if project is None:
            raise HTTPException(500, "Project was created but could not be loaded")
    else:
        message = "Tracker trigger linked to existing project."

    attach_tracker_reference(config, project["id"], tracker_ref)
    emit_project_event(
        config,
        project["id"],
        event="tracker_trigger_ingested",
        status="running" if launched else "idle",
        story_id=1 if created else None,
        message=f"Linked {tracker.display_name} {request.item_kind} {request.item.external_id}: {request.item.title}",
        extra={
            "tracker_ref": tracker_ref,
            "tracker_provider": request.tracker_id,
            "tracker_kind": request.item_kind,
            "tracker_event": request.action,
            "tracker_transport": tracker.kind,
        },
    )

    return {
        "status": "ok",
        "created": created,
        "launched": launched,
        "message": message,
        "log_path": log_path,
        "tracker_ref": tracker_ref,
        "project": build_project_detail(config, project["id"]),
    }
