# Verification Baseline

This is the public release-gate baseline for a clean checkout of Autopilot.

## Clean Setup

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
(cd dashboard && npm install)
```

## Official Baseline

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser --port 8421 --frontend-port 3021
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

## Expected Outcomes

- `pytest` passes without test failures
- `ruff` reports no Python lint violations
- dashboard `lint` and `build` succeed
- `autopilot dashboard --no-browser` starts successfully
- `autopilot live --once` exits cleanly
- `autopilot status` exits cleanly

## Dashboard Smoke Check

While the dashboard process is running, verify the API and UI surfaces:

```bash
curl -s http://127.0.0.1:8421/api/health
curl -I http://127.0.0.1:3021/
curl -I http://127.0.0.1:3021/control-plane
```

Healthy responses should include:

- `{"status":"ok"}` from `/api/health`
- `200 OK` from `/`
- `200 OK` from `/control-plane`

## If The Baseline Fails

- use [docs/troubleshooting.md](troubleshooting.md) for common local setup and runtime issues
- record the failing command, environment details, and any provider configuration differences
- do not treat a release candidate as green until the full baseline is repeatable from a clean checkout
