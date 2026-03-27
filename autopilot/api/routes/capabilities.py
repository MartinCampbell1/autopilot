"""Routes for MCP connectors, skill packs, and role templates."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autopilot.api.deps import get_config
from autopilot.core.capability_store import (
    MCPConnector,
    SkillPack,
    delete_connector,
    delete_skill_pack,
    load_connectors_registry,
    load_role_templates,
    load_skill_packs_registry,
    upsert_connector,
    upsert_skill_pack,
)

router = APIRouter()


class ConnectorRequest(BaseModel):
    id: str
    name: str
    connector_type: str
    description: str = ""
    transport: str = "builtin"
    tags: list[str] = Field(default_factory=list)
    providers: list[str] = Field(default_factory=lambda: ["codex", "claude", "gemini"])
    risk_level: str = "medium"
    scopes: list[str] = Field(default_factory=list)
    enabled: bool = True
    config: dict = Field(default_factory=dict)


class SkillPackRequest(BaseModel):
    id: str
    name: str
    description: str
    prompt: str
    tags: list[str] = Field(default_factory=list)
    default_roles: list[str] = Field(default_factory=list)
    preferred_connectors: list[str] = Field(default_factory=list)
    enabled: bool = True


@router.get("/catalog")
async def get_capabilities_catalog() -> dict:
    config = get_config()
    return {
        "connectors": [connector.model_dump() for connector in load_connectors_registry(config)],
        "skill_packs": [skill_pack.model_dump() for skill_pack in load_skill_packs_registry(config)],
        "roles": [role.model_dump() for role in load_role_templates()],
    }


@router.get("/connectors")
async def list_connectors() -> dict[str, list[dict]]:
    config = get_config()
    return {"connectors": [connector.model_dump() for connector in load_connectors_registry(config)]}


@router.post("/connectors")
async def create_connector(request: ConnectorRequest) -> dict:
    config = get_config()
    connector = MCPConnector.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_connector(config, connector)
    return {"status": "ok", "connector": stored.model_dump()}


@router.patch("/connectors/{connector_id}")
async def update_connector(connector_id: str, request: ConnectorRequest) -> dict:
    if connector_id != request.id:
        raise HTTPException(400, "Connector id mismatch")
    config = get_config()
    existing = {connector.id for connector in load_connectors_registry(config)}
    if connector_id not in existing:
        raise HTTPException(404, f"Connector {connector_id} not found")
    connector = MCPConnector.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_connector(config, connector)
    return {"status": "ok", "connector": stored.model_dump()}


@router.delete("/connectors/{connector_id}")
async def remove_connector(connector_id: str) -> dict[str, str]:
    config = get_config()
    existing = {connector.id: connector for connector in load_connectors_registry(config)}
    connector = existing.get(connector_id)
    if connector is None:
        raise HTTPException(404, f"Connector {connector_id} not found")
    if connector.built_in:
        raise HTTPException(400, f"Connector {connector_id} is built in and cannot be deleted")
    delete_connector(config, connector_id)
    return {"status": "ok", "message": f"Connector {connector_id} deleted."}


@router.get("/skill-packs")
async def list_skill_packs() -> dict[str, list[dict]]:
    config = get_config()
    return {"skill_packs": [skill_pack.model_dump() for skill_pack in load_skill_packs_registry(config)]}


@router.post("/skill-packs")
async def create_skill_pack(request: SkillPackRequest) -> dict:
    config = get_config()
    skill_pack = SkillPack.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_skill_pack(config, skill_pack)
    return {"status": "ok", "skill_pack": stored.model_dump()}


@router.patch("/skill-packs/{skill_pack_id}")
async def update_skill_pack(skill_pack_id: str, request: SkillPackRequest) -> dict:
    if skill_pack_id != request.id:
        raise HTTPException(400, "Skill pack id mismatch")
    config = get_config()
    existing = {skill_pack.id for skill_pack in load_skill_packs_registry(config)}
    if skill_pack_id not in existing:
        raise HTTPException(404, f"Skill pack {skill_pack_id} not found")
    skill_pack = SkillPack.model_validate({**request.model_dump(), "built_in": False})
    stored = upsert_skill_pack(config, skill_pack)
    return {"status": "ok", "skill_pack": stored.model_dump()}


@router.delete("/skill-packs/{skill_pack_id}")
async def remove_skill_pack(skill_pack_id: str) -> dict[str, str]:
    config = get_config()
    existing = {skill_pack.id: skill_pack for skill_pack in load_skill_packs_registry(config)}
    skill_pack = existing.get(skill_pack_id)
    if skill_pack is None:
        raise HTTPException(404, f"Skill pack {skill_pack_id} not found")
    if skill_pack.built_in:
        raise HTTPException(400, f"Skill pack {skill_pack_id} is built in and cannot be deleted")
    delete_skill_pack(config, skill_pack_id)
    return {"status": "ok", "message": f"Skill pack {skill_pack_id} deleted."}
