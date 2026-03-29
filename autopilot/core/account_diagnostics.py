"""Persisted adapter diagnostics and quota probes for managed accounts."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from autopilot.core.account_manager import AccountManager
from autopilot.core.adapters import AdapterProbeResult, get_adapter, list_provider_families
from autopilot.core.config import AutopilotConfig


def _read_json(path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def load_account_probe_state(config: AutopilotConfig) -> dict[str, Any]:
    """Load the persisted account probe cache."""
    return _read_json(
        config.account_probe_state_path,
        {"providers": {}, "recorded_at": None},
    )


def save_account_probe_state(config: AutopilotConfig, state: dict[str, Any]) -> None:
    """Persist the account probe cache."""
    config.account_probe_state_path.parent.mkdir(parents=True, exist_ok=True)
    config.account_probe_state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _serialize_probe(result: AdapterProbeResult) -> dict[str, Any]:
    payload = {
        "status": result.status.value,
        "summary": result.summary,
        "output": result.output,
    }
    if result.diagnostics is not None:
        payload["diagnostics"] = asdict(result.diagnostics)
    return payload


def build_account_diagnostics_snapshot(
    config: AutopilotConfig,
    manager: AccountManager,
    *,
    refresh: bool = False,
    timeout: int = 15,
) -> dict[str, Any]:
    """Build a diagnostics snapshot for the current account pool, optionally refreshing probes."""
    cached = load_account_probe_state(config)
    providers_payload: dict[str, list[dict[str, Any]]] = {}

    for provider in list_provider_families():
        profiles = manager.pools.get(provider, [])
        cached_entries = {
            entry["name"]: entry
            for entry in cached.get("providers", {}).get(provider, [])
            if entry.get("name")
        }
        provider_entries: list[dict[str, Any]] = []

        for profile in profiles:
            adapter = get_adapter(profile.resolved_adapter_id)
            env = manager.build_env(profile)
            entry: dict[str, Any] = {
                "name": profile.name,
                "provider": profile.provider,
                "adapter_id": profile.resolved_adapter_id,
                "requests_made": profile.requests_made,
                "available": profile.check_available(),
                "cooldown_until": profile.cooldown_until,
                "runtime_metadata": asdict(adapter.runtime_metadata(profile)),
                "resume_state": asdict(adapter.resume_state(profile)),
            }

            if refresh:
                environment_probe = adapter.test_environment(profile, env=env, timeout=timeout)
                quota_probe = adapter.quota_probe(profile, env=env, timeout=timeout)
                entry["environment_probe"] = _serialize_probe(environment_probe)
                entry["quota_probe"] = _serialize_probe(quota_probe)
            else:
                cached_entry = cached_entries.get(profile.name, {})
                entry["environment_probe"] = cached_entry.get("environment_probe")
                entry["quota_probe"] = cached_entry.get("quota_probe")

            provider_entries.append(entry)

        providers_payload[provider] = provider_entries

    snapshot = {
        "recorded_at": cached.get("recorded_at"),
        "providers": providers_payload,
    }

    if refresh:
        from autopilot.core.project_store import utcnow_iso

        snapshot["recorded_at"] = utcnow_iso()
        save_account_probe_state(config, snapshot)

    return snapshot
