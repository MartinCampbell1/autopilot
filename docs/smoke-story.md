# Smoke And Evaluation Story

This is the minimum public evaluation path for Autopilot before a fuller benchmark harness exists.

It is intentionally small and repeatable. The goal is to prove that a fresh engineer can install the product, validate the operator surfaces, and understand what is working without private branch context.

## What This Story Proves

The smoke story validates four things:

1. the repository installs from docs only
2. the public verification baseline is green
3. the dashboard and control-plane surfaces render correctly
4. the product story from intake to execution inspection is understandable from the public docs

This is not yet a scored benchmark harness. It is the release-candidate adoption check that comes before a larger evaluation framework.

## Smoke Path

### 1. Install From Clean Checkout

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
(cd dashboard && npm install)
```

### 2. Run The Official Verification Baseline

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

Expected result:

- all commands exit cleanly
- `pytest` and `ruff` are green
- dashboard `lint` and `build` are green
- `live` and `status` render operator-readable output

### 3. Smoke The Dashboard Surfaces

```bash
./.venv/bin/autopilot dashboard --no-browser --port 8421 --frontend-port 3021
curl -s http://127.0.0.1:8421/api/health
curl -I http://127.0.0.1:3021/
curl -I http://127.0.0.1:3021/control-plane
```

Expected result:

- `/api/health` returns `{"status":"ok"}`
- `/` returns `200 OK`
- `/control-plane` returns `200 OK`

### 4. Follow One Public Workflow

Pick one of the public walkthroughs and verify that the product story is coherent:

- [docs/quickstart.md](quickstart.md)
- [docs/workflow.md](workflow.md)
- [docs/examples/issue-driven-flow.md](examples/issue-driven-flow.md)

Success means the reader can answer:

- where work starts
- how provider/runtime selection happens
- where previews and approvals appear
- how the final PR or handoff artifact is surfaced

## How To Report The Result

For a release-candidate pass, record:

- the commit or PR SHA
- the commands that were run
- whether each step passed
- any platform-specific caveats
- screenshots only when they clarify a UI problem or onboarding confusion

## Current Boundary

This story is deliberately narrower than a future benchmark harness.

Not yet included:

- scored task suites
- SWE-Bench or WebArena-style evaluation
- automated cross-provider quality comparisons
- long-running workload benchmarks

Those stay in post-release scope until the public product surface is stable.
