# Release Notes Template

## Release

- Version: `vX.Y.Z`
- Date: `YYYY-MM-DD`
- Status: `rc` or `ga`

## What This Release Is

One paragraph describing what changed at the product level and why the release matters.

## Highlights

- highlight one
- highlight two
- highlight three

## What Is Included

- CLI
- API
- dashboard
- execution-plane or workflow contracts

## Verification Baseline

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

## Upgrade Notes

- package install or dependency notes
- config changes
- migration notes if any

## Known Limitations

- limitation one
- limitation two

## Next Focus

- next focus one
- next focus two
