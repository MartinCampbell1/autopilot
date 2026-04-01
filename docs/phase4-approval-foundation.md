# Phase 4: Approval Foundation

This is the first non-invasive approval layer for the execution plane.

## What landed

- file-backed approval records in control-plane state
- file-backed execution issues linked to commands and approvals
- explicit external commands for execution projects
- project-level command policy
- optional runtime-agent linkage for approvals and issues
- approve / reject / apply transitions
- event emission for:
  - `approval_requested`
  - `approval_approved`
  - `approval_rejected`
  - `approval_applied`
  - `execution_issue_created`
  - `execution_issue_resolved`

## Supported commands

- `launch`
- `pause`
- `resume`
- `archive`
- `update_budget_policy`

## Why this shape

- It does not force approvals into the current dashboard or runtime loop.
- It is simple enough for FounderOS or another orchestrator to adopt immediately.
- It creates a stable primitive that can later evolve into richer `issue` / `approval` / `company` models.
- It allows policy-based escalation for risky launches and budget changes instead of relying only on manual `require_approval`.

## Runtime-linked issues

Execution issues are now also created from runtime signals such as:

- `worker_failed`
- `story_gate_failed`
- `critic_rejected`
- `story_stuck`
- `story_merge_blocked`
- `budget_paused`
- `run_failed`

And resolved automatically on recovery events such as:

- `story_done`
- `story_skipped`
- `checkout_recovered`
- `run_started`
- `resumed`
- `run_finished`

Each issue now carries richer payload:

- `root_cause`
- `source_event`
- structured `context`

Runtime contexts include project status plus story, checkout, worker/critic, and budget metadata when available.

When runtime events provide structured extras, issue creation now preserves them. In practice this means gate failures keep the failing gate name/output, merge-blocked issues keep branch/worktree context, and connector failures keep activation error detail instead of collapsing everything into a flat message.

When the affected execution scope is known, approvals and issues now also preserve stable runtime-agent references:

- `runtime_agent_id` for single-agent runtime issues
- `runtime_agent_ids` for multi-agent approval scopes such as pausing an active story run

That same linkage now powers agent-centric detail views in the execution plane, so FounderOS can inspect one runtime agent and see its related issues, approvals, and events together.

Execution-plane agent views now also derive policy-aware `suggested_commands`, including whether each suggestion would require approval under the current project command policy. That lets an upstream orchestrator distinguish between direct execution candidates and approval-gated next actions without reimplementing policy checks.

That same policy signal now drives `POST /api/execution-plane/agents/actions/execute`: an orchestrator can submit one flattened action key in `auto` mode, and the execution plane will either execute the safe command immediately or create a linked approval flow when policy says the action must be gated.

That orchestration path is now also observable through explicit execution events, so upstream systems can audit when an agent-scoped action was executed directly versus converted into a pending approval.

Single-action execution now also supports idempotent persisted run records, so a retrying orchestrator can safely repeat the same direct action request and receive the stored outcome instead of applying the action twice or opening duplicate approvals.

The same policy-aware behavior is now available in batch through `POST /api/execution-plane/agents/actions/execute-batch`, which lets an upstream orchestrator apply filtered safe actions or open the corresponding approvals in one call while preserving the same issue/approval/event semantics.

That batch surface now also supports stable `policy_profile` resolution, so approval escalation rules do not need to be hard-coded in FounderOS. A founder workflow can ask for a shared profile like `safe_budget_maintenance` or `budget_maintenance_with_high_priority_escalation` and keep the exact skip/request rules inside the execution plane.

The same batch request can also be previewed through `POST /api/execution-plane/agents/actions/preview-batch`, which gives upstream systems a non-mutating planning pass before they commit to opening approvals or applying safe actions.

Batch preview/execution now also persists run reports with optional idempotency keys, so an upstream orchestrator can safely retry a request and get the same recorded outcome instead of opening duplicate approvals or replaying the same safe action twice.

Those persisted run reports now also emit batch lifecycle events per affected project, which makes orchestration runs visible in the same execution event stream as runtime failures, approvals, and direct action executions.

The same run records can now also be grouped under persisted orchestrator sessions. That gives FounderOS a stable control-plane primitive for one external orchestration pass, with linked runs, approvals, issues, runtime-agent ids, explicit open/completed lifecycle transitions, and a session-level event timeline.

Those sessions now also expose a live action scope, so an upstream orchestrator can preview or execute the current safe/approval-gated actions for one session directly instead of respecifying project filters on every call.

They now also expose a higher-level control summary with typed recommendations such as reviewing pending approvals, previewing safe actions, executing safe actions, triaging open issues, or completing a healthy session.

Those typed recommendations are now directly executable through `POST /api/execution-plane/orchestrator-sessions/{session_id}/control/apply`, so FounderOS can operate on session-level intent instead of only on raw action keys.

Current recommendation apply semantics are intentionally small and explicit:

- session action recommendations delegate into the existing preview/execute batch runtime
- approval and issue review recommendations return the linked inspection payload
- session completion recommendations apply the session status update

Each apply also emits `execution_plane_orchestrator_session_recommendation_applied`, so the shared execution timeline records the fact that the orchestrator acted on a session recommendation.

On top of single recommendation apply, session control now also supports policy-driven orchestration passes through:

- `GET /api/execution-plane/orchestrator-sessions/control/profiles`
- `POST /api/execution-plane/orchestrator-sessions/{session_id}/control/apply-plan`

This lets FounderOS run a full typed control pass such as:

- `safe_progress`: execute safe actions, inspect approval blockers, preview approval-gated work, then close the session when healthy
- `review_only`: inspect blockers without mutating project/session state
- `close_healthy`: only complete a healthy session

Those passes also emit `execution_plane_orchestrator_session_control_plan_applied`, so the audit timeline now captures not only individual recommendation applies, but the whole session-level orchestration pass that triggered them.

Each session control pass is now also persisted as its own record and linked back into the parent orchestrator session. FounderOS can query:

- global pass history through `GET /api/execution-plane/orchestrator-sessions/control/passes`
- global pass summary through `GET /api/execution-plane/orchestrator-sessions/control/passes/summary`
- one pass detail through `GET /api/execution-plane/orchestrator-sessions/control/passes/{control_pass_id}`
- session-scoped pass history through `GET /api/execution-plane/orchestrator-sessions/{session_id}/control/passes`
- session-scoped pass summary through `GET /api/execution-plane/orchestrator-sessions/{session_id}/control/passes/summary`

That means approvals, issues, action runs, and session control passes now all have first-class persisted history objects instead of existing only as timeline events.

Control-pass summaries aggregate by pass status, profile, actor, orchestrator, final control state, stop reason, and session lifecycle before/after the pass. That gives FounderOS a cheap way to inspect whether its orchestration passes are mostly closing healthy sessions, stopping on approval blockers, or degenerating into review-only/noop behavior.

Persisted pass recording also emits `execution_plane_orchestrator_session_control_pass_recorded`, so dashboards can track both the execution of a pass and the fact that its durable record was stored.

## What is not here yet

- multi-step approval policies
- approver groups
- budget-threshold-triggered approvals
- issue-linked approvals
- plugin hooks on approval transitions
