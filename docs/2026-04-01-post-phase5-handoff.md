# FounderOS Autopilot - Post-Phase-5 Handoff

Date: `2026-04-01`

Status: canonical handoff for the next chat after closing `Phase 0` through `Phase 5`

Supersedes as the default starting point for future work:

- [2026-03-31-next-product-plan.md](2026-03-31-next-product-plan.md)

## Current GitHub State

- PR: [#1](https://github.com/MartinCampbell1/autopilot/pull/1)
- state: `OPEN`
- review state: ready for review
- merge state at the time of handoff: `CLEAN`

Treat the current clean PR head as the release-candidate baseline.

## Product State In Plain Language

Autopilot is now in strong pre-release shape as a founder-facing execution plane.

What is already real:

- deterministic execution loop with operator-visible gates, budgets, and critic flow
- preview -> approval/apply trust layer in CLI and dashboard
- local-first and cloud/hybrid runtime portability
- public provider/runtime contracts
- public tool and extension surface
- workflow closure from source item or brief to PR or handoff artifact
- public OSS surface:
  - license
  - contributing docs
  - code of conduct
  - issue and PR templates
  - roadmap
  - quickstart
  - examples
  - troubleshooting
  - verification baseline
  - smoke/evaluation story
  - screenshots

Important boundary:

- `Quorum` and `Autopilot` are now connected by a stable `Execution Brief` contract and task-source workflow
- they are not yet one unified FounderOS interface
- the merge happened at the contract/workflow layer, not as a single shared UI product

## Phase Status

- `Phase 0`: done
- `Phase 1`: done
- `Phase 2`: done
- `Phase 3`: done
- `Phase 4`: done
- `Phase 5`: done
- `Phase 6`: not started by design; this is post-release expansion work

## What Was Closed

### `Phase 0`

- release-candidate baseline frozen
- release checklist, release notes template, changelog, README verification contract
- CI attached and green

### `Phase 1`

- preview/apply trust loop
- explainable execution-plane contract
- dashboard and CLI approval/apply surfaces

### `Phase 2`

- first-class local providers
- stable provider and runtime profile contracts
- intake/runtime selection and local-first docs

### `Phase 3`

- user-facing tools layer over connector registry
- extension lifecycle and examples
- configured tracker/notifier extension path

### `Phase 4`

- stable `TaskSource`
- isolated worktree default path
- `delivery_loop`, `delivery_status`, and `handoff_artifact`
- source -> execution -> PR/handoff provenance in dashboard and API

### `Phase 5`

- OSS/community surface
- public README and product positioning
- quickstart, workflow, comparison, examples, troubleshooting
- screenshots and smoke/evaluation story
- portable docs links for external readers

## Remaining Work

The pre-release phased plan is done. What remains is not more `Phase 0-5` cleanup by default.

Default next work should be one of these:

1. merge PR `#1` and cut the first public release candidate
2. start `Phase 6` post-release expansion
3. start new explicitly promoted follow-up phases if product direction changed

Current non-blocking tails:

- GitHub Actions still warns about deprecated Node 20 actions
- local `autopilot dashboard --no-browser` shutdown can log a noisy Ctrl-C traceback under Python `3.14`, but smoke passes

## Guardrails For The Next Agent

- do not reopen `Phase 0-5` implementation work unless there is a concrete regression
- do not treat `Phase 6` as required before the first public release
- do not claim `Quorum` and `Autopilot` already share one unified UI; they do not
- preserve the design law:
  - deterministic orchestration
  - LLMs do task work, not core coordination

## Local Workspace Notes

The current checkout is dirty for unrelated reasons. Do not revert or “clean up” these user-side changes unless explicitly asked:

- `dashboard/app/globals.css`
- `dashboard/app/projects/[projectId]/page.tsx`
- `dashboard/components/app-sidebar.tsx`
- `docs/2026-03-31-merged-handoff-and-plan.md`

Also ignore the known unrelated untracked artifacts already present in the workspace unless the task explicitly needs them.

## Start Here In The Next Chat

1. Read this file first.
2. Treat PR `#1` as the green release-candidate baseline.
3. If the user wants release work, focus on merge/release-candidate cut.
4. If the user wants new product work, start from `Phase 6` or from newly promoted phases, not from `Phase 0-5`.
