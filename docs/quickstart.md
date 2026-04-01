# Quickstart Guide

This is the shortest supported path from clean checkout to a usable Autopilot run.

## 1. Install The Local Baseline

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,api]"
(cd dashboard && npm install)
```

## 2. Pick A Starting Path

Choose one of the public entry paths:

- local idea to project:
  - `autopilot init /path/to/project --idea "Build a FastAPI bug tracker"`
- local-first runtime:
  - configure `providers:` and `runtime_profiles:` as described in [docs/local-first-runtime.md](/Users/martin/Desktop/autopilot/docs/local-first-runtime.md)
- issue-driven execution:
  - use the source-item path in [docs/examples/issue-driven-flow.md](/Users/martin/Desktop/autopilot/docs/examples/issue-driven-flow.md)

## 3. Validate The Runtime

```bash
./.venv/bin/autopilot doctor /path/to/project --refresh
./.venv/bin/autopilot status
```

## 4. Launch A First Run

CLI path:

```bash
./.venv/bin/autopilot run /path/to/project
./.venv/bin/autopilot trace /path/to/project
```

Dashboard path:

```bash
./.venv/bin/autopilot dashboard --no-browser
```

The intake screen lets you choose the execution provider, runtime profile, and task source before launch.

![Autopilot Intake](assets/intake.png)

After launch, the control plane exposes previews, approvals, sessions, and apply state from one operator surface.

![Autopilot Control Plane](assets/control-plane.png)

## 5. Verify The Baseline

Run the public release-gate commands before treating the environment as healthy:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

For the full clean-checkout contract, including dashboard smoke steps, see [docs/verification-baseline.md](/Users/martin/Desktop/autopilot/docs/verification-baseline.md).
For the repeatable public adoption check that sits above those raw commands, see [docs/smoke-story.md](/Users/martin/Desktop/autopilot/docs/smoke-story.md).

## 6. Follow-On Guides

- [docs/workflow.md](/Users/martin/Desktop/autopilot/docs/workflow.md)
- [docs/local-first-runtime.md](/Users/martin/Desktop/autopilot/docs/local-first-runtime.md)
- [docs/extensions.md](/Users/martin/Desktop/autopilot/docs/extensions.md)
- [docs/troubleshooting.md](/Users/martin/Desktop/autopilot/docs/troubleshooting.md)
