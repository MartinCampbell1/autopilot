"""Account routes for account status and health."""

from fastapi import APIRouter

from autopilot.api.deps import get_account_manager

router = APIRouter()


@router.get("/")
async def list_accounts() -> dict[str, dict]:
    manager = get_account_manager()
    result: dict[str, list[dict]] = {}
    for provider in ("codex", "claude", "gemini"):
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
