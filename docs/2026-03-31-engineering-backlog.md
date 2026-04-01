# Autopilot — Engineering Backlog

Snapshot date: `2026-03-31`

Related docs:

- [README.md](../README.md)
- [docs/autopilot-design.md](autopilot-design.md)
- [docs/autopilot-implementation-plan.md](autopilot-implementation-plan.md)
- [docs/phase1-adapter-foundation.md](phase1-adapter-foundation.md)
- [docs/phase2-runtime-control-primitives.md](phase2-runtime-control-primitives.md)
- [docs/phase3-founderos-execution-plane.md](phase3-founderos-execution-plane.md)
- [docs/phase4-approval-foundation.md](phase4-approval-foundation.md)

## Purpose

This is the execution-grade backlog for `Autopilot`.

It translates the roadmap into:

- epics
- implementation stories
- concrete target files in the current repo
- donor repos/patterns
- acceptance criteria

This backlog is based on the **current** state of `/Users/martin/Desktop/autopilot`, not on older snapshots.

## Status Update On `codex/founderos-control-plane`

This backlog remains useful as scope/history, but it is no longer a pure todo list for the current branch.

Already implemented on `codex/founderos-control-plane`:

- `P0`:
  - cost and usage accounting
  - worker trace and forensic replay
  - GitHub PR loop and reactions engine
  - headless mode and serviceability
  - OSS doctor and onboarding hardening
  - story dependency graph
- `P1`:
  - minimal plugin/provider interface
  - operator notifications/review surfaces
  - quality ratcheting
  - multi-agent pipeline per story
  - narrower multi-phase review
  - discovery board/context sharing
- `P2`:
  - tracker triggers
  - guided interview/spec bootstrap
  - TUI/live view
  - multi-attempt per task
  - scheduled maintenance runs

Current stabilization baseline on this branch:

- `./.venv/bin/python -m pytest -q` -> `277 passed`
- `npm run build` in `dashboard` -> passed
- `npm run lint` in `dashboard` -> passed after ignoring the unrelated generated artifact dir `.next.broken-20260329`

Treat the remaining stories below as planning context unless a regression reopens them or a new branch explicitly chooses to extend them.

## Current State Summary

The current repo is already well beyond the early MVP plan.

Confirmed present:

- multi-account pool and provider rotation
- escalation chain
- worker -> gates -> critic loop
- typed adapter foundation
- runtime budgets + auto-pause
- approvals/issues/action runs/orchestrator sessions/control passes
- execution-plane API for FounderOS
- large operator dashboard surface
- persisted account diagnostics/probe snapshots

Important grounding:

- [autopilot/core/account_diagnostics.py](../autopilot/core/account_diagnostics.py)
- [autopilot/core/adapters.py](../autopilot/core/adapters.py)
- [autopilot/core/execution_plane.py](../autopilot/core/execution_plane.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)
- [autopilot/core/loop_runner.py](../autopilot/core/loop_runner.py)
- [autopilot/cli/run.py](../autopilot/cli/run.py)
- [dashboard/app/control-plane/page.tsx](../dashboard/app/control-plane/page.tsx)

## Gaps This Backlog Focuses On

The current repo still has the biggest gaps in:

- cost visibility
- worker-loop traceability
- GitHub/CI/review feedback closure
- headless/server mode
- OSS diagnostics and onboarding
- dependency-aware parallelism
- notifier/service hardening

## Priority Order

- `P0`: required to make Autopilot feel like a serious OSS execution plane
- `P1`: next layer that materially improves usability and throughput
- `P2`: useful later, but not required for the first strong public release
- `P3`: preserve as future directions, not active build targets yet

---

## P0 Epic 1 — Cost and Usage Accounting

### Why

Autopilot already tracks iteration budgets, but not real provider/account/model cost visibility.

### Story 1.1 — Add a run cost model

Target files:

- [autopilot/core/models.py](../autopilot/core/models.py)
- [autopilot/core/runtime_budgets.py](../autopilot/core/runtime_budgets.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/cost_accounting.py`

Donor repos:

- `Bernstein`
- `Conclave`
- `tokscale`

Acceptance criteria:

- define a typed cost summary for run/story/project scope
- support `provider`, `adapter_id`, `account/profile`, `model`, `estimated_cost`, `token counts when available`
- missing token data does not fail the run

### Story 1.2 — Persist usage on worker and critic iterations

Target files:

- [autopilot/core/loop_runner.py](../autopilot/core/loop_runner.py)
- [autopilot/core/critic.py](../autopilot/core/critic.py)
- [autopilot/core/execution_plane.py](../autopilot/core/execution_plane.py)

Donor repos:

- `Bernstein`
- `ccusage`
- `toktrack`

Acceptance criteria:

- each worker/critic iteration emits a usage payload
- execution-plane project detail exposes aggregate cost summary
- per-agent and per-project rollups are queryable

### Story 1.3 — Add CLI and API surfaces for cost inspection

Target files:

- [autopilot/cli/main.py](../autopilot/cli/main.py)
- [autopilot/cli/run.py](../autopilot/cli/run.py)
- [autopilot/api/routes/projects.py](../autopilot/api/routes/projects.py)
- [dashboard/lib/api.ts](../dashboard/lib/api.ts)

Donor repos:

- `Bernstein`
- `CodexBar`

Acceptance criteria:

- `autopilot cost` exists
- API returns project/session cost summaries
- dashboard can show spend without custom manual inspection

---

## P0 Epic 2 — Worker Trace and Forensic Replay

### Why

The repo has action-run replay and execution-plane audit surfaces, but still lacks a proper worker-loop trace.

### Story 2.1 — Add structured worker iteration journal

Target files:

- [autopilot/core/loop_runner.py](../autopilot/core/loop_runner.py)
- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/critic.py](../autopilot/core/critic.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/run_trace.py`

Donor repos:

- `Bernstein`
- `Trigger.dev`
- `OpenHands`

Acceptance criteria:

- each iteration records prompt type, provider/account, gate results, critic result, timing, escalation state
- traces are stored as structured JSON, not only human logs
- no regression in current `.ralph/*` files

### Story 2.2 — Expose trace CLI

Target files:

- [autopilot/cli/main.py](../autopilot/cli/main.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/cli/trace.py`

Donor repos:

- `Bernstein`

Acceptance criteria:

- `autopilot trace <project|story|run>` shows chronological iteration history
- output remains readable in plain terminal

### Story 2.3 — Add forensic replay view

Target files:

- [autopilot/core/run_trace.py](../autopilot/core/run_trace.py)
- [autopilot/core/execution_plane.py](../autopilot/core/execution_plane.py)
- [dashboard/components/runtime-agent-activity-section.tsx](../dashboard/components/runtime-agent-activity-section.tsx)

Donor repos:

- `Bernstein`
- `OpenHands`

Acceptance criteria:

- past run can be replayed as a step-by-step trace view
- this is clearly labeled as forensic replay, not deterministic rerun

---

## P0 Epic 3 — GitHub PR Loop and Reactions Engine

### Why

This is the single biggest external-loop gap versus stronger competitors.

### Story 3.1 — Introduce branch-per-story + PR lifecycle

Target files:

- [autopilot/core/worktree.py](../autopilot/core/worktree.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)
- [autopilot/core/execution_plane.py](../autopilot/core/execution_plane.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/github_prs.py`

Donor repos:

- `Agent Orchestrator`
- `Open SWE`
- `OpenHands`

Acceptance criteria:

- story can map to a stable branch name
- PR metadata can be stored in runtime state
- merge/manual handoff state is explicit

### Story 3.2 — Add CI/review reaction handling

Target files:

- [autopilot/core/control_plane_issues.py](../autopilot/core/control_plane_issues.py)
- [autopilot/core/execution_plane.py](../autopilot/core/execution_plane.py)
- [autopilot/api/routes/execution_plane.py](../autopilot/api/routes/execution_plane.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/github_reactions.py`

Donor repos:

- `Agent Orchestrator`
- `Symphony`

Acceptance criteria:

- support at least:
  - `ci_failed`
  - `review_comment_received`
  - `changes_requested`
  - `approved_and_green`
- events route back to the owning story/run/issue
- safe auto-resume is policy-controlled

### Story 3.3 — Surface PR state in dashboard

Target files:

- [dashboard/lib/control-plane-models.ts](../dashboard/lib/control-plane-models.ts)
- [dashboard/components/story-detail-panel.tsx](../dashboard/components/story-detail-panel.tsx)
- [dashboard/components/runtime-agent-inspector-column.tsx](../dashboard/components/runtime-agent-inspector-column.tsx)

Donor repos:

- `Agent Orchestrator`
- `Open SWE`

Acceptance criteria:

- operator can see PR link/status, CI state, review state
- review-triggered issues/approvals appear in existing triage surfaces

---

## P0 Epic 4 — Headless Mode and Serviceability

### Why

Autopilot currently assumes attended terminal flows too much for what it already is architecturally.

### Story 4.1 — Add `--headless` execution mode

Target files:

- [autopilot/cli/main.py](../autopilot/cli/main.py)
- [autopilot/cli/run.py](../autopilot/cli/run.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/headless.py`

Donor repos:

- `Conclave`
- `Bernstein`

Acceptance criteria:

- `autopilot run --headless` works without rich interactive assumptions
- emits structured JSON summary
- returns meaningful exit codes

### Story 4.2 — Add daemon/service mode

Target files:

- [autopilot/cli/run.py](../autopilot/cli/run.py)
- new: `/Users/martin/Desktop/autopilot/deploy/systemd/autopilot.service`
- new: `/Users/martin/Desktop/autopilot/deploy/launchd/com.autopilot.plist`

Donor repos:

- `sleepless-agent`
- `Symphony`

Acceptance criteria:

- documented service install for macOS and Linux
- process can restart on failure
- logs are structured enough for later inspection

---

## P0 Epic 5 — OSS Doctor and Onboarding Hardening

### Why

The repo already has persisted probe logic in [account_diagnostics.py](../autopilot/core/account_diagnostics.py), but not a real user-facing `doctor`.

### Story 5.1 — Promote diagnostics into `autopilot doctor`

Target files:

- [autopilot/core/account_diagnostics.py](../autopilot/core/account_diagnostics.py)
- [autopilot/core/adapters.py](../autopilot/core/adapters.py)
- [autopilot/core/provider_sessions.py](../autopilot/core/provider_sessions.py)
- [autopilot/cli/main.py](../autopilot/cli/main.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/cli/doctor.py`

Donor repos:

- `Agent Orchestrator`
- `Bernstein`

Acceptance criteria:

- `autopilot doctor` checks profiles, binaries, git, Ralph, runtime homes, stale worktree/lease issues
- output clearly distinguishes `ok`, `warning`, `error`
- safe follow-up suggestions are included

### Story 5.2 — Upgrade `autopilot init`

Current grounding:

- [autopilot/cli/init_cmd.py](../autopilot/cli/init_cmd.py) is currently minimal

Target files:

- [autopilot/cli/init_cmd.py](../autopilot/cli/init_cmd.py)
- [autopilot/core/project_bootstrap.py](../autopilot/core/project_bootstrap.py)
- [autopilot/core/adapters.py](../autopilot/core/adapters.py)

Donor repos:

- `Wiggum CLI`

Acceptance criteria:

- detects likely stack/build/test/lint commands
- writes useful defaults instead of only running `ralph install`
- still works for greenfield repos and existing repos

---

## P0 Epic 6 — Story Dependency Graph

### Why

This is already present as design intent in [docs/autopilot-design.md](autopilot-design.md), but not as an implemented runtime model.

### Story 6.1 — Extend story schema with dependencies

Target files:

- [autopilot/core/project_store.py](../autopilot/core/project_store.py)
- [autopilot/core/models.py](../autopilot/core/models.py)
- [autopilot/core/execution_brief.py](../autopilot/core/execution_brief.py)

Donor repos:

- `ClawTeam`

Acceptance criteria:

- stories may declare `blocked_by`
- normalized PRD preserves dependency information
- impossible/self-cyclic references are rejected

### Story 6.2 — Enforce dependency-aware scheduling

Target files:

- [autopilot/cli/run.py](../autopilot/cli/run.py)
- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/dispatcher.py](../autopilot/core/dispatcher.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)

Donor repos:

- `ClawTeam`
- existing local design note

Acceptance criteria:

- blocked stories are never started early
- completion auto-unblocks dependents
- unrelated stories continue when one branch is stuck/escalating

---

## P1 Epic 7 — Minimal Plugin/Provider Interface

### Why

The current adapter layer is good, but still too tied to the existing provider families.

### Story 7.1 — Formalize minimal plugin slots

Target files:

- [autopilot/core/adapters.py](../autopilot/core/adapters.py)
- [autopilot/core/providers.py](../autopilot/core/providers.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/plugins.py`

Donor repos:

- `Agent Orchestrator`

Acceptance criteria:

- support minimal slots:
  - `AgentProvider`
  - `Runtime`
  - `Tracker`
  - `Notifier`
- existing `codex`, `claude`, `gemini` continue working unchanged

### Story 7.2 — Add at least one non-core provider adapter path

Target files:

- [autopilot/core/adapters.py](../autopilot/core/adapters.py)
- [tests/test_providers.py](../tests/test_providers.py)

Donor repos:

- `agtx`
- `Open SWE`

Acceptance criteria:

- one additional provider path can be added without special-casing the whole codebase

---

## P1 Epic 8 — Operator Notifications and Review Surfaces

### Why

Current notifier support is effectively Telegram-only and too narrow.

### Story 8.1 — Generalize notifier abstraction

Current grounding:

- [autopilot/core/notifier.py](../autopilot/core/notifier.py) is Telegram-specific today

Target files:

- [autopilot/core/notifier.py](../autopilot/core/notifier.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/notifiers.py`
- [tests/test_notifier.py](../tests/test_notifier.py)

Donor repos:

- `ralphex`
- `Untether`

Acceptance criteria:

- support Telegram, Slack webhook, email or custom webhook/script
- notification routing is config-driven

### Story 8.2 — Add narrower multi-phase review

Target files:

- [autopilot/core/critic.py](../autopilot/core/critic.py)
- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [tests/test_critic.py](../tests/test_critic.py)

Donor repos:

- `ralphex`
- `Conclave`

Acceptance criteria:

- optional review fan-out for:
  - security
  - architecture
  - tests
- aggregate one final verdict surface for the operator

---

## P1 Epic 9 — Quality Ratcheting

### Why

This is a high-leverage small change.

### Story 9.1 — Detect quality regressions across iterations

Target files:

- [autopilot/core/gates.py](../autopilot/core/gates.py)
- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/loop_runner.py](../autopilot/core/loop_runner.py)

Donor repos:

- `toryo`

Acceptance criteria:

- if a required gate was green and becomes red, the iteration is marked as a regression
- operator can distinguish regression from first-time failure

### Story 9.2 — Add safe regression handling policy

Target files:

- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)

Donor repos:

- `toryo`

Acceptance criteria:

- configurable behavior:
  - block and retry
  - quarantine for manual attention
- auto-revert is deferred until explicitly enabled

---

## P1 Epic 10 — Multi-Agent Pipeline per Story

### Why

The runtime is still mostly "one worker does most of the execution."

### Story 10.1 — Add optional research -> implement -> review pipeline

Target files:

- [autopilot/core/loop_runner.py](../autopilot/core/loop_runner.py)
- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/runtime_agents.py](../autopilot/core/runtime_agents.py)

Donor repos:

- `agtx`
- `MassGen`

Acceptance criteria:

- one story can optionally run through multiple role-specific passes
- pipeline configuration remains per-story or per-launch-profile, not globally hardcoded

### Story 10.2 — Add discovery board/context sharing

Target files:

- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)
- [dashboard/components/runtime-agent-activity-section.tsx](../dashboard/components/runtime-agent-activity-section.tsx)

Donor repos:

- `Conclave`

Acceptance criteria:

- discoveries can be stored and surfaced as structured markers
- later stories can receive accumulated warnings/intents/constraints

---

## P2 Epic 11 — Better Triggering and Task Intake

### Story 11.1 — Add tracker triggers

Target files:

- [autopilot/api/main.py](../autopilot/api/main.py)
- [autopilot/core/project_store.py](../autopilot/core/project_store.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/api/routes/integrations.py`

Donor repos:

- `Open SWE`
- `Operum`
- `Agent Orchestrator`

Acceptance criteria:

- support GitHub Issues first
- Linear/Jira can be added without redesign

### Story 11.2 — Add guided interview -> spec bootstrap

Target files:

- [autopilot/core/intake.py](../autopilot/core/intake.py)
- [autopilot/cli/init_cmd.py](../autopilot/cli/init_cmd.py)
- [dashboard/components/intake-chat.tsx](../dashboard/components/intake-chat.tsx)

Donor repos:

- `Wiggum CLI`

Acceptance criteria:

- user can generate a better initial spec without manually editing JSON first

---

## P2 Epic 12 — Runtime Expansion

### Story 12.1 — Add TUI view

Target files:

- new: `/Users/martin/Desktop/autopilot/autopilot/cli/live.py`

Donor repos:

- `Bernstein`
- `agtx`

Acceptance criteria:

- SSH-friendly live view of projects/stories/runs

### Story 12.2 — Add multi-attempt per task

Target files:

- [autopilot/core/orchestrator.py](../autopilot/core/orchestrator.py)
- [autopilot/core/escalation.py](../autopilot/core/escalation.py)

Donor repos:

- `Forge`

Acceptance criteria:

- bounded alternate attempts can compete on one task
- best valid outcome wins by policy

### Story 12.3 — Add scheduled maintenance runs

Target files:

- [autopilot/cli/run.py](../autopilot/cli/run.py)
- new: `/Users/martin/Desktop/autopilot/autopilot/core/scheduler.py`

Donor repos:

- `Untether`
- `Trigger.dev`

Acceptance criteria:

- recurring maintenance workflow can be scheduled without manual shell loops

---

## P3 Epic 13 — Advanced Safety and Coordination

These are preserved, but not recommended before the earlier epics land.

### Candidates

- file reservation system
- symbol-level locks
- Git-backed task tracking mode
- deeper sandbox hardening beyond Docker
- visual workflow editor
- day/night quota scheduling
- optional proxy-backed provider/cost layer

Primary donor repos:

- `swarm-tools`
- `wit`
- `GNAP`
- `Greywall`
- `nono`
- `VibeGrid`
- `sleepless-agent`
- `codex-lb`
- `CLIProxyAPI`

Acceptance criteria for promotion to active backlog:

- a concrete failure mode in the current repo justifies the extra complexity

---

## Suggested Execution Order

1. `P0 Epic 5` — doctor and onboarding
2. `P0 Epic 6` — story dependency graph
3. `P0 Epic 4` — headless + daemon foundations
4. `P0 Epic 1` — cost accounting
5. `P0 Epic 2` — trace and replay
6. `P0 Epic 3` — GitHub PR loop and reactions
7. `P1 Epic 9` — quality ratcheting
8. `P1 Epic 8` — notifications and narrower multi-review
9. `P1 Epic 7` — minimal plugin/provider interface
10. `P1 Epic 10` — multi-agent pipeline and discovery board

## Notes On Current Repo Hygiene

The repo is currently not clean.
Observed nontrivial dirty state includes:

- modified dashboard control-plane page
- untracked `src/`
- untracked `.venv`
- untracked experimental files like `providers 2.py`

That does **not** block this backlog, but it does mean implementation work should avoid accidental cleanup or destructive resets.
