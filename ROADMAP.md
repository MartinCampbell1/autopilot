# Roadmap

This roadmap tracks the public product direction for Autopilot as the execution plane for FounderOS.

## Current Focus

### Release Candidate Wrap-Up

- merge the green release-candidate PR and decide the first public release cut
- keep verification reproducible from a clean setup path
- start post-release expansion only after the release-candidate decision is explicit

### Product Principles

- deterministic orchestration
- local-first runtime support
- human-visible approvals, budgets, and quality gates
- extensible tools and provider contracts without core rewrites

## Recently Completed

- workflow closure from source item to final PR or handoff artifact
- public workflow, comparison, quickstart, verification, and smoke-story docs for external adopters
- OSS release hygiene and contributor surface
- first public screenshots and portable external docs links
- `Phase 0` through `Phase 5` of the pre-release plan

## Next Up

- merge or cut the first public release candidate
- optional cleanup:
  - GitHub Actions Node 20 deprecation warnings
  - noisy local Ctrl-C shutdown traceback for `autopilot dashboard --no-browser` under Python `3.14`
- after release, move into `Phase 6` expansion

## After First Public Release

- VS Code and IDE integration
- richer TUI beyond current `live`
- benchmark and evaluation harnesses
- stronger task memory and lessons surfaces
- deeper tracker and issue automation

## Explicitly Deferred

These are intentionally out of pre-release scope unless promoted by a concrete failure mode:

- symbol-level locks and file reservations
- deeper sandbox hardening beyond the initial Docker path
- visual workflow editor
- day/night quota scheduling
- proxy-backed provider and cost layer
- marketplace-style extension distribution
