# PR Summary

Date: `2026-03-31`

Branch: `codex/founderos-control-plane`

## What This Branch Delivers

- Phase 3 control-plane deep-link/share hardening
- the active `P0`, `P1`, and `P2` backlog slices from the merged handoff
- final stabilization for the current branch baseline
- whole-product hardening for real CLI/API/dashboard smoke paths

## Late-Stage Additions In The Final Pass

- bounded multi-attempt per task in the worker loop
- scheduled maintenance runs via `autopilot run --schedule ...` and `autopilot run-all --schedule ...`
- dashboard lint stabilization by ignoring generated `.next.broken-*` artifact directories
- repo-local gate execution for `.venv` / project-local toolchains during headless runs
- dashboard Next 16 stabilization by removing the forced `--webpack` path from the operator entrypoint
- dashboard build/lint hardening around `node_modules.partial.*` install artifacts and control-plane build typing
- handoff/backlog/status docs synced to the actual branch truth
- `README.md` refreshed to match the current CLI and platform surface

## Verification

- `./.venv/bin/python -m pytest -q`
  - `281 passed in 7.73s`
- `./.venv/bin/ruff check /Users/martin/Desktop/autopilot/autopilot /Users/martin/Desktop/autopilot/tests`
  - passed
- `npm run build` in `dashboard`
  - passed
- `npm run lint` in `dashboard`
  - passed
- `./.venv/bin/autopilot dashboard --no-browser`
  - passed smoke: backend `/api/health`, frontend `/`, and frontend `/control-plane` all returned `200`
- browser smoke against `http://127.0.0.1:3020/` and `http://127.0.0.1:3020/control-plane`
  - rendered successfully
- `./.venv/bin/autopilot live --once`
  - passed
- `./.venv/bin/autopilot status`
  - passed

## Review Anchors

Primary code areas for review:

- [autopilot/core/orchestrator.py](/Users/martin/Desktop/autopilot/autopilot/core/orchestrator.py)
- [autopilot/core/gates.py](/Users/martin/Desktop/autopilot/autopilot/core/gates.py)
- [autopilot/core/escalation.py](/Users/martin/Desktop/autopilot/autopilot/core/escalation.py)
- [autopilot/core/scheduler.py](/Users/martin/Desktop/autopilot/autopilot/core/scheduler.py)
- [autopilot/cli/dashboard.py](/Users/martin/Desktop/autopilot/autopilot/cli/dashboard.py)
- [autopilot/cli/run.py](/Users/martin/Desktop/autopilot/autopilot/cli/run.py)
- [autopilot/cli/main.py](/Users/martin/Desktop/autopilot/autopilot/cli/main.py)
- [dashboard/app/control-plane/page.tsx](/Users/martin/Desktop/autopilot/dashboard/app/control-plane/page.tsx)
- [dashboard/package.json](/Users/martin/Desktop/autopilot/dashboard/package.json)
- [dashboard/.gitignore](/Users/martin/Desktop/autopilot/dashboard/.gitignore)

Primary status docs:

- [2026-03-31-branch-completion-note.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-branch-completion-note.md)
- [2026-03-31-merged-handoff-and-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-merged-handoff-and-plan.md)
- [2026-03-31-control-plane-handoff.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-control-plane-handoff.md)
- [2026-03-31-engineering-backlog.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-engineering-backlog.md)

## Intentional Boundary

`P3` work is still intentionally out of scope for this branch unless a separate follow-up explicitly promotes one of those items.
