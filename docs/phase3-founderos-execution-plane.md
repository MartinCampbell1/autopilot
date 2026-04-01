# Phase 3: FounderOS Execution Plane

This phase turns `Autopilot` into a cleaner execution/control plane for an upstream founder workflow without replacing the existing execution-first runtime.

## What landed

- Typed `ExecutionBrief` now carries:
  - `initiative`
  - `orchestration`
  - `provenance`
- Brief ingestion persists the source artifact at `.agents/tasks/execution-brief.json`
- Registered projects keep lightweight `control_plane` metadata for:
  - source kind
  - brief location
  - initiative mapping
  - orchestration refs
  - provenance
- Stable execution-plane API:
  - `GET /api/execution-plane/execution-brief/schema`
  - `POST /api/execution-plane/projects/from-brief`
  - `GET /api/execution-plane/projects`
  - `GET /api/execution-plane/agents`
  - `GET /api/execution-plane/agents/actions`
  - `GET /api/execution-plane/agents/actions/policy-profiles`
  - `GET /api/execution-plane/agents/action-runs`
  - `GET /api/execution-plane/agents/action-runs/summary`
  - `GET /api/execution-plane/agents/action-runs/{run_id}`
  - `POST /api/execution-plane/orchestrator-sessions`
  - `GET /api/execution-plane/orchestrator-sessions`
  - `GET /api/execution-plane/orchestrator-sessions/summary`
  - `GET /api/execution-plane/orchestrator-sessions/{session_id}`
  - `GET /api/execution-plane/orchestrator-sessions/{session_id}/events`
  - `GET /api/execution-plane/orchestrator-sessions/{session_id}/actions`
  - `GET /api/execution-plane/orchestrator-sessions/{session_id}/actions/summary`
  - `POST /api/execution-plane/orchestrator-sessions/{session_id}/actions/preview`
  - `POST /api/execution-plane/orchestrator-sessions/{session_id}/actions/execute`
  - `GET /api/execution-plane/orchestrator-sessions/{session_id}/control`
  - `POST /api/execution-plane/orchestrator-sessions/{session_id}/status`
  - `GET /api/execution-plane/agents/actions/{action_key}`
  - `POST /api/execution-plane/agents/actions/execute`
  - `POST /api/execution-plane/agents/actions/preview-batch`
  - `POST /api/execution-plane/agents/actions/execute-batch`
  - `GET /api/execution-plane/agents/summary`
  - `GET /api/execution-plane/agents/{runtime_agent_id}`
  - `GET /api/execution-plane/projects/{project_id}`
  - `GET /api/execution-plane/projects/{project_id}/agents`
  - `GET /api/execution-plane/events`
  - `GET /api/execution-plane/projects/{project_id}/events`

## Why this shape

- It keeps the current `Autopilot` runtime intact.
- It avoids a giant rewrite of the dashboard project model.
- It gives `FounderOS` a stable surface for execution state, while the dashboard can keep using the existing `/api/projects/*` routes.

## Snapshot contract

Execution-plane snapshots expose:

- project identity and filesystem path
- PRD and persisted brief paths
- initiative and orchestration mapping
- runtime status and active story
- story progress counters
- launch profile
- budget policy and usage

Detailed views additionally expose:

- persisted brief payload
- phases and stories
- timeline
- derived runtime agents / roles
- runtime-control / workspace policy inspection

Global agent exports now flatten those per-project runtime agents into a FounderOS-facing control-plane surface with:

- stable `runtime_agent_id`
- project / initiative / orchestration context
- open issue counts
- pending approval counts
- per-agent budget summary
- per-agent attention summary with recommended action
- structured `recommendations`
- policy-aware `suggested_commands`

Per-agent detail now also exposes:

- current runtime snapshot when the agent is still present in live project state
- issue history
- approval history
- event history
- lightweight per-agent history counters
- budget and attention summaries derived from current runtime state
- actionable recommendations and command suggestions that an upstream orchestrator can apply at project scope

Agent summary exports now expose aggregate triage counts for:

- total and active runtime agents
- blocked / approval-gated / budget-risk / budget-exhausted agents
- role distribution
- per-project agent counts
- actionable agents
- recommendation-kind distribution
- suggested-command distribution

For orchestration loops that want a flatter queue, `GET /api/execution-plane/agents/actions` now exports recommendation and suggested-command items directly, with project/runtime-agent context, priority, and approval requirement metadata.

Those action items are now also addressable and executable:

- `GET /api/execution-plane/agents/actions/{action_key}` resolves one current action item
- `POST /api/execution-plane/agents/actions/execute` accepts one `action_key` plus an execution `mode`

Single-action execution now accepts an optional `idempotency_key`, persists a `run_kind=single_action` report, and replays the recorded result on retry instead of re-running the same action.

The first execution mode is intentionally conservative:

- `auto` executes safe suggested commands immediately
- `auto` converts approval-gated suggested commands into linked issue + approval records
- recommendation-only items remain non-executable hints rather than mutating control-plane actions

There is now also a batch form for orchestrators:

- `POST /api/execution-plane/agents/actions/execute-batch`
- `POST /api/execution-plane/agents/actions/preview-batch`

That batch route accepts either explicit `action_keys` or a filtered selection scoped by `project_id`, `initiative_id`, or `orchestrator`. For filtered selection it defaults to executable command suggestions only, so FounderOS can safely say "apply the current safe budget actions for this project" without manually resolving every action key first.

To keep that stable across orchestrators, execution-plane now exposes built-in batch policy profiles via `GET /api/execution-plane/agents/actions/policy-profiles`. The first profiles are intentionally narrow:

- `balanced_safe`
- `safe_budget_maintenance`
- `budget_maintenance_with_high_priority_escalation`

Batch execution accepts `policy_profile` plus optional typed policy overrides, so FounderOS can start from a shared profile and only override the parts that are initiative-specific.

`preview-batch` uses the same selection and policy logic but returns planned outcomes without mutating project state, creating approvals, or emitting action execution events.

Both `preview-batch` and `execute-batch` now persist stable run reports with:

- run id
- optional `idempotency_key`
- request fingerprint
- policy snapshot
- selection snapshot
- per-result outcomes
- derived project / initiative / orchestrator scope

Those reports can be queried later through `GET /api/execution-plane/agents/action-runs` and `GET /api/execution-plane/agents/action-runs/{run_id}`.

The same run-report surface now includes both `run_kind=batch` and `run_kind=single_action`, so FounderOS can audit direct action executions and policy-driven batch runs through one contract.

For control-plane dashboards and FounderOS triage loops, `GET /api/execution-plane/agents/action-runs/summary` now exposes aggregate counts by status, run kind, actor, policy profile, project, and orchestrator. Both list and summary surfaces can be filtered by `run_kind`.

For higher-level FounderOS orchestration passes, execution-plane now also exposes persisted orchestrator sessions. A session groups action runs, approvals, issues, runtime-agent linkage, and project scope under one stable `orchestrator_session_id`, so external control loops can open a session, execute or preview actions against it, and later inspect one aggregated record instead of stitching together raw events.

Session detail now also exposes an orchestration timeline:

- linked execution events
- aggregate `event_count`
- `latest_event_at`
- per-event and per-status counters

And the same timeline can be queried directly through `GET /api/execution-plane/orchestrator-sessions/{session_id}/events`.

Sessions now also expose a current control scope. FounderOS can ask for the live action feed of one session through `GET /api/execution-plane/orchestrator-sessions/{session_id}/actions`, inspect aggregate counts through `/actions/summary`, and then preview or execute that session-scoped action set without recomputing project filters on its side.

On top of that, `GET /api/execution-plane/orchestrator-sessions/{session_id}/control` now returns a session-level control object with:

- derived `state`
- action / approval / issue counts
- typed `recommendations`
- suggested operations for previewing, executing, triaging, or completing the session

FounderOS can now also apply those recommendations directly through `POST /api/execution-plane/orchestrator-sessions/{session_id}/control/apply`. This is a typed session-level operation layer on top of the lower-level action feed:

- `execute_safe_actions` and preview-style recommendations route into the existing session-scoped batch executor
- `review_pending_approvals` and `triage_open_issues` return the linked approval / issue surface without recomputing session joins upstream
- `complete_session` applies the session status transition directly

That gives the upstream control plane a stable way to act on session recommendations without unpacking and replaying the raw operation payload on its own.

Execution-plane now also exposes a policy-driven session pass layer:

- `GET /api/execution-plane/orchestrator-sessions/control/profiles`
- `POST /api/execution-plane/orchestrator-sessions/{session_id}/control/apply-plan`

This lets FounderOS apply a whole session control pass instead of one recommendation at a time. The initial built-in profiles are:

- `safe_progress`: inspect blocking approvals, execute safe actions, preview approval-gated actions, triage issues, and close a healthy session
- `review_only`: inspect approvals/issues and preview actions without mutating the session
- `close_healthy`: only close a healthy session

Each pass recomputes session control between steps, applies matching typed recommendations in profile order, and returns a stable summary with applied steps, errors, stop reason, and final control state.

Those session control passes are now also persisted as first-class records. Execution-plane exposes:

- `GET /api/execution-plane/orchestrator-sessions/control/passes`
- `GET /api/execution-plane/orchestrator-sessions/control/passes/summary`
- `GET /api/execution-plane/orchestrator-sessions/control/passes/{control_pass_id}`
- `GET /api/execution-plane/orchestrator-sessions/{session_id}/control/passes`
- `GET /api/execution-plane/orchestrator-sessions/{session_id}/control/passes/summary`

Session detail now includes linked `control_passes` plus `control_pass_count`, so FounderOS can inspect both the current session state and the history of control passes that shaped it.

The summary surfaces aggregate control-pass analytics by:

- pass `status`
- `profile`
- `actor`
- `orchestrator`
- pass `final_state`
- `stopped_reason`
- session status before/after the pass

Those mutations now emit explicit audit events into the shared execution stream:

- `execution_plane_agent_action_executed`
- `execution_plane_agent_action_pending_approval`
- `execution_plane_agent_action_run_recorded`

Batch orchestration now also emits lifecycle events:

- `execution_plane_agent_batch_previewed`
- `execution_plane_agent_batch_executed`

Orchestrator sessions emit their own lifecycle events as well:

- `execution_plane_orchestrator_session_created`
- `execution_plane_orchestrator_session_updated`
- `execution_plane_orchestrator_session_recommendation_applied`
- `execution_plane_orchestrator_session_control_plan_applied`
- `execution_plane_orchestrator_session_control_pass_recorded`

Event exports expose:

- project-scoped execution events
- initiative/orchestrator filtering
- enriched initiative and orchestration context per event
- optional `runtime_agent_id` filtering when events carry agent linkage

Global agent exports also support filtering by derived `attention_state`, `recommendation_kind`, `suggested_command`, `command_requires_approval`, and `actionable_only`, so FounderOS can ask for only blocked, approval-gated, budget-risk, or otherwise actionable agents.

## Command and approval foundation

Execution-plane now also exposes explicit external commands:

- `launch`
- `pause`
- `resume`
- `archive`
- `update_budget_policy`

Each command can be:

- executed immediately
- turned into a pending approval
- approved or rejected later
- applied after approval

Commands are now also evaluated against a per-project command policy, so risky launches and budget-threshold changes can auto-escalate into:

- execution issue
- linked approval request

The same issue surface now also receives runtime-linked issues from actual execution failures and recovery events, so FounderOS can treat both control-plane and runtime problems as one typed stream.

Those issues now expose structured triage payloads, including `root_cause`, `source_event`, and per-story/per-project runtime context.

Runtime-linked issues and approval requests can now also carry `runtime_agent_id` or `runtime_agent_ids` when the affected execution scope is known.

Runtime events emitted by the execution loop now also carry richer structured payloads for:

- gate failures via `story_gate_failed`
- critic rejections
- worker failures
- connector activation failures
- merge-blocked stories
- stuck stories

That makes the upstream execution-plane event stream more useful for FounderOS triage without changing the underlying worker -> gates -> critic loop.

This gives FounderOS a minimal approval primitive without inserting a mandatory approval gate into the existing runtime loop.

## Next likely increments

- initiative-to-project index and reverse lookup
- richer upstream event/export stream
- explicit external orchestrator commands
- approval and company/agent/issue foundations
