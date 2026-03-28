"""API tests for MCP connector and skill-pack registries."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autopilot.api.routes import capabilities as capabilities_routes
from autopilot.core.config import AutopilotConfig


def _build_client(config: AutopilotConfig, monkeypatch) -> TestClient:
    monkeypatch.setattr(capabilities_routes, "get_config", lambda: config)
    app = FastAPI()
    app.include_router(capabilities_routes.router, prefix="/api/capabilities")
    return TestClient(app)


def test_capabilities_catalog_lists_defaults(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    response = client.get("/api/capabilities/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert any(connector["id"] == "browser_devtools" for connector in payload["connectors"])
    assert any(skill_pack["id"] == "fastapi-backend" for skill_pack in payload["skill_packs"])
    assert any(role["id"] == "backend_worker" for role in payload["roles"])
    assert any(connector_type["id"] == "mcp_server" for connector_type in payload["connector_types"])
    assert any(policy["role_id"] == "frontend_worker" for policy in payload["routing_policies"])
    assert any(preset["id"] == "parallel" for preset in payload["launch_presets"])


def test_create_and_update_connector_and_skill_pack(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    create_connector = client.post(
        "/api/capabilities/connectors",
        json={
            "id": "solana_rpc",
            "name": "Solana RPC",
            "connector_type": "mcp_server",
            "description": "Call Solana RPC endpoints",
            "transport": "http",
            "tags": ["backend", "trading", "api"],
            "providers": ["codex"],
            "risk_level": "medium",
            "scopes": ["network"],
            "enabled": True,
            "config": {"base_url": "https://rpc.example.com"},
        },
    )
    assert create_connector.status_code == 200
    assert create_connector.json()["connector"]["id"] == "solana_rpc"

    update_connector = client.patch(
        "/api/capabilities/connectors/solana_rpc",
        json={
            "id": "solana_rpc",
            "name": "Solana RPC",
            "connector_type": "mcp_server",
            "description": "Call Solana RPC endpoints safely",
            "transport": "http",
            "tags": ["backend", "trading", "api"],
            "providers": ["codex", "claude"],
            "risk_level": "high",
            "scopes": ["network"],
            "enabled": False,
            "config": {"base_url": "https://rpc.example.com"},
        },
    )
    assert update_connector.status_code == 200
    assert update_connector.json()["connector"]["enabled"] is False

    create_skill_pack = client.post(
        "/api/capabilities/skill-packs",
        json={
            "id": "solana-trading",
            "name": "Solana Trading",
            "description": "Implement Solana market data and execution stories.",
            "prompt": "Prefer narrow trading stories with explicit wallet, RPC, and safety checks.",
            "tags": ["trading", "backend"],
            "default_roles": ["backend_worker"],
            "preferred_connectors": ["solana_rpc", "python_exec"],
            "enabled": True,
        },
    )
    assert create_skill_pack.status_code == 200
    assert create_skill_pack.json()["skill_pack"]["id"] == "solana-trading"

    update_skill_pack = client.patch(
        "/api/capabilities/skill-packs/solana-trading",
        json={
            "id": "solana-trading",
            "name": "Solana Trading",
            "description": "Implement Solana market data and execution stories with safety rails.",
            "prompt": "Break trading work into ingestion, decision, execution, and monitoring slices.",
            "tags": ["trading", "backend", "risk"],
            "default_roles": ["backend_worker", "runtime_investigator"],
            "preferred_connectors": ["solana_rpc", "python_exec"],
            "enabled": False,
        },
    )
    assert update_skill_pack.status_code == 200
    assert update_skill_pack.json()["skill_pack"]["enabled"] is False

    connectors_payload = client.get("/api/capabilities/connectors").json()["connectors"]
    skill_packs_payload = client.get("/api/capabilities/skill-packs").json()["skill_packs"]

    assert any(connector["id"] == "solana_rpc" for connector in connectors_payload)
    assert any(skill_pack["id"] == "solana-trading" for skill_pack in skill_packs_payload)
    assert config.connectors_json_path.exists()
    assert config.skill_packs_json_path.exists()


def test_delete_custom_connector_and_skill_pack(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    client.post(
        "/api/capabilities/connectors",
        json={
            "id": "temporary_connector",
            "name": "Temporary Connector",
            "connector_type": "mcp_server",
            "description": "Temporary connector",
            "transport": "stdio",
            "tags": ["debug"],
            "providers": ["codex"],
            "risk_level": "medium",
            "scopes": ["workspace"],
            "enabled": True,
            "config": {"command": "demo"},
        },
    )
    client.post(
        "/api/capabilities/skill-packs",
        json={
            "id": "temporary_skill",
            "name": "Temporary Skill",
            "description": "Temporary skill",
            "prompt": "Do the temporary thing.",
            "tags": ["debug"],
            "default_roles": ["backend_worker"],
            "preferred_connectors": ["temporary_connector"],
            "enabled": True,
        },
    )

    delete_connector_response = client.delete("/api/capabilities/connectors/temporary_connector")
    delete_skill_response = client.delete("/api/capabilities/skill-packs/temporary_skill")

    assert delete_connector_response.status_code == 200
    assert delete_skill_response.status_code == 200
    assert not any(
        connector["id"] == "temporary_connector"
        for connector in client.get("/api/capabilities/connectors").json()["connectors"]
    )
    assert not any(
        skill_pack["id"] == "temporary_skill"
        for skill_pack in client.get("/api/capabilities/skill-packs").json()["skill_packs"]
    )


def test_validate_connector_and_persist_status(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    invalid_response = client.post(
        "/api/capabilities/connectors/validate",
        json={
            "id": "broken_api",
            "name": "Broken API",
            "connector_type": "http_api",
            "description": "Broken http connector",
            "transport": "http",
            "tags": ["api"],
            "providers": ["codex"],
            "risk_level": "medium",
            "scopes": ["network"],
            "enabled": True,
            "config": {},
        },
    )
    assert invalid_response.status_code == 200
    assert invalid_response.json()["result"]["status"] == "invalid"

    create_response = client.post(
        "/api/capabilities/connectors",
        json={
            "id": "valid_api",
            "name": "Valid API",
            "connector_type": "http_api",
            "description": "Valid http connector",
            "transport": "http",
            "tags": ["api"],
            "providers": ["codex"],
            "risk_level": "medium",
            "scopes": ["network"],
            "enabled": True,
            "config": {"base_url": "https://api.example.com"},
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["connector"]["validation_status"] == "valid"

    validate_saved = client.post("/api/capabilities/connectors/valid_api/validate")
    assert validate_saved.status_code == 200
    assert validate_saved.json()["result"]["status"] == "valid"


def test_update_routes_validate_mismatch_and_missing_ids(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    mismatch = client.patch(
        "/api/capabilities/connectors/one",
        json={
            "id": "two",
            "name": "Mismatch",
            "connector_type": "builtin",
        },
    )
    assert mismatch.status_code == 400

    missing = client.patch(
        "/api/capabilities/skill-packs/missing-pack",
        json={
            "id": "missing-pack",
            "name": "Missing",
            "description": "Not found",
            "prompt": "Prompt",
        },
    )
    assert missing.status_code == 404

    built_in_delete = client.delete("/api/capabilities/connectors/shell_exec")
    assert built_in_delete.status_code == 400


def test_update_routing_policy_and_launch_presets(tmp_path: Path, monkeypatch) -> None:
    config = AutopilotConfig(autopilot_home_override=str(tmp_path / ".autopilot"))
    client = _build_client(config, monkeypatch)

    update_response = client.patch(
        "/api/capabilities/routing-policies/backend_worker",
        json={
            "role_id": "backend_worker",
            "preferred_skill_packs": ["fastapi-backend"],
            "required_connectors": ["context7"],
            "preferred_connectors": ["http_api", "web_docs"],
            "forbidden_connectors": ["browser_devtools"],
        },
    )
    assert update_response.status_code == 200
    payload = update_response.json()["routing_policy"]
    assert payload["required_connectors"] == ["context7"]

    routing_response = client.get("/api/capabilities/routing-policies")
    assert routing_response.status_code == 200
    assert any(
        policy["role_id"] == "backend_worker" and policy["required_connectors"] == ["context7"]
        for policy in routing_response.json()["routing_policies"]
    )

    launch_presets = client.get("/api/capabilities/launch-presets")
    assert launch_presets.status_code == 200
    assert any(preset["id"] == "team" for preset in launch_presets.json()["launch_presets"])
