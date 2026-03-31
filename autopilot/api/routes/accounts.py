"""Account routes for account status, login, and profile import."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from autopilot.api.deps import get_account_manager, get_config
from autopilot.core.account_diagnostics import build_account_diagnostics_snapshot
from autopilot.core.adapters import list_provider_families
from autopilot.core.provider_sessions import (
    import_current_session,
    is_valid_provider,
    open_login_terminal,
)

router = APIRouter()


@router.get("/")
async def list_accounts() -> dict[str, dict]:
    manager = get_account_manager()
    result: dict[str, list[dict]] = {}
    for provider in list_provider_families():
        if provider in manager.pools:
            result[provider] = manager.pool_status(provider)
    return {"accounts": result}


@router.get("/health")
async def accounts_health() -> dict[str, int]:
    manager = get_account_manager()
    total = sum(len(profiles) for profiles in manager.pools.values())
    available = sum(sum(1 for profile in profiles if profile.check_available()) for profiles in manager.pools.values())
    return {
        "total": total,
        "available": available,
        "on_cooldown": total - available,
    }


@router.get("/diagnostics")
async def account_diagnostics(refresh: bool = False) -> dict[str, object]:
    config = get_config()
    manager = get_account_manager()
    diagnostics = build_account_diagnostics_snapshot(config, manager, refresh=refresh)
    return diagnostics


@router.post("/diagnostics/refresh")
async def refresh_account_diagnostics() -> dict[str, object]:
    config = get_config()
    manager = get_account_manager()
    diagnostics = build_account_diagnostics_snapshot(config, manager, refresh=True)
    return diagnostics


@router.post("/{provider}/open-login")
async def open_provider_login(provider: str) -> dict[str, str]:
    if not is_valid_provider(provider):
        raise HTTPException(404, f"Unknown provider: {provider}")

    command = open_login_terminal(provider)
    return {
        "status": "ok",
        "provider": provider,
        "command": command,
        "message": "Login flow opened in a separate terminal window.",
    }


@router.post("/{provider}/import")
async def import_provider_session(provider: str) -> dict[str, str]:
    if not is_valid_provider(provider):
        raise HTTPException(404, f"Unknown provider: {provider}")

    config = get_config()

    try:
        account_name = import_current_session(provider, config.profiles_dir)
    except FileNotFoundError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        "status": "ok",
        "provider": provider,
        "account_name": account_name,
        "message": f"Imported {provider} session as {account_name}.",
    }
