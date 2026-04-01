# Control Plane Handoff

Date: 2026-03-31

> Historical architecture handoff. For new work use [2026-03-31-next-product-plan.md](2026-03-31-next-product-plan.md) as the canonical next-step plan.

Branch: `codex/founderos-control-plane`

Local HEAD when this handoff was written: `e518450`

Latest published remote before this handoff commit: `7899cfa40642cc446b52a4e02978c764a433f8ca`

Status update on current branch:

- the deep-link/share actions called out below are already implemented
- the broader active backlog after this handoff has also been executed on `codex/founderos-control-plane`
- use the remaining sections here as architectural context, not as an up-to-date todo list

## Where We Are

This is no longer early foundation work.

- `Phase 1` is effectively closed for the current scope.
- `Phase 2` is effectively closed for the core runtime-control scope.
- `Phase 3` is already real and working. Current work is mostly:
  - operator UX hardening
  - execution/control-plane usability
  - cleanup/refactor so the UI can keep growing without turning back into a monolith

The system is already strong enough to demo honestly as:

- `Autopilot` = execution/control plane
- `FounderOS` = orchestration and operator layer on top of Autopilot
- `Quorum` = upstream intelligence / selection / decision layer

This is not “unbuilt”. It is in the “working and increasingly hardened” stage.

## What Is Already Implemented

### Backend / API

- Adapter-based provider/runtime architecture
- Multi-account preservation
- Runtime diagnostics/probes
- Ownership leases
- Atomic checkout intent
- Budgets and auto-pause
- Workspace/worktree inspection and recovery
- Execution-plane API for FounderOS-facing orchestration
- Sessions, approvals, issues, runtime agents, action runs, control passes
- Batch action execution and policy-driven orchestration
- Persisted run/control-pass history
- Session-level control/recommendation flows

Key docs:

- `docs/phase1-adapter-foundation.md`
- `docs/phase2-runtime-control-primitives.md`
- `docs/phase3-founderos-execution-plane.md`
- `docs/phase4-approval-foundation.md`
- `docs/execution-brief-bridge.md`

### Dashboard / Operator Surface

The dashboard now includes a serious `Control Plane` UI with:

- session overview/history
- session drill-down
- linked approvals/issues/events
- selected action run and outcome inspection
- runtime agent drill-down
- agent timeline and priority queues
- session lineage
- triage inbox
- queue advance notices
- deep linked selection via URL
- copy-link actions in header and session drill-down

Recent product-facing addition:

- deep-linkable selection and copy-link actions for current control context

## Current UI Architecture

The control-plane page is no longer a huge monolithic component.

### Thin Page Shell

- `dashboard/app/control-plane/page.tsx`

This is now a thin shell that:

- reads URL query params
- mounts the controller
- syncs selected ids back into the URL
- renders loading/layout shells

### Main Coordinator

- `dashboard/lib/use-control-plane-page-controller.tsx`

This is now the main coordinator hook instead of burying everything in the page file.

### Extracted Hooks / Logic

- `dashboard/lib/use-control-plane-actions.ts`
- `dashboard/lib/use-control-plane-agent-navigation.ts`
- `dashboard/lib/use-control-plane-agent-priority-queues.ts`
- `dashboard/lib/use-control-plane-bootstrap.ts`
- `dashboard/lib/use-control-plane-data-loader.ts`
- `dashboard/lib/use-control-plane-linked-selection.ts`
- `dashboard/lib/use-control-plane-operator-persistence.ts`
- `dashboard/lib/use-control-plane-page-controller.tsx`
- `dashboard/lib/use-control-plane-queue-advance.ts`
- `dashboard/lib/use-control-plane-queue-target-navigation.ts`
- `dashboard/lib/use-control-plane-reveal-flows.ts`
- `dashboard/lib/use-control-plane-run-selection.ts`
- `dashboard/lib/use-control-plane-runtime-agent-model.ts`
- `dashboard/lib/use-control-plane-runtime-agent-props.ts`
- `dashboard/lib/use-control-plane-session-drilldown-props.ts`
- `dashboard/lib/use-control-plane-session-lineage-model.ts`
- `dashboard/lib/use-control-plane-session-lineage-queues.ts`
- `dashboard/lib/use-control-plane-session-overview-model.ts`
- `dashboard/lib/use-control-plane-triage-inbox.ts`
- `dashboard/lib/use-control-plane-view-state.ts`
- `dashboard/lib/control-plane-data.ts`
- `dashboard/lib/control-plane-linking.ts`
- `dashboard/lib/control-plane-models.ts`
- `dashboard/lib/control-plane-operator-state.ts`
- `dashboard/lib/control-plane-section-props.tsx`
- `dashboard/lib/control-plane-session-drilldown-props.ts`
- `dashboard/lib/control-plane-triage.ts`
- `dashboard/lib/control-plane-ui.ts`

### Extracted Components

- `dashboard/components/control-plane-header-sections.tsx`
- `dashboard/components/control-plane-layout.tsx`
- `dashboard/components/control-plane-loading-shell.tsx`
- `dashboard/components/control-plane-main-sections.tsx`
- `dashboard/components/control-plane-overview-sections.tsx`
- `dashboard/components/control-plane-workspace-section.tsx`
- `dashboard/components/linked-decisions-card.tsx`
- `dashboard/components/queue-advance-notice.tsx`
- `dashboard/components/queue-panels.tsx`
- `dashboard/components/runtime-agent-activity-section.tsx`
- `dashboard/components/runtime-agent-inspector-column.tsx`
- `dashboard/components/runtime-agent-section.tsx`
- `dashboard/components/runtime-agent-timeline-section.tsx`
- `dashboard/components/selected-action-run-card.tsx`
- `dashboard/components/selected-control-pass-card.tsx`
- `dashboard/components/selected-outcome-inspector.tsx`
- `dashboard/components/selected-session-context-card.tsx`
- `dashboard/components/session-drilldown-activity-section.tsx`
- `dashboard/components/session-drilldown-control-section.tsx`
- `dashboard/components/session-drilldown-section.tsx`
- `dashboard/components/session-lineage-section.tsx`
- `dashboard/components/triage-inbox-section.tsx`

## Current Product State

The control plane is already good enough to:

- inspect session-level control state
- drive approvals/issues/actions
- inspect runs/outcomes/agents
- triage attention and decision queues
- hand off specific contexts through deep links

This means the current work is mostly refinement and hardening, not basic implementation.

## Immediate Remaining Front

This section is now mostly historical.
The highest-priority share/deep-link work described here was completed later on the same branch.

### 1. Finish Share / Deep-Link Affordances

The URL sync is in place and copy-link actions now exist in:

- `dashboard/components/control-plane-header-sections.tsx`
- `dashboard/components/session-drilldown-control-section.tsx`

This share/handoff work has now landed:

- copy/open focused link actions in:
  - `dashboard/components/selected-action-run-card.tsx`
  - `dashboard/components/selected-session-context-card.tsx`
  - `dashboard/components/runtime-agent-section.tsx`
- restore exact inspected selection after reload/share for those surfaces

If more control-plane work is needed now, it should be verification-focused:

- broader UI-level coverage around control-plane flows
- selection restoration tests after reload/direct entry
- queue-focus and notice/feedback verification under session switches
- API payload consistency checks for execution-plane surfaces

### 2. Operator Hardening

After the share actions, the next UX hardening steps are:

- make more inspector surfaces URL-aware and sharable
- ensure selection survives navigation/handoff in a predictable way
- tighten clipboard and notice/error behavior
- verify linked-selection / queue focus flows after reloads and direct deep-link entry

### 3. UI Test / Workflow Hardening

The dashboard build is green, but the next serious hardening layer should include:

- broader UI-level coverage around control-plane flows
- verification of deep-link entry behavior
- verification of session/agent/run/pass selection restoration
- inspection of queue notice/feedback flows under reloads and session switches

### 4. Backend / API Hardening

The backend is already strong, but still worth tightening:

- broader tests around execution-plane contract stability
- more edge-case coverage around action runs, sessions, approvals, issues
- review of event payload consistency

### 5. Later Work, Not Immediate

This is still mostly not started:

- plugin / extension layer

That remains a later phase, not the current critical path.

## Recommended First Task In The New Chat

Start with this:

1. Read this file.
2. Continue from the current branch.
3. Treat the deep-link/share task in this handoff as already done.
4. Use this doc for control-plane architecture context and focus only on verification, regression fixes, or explicit new requirements.

If you want a one-line prompt for the next chat, use:

> Continue from `docs/2026-03-31-control-plane-handoff.md`. We are still in `Phase 3` hardening on branch `codex/founderos-control-plane`, but the deep-link/share actions described in that handoff are already implemented. Use the doc as architecture context and focus only on verification, regression fixes, or explicitly justified new work.

## Notes / Caveats

- There are unrelated untracked artifacts in the repo. Do not touch them unless explicitly asked.
- In this environment, direct `git push` has sometimes been unreliable, so publishing via patch + temp clone has been the safe path.
- `dashboard/.next.broken-20260329/` exists as unrelated noise and can pollute full-lint behavior.
