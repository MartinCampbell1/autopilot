# Example: Issue-Driven Flow

This path is for turning one upstream source item into a tracked execution run with isolated workspace handling and a final PR or handoff artifact.

## Goal

Start from a GitHub issue or tracker item and keep source provenance visible through execution and delivery.

## Flow

1. Ingest a source item through the project API or integration route.
2. Persist `task_source` with `source_kind`, `external_id`, `repo`, `branch_policy`, and `brief_ref`.
3. Create the project and execution brief.
4. Run the project with `isolated_worktree` as the default path when the repo is Git-ready.
5. Track the result through `delivery_loop`, `delivery_status`, and the final handoff artifact.

## Example Source Contract

```json
{
  "source_kind": "github_issue",
  "external_id": "42",
  "repo": "martin/autopilot",
  "branch_policy": "isolated_worktree",
  "brief_ref": ".agents/tasks/execution-brief.json"
}
```

## What Good Looks Like

- the workspace knows which source item started the run
- the dashboard can show source, brief, execution state, and handoff in one project context
- the final PR or handoff artifact can be traced back to the original issue without manual glue

## Notes

- use this pattern for tracker-driven work as well; only `source_kind` and `external_id` need to change
- the source item should survive restarts, review loops, and handoff state changes
