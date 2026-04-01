# Troubleshooting

This guide is for fresh operators and external engineers using Autopilot without prior branch context.

## `doctor` says a provider is not ready

Check:

- the provider entry exists in `config.yaml`
- `mode`, `transport`, and `auth_strategy` match the actual runtime path
- local endpoints are reachable if you use `openai_compatible`
- command-based runtimes are executable if you use `local_command`

Then rerun:

```bash
./.venv/bin/autopilot doctor /path/to/project --refresh
```

## The dashboard starts but pages do not load

Use the official smoke path:

```bash
./.venv/bin/autopilot dashboard --no-browser
curl -s http://127.0.0.1:8420/api/health
curl -I http://127.0.0.1:3020/
curl -I http://127.0.0.1:3020/control-plane
```

Expected:

- `/api/health` returns `{"status":"ok"}`
- `/` returns `200`
- `/control-plane` returns `200`

If ports are already taken, launch with explicit alternatives:

```bash
./.venv/bin/autopilot dashboard --no-browser --port 8421 --frontend-port 3021
```

## A project is not using isolated worktrees

Check:

- `branch_policy` is `isolated_worktree`
- the repo is Git-ready

If not, Autopilot falls back to the shared checkout path.

## A preview or approval flow looks inconsistent

Check:

- the `preview_id`
- the selected `apply_mode`
- whether the preview was created for the same action set and session

Autopilot intentionally rejects apply paths when the preview no longer matches the current execution context.

## The handoff looks missing even though work completed

Check the project surfaces in this order:

- `delivery_loop`
- `delivery_status`
- story `handoff_artifact`
- timeline events with `task_source` and `handoff`

If execution completed without a PR or handoff artifact, the project should show a handoff-pending state rather than a fake green result.

## Verification baseline fails

Run the release baseline exactly:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

If you change public contracts, update the docs and mention any skipped or platform-specific checks in the PR.
