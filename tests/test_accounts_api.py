"""API tests for account status and diagnostics routes."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import accounts as accounts_routes
from autopilot.core.config import AutopilotConfig


class _FakeManager:
    pools = {"codex": [], "claude": [], "gemini": []}

    def pool_status(self, provider: str) -> list[dict]:
        return [{"name": "acc1", "available": True, "requests_made": 0, "cooldown_remaining_sec": 0}]


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(accounts_routes, "get_config", lambda: config)
    monkeypatch.setattr(accounts_routes, "get_account_manager", lambda: _FakeManager())
    app = FastAPI()
    app.include_router(accounts_routes.router, prefix="/api/accounts")
    return TestClient(app)


def test_accounts_diagnostics_route_supports_refresh_flag(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    monkeypatch.setattr(
        accounts_routes,
        "build_account_diagnostics_snapshot",
        lambda _config, _manager, refresh=False: {"recorded_at": None, "refresh": refresh, "providers": {}},
    )

    response = client.get("/api/accounts/diagnostics?refresh=true")

    assert response.status_code == 200
    assert response.json()["refresh"] is True


def test_accounts_refresh_diagnostics_route_refreshes_cache(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    monkeypatch.setattr(
        accounts_routes,
        "build_account_diagnostics_snapshot",
        lambda _config, _manager, refresh=False: {"recorded_at": "2026-03-29T00:00:00+00:00", "refresh": refresh, "providers": {}},
    )

    response = client.post("/api/accounts/diagnostics/refresh")

    assert response.status_code == 200
    assert response.json()["refresh"] is True
