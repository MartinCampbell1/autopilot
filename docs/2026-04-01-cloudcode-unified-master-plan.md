# Cloud Code -> FounderOS Unified Master Plan

> [!IMPORTANT]
> This document is no longer the most complete implementation blueprint.
> Use `/Users/martin/Downloads/founderos-autopilot-unified-megaplan-2026-04-01.md`
> as the primary implementation plan for remaining work.
>
> Keep this file as a compact architecture summary and delta document.
> Keep `docs/2026-04-01-claude-code-direct-borrow-plan.md` as the canonical
> donor -> target file map.

## Purpose

This document is the merged implementation plan after comparing four sources:

1. `docs/2026-04-01-claude-code-direct-borrow-plan.md`
2. `/Users/martin/Downloads/autopilot-cloudcode-p0-p2-function-backlog-2026-04-01.md`
3. `/Users/martin/geminicode/EXHAUSTIVE-BORROW-CATALOG.md`
4. the follow-up "mega-plan" notes about exact edit safety, AST shell validation,
   worktree isolation, compaction, memory distillation, and structured subagent output

The earlier direct-borrow plan remains the canonical donor -> target file map.
This document adds the missing engineering detail, missing runtime invariants,
and a merged implementation order.

## What The Canonical Plan Already Covered Well

The existing canonical plan already captured most of the high-value donor surface:

- executable tool contracts
- permission engine and hook runtime
- shell/path safety at a high level
- verifier contract and anti-hallucination posture
- fork/no-peek/no-race subagent rules
- task lifecycle, transcripts, resume, and compaction
- plugin loader / policy / commands / hooks / MCP
- structured I/O and session state
- onboarding, doctor, GitHub bootstrap, review, ship
- session cost persistence

That plan was already good enough to start implementation.

## Delta Against The Canonical Plan

The external backlog and exhaustive catalog did not overturn the earlier plan,
but they did add important missing or under-specified mechanisms.

### Missing Or Under-Specified Runtime Pieces

The following items were not explicit enough in the canonical plan and should now
be treated as first-class design requirements:

1. `QueryEngine.ts`-style runtime ownership
   - one query loop owns mutable messages, usage accounting, denials, recovery,
     and streaming coordination
   - do not scatter query-state mutation across unrelated modules

2. streaming tool execution
   - tools should be able to start while model output is still streaming
   - do not wait for a fully materialized assistant turn if the tool-use is
     already parseable

3. prompt-too-long recovery hierarchy
   - collapse drain first
   - reactive compaction second
   - fail after bounded retries
   - keep SDK/user-facing history clean while recovery is in progress

4. API-round message grouping
   - compaction should drop whole API rounds, not random individual messages
   - this preserves tool/result invariants and semantic units

5. tool result budgeting
   - large tool outputs should go to disk with preview + pointer, not straight
     into prompt history

6. concurrent-read / serial-write orchestration
   - read-only tools can batch
   - write tools must serialize and thread context carefully

7. command semantics
   - `grep 1`, `diff 1`, `find 1` are not generic failures
   - shell result interpretation must be command-aware

8. hard budget enforcement
   - per-turn token budget
   - per-story cost budget
   - per-run cost budget
   - denial budget / repeated-denial breaker
   - total story timeout / watchdog

9. proactive quota probing
   - pre-flight provider/account budget and quota checks before long autonomous runs

10. work item lease health
   - atomic claim
   - heartbeat
   - PID liveness
   - stale timeout

11. quality ratchet and stuck detection
   - once a gate passes, later attempts must not regress
   - repeated same-failure loops must escalate instead of spinning

12. settings hierarchy and policy cascade
   - managed settings
   - project settings
   - local settings
   - flags
   - policy overrides
   - explicit precedence

13. feature gating and sticky session latches
   - session-level sticky configuration for cache mode, permission mode, provider
     behavior, and feature flags

14. memory taxonomy and distillation gates
   - user memory
   - feedback memory
   - project memory
   - reference memory
   - threshold-gated extraction and background consolidation

15. infrastructure hygiene
   - process cleanup
   - retry taxonomy
   - atomic append I/O
   - bounded logging structures
   - size watchdogs
   - query re-entry guards

16. transcript persistence and filtering
   - JSONL transcript persistence
   - compact attribute snapshots instead of raw repeated payloads

### Missing Or Under-Specified Safety Details

These were present conceptually but need stricter implementation requirements:

1. exact edit enforcement
   - record read-state with `mtime` and content hash
   - reject stale edits
   - reject ambiguous multi-match edits unless `replace_all=true`
   - normalize curly quotes and trailing whitespace when matching
   - preserve exact replacement behavior
   - size guard and BOM-aware decoding for large/unusual files

2. AST-first shell safety
   - do not reduce this to simple `shlex.split()`
   - the donor value is fail-closed syntax understanding plus read-only flag
     allowlists and path-aware blocking

3. dangerous shell/path edge cases
   - shell expansion syntax blocking
   - symlink-safe TOCTOU checks
   - UNC/private/network path detection where applicable
   - dangerous removal blocklists
   - hidden write detection via flags and shell forms

4. verifier evidence enforcement
   - no PASS without command + output + verdict
   - require at least one adversarial probe before PASS
   - verifier must be read-only

5. permission audit trail
   - permission decisions should be attributable, logged, and source-aware

### Multi-Agent Details Missing From The Canonical Plan

The canonical plan covered subagents well, but these lower-level mechanics were
not explicit enough:

- mailbox-based permission sync between coordinator and workers
- resolve-once race guards for multi-source permission settlement
- environment-variable allowlisting for spawned workers
- deterministic agent identity and session/task identity rules
- explicit teammate communication contract instead of relying on ambient text
- task output files as durable completion artifacts

### Product / Protocol Details Missing From The Canonical Plan

These are not all P0, but they belong in the full plan:

- structured request correlation ring and dedup window
- explicit `requires_action` payload schema
- session tag / rename / fork support
- manual `/compact` command
- `/security-review` as a later flow
- session browser / resume / cross-clone registry
- frontmatter-defined agent/plugin metadata
- idempotent settings/config migrations

## Corrections To The Mega-Plan

Some ideas from the mega-plan are directionally right but should be adapted:

1. Use typed JSON / schema-enforced responses, not XML
   - the donor repo is strongest where it uses explicit typed control messages,
     session state, and request/response schemas

2. Use AST-style fail-closed shell analysis, not only `shlex`
   - `shlex` can be a helper, not the primary safety model

3. Memory distillation should be threshold-gated and background-safe
   - not only a nightly cron
   - preserve active work, skills, plans, and async task state

4. Worktree isolation should include lifecycle and hygiene
   - create
   - restore
   - stale sweep
   - agent-specific cleanup
   - safe merge/retain rules
   - hook behavior must be controlled so agent sandboxes do not accidentally run
     unrelated local automation

5. `clone_thread()` is correct in spirit
   - but the stronger donor idea is fork cache parity via byte-identical prefixes
     and explicit fork-child semantics

## Unified Target Architecture

### Pillar 1: Query Runtime And Context Pressure

Add a real query/runtime core that owns:

- mutable message state
- usage accounting
- permission denials
- tool streaming coordination
- prompt-too-long recovery
- compaction entry points
- session-state updates

New modules:

- `autopilot/core/query_runtime.py`
- `autopilot/core/context_pressure.py`
- `autopilot/core/token_budget.py`
- `autopilot/core/tool_result_store.py`
- `autopilot/core/query_guards.py`

Borrow explicitly from:

- `QueryEngine.ts`
- `query.ts`
- `query/tokenBudget.ts`
- `services/compact/grouping.ts`
- `services/compact/compact.ts`
- `services/tools/StreamingToolExecutor.ts`
- `toolOrchestration.ts`
- `toolResultStorage.ts`

### Pillar 2: Tool Contracts, Permissions, Hooks, And Shell Truth

Keep the earlier P0, but make the following additions explicit:

- source-aware permission precedence
- denial circuit breaker
- tool result mapping as a single-pass invariant
- audit trail for permission decisions
- AST-first shell parsing and read-only validation
- command-aware exit semantics
- exact file-edit safety with read-state cache

New or expanded modules:

- `autopilot/core/tool_contracts.py`
- `autopilot/core/tool_runner.py`
- `autopilot/core/tool_permissions.py`
- `autopilot/core/tool_hooks.py`
- `autopilot/core/file_read_state.py`
- `autopilot/core/shell_validation.py`
- `autopilot/core/path_validation.py`
- `autopilot/core/read_only_validation.py`
- `autopilot/core/command_semantics.py`
- `autopilot/core/permission_audit.py`

### Pillar 3: Verifier, Quality Ratchet, And Anti-Hallucination Wall

The verifier is only one layer. The full wall is:

1. read-before-edit
2. stale-write prevention
3. fork no-peek / no-race
4. verifier evidence contract
5. tool result budgeting
6. shell exit semantics
7. denial breaker / escalation

Additional runtime quality modules:

- `autopilot/core/verification_agent.py`
- `autopilot/core/quality_ratchet.py`
- `autopilot/core/stuck_detector.py`
- `autopilot/core/attempt_planner.py`

### Pillar 4: Multi-Agent Runtime, Tasks, And Worktrees

Formalize a unified task runtime with:

- task ids
- task type
- status
- notification state
- foreground/background transitions
- kill/cleanup semantics
- output-file contract
- permission synchronization
- durable transcripts

New or expanded modules:

- `autopilot/core/subagent_protocol.py`
- `autopilot/core/task_runtime.py`
- `autopilot/core/session_state.py`
- `autopilot/core/session_tasks.py`
- `autopilot/core/runtime_agents.py`
- `autopilot/core/worktree.py`
- `autopilot/core/work_item_lease.py`

### Pillar 5: Settings, Instructions, And Configuration Governance

Make configuration composable and explainable:

- managed settings
- project settings
- local overrides
- runtime flags
- policy transforms
- feature gates
- sticky session latches
- idempotent migrations

New or expanded modules:

- `autopilot/core/settings_hierarchy.py`
- `autopilot/core/feature_flags.py`
- `autopilot/core/config_migrations.py`
- `autopilot/core/instructions_memory.py`
- `autopilot/core/project_instructions.py`

### Pillar 6: Memory, Compaction, And Distillation

Separate three related concerns:

1. session compaction
2. session memory extraction
3. long-term project memory distillation

New or expanded modules:

- `autopilot/core/session_compaction.py`
- `autopilot/core/micro_compaction.py`
- `autopilot/core/session_memory.py`
- `autopilot/core/memory_extraction.py`
- `autopilot/core/memory_types.py`
- `autopilot/core/knowledge_distiller.py`
- `autopilot/core/guardrails_memory.py`

### Pillar 7: Structured Control Plane And Protocol

Promote the control plane from SSE text feed to typed runtime protocol:

- structured request/response
- request correlation ids
- timeout/cancel semantics
- dedup ring
- ordered replay
- `requires_action` state with typed details
- session tag/rename/fork metadata

New or expanded modules:

- `autopilot/core/structured_io.py`
- `autopilot/core/control_messages.py`
- `autopilot/core/session_registry.py`
- `autopilot/api/routes/events.py`
- `autopilot/api/sse.py`

### Pillar 8: Plugin And MCP Platform

Keep the earlier plugin plan, but explicitly add:

- manifest validation before activation
- install ledger
- dependency closure
- secret-safe options storage
- background install/reconcile
- later marketplace / autoupdate / LSP

New or expanded modules:

- `autopilot/core/plugin_loader.py`
- `autopilot/core/plugin_models.py`
- `autopilot/core/plugin_validation.py`
- `autopilot/core/plugin_storage.py`
- `autopilot/core/plugin_commands.py`
- `autopilot/core/plugin_skills.py`
- `autopilot/core/plugin_hooks.py`
- `autopilot/core/plugin_mcp.py`
- `autopilot/core/plugin_startup.py`
- later:
  - `autopilot/core/plugin_marketplace.py`
  - `autopilot/core/plugin_versioning.py`
  - `autopilot/core/plugin_lsp.py`
  - `autopilot/core/plugin_output_styles.py`
  - `autopilot/core/plugin_hints.py`

### Pillar 9: Budgets, Retries, Resilience, And Observability

The cost tracker alone is not enough. Add:

- hard budget caps
- retry taxonomy
- exponential backoff + jitter
- provider/model routing registry
- sticky cache policy
- process cleanup
- bounded queues/logging
- size watchdogs

New or expanded modules:

- `autopilot/core/budget_enforcer.py`
- `autopilot/core/retry_policy.py`
- `autopilot/core/provider_registry.py`
- `autopilot/core/cache_policy.py`
- `autopilot/core/process_hygiene.py`
- `autopilot/core/log_buffers.py`
- `autopilot/core/size_watchdog.py`

### Pillar 10: Operator Flows

Keep the earlier plan for:

- `/init`
- `/init-verifiers`
- `/doctor`
- `/review`
- `/ship`
- GitHub bootstrap
- `/resume`

Add later:

- `/compact`
- `/security-review`
- richer context-usage inspection

## Unified Phase Order

### Phase 0: Immediate Quick Wins

Ship first because these are cheap and close real gaps:

1. verifier output validation in `critic.py`
2. informational shell exit semantics
3. denial circuit breaker
4. hard budget caps and total story timeout
5. verification nudge on close-out

### Phase 1: Runtime Safety Wall

Implement the core safety wall in this order:

1. tool contracts V2
2. tool runner lifecycle V2
3. permission engine V2
4. hook engine V2
5. file read-state + exact edit safety
6. AST shell stack + path validation + read-only validation
7. permission audit trail

### Phase 2: Query Engine And Context Pressure

Implement:

1. query runtime ownership
2. streaming tool execution
3. token budget logic
4. compaction grouping and recovery hierarchy
5. tool result storage
6. proactive quota checks
7. prompt-too-long retry and recovery

### Phase 3: Multi-Agent And Worktrees

Implement:

1. subagent protocol
2. task runtime
3. mailbox / resolve-once permission settlement
4. output-file contract
5. worktree lifecycle manager
6. work item lease / heartbeat
7. transcript persistence

### Phase 4: Structured Control Plane And Settings

Implement:

1. structured I/O
2. control schemas
3. explicit session state and `requires_action`
4. session registry / tag / rename / fork
5. settings hierarchy
6. feature gates and sticky session latches
7. config migration primitives

### Phase 5: Memory And Intelligence

Implement:

1. session memory extraction
2. semantic compaction
3. knowledge distillation
4. guardrails memory
5. quality ratchet
6. stuck detection
7. attempt-planning / escalation strategies

### Phase 6: Plugin Foundation

Implement:

1. plugin loader + validation
2. plugin storage/options/secrets
3. commands / skills / hooks discovery
4. plugin MCP integration
5. startup checks and background reconciliation

### Phase 7: Operator Product Surface

Implement:

1. `/init`
2. `/init-verifiers`
3. `/doctor`
4. GitHub bootstrap
5. `/review`
6. `/ship`
7. `/resume`
8. `/compact`

### Phase 8: Later Ecosystem And Remote

Only after the core is stable:

- plugin marketplace
- plugin autoupdate
- plugin LSP
- output styles
- hints
- remote worker protocol
- transport swap / replay hardening
- hosted auth/JWT refresh

## PR Batching

### Batch A: Safety Wall

- tool contracts
- tool runner
- permissions
- hooks
- exact-edit safety
- shell safety
- verifier hardening

### Batch B: Query Runtime

- query runtime
- token budget
- result budgeting
- compaction grouping
- recovery hierarchy
- budget enforcer

### Batch C: Multi-Agent Runtime

- subagent protocol
- task runtime
- worktree lifecycle
- work item lease
- transcripts and output artifacts

### Batch D: Control Plane And Settings

- structured I/O
- session state
- event dedup/replay
- session registry
- settings hierarchy

### Batch E: Memory And Quality

- session memory
- memory extraction
- knowledge distiller
- quality ratchet
- stuck detector

### Batch F: Plugin Platform

- plugin loader
- validation
- storage/options
- commands/skills/hooks
- MCP integration
- startup checks

### Batch G: Operator Flows

- init
- init-verifiers
- doctor
- GitHub bootstrap
- review
- ship
- resume

## Explicit Non-Goals For The First Implementation Wave

Do not let the plan sprawl into these before the core lands:

- donor UI shell replication
- Anthropic billing / overage / subscriber logic
- marketplace polish
- LSP richness
- hosted bridge infra
- vendor-specific analytics backends

Port the runtime semantics, not the product vanity layer.

## Definition Of Done

The merged borrow is successful only when all of these are true:

1. a worker cannot claim completion without verifier-backed evidence
2. a file edit cannot proceed without fresh read-state and exact-match safety
3. shell execution is path-aware, AST-aware, and fail-closed
4. long sessions compact without breaking API invariants or losing active work
5. subagents are resumable, isolated, and cannot fabricate partial certainty
6. session state is machine-readable and resumable
7. plugins are lifecycle-complete enough to load commands/hooks/MCP safely
8. budget exhaustion stops or degrades execution predictably instead of looping

## How To Use This Plan

Use the documents together:

- `docs/2026-04-01-claude-code-direct-borrow-plan.md`
  - canonical donor -> target file map
- `docs/2026-04-01-cloudcode-unified-master-plan.md`
  - merged implementation architecture and missing-detail delta

The first document answers "what donor file maps where."
This document answers "what the full system must become."
