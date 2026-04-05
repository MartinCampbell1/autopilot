"""Intake routes for chat-based PRD generation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ValidationError

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.capability_store import (
    build_planning_context,
    load_connectors_registry,
    load_role_templates,
    load_skill_packs_registry,
)
from autopilot.core.execution_brief import render_execution_brief_as_spec
from autopilot.core.intake import (
    IntakeSession,
    build_spec_bootstrap,
    generate_prd_from_session_bootstrap,
    generate_prd_from_spec,
    run_intake_turn,
)
from autopilot.core.intake_sessions import (
    get_intake_session,
    get_intake_session_record,
    list_intake_session_records,
    save_intake_session,
)
from autopilot.core.shared_contract_adapters import shared_execution_brief_to_internal
from autopilot.core.shared_contract_codec import load_shared_execution_brief

router = APIRouter()


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    prd_ready: bool
    prd: dict | None = None
    spec_bootstrap: dict | None = None
    can_generate_prd: bool = False


class GeneratePrdRequest(BaseModel):
    session_id: str


class IntakeSessionSummary(BaseModel):
    id: str
    title: str = ""
    messages: int
    prd_ready: bool
    bootstrap_ready: bool = False
    updated_at: str = ""
    last_message: str = ""
    project_name: str = ""
    linked_project_id: str = ""
    linked_project_name: str = ""


class SessionsResponse(BaseModel):
    sessions: list[IntakeSessionSummary] = Field(default_factory=list)


class IntakeTranscriptMessage(BaseModel):
    role: str
    content: str


class IntakeSessionDetail(BaseModel):
    session_id: str
    title: str = ""
    messages: list[IntakeTranscriptMessage] = Field(default_factory=list)
    prd_ready: bool
    bootstrap_ready: bool = False
    prd: dict | None = None
    spec_bootstrap: dict | None = None
    can_generate_prd: bool = False
    project_name: str = ""
    updated_at: str = ""
    linked_project_id: str = ""
    linked_project_name: str = ""


class SpecImportRequest(BaseModel):
    spec: str


class SharedExecutionBriefImportRequest(BaseModel):
    brief: dict[str, object] = Field(default_factory=dict)


class SpecImportResponse(BaseModel):
    prd: dict


def build_session_title(session: IntakeSession) -> str:
    bootstrap = dict(session.spec_bootstrap or {})
    candidates = [
        str(session.linked_project_name or "").strip(),
        str(session.project_name or "").strip(),
        str((session.prd or {}).get("title") or "").strip(),
        str(bootstrap.get("title") or "").strip(),
    ]
    for candidate in candidates:
        if candidate:
            return candidate

    first_user_message = next(
        (
            str(message.get("content") or "").strip()
            for message in session.messages
            if str(message.get("role") or "").strip() == "user"
            and str(message.get("content") or "").strip()
        ),
        "",
    )
    if first_user_message:
        return first_user_message[:96]
    return f"Intake session {session.session_id}"


def build_session_detail(
    session: IntakeSession,
    *,
    updated_at: str = "",
) -> IntakeSessionDetail:
    bootstrap = session.spec_bootstrap or build_spec_bootstrap(session)
    return IntakeSessionDetail(
        session_id=session.session_id,
        title=build_session_title(session),
        messages=[
            IntakeTranscriptMessage(
                role=str(message.get("role") or ""),
                content=str(message.get("content") or ""),
            )
            for message in session.messages
        ],
        prd_ready=session.prd is not None,
        bootstrap_ready=bool(bootstrap),
        prd=session.prd,
        spec_bootstrap=bootstrap,
        can_generate_prd=bool(bootstrap or session.prd),
        project_name=session.project_name,
        updated_at=updated_at,
        linked_project_id=session.linked_project_id,
        linked_project_name=session.linked_project_name,
    )


@router.post("/message", response_model=ChatResponse)
async def intake_message(msg: ChatMessage) -> ChatResponse:
    config = get_config()
    session = get_intake_session(config, msg.session_id) if msg.session_id else None
    if session is None:
        session_id = str(uuid.uuid4())[:8]
        session = IntakeSession(session_id=session_id)

    manager = get_account_manager()
    profile = manager.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = manager.build_env(profile)
    planning_context = build_planning_context(
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        role_templates=load_role_templates(),
    )
    response = run_intake_turn(
        session=session,
        user_message=msg.message,
        provider="codex",
        env=env,
        planning_context=planning_context,
        timeout_sec=min(config.codex_timeout_sec, 300),
    )
    save_intake_session(config, session)

    return ChatResponse(
        session_id=session.session_id,
        response=response,
        prd_ready=session.prd is not None,
        prd=session.prd,
        spec_bootstrap=session.spec_bootstrap or build_spec_bootstrap(session),
        can_generate_prd=bool(session.spec_bootstrap or session.prd),
    )


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions() -> SessionsResponse:
    config = get_config()
    summaries: list[IntakeSessionSummary] = []
    for record in list_intake_session_records(config):
        session = get_intake_session(config, record.session_id)
        if session is None:
            continue
        summaries.append(
            IntakeSessionSummary(
                id=session.session_id,
                title=build_session_title(session),
                messages=len(session.messages),
                prd_ready=session.prd is not None,
                bootstrap_ready=bool(session.spec_bootstrap or build_spec_bootstrap(session)),
                updated_at=record.updated_at,
                last_message=str(session.messages[-1].get("content") or "").strip()
                if session.messages
                else "",
                project_name=session.project_name,
                linked_project_id=session.linked_project_id,
                linked_project_name=session.linked_project_name,
            )
        )
    return SessionsResponse(sessions=summaries)


@router.get("/sessions/{session_id}", response_model=IntakeSessionDetail)
async def get_session(session_id: str) -> IntakeSessionDetail:
    record = get_intake_session_record(get_config(), session_id)
    if record is None:
        raise HTTPException(404, f"Intake session {session_id} not found")

    session = get_intake_session(get_config(), session_id)
    if session is None:
        raise HTTPException(404, f"Intake session {session_id} not found")

    return build_session_detail(session, updated_at=record.updated_at)


@router.post("/generate-prd", response_model=SpecImportResponse)
async def generate_prd_from_interview(request: GeneratePrdRequest) -> SpecImportResponse:
    config = get_config()
    session = get_intake_session(config, request.session_id)
    if session is None:
        raise HTTPException(404, f"Intake session {request.session_id} not found")

    manager = get_account_manager()
    profile = manager.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = manager.build_env(profile)
    planning_context = build_planning_context(
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        role_templates=load_role_templates(),
    )
    try:
        prd = generate_prd_from_session_bootstrap(
            session,
            provider="codex",
            env=env,
            planning_context=planning_context,
            timeout_sec=config.codex_timeout_sec,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, str(exc)) from exc
    save_intake_session(config, session)

    return SpecImportResponse(prd=prd)


@router.post("/spec", response_model=SpecImportResponse)
async def import_spec(req: SpecImportRequest) -> SpecImportResponse:
    manager = get_account_manager()
    config = get_config()
    profile = manager.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = manager.build_env(profile)
    planning_context = build_planning_context(
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        role_templates=load_role_templates(),
    )
    try:
        prd = generate_prd_from_spec(
            req.spec,
            provider="codex",
            env=env,
            planning_context=planning_context,
            timeout_sec=config.codex_timeout_sec,
        )
    except (ValueError, ValidationError) as exc:
        raise HTTPException(400, str(exc)) from exc

    return SpecImportResponse(prd=prd)


@router.post("/shared-brief", response_model=SpecImportResponse)
async def import_shared_execution_brief(req: SharedExecutionBriefImportRequest) -> SpecImportResponse:
    manager = get_account_manager()
    config = get_config()
    profile = manager.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = manager.build_env(profile)
    planning_context = build_planning_context(
        connectors=load_connectors_registry(config),
        skill_packs=load_skill_packs_registry(config),
        role_templates=load_role_templates(),
    )
    try:
        shared_brief = load_shared_execution_brief(dict(req.brief))
        internal_brief = shared_execution_brief_to_internal(shared_brief)
        prd = generate_prd_from_spec(
            render_execution_brief_as_spec(internal_brief),
            provider="codex",
            env=env,
            planning_context=planning_context,
            timeout_sec=config.codex_timeout_sec,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return SpecImportResponse(prd=prd)
