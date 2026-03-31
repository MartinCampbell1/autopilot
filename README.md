# Autopilot

Autopilot is a standalone CLI for orchestrating autonomous AI programmers with account rotation, critic loops, and project-level automation.

Current capabilities on this branch include:

- autonomous story execution with worker -> gates -> critic loops
- account preservation, cooldowns, and runtime budgeting
- dependency-aware project/story scheduling
- trace, cost, and diagnostic surfaces
- headless execution and scheduled maintenance runs
- execution/control-plane dashboard for projects, sessions, runtime agents, and action runs

## Core Commands

```bash
autopilot init /path/to/project --idea "Build a FastAPI bug tracker"
autopilot doctor /path/to/project
autopilot run /path/to/project
autopilot run /path/to/project --headless
autopilot run-all --headless
autopilot run-all --schedule 6h --max-runs 4
autopilot trace /path/to/project
autopilot live --once
autopilot dashboard
```

Useful patterns:

- `autopilot run --headless` emits structured JSON events and a final summary
- `autopilot run-all --schedule 30m|6h|daily --max-runs N` runs recurring maintenance without shell loops
- `autopilot doctor` checks provider readiness, onboarding state, and project gating
- `autopilot trace` shows the structured worker/runtime history for a project
- `autopilot live` renders an SSH-friendly snapshot of accounts, projects, stories, and recent events

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
autopilot version
```

## Current Status

The repo is well past the initial scaffold stage.

Current branch status:

- Phase 1 foundation is in place
- Phase 2 runtime-control primitives are in place
- Phase 3 execution/control-plane work is real and operational
- the active `P0`, `P1`, and `P2` hardening backlog called out in the 2026-03-31 handoff docs has been implemented on `codex/founderos-control-plane`

Recommended verification baseline:

```bash
./.venv/bin/python -m pytest -q
cd dashboard && npm run lint && npm run build
```
