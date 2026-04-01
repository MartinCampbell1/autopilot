# Release Checklist

This checklist defines the minimum release hygiene for the current release-candidate baseline.

## Versioning Strategy

Current package version in [pyproject.toml](/Users/martin/Desktop/autopilot/pyproject.toml): `0.1.0`

Use the following rule set:

- keep `0.1.0` as the current baseline while the branch is being reviewed and prepared for a first public release candidate
- use `0.1.x` only for release-candidate stabilization, packaging fixes, smoke regressions, and documentation corrections
- use `0.2.0` when the Operator Trust Layer introduces new public execution-plane contracts such as preview artifacts and apply modes
- use `0.3.0` when local-first provider portability becomes a documented and supported public path
- use `1.0.0` only after the public workflow, extension contract, and OSS docs surface are stable enough to treat as a lasting external contract

## Branch Freeze

- confirm the branch scope is limited to the already-landed baseline plus release-hygiene changes
- do not reopen closed `P0`, `P1`, or `P2` work unless a regression requires it
- do not promote a `P3` item by default
- ensure the canonical next-step handoff is [2026-03-31-next-product-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-next-product-plan.md)

## PR And Review

- review the existing branch diff against [2026-03-31-pr-summary.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-pr-summary.md)
- move the PR out of draft before requesting final review
- ensure CI or an equivalent recorded verification baseline exists
- merge only after the verification contract is green

## Verification Contract

Run and record:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/ruff check autopilot tests
(cd dashboard && npm run lint)
(cd dashboard && npm run build)
./.venv/bin/autopilot dashboard --no-browser
./.venv/bin/autopilot live --once
./.venv/bin/autopilot status
```

## Documentation Sync

- `README.md` matches the current product surface and release baseline
- [2026-03-31-next-product-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-next-product-plan.md) is the only canonical next-step handoff
- older handoff docs are clearly marked as historical context
- release checklist, changelog, and release notes template exist

## Release Artifacts

- update [CHANGELOG.md](/Users/martin/Desktop/autopilot/CHANGELOG.md)
- copy [release-notes-template.md](/Users/martin/Desktop/autopilot/docs/release-notes-template.md) into the actual release notes draft
- include the verification baseline in the release notes
- include the public smoke and evaluation story in the release body when the goal is external adoption
- link to the main architecture and handoff docs in the release body
