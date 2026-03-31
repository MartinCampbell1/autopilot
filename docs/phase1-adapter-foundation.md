# Phase 1 Adapter Foundation

This document captures the current repository audit and the first safe migration step toward a FounderOS execution/control plane.

## Audit Summary

Keep as-is for now:

- `autopilot/core/account_manager.py`: already owns multi-account discovery, leasing, cooldown, and rotation.
- `autopilot/core/orchestrator.py`: already owns the execution-first worker -> gates -> critic loop.
- `autopilot/core/loop_runner.py`: still owns Ralph-specific build/retry flow and progress tracking.
- `autopilot/core/worktree.py`: useful base for later atomic checkout/worktree policy work.

Refactor incrementally:

- `autopilot/core/providers.py`: was an untyped command table; now becomes a compatibility facade over typed adapters.
- `autopilot/core/provider_sessions.py`: provider-specific session import/login logic now belongs in adapters.
- `autopilot/core/critic.py`: provider-specific runtime invocation now belongs in adapters.
- `autopilot/core/loop_runner.py`: generic provider prompt execution now routes through adapters.

Do not rewrite yet:

- Multi-account pool layout under `profiles/<provider>/accN`.
- Ralph-driven worker execution path.
- Existing project state/orchestrator contracts.

## Landed In This Increment

- Added typed local adapters in `autopilot/core/adapters.py` for:
  - `codex_local`
  - `claude_local`
  - `gemini_local`
- Preserved existing provider names (`codex`, `claude`, `gemini`) as aliases to default local adapters.
- Moved adapter-owned concerns behind explicit contracts:
  - `execute()`
  - `parse_output()`
  - `test_environment()`
  - `quota_probe()`
  - resume-state inspection
  - runtime metadata/diagnostics
- Kept `AccountManager` as the owner of pool rotation while delegating runtime-home/env/session semantics to adapters.
- Migrated `provider_sessions`, `loop_runner`, and `critic` to the adapter registry.
- Added persisted account probe state and diagnostics exposure:
  - `autopilot/core/account_diagnostics.py`
  - `GET /api/accounts/diagnostics`
  - `POST /api/accounts/diagnostics/refresh`

## Runtime-Home Model

- `codex_local`: managed runtime home is the account directory itself, exposed as `CODEX_HOME`.
- `claude_local`: managed runtime home is `<profile>/home`, exposed as `HOME`.
- `gemini_local`: managed runtime home is `<profile>/home`, exposed as `HOME`.

This keeps the current pool layout intact while making runtime isolation explicit in the adapter contract.

## Safe Next Steps

1. Introduce a small runtime-agent model that binds story ownership to an adapter/profile lease.
2. Add atomic checkout metadata on top of the existing worktree helpers before changing merge policy.
3. Add per-agent and per-project runtime budgets with auto-pause, without changing the core worker loop shape.
4. Expose a stable execution-plane API for FounderOS once diagnostics, ownership, and budgets are in place.
