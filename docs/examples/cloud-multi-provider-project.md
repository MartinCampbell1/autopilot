# Example: Cloud Multi-Provider Project

This path is for teams that want explicit routing and fallback across managed providers while keeping one execution contract.

## When To Use It

- you want one project to run on cloud providers with different strengths
- you need operator-visible provider selection and runtime profiles
- you want to preserve review, approval, and budget behavior across providers

## Minimal Config Shape

```yaml
providers:
  - id: codex-cloud
    family: codex
    mode: cloud
    transport: cli
    auth_strategy: account_pool
    capabilities: [exec, review, critic]
  - id: claude-cloud
    family: claude
    mode: cloud
    transport: cli
    auth_strategy: account_pool
    capabilities: [review, critic]

runtime_profiles:
  - id: cloud
    sandbox_mode: host
    network_policy: default
    filesystem_policy: workspace-write
    default_tools: [shell, git, browser]
```

## Project Flow

1. Import or create a project.
2. Choose `Execution Provider` and `Runtime Profile` in intake.
3. Launch the project.
4. Use the dashboard and `autopilot status` to inspect the chosen provider/runtime contract.

## What Good Looks Like

- the project contract stays stable while providers change
- `doctor` and dashboard surfaces show which provider/runtime are actually selected
- operator trust surfaces such as previews, approvals, and quality gates still behave the same way

## Notes

- this is a portability layer, not an invitation to make orchestration provider-specific
- prefer changing provider configuration over adding conditional orchestration branches
