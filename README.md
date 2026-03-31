# Autopilot

Autopilot is the execution plane for FounderOS: a local-first CLI, API, and dashboard that turns an `Execution Brief` into tracked implementation with deterministic orchestration, quality gates, worktree isolation, budgets, approvals, and operator-visible run state.

It is not another swarm orchestrator. `Quorum` decides what to build and why, `Execution Brief` is the contract, and `Autopilot` is the system that executes under explicit budget, approval, and review loops.

## Release-Candidate Status

Current branch truth:

- branch hardening on `codex/founderos-control-plane` is already closed
- the active `P0`, `P1`, and `P2` backlog slices from the 2026-03-31 branch handoff are already landed
- the next default mode is `review/merge baseline -> productization -> OSS release surface`
- `P3` items remain deferred unless a concrete failure mode justifies promotion

The canonical next-step handoff is:

- [docs/2026-03-31-next-product-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-next-product-plan.md)

Release hygiene docs:

- [docs/release-checklist.md](/Users/martin/Desktop/autopilot/docs/release-checklist.md)
- [docs/release-notes-template.md](/Users/martin/Desktop/autopilot/docs/release-notes-template.md)
- [CHANGELOG.md](/Users/martin/Desktop/autopilot/CHANGELOG.md)

Current capabilities include:

- autonomous story execution with worker -> gates -> critic loops
- account preservation, cooldowns, and runtime budgeting
- dependency-aware project/story scheduling
- trace, cost, and diagnostic surfaces
- headless execution and scheduled maintenance runs
- execution/control-plane dashboard for projects, sessions, runtime agents, approvals, and action runs
- execution-plane APIs for briefs, sessions, action previews, control passes, and command policy

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
cd dashboard && npm install
cd ..

autopilot init /path/to/project --idea "Build a FastAPI bug tracker"
autopilot doctor /path/to/project
autopilot run /path/to/project
autopilot run /path/to/project --headless
autopilot run-all --headless
autopilot run-all --schedule 6h --max-runs 4
autopilot trace /path/to/project
autopilot live --once
autopilot status
autopilot dashboard
```

Useful patterns:

- `autopilot run --headless` emits structured JSON events and a final summary
- `autopilot run-all --schedule 30m|6h|daily --max-runs N` runs recurring maintenance without shell loops
- `autopilot doctor` checks provider readiness, onboarding state, and project gating
- `autopilot trace` shows the structured worker/runtime history for a project
- `autopilot live` renders an SSH-friendly snapshot of accounts, projects, stories, and recent events

## Official Verification Baseline

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

Supporting architecture docs:

- [docs/execution-brief-bridge.md](/Users/martin/Desktop/autopilot/docs/execution-brief-bridge.md)
- [docs/phase3-founderos-execution-plane.md](/Users/martin/Desktop/autopilot/docs/phase3-founderos-execution-plane.md)
- [docs/phase4-approval-foundation.md](/Users/martin/Desktop/autopilot/docs/phase4-approval-foundation.md)
