# Roadmap

This roadmap tracks the public product direction for Autopilot as the execution plane for FounderOS.

## Current Focus

### Release Candidate

- stabilize the `Execution Brief -> tracked execution -> PR/handoff` loop
- finish the OSS/community release surface
- keep verification reproducible from a clean setup path

### Product Principles

- deterministic orchestration
- local-first runtime support
- human-visible approvals, budgets, and quality gates
- extensible tools and provider contracts without core rewrites

## In Progress

- workflow closure from source item to final PR or handoff artifact
- public docs, examples, and troubleshooting for external adopters
- OSS release hygiene and contributor surface

## Planned Before First Public Release

- product README and quickstart polish
- documented extension examples for providers, tools, and trackers
- repeatable smoke and verification baseline
- clearer positioning versus swarm tools and coding copilots

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
