# Workflow Guide

This is the public operator path from one source item or local brief to a final PR or handoff artifact.

## Entry Points

Autopilot accepts three canonical starting points:

- local brief
- GitHub issue
- tracker item

Each path resolves into the same execution contract:

- `task_source` keeps the upstream provenance
- `Execution Brief` defines what should be built
- project state, reviews, previews, approvals, and handoff stay attached to the same delivery loop

## Default Delivery Loop

1. Create or ingest the source item.
2. Persist the project with `task_source` and the execution brief reference.
3. Validate provider and runtime readiness with `autopilot doctor`.
4. Execute the project in the default isolated workspace or worktree path when the repository is Git-ready.
5. Inspect previews, approvals, issues, and applied action runs from the same run context.
6. Review the final delivery state through `delivery_loop`, `delivery_status`, and the handoff artifact.
7. Merge the PR or use the handoff artifact as the contract for downstream review.

## Operator Surfaces

Dashboard:

- intake selects provider, runtime profile, and task source
- control plane exposes preview, approval, issue, and apply state
- workspace and story views show the delivery loop from source to handoff

CLI:

- `autopilot init /path/to/project --idea "..."`
- `autopilot doctor /path/to/project --refresh`
- `autopilot run /path/to/project`
- `autopilot preview-actions <session_id>`
- `autopilot apply-preview <preview_id>`
- `autopilot approvals`
- `autopilot apply-approval <approval_id>`
- `autopilot trace /path/to/project`
- `autopilot live --once`
- `autopilot status`

## What To Expect In A Healthy Run

- source provenance survives retries, review loops, and handoff updates
- risky action batches can be previewed before apply
- approvals and issues are tied back to the same run context
- isolated worktree execution is the default when the repository is ready for it
- the final PR or handoff artifact still points back to the original source item

## Related Guides

- [docs/examples/local-only-project.md](examples/local-only-project.md)
- [docs/examples/cloud-multi-provider-project.md](examples/cloud-multi-provider-project.md)
- [docs/examples/issue-driven-flow.md](examples/issue-driven-flow.md)
- [docs/troubleshooting.md](troubleshooting.md)
