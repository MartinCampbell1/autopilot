# FounderOS Autopilot - Next Product Plan

Date: `2026-03-31`

Status: canonical handoff for the next chat after branch hardening

Supersedes as the default starting point for future work:

- [2026-03-31-merged-handoff-and-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-merged-handoff-and-plan.md)
- [2026-03-31-control-plane-handoff.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-control-plane-handoff.md)

Grounding docs:

- [2026-03-31-pr-summary.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-pr-summary.md)
- [2026-03-31-branch-completion-note.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-branch-completion-note.md)
- [execution-brief-bridge.md](/Users/martin/Desktop/autopilot/docs/execution-brief-bridge.md)
- [phase3-founderos-execution-plane.md](/Users/martin/Desktop/autopilot/docs/phase3-founderos-execution-plane.md)
- [phase4-approval-foundation.md](/Users/martin/Desktop/autopilot/docs/phase4-approval-foundation.md)

## North Star

`FounderOS` is not another swarm orchestrator.

- `Quorum` chooses what to build and why.
- `Execution Brief` is the decision contract.
- `Autopilot` executes under deterministic orchestration, budget controls, approvals, quality gates, worktree isolation, and review loops.

The next move is not to replay already-closed hardening work.
The next move is to turn the current execution plane into a public, extensible, local-first, and trustworthy product.

## Baseline Facts

Treat the following as already true on `codex/founderos-control-plane`:

- branch-level hardening is already closed
- `Phase 3` is already real and operational
- the active `P0`, `P1`, and `P2` backlog slices from the March 31 handoff are already implemented
- dashboard stabilization, doctor, trace, cost, headless, schedule, live, status, and control-plane surfaces are already present
- `P3` items are not active by default

Current default operating mode for the next agent:

1. review and merge the frozen baseline
2. productize the existing execution plane
3. expand the OSS release surface

Do not reopen the already-landed branch tasks unless a regression proves the branch truth wrong.

## Immediate Actions

Start here in the next chat:

1. Read [2026-03-31-pr-summary.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-pr-summary.md) and [2026-03-31-branch-completion-note.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-branch-completion-note.md).
2. Use this file as the single source of truth for what comes next.
3. Default to `Phase 0` until the baseline is reviewed, green, and merged.
4. Promote `P3` only if a concrete runtime or operator failure mode demands it.

## Phase 0 - Freeze Baseline And Prepare Public Release

Goal: lock the current branch as a release candidate and stop arguing with stale docs.

Changes:

- close the current branch lifecycle:
  - review the existing draft PR
  - move it to ready-for-review
  - ensure baseline CI is attached and readable
  - merge only after the verification contract is green
- keep one canonical handoff for the next chat instead of competing branch notes
- finish minimum release hygiene:
  - release checklist
  - version bump strategy
  - changelog skeleton
  - release notes skeleton
  - official smoke commands in `README.md`

Public contracts:

- release verification contract:
  - `./.venv/bin/python -m pytest -q`
  - `./.venv/bin/ruff check autopilot tests`
  - `(cd dashboard && npm run lint)`
  - `(cd dashboard && npm run build)`
  - `./.venv/bin/autopilot dashboard --no-browser`
  - `./.venv/bin/autopilot live --once`
  - `./.venv/bin/autopilot status`

Acceptance:

- one source-of-truth handoff exists for the next chat
- the branch is reviewable as a release candidate
- release notes, checklist, and README do not contradict product reality

## Phase 1 - Operator Trust Layer

Goal: make execution safe and reviewable before apply, not only after the fact.

Existing foundation to extend:

- [phase4-approval-foundation.md](/Users/martin/Desktop/autopilot/docs/phase4-approval-foundation.md)
- [autopilot/core/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py)
- [autopilot/api/routes/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/execution_plane.py)
- [dashboard/app/control-plane/page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx)

Changes:

- upgrade the current preview and approval surfaces into a full `preview -> approve/apply` loop
- show candidate diffs before apply instead of only surfacing approvals and action outcomes
- add explicit policy for destructive or high-risk actions
- keep the orchestration deterministic; do not move core coordination into the LLM
- expose the decision path:
  - what changes
  - why it is proposed
  - which gates or critic signals approved or blocked it

Public contracts to add or stabilize:

- `preview_id`
- `diff_summary`
- `patch_bundle` or `artifact_ref`
- `approval_required`
- `apply_mode` with `auto`, `manual`, and `policy`

Acceptance:

- any risky run can be previewed before apply
- the operator can inspect a summary and diff before approval
- dashboard and CLI can show preview state, approval state, and final applied result from one run context
- existing auto-runs still work when project policy allows auto-apply

## Phase 2 - Local-First Runtime And Model Portability

Goal: remove the product dependency on a small set of cloud CLIs and make private execution a first-class path.

Existing foundation to extend:

- [autopilot/core/adapters.py](/Users/martin/Desktop/autopilot/autopilot/core/adapters.py)
- [autopilot/core/providers.py](/Users/martin/Desktop/autopilot/autopilot/core/providers.py)
- [autopilot/core/config.py](/Users/martin/Desktop/autopilot/autopilot/core/config.py)
- [autopilot/core/capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py)
- [autopilot/cli/doctor.py](/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py)

Changes:

- add first-class local providers:
  - Ollama
  - OpenAI-compatible local endpoints
  - configurable local command and server adapters
- move provider selection into a stable user-facing config contract
- add runtime execution profiles:
  - `cloud`
  - `local`
  - `hybrid`
- prepare an optional isolated runtime profile with Docker first

Public contracts:

- provider config schema:
  - `id`
  - `family`
  - `mode`
  - `transport`
  - `endpoint` or `command`
  - `auth_strategy`
  - `capabilities`
- runtime profile schema:
  - `sandbox_mode`
  - `network_policy`
  - `filesystem_policy`
  - `default_tools`

Acceptance:

- the same project and run contract can target cloud or local providers without orchestration rewrites
- `autopilot doctor` validates local providers and cloud providers through the same surface
- `README.md` documents a local-first setup path

## Phase 3 - User-Facing Tools And Extension Surface

Goal: expose the existing capability and connector work as a clear extension system without inventing a giant plugin ecosystem.

Existing foundation to extend:

- [autopilot/core/capability_store.py](/Users/martin/Desktop/autopilot/autopilot/core/capability_store.py)
- [autopilot/core/plugins.py](/Users/martin/Desktop/autopilot/autopilot/core/plugins.py)
- [autopilot/api/routes/capabilities.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/capabilities.py)
- [dashboard/components/settings-capabilities.tsx](/Users/martin/Desktop/autopilot/dashboard/components/settings-capabilities.tsx)

Changes:

- create one user-facing tools layer over the current capability store and connector registries
- support a curated tool set:
  - shell
  - git
  - browser or devtools
  - HTTP API
  - database
  - MCP server
- define extension contracts for:
  - tracker
  - notifier
  - provider
  - tool or connector
- document how to add a provider, tool, or tracker without core edits

Public contracts:

- tool or connector schema:
  - `tool_id`
  - `kind`
  - `transport`
  - `scope`
  - `approval_policy`
  - `provider_compatibility`
- extension lifecycle:
  - `register`
  - `validate`
  - `expose`
  - `audit`

Acceptance:

- a user can register a new provider or tool without changing core orchestration logic
- at least three extension examples are documented
- dashboard and API can show active tools and connectors per project and run

## Phase 4 - FounderOS Workflow Closure

Goal: close the path from idea to brief to tracked execution to PR or handoff artifact.

Existing foundation to extend:

- [execution-brief-bridge.md](/Users/martin/Desktop/autopilot/docs/execution-brief-bridge.md)
- [autopilot/core/execution_brief.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_brief.py)
- [autopilot/core/worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py)
- [autopilot/core/project_bootstrap.py](/Users/martin/Desktop/autopilot/autopilot/core/project_bootstrap.py)
- [autopilot/core/github_prs.py](/Users/martin/Desktop/autopilot/autopilot/core/github_prs.py)

Changes:

- stabilize the handoff from `Quorum` and `Execution Brief` into `Autopilot`
- add a canonical task-source layer for:
  - local brief
  - GitHub issue
  - tracker item
- make isolated workspace or worktree execution the default path
- normalize the delivery loop:
  - source item
  - execution plan
  - run
  - review
  - PR or handoff artifact

Public contracts:

- `TaskSource`:
  - `source_kind`
  - `external_id`
  - `repo`
  - `branch_policy`
  - `brief_ref`
- `ExecutionBrief` stays the stable contract between `Quorum` and `Autopilot`

Acceptance:

- one source item can move from brief or issue to PR or handoff without manual glue
- worktree isolation is the default execution path
- provenance is visible in the dashboard and run records

## Phase 5 - OSS Release Surface And Community Readiness

Goal: make the repo understandable and usable by engineers without private branch context.

Changes:

- add open-source release basics:
  - license
  - `CONTRIBUTING`
  - `CODE_OF_CONDUCT`
  - issue and PR templates
  - roadmap
- rewrite the public docs surface around product questions:
  - what it is
  - why it matters
  - quickstart
  - architecture
  - comparison
  - screenshots or GIFs
- add examples:
  - local-only project
  - cloud multi-provider project
  - issue-driven flow
- publish a minimal benchmark and smoke story

Acceptance:

- a new engineer can install and understand the product from docs only
- setup, extension, workflow, and troubleshooting docs exist for external readers
- the positioning against swarm tools and coding copilots is explicit

## Phase 6 - Post-Release Expansion

Goal: grow value after the first serious public release instead of bloating the pre-release scope.

Changes after release:

- VS Code or IDE integration
- richer TUI beyond current `live`
- benchmark harness
- lessons and memory layer
- stronger issue and tracker automations
- marketplace only after the extension contract is stable

Deferred by default unless explicitly promoted:

- symbol-level locks
- file reservations
- Git-backed task tracking mode
- deeper sandbox hardening beyond Docker
- visual workflow editor
- day and night quota scheduling
- proxy-backed provider and cost layer

## Test Plan

- release gate: full local verification baseline green from clean-clone instructions
- trust layer: preview, apply, approval flows plus destructive-action policy coverage
- provider portability: one cloud provider and one local provider on the same workflow contract
- tools and extensibility: register a custom tool, provider, or tracker without core edits
- workflow closure: brief or issue to isolated workspace to run to PR or handoff artifact
- OSS surface: fresh-user quickstart works from docs only

## Assumptions And Defaults

- use a phased plan, not one flat backlog
- implementation comes after the current baseline is frozen and merged
- already-landed branch work is not to be rebuilt
- deterministic orchestration remains the design law; LLMs do task work, not core coordination
- extend existing plugin, provider, and sandbox contracts instead of rebuilding them for architecture purity
- keep `P3` inactive unless a concrete failure mode makes it necessary
