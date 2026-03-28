"""Intake routes for chat-based PRD generation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.capability_store import (
    build_planning_context,
    load_connectors_registry,
    load_role_templates,
    load_skill_packs_registry,
)
from autopilot.core.intake import IntakeSession, generate_prd_from_spec, run_intake_turn

router = APIRouter()

sessions: dict[str, IntakeSession] = {}


class ChatMessage(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    response: str
    prd_ready: bool
    prd: dict | None = None


class SpecImportRequest(BaseModel):
    spec: str


class SpecImportResponse(BaseModel):
    prd: dict


@router.post("/message", response_model=ChatResponse)
async def intake_message(msg: ChatMessage) -> ChatResponse:
    if msg.session_id and msg.session_id in sessions:
        session = sessions[msg.session_id]
    else:
        session_id = str(uuid.uuid4())[:8]
        session = IntakeSession(session_id=session_id)
        sessions[session_id] = session

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
    response = run_intake_turn(
        session=session,
        user_message=msg.message,
        provider="codex",
        env=env,
        planning_context=planning_context,
        timeout_sec=min(config.codex_timeout_sec, 300),
    )

    return ChatResponse(
        session_id=session.session_id,
        response=response,
        prd_ready=session.prd is not None,
        prd=session.prd,
    )


@router.get("/sessions")
async def list_sessions() -> dict[str, list[dict]]:
    return {
        "sessions": [
            {
                "id": session.session_id,
                "messages": len(session.messages),
                "prd_ready": session.prd is not None,
            }
            for session in sessions.values()
        ]
    }


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
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return SpecImportResponse(prd=prd)
