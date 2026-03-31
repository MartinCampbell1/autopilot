# Phase 2 Runtime Control Primitives

This is the first incremental slice of Phase 2. It does not introduce budgets yet, but it establishes the minimum ownership and atomic checkout semantics needed for a control plane.

## Landed In This Increment

- Added file-backed story work-item leases in `autopilot/core/runtime_control.py`.
- Added runtime budgets in `autopilot/core/runtime_budgets.py`.
- Added explicit runtime roles:
  - `coordinator`
  - `worker`
  - `critic`
  - `specialist`
- Integrated coordinator lease acquisition into `autopilot/cli/run.py` before active story execution begins.
- Leases now reserve the intended checkout target:
  - shared main workspace for sequential execution
  - worktree path + branch name for parallel execution
- Story runtime state now carries:
  - `ownership`
  - `checkout`
- Project runtime state now carries:
  - `budget_policy`
  - `budget_usage`
- Execution-plane detail can now derive first-class `runtime_agents` from:
  - story team assignments
  - active worker / critic labels
  - story ownership and checkout state
  - active lease metadata when present
- Runtime events can now carry stable runtime-agent references:
  - `runtime_agent_id`
  - `runtime_agent_ids`
  - worker / critic / specialist agent ids when known
- Execution-plane agent summaries can now derive:
  - per-agent budget state from runtime budget counters
  - per-agent attention state from issues, approvals, budget pressure, and story status
- Added project budget policy API update surface:
  - `PATCH /api/projects/{project_id}/budget-policy`
- Added runtime-control inspection and checkout recovery surface:
  - `GET /api/projects/{project_id}/runtime-control`
  - `POST /api/projects/{project_id}/stories/{story_id}/recover-checkout`
  - `POST /api/projects/{project_id}/runtime-control/recover-stale`
- The run loop now auto-pauses before starting a new iteration when the next worker/critic assignment would exceed:
  - project worker/critic iteration budgets
  - per-agent worker/critic iteration budgets
- Added workspace policy inspection in `autopilot/core/workspace_policy.py`:
  - story checkout health
  - lease/checkouts mismatch detection
  - orphaned worktree detection
  - safe recovery for non-running projects
  - stale lease detection from heartbeat age + runtime pid liveness
- Added lease heartbeat refresh during active story execution in `autopilot/cli/run.py`.

## Why This Shape

- It preserves the current execution-first runtime instead of replacing it with a heartbeat-first control loop.
- It gives FounderOS-compatible control-plane visibility into who owns active work and which checkout path is reserved.
- It adds a minimal agent/role surface without introducing a second scheduler or separate agent database.
- It keeps the write surface small: one lease file per active story.

## What Is Not Done Yet

- Richer workspace/worktree policy enforcement beyond atomic story checkout intent.
- A higher-level company/agent/issue/approval model.
- More opinionated merge-blocked recovery policy.
- FounderOS-facing runtime-control API with stronger external orchestration contracts.

## Safe Next Steps

1. Add runtime budgets to the same control-plane state area and wire them into worker/critic dispatch.
2. Expose lease and budget state via the API for an external FounderOS orchestrator.
3. Tighten worktree policy so merge-blocked and abandoned checkouts can be surfaced and recovered explicitly.
