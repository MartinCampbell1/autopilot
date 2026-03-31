# Autopilot — Merged Handoff and Implementation Plan

Date: `2026-03-31`

Primary source docs:

- [2026-03-31-pr-summary.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-pr-summary.md)
- [2026-03-31-branch-completion-note.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-branch-completion-note.md)
- [2026-03-31-control-plane-handoff.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-control-plane-handoff.md)
- [2026-03-31-engineering-backlog.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-engineering-backlog.md)
- [2026-03-31-autopilot-priority-roadmap.md](/Users/martin/multi-agent/docs/plans/2026-03-31-autopilot-priority-roadmap.md)
- [autopilot-design.md](/Users/martin/Desktop/autopilot/docs/autopilot-design.md)
- [phase3-founderos-execution-plane.md](/Users/martin/Desktop/autopilot/docs/phase3-founderos-execution-plane.md)

## Purpose

This is the one-file handoff for the next agent.

It merges:

- the current `control-plane` branch status
- the current immediate UI hardening work
- the broader `Autopilot` platform backlog
- the GitHub-research-driven feature roadmap

Use this as the main doc in the next chat.

## Current Branch / Current Reality

Confirmed current local branch:

- `codex/founderos-control-plane`

Recent local commits:

- `4b9e575` docs: add control plane handoff
- `e518450` feat: add control plane deep link copy actions
- `5d0cd62` feat: sync control plane selection to url
- `b6845b3` refactor: extract control plane page controller

## Where We Are By Phase

- `Phase 1`: closed for current scope
- `Phase 2`: closed for core runtime-control scope
- `Phase 3`: already real and working

## Status Update On This Branch

As of the current `codex/founderos-control-plane` branch state, the active backlog from this handoff is no longer pending.

Already landed on branch:

- control-plane deep-link/share actions for selected action run, selected session context, and runtime agent
- `P0` hardening backlog:
  - doctor/onboarding
  - story dependencies
  - headless/daemon
  - cost accounting
  - trace/replay
  - GitHub PR loop/reactions
  - quality ratcheting
- `P1` backlog:
  - notifier layer
  - plugin/provider interface
  - multi-agent pipeline per story
  - narrower multi-phase review
  - discovery board/context sharing
- `P2` backlog:
  - tracker triggers
  - guided interview/spec bootstrap
  - TUI/live view
  - multi-attempt per task
  - scheduled maintenance runs
- branch-level product verification hardening:
  - repo-local gate execution for headless runs
  - dashboard Next 16/Turbopack stabilization
  - successful operator smoke on API, `/`, and `/control-plane`

That means the remaining items in this document are mostly historical planning context.
The next intentional work should be either:

- review / merge / publish work on the existing branch, or
- an explicit promotion of a `P3` item with justification for why it should become active work now

That means the current work is **not** foundation building from scratch.
It is:

- control-plane hardening
- operator UX refinement
- execution/control-plane completion
- preparing the system to grow without turning monolithic again

## What Is Already Implemented

### Backend / API

- adapter-based provider/runtime architecture
- multi-account preservation and routing
- runtime diagnostics/probes
- ownership leases
- worktree/runtime control primitives
- budgets and auto-pause
- approvals, issues, action runs
- execution-plane API
- orchestrator sessions and control passes
- batch action execution and session-level control plans

### Dashboard / Operator Surface

- serious control-plane page
- session overview/history
- drill-down views
- runtime agent drill-down
- triage inbox
- queue advance notices
- URL-synced selection
- existing copy-link actions for current control context

## Immediate Critical Path

This section is now historical context.
The steps below were the correct next moves when the handoff was first written, but they are already completed on the current branch.

### Track A — Finish Deep-Link / Share Affordances

Implement focused share/open actions for:

- selected action run
- selected session context
- runtime agent

Reuse the existing URL sync and clipboard flow already present in:

- [dashboard/app/control-plane/page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx)
- [dashboard/lib/use-control-plane-page-controller.tsx](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-page-controller.tsx)
- [dashboard/components/control-plane-header-sections.tsx](/Users/martin/Desktop/autopilot/dashboard/components/control-plane-header-sections.tsx)
- [dashboard/components/session-drilldown-control-section.tsx](/Users/martin/Desktop/autopilot/dashboard/components/session-drilldown-control-section.tsx)
- [dashboard/lib/use-control-plane-queue-target-navigation.ts](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-queue-target-navigation.ts)

Primary target files:

- [dashboard/components/selected-action-run-card.tsx](/Users/martin/Desktop/autopilot/dashboard/components/selected-action-run-card.tsx)
- [dashboard/components/selected-session-context-card.tsx](/Users/martin/Desktop/autopilot/dashboard/components/selected-session-context-card.tsx)
- [dashboard/components/runtime-agent-section.tsx](/Users/martin/Desktop/autopilot/dashboard/components/runtime-agent-section.tsx)
- [dashboard/components/runtime-agent-inspector-column.tsx](/Users/martin/Desktop/autopilot/dashboard/components/runtime-agent-inspector-column.tsx)
- [dashboard/lib/control-plane-linking.ts](/Users/martin/Desktop/autopilot/dashboard/lib/control-plane-linking.ts)

Acceptance criteria:

- operator can copy a deep link to the exact selected run
- operator can copy a deep link to the exact selected session context
- operator can copy a deep link to the exact selected runtime agent
- opening the shared link restores the correct focused selection after reload
- notices/errors for clipboard/share are consistent with existing flow

### Track A.1 — Operator Hardening After Share Actions

After the share affordances land, continue with:

- more inspector surfaces becoming URL-aware
- selection restoration after reload/direct entry
- queue focus flow verification after reloads/session switches
- broader UI coverage around linked selection behavior

Primary files:

- [dashboard/lib/use-control-plane-linked-selection.ts](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-linked-selection.ts)
- [dashboard/lib/use-control-plane-view-state.ts](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-view-state.ts)
- [dashboard/lib/use-control-plane-session-lineage-selection.ts](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-session-lineage-selection.ts)
- [dashboard/lib/use-control-plane-run-selection.ts](/Users/martin/Desktop/autopilot/dashboard/lib/use-control-plane-run-selection.ts)

## Broader Platform Plan

This is the merged backlog after the current branch-local control-plane work.

### P0 — Must-Have Platform Hardening

These are the next platform epics once the current share/deep-link task is done.

#### P0.1 `autopilot doctor` + onboarding hardening

Why:

- current repo already has [account_diagnostics.py](/Users/martin/Desktop/autopilot/autopilot/core/account_diagnostics.py)
- current [init_cmd.py](/Users/martin/Desktop/autopilot/autopilot/cli/init_cmd.py) is still too minimal

Target files:

- [autopilot/core/account_diagnostics.py](/Users/martin/Desktop/autopilot/autopilot/core/account_diagnostics.py)
- [autopilot/core/provider_sessions.py](/Users/martin/Desktop/autopilot/autopilot/core/provider_sessions.py)
- [autopilot/core/adapters.py](/Users/martin/Desktop/autopilot/autopilot/core/adapters.py)
- [autopilot/cli/init_cmd.py](/Users/martin/Desktop/autopilot/autopilot/cli/init_cmd.py)
- [autopilot/cli/main.py](/Users/martin/Desktop/autopilot/autopilot/cli/main.py)

Donor repos:

- `Agent Orchestrator`
- `Bernstein`
- `Wiggum CLI`

Key outcomes:

- `autopilot doctor`
- stack/build/test/lint auto-detection
- better first-run experience

#### P0.2 Story dependency graph + auto-unblock

Why:

- already present in design as intent
- not implemented as first-class runtime data

Target files:

- [autopilot/core/project_store.py](/Users/martin/Desktop/autopilot/autopilot/core/project_store.py)
- [autopilot/core/models.py](/Users/martin/Desktop/autopilot/autopilot/core/models.py)
- [autopilot/core/execution_brief.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_brief.py)
- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/dispatcher.py](/Users/martin/Desktop/autopilot/autopilot/core/dispatcher.py)
- [autopilot/cli/run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py)

Donor repos:

- `ClawTeam`

Key outcomes:

- `blocked_by`
- auto-unblock
- dependency-aware parallelism

#### P0.3 Headless mode + service mode

Why:

- current runtime is already strong enough for server/daemon use
- CLI surface is still too terminal-attended

Target files:

- [autopilot/cli/run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py)
- [autopilot/cli/main.py](/Users/martin/Desktop/autopilot/autopilot/cli/main.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/headless.py`
- new: `/Users/martin/Desktop/autopilot/deploy/systemd/autopilot.service`
- new: `/Users/martin/Desktop/autopilot/deploy/launchd/com.autopilot.plist`

Donor repos:

- `Conclave`
- `Bernstein`
- `sleepless-agent`
- `Symphony`

Key outcomes:

- `autopilot run --headless`
- JSON summaries
- restartable daemon/service mode

#### P0.4 Cost and token accounting

Why:

- budgets exist
- spend observability does not

Target files:

- [autopilot/core/runtime_budgets.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_budgets.py)
- [autopilot/core/loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py)
- [autopilot/core/critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py)
- [autopilot/core/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py)
- [autopilot/cli/run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/cost_accounting.py`

Donor repos:

- `Bernstein`
- `Conclave`
- `tokscale`
- `ccusage`

Key outcomes:

- per-run / per-story / per-project cost summaries
- CLI/API/dashboard cost visibility

#### P0.5 Worker trace + forensic replay

Why:

- execution-plane audit exists
- worker-loop trace does not

Target files:

- [autopilot/core/loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py)
- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py)
- [autopilot/core/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py)
- [dashboard/components/runtime-agent-activity-section.tsx](/Users/martin/Desktop/autopilot/dashboard/components/runtime-agent-activity-section.tsx)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/run_trace.py`
- new: `/Users/martin/Desktop/autopilot/autopilot/cli/trace.py`

Donor repos:

- `Bernstein`
- `Trigger.dev`
- `OpenHands`

Key outcomes:

- structured worker iteration journal
- `autopilot trace`
- replayable forensic view

#### P0.6 GitHub PR loop + reactions engine

Why:

- biggest gap versus external delivery loop

Target files:

- [autopilot/core/worktree.py](/Users/martin/Desktop/autopilot/autopilot/core/worktree.py)
- [autopilot/core/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/core/execution_plane.py)
- [autopilot/core/control_plane_issues.py](/Users/martin/Desktop/autopilot/autopilot/core/control_plane_issues.py)
- [autopilot/api/routes/execution_plane.py](/Users/martin/Desktop/autopilot/autopilot/api/routes/execution_plane.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/github_prs.py`
- new: `/Users/martin/Desktop/autopilot/autopilot/core/github_reactions.py`

Donor repos:

- `Agent Orchestrator`
- `Open SWE`
- `OpenHands`
- `Symphony`

Key outcomes:

- branch-per-story
- PR metadata
- CI fail/review comment/approved-and-green reactions

#### P0.7 Quality ratcheting

Why:

- small change, large trust gain

Target files:

- [autopilot/core/gates.py](/Users/martin/Desktop/autopilot/autopilot/core/gates.py)
- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py)

Donor repos:

- `toryo`

Key outcomes:

- quality can improve or hold
- never silently degrade

### P1 — Throughput and Operability Upgrades

#### P1.1 Generalized notifier layer

Current grounding:

- [autopilot/core/notifier.py](/Users/martin/Desktop/autopilot/autopilot/core/notifier.py) is effectively Telegram-only today

Target files:

- [autopilot/core/notifier.py](/Users/martin/Desktop/autopilot/autopilot/core/notifier.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/notifiers.py`

Donor repos:

- `ralphex`
- `Untether`

#### P1.2 Minimal plugin/provider interface

Target files:

- [autopilot/core/adapters.py](/Users/martin/Desktop/autopilot/autopilot/core/adapters.py)
- [autopilot/core/providers.py](/Users/martin/Desktop/autopilot/autopilot/core/providers.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/plugins.py`

Donor repos:

- `Agent Orchestrator`

#### P1.3 Multi-agent pipeline per story

Target files:

- [autopilot/core/loop_runner.py](/Users/martin/Desktop/autopilot/autopilot/core/loop_runner.py)
- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/runtime_agents.py](/Users/martin/Desktop/autopilot/autopilot/core/runtime_agents.py)

Donor repos:

- `agtx`
- `MassGen`

#### P1.4 Narrower multi-phase review

Start with:

- security
- architecture
- tests

Target files:

- [autopilot/core/critic.py](/Users/martin/Desktop/autopilot/autopilot/core/critic.py)
- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)

Donor repos:

- `ralphex`
- `Conclave`

#### P1.5 Discovery board / context sharing

Target files:

- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/project_store.py](/Users/martin/Desktop/autopilot/autopilot/core/project_store.py)

Donor repos:

- `Conclave`

### P2 — Useful Later, Not Immediate

- tracker triggers: GitHub Issues / Linear / Jira
- guided interview -> spec bootstrap
- TUI view
- multi-attempt per task
- scheduled maintenance runs
- optional proxy-backed accounting/provider layer

Primary donors:

- `Open SWE`
- `Operum`
- `Wiggum CLI`
- `Bernstein`
- `agtx`
- `Forge`
- `Untether`
- `Trigger.dev`
- `codex-lb`
- `CLIProxyAPI`

### P3 — Preserve, Do Not Actively Build Yet

- day/night quota scheduling
- file reservations
- symbol-level locks
- Git-backed task tracking mode
- deeper sandbox hardening beyond Docker
- visual workflow editor
- GitHub label pipeline mode
- handoff/assign/send-message orchestration vocabulary

Primary donors:

- `sleepless-agent`
- `swarm-tools`
- `wit`
- `GNAP`
- `Greywall`
- `nono`
- `VibeGrid`
- AWS CLI Agent Orchestrator patterns

## Recommended Next-Agent Execution Order

1. Read this file.
2. Read [2026-03-31-control-plane-handoff.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-control-plane-handoff.md).
3. Treat `Track A`, `P0`, `P1`, and `P2` in this document as already implemented on the branch unless a regression proves otherwise.
4. If more branch work is needed, bias toward verification, cleanup, PR prep, or missing test coverage around the new surfaces.
5. Do not start `P3` work by default. Promote a `P3` item only if there is a concrete failure mode or operator need that justifies it now.

## Ready Prompt For The New Chat

Use this if you want the next agent to continue from the current truth instead of rebuilding context:

> Continue from [2026-03-31-merged-handoff-and-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-merged-handoff-and-plan.md). We are in Phase 3 hardening on branch `codex/founderos-control-plane`. First finish deep-link/share actions for selected action run, selected session context, and runtime agent using the existing control-plane URL sync and clipboard flow. After that, continue the P0 backlog in order: doctor/onboarding, story dependencies, headless/daemon, cost accounting, trace/replay, GitHub PR loop/reactions, quality ratcheting.

Updated prompt for the current branch truth:

> Continue from [2026-03-31-merged-handoff-and-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-merged-handoff-and-plan.md). We are on branch `codex/founderos-control-plane`. The control-plane deep-link work plus the active `P0`, `P1`, and `P2` backlog items are already landed on this branch. Do not repeat them. Verify and stabilize the current branch, or explicitly justify promoting a `P3` item before building more surface area.

## Notes

- The repo is currently dirty. Do not run destructive cleanup.
- There are unrelated untracked artifacts in the repo. Ignore them unless the task directly touches them.
- Keep the current control-plane architecture thin and modular. Do not collapse the extracted hooks/components back into the page shell.
