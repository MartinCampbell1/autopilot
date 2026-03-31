# Changelog

This project follows Keep a Changelog style entries and uses semantic versioning for public releases.

## [Unreleased]

### Added

- Canonical post-hardening handoff in [docs/2026-03-31-next-product-plan.md](/Users/martin/Desktop/autopilot/docs/2026-03-31-next-product-plan.md).
- Release hygiene surface with [docs/release-checklist.md](/Users/martin/Desktop/autopilot/docs/release-checklist.md) and [docs/release-notes-template.md](/Users/martin/Desktop/autopilot/docs/release-notes-template.md).

### Changed

- Public README positioning now describes Autopilot as the FounderOS execution plane and publishes the official verification contract.
- Older handoff docs now point to the canonical next-step product plan instead of competing as active sources of truth.

### Fixed

- Dashboard production builds now ignore duplicate `* 2.ts`, `* 2.tsx`, and `* 2.mts` workspace artifacts during TypeScript evaluation.

## [0.1.0] - YYYY-MM-DD

### Added

- FounderOS execution-plane baseline with CLI, API, dashboard, approvals, sessions, action runs, and control-plane surfaces.
- Branch hardening across doctor, trace, cost, headless, schedule, live, status, and dashboard stabilization.

### Changed

- Documentation and release-hygiene surface aligned around the frozen baseline and next-step productization plan.

### Fixed

- Placeholder for release-specific fixes recorded at cut time.
