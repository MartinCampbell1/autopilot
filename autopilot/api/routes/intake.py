"""Intake routes for chat-based PRD generation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from autopilot.api.deps import get_account_manager
from autopilot.core.intake import IntakeSession, run_intake_turn

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


@router.post("/message", response_model=ChatResponse)
async def intake_message(msg: ChatMessage) -> ChatResponse:
    if msg.session_id and msg.session_id in sessions:
        session = sessions[msg.session_id]
    else:
        session_id = str(uuid.uuid4())[:8]
        session = IntakeSession(session_id=session_id)
        sessions[session_id] = session

    manager = get_account_manager()
    profile = manager.get_next("codex")
    if profile is None:
        raise HTTPException(503, "No available accounts for intake")

    env = manager.build_env(profile)
    response = run_intake_turn(
        session=session,
        user_message=msg.message,
        provider="codex",
        env=env,
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
