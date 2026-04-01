# Example: Local-Only Project

This path is for operators who want to keep execution local to the workstation or a self-hosted model endpoint.

## When To Use It

- privacy matters more than managed-provider convenience
- you already have a local runtime such as an OpenAI-compatible endpoint
- you want the same orchestration contract without cloud-only account setup

## Minimal Config

```yaml
providers:
  - id: local-openai
    family: openai_compatible
    mode: local
    transport: http
    endpoint: http://127.0.0.1:11434/v1
    auth_strategy: none
    capabilities: [exec, review, critic]

runtime_profiles:
  - id: local
    sandbox_mode: host
    network_policy: local-only
    filesystem_policy: workspace-write
    default_tools: [shell, git]
```

## Project Flow

```bash
./.venv/bin/autopilot doctor /path/to/project --refresh
./.venv/bin/autopilot run /path/to/project
./.venv/bin/autopilot trace /path/to/project
./.venv/bin/autopilot live --once
```

## What Good Looks Like

- `doctor` validates the local provider contract
- the project can run without changing orchestration logic
- trace and live views still show the same run lifecycle, budgets, and gates

## Notes

- local runtime support changes the execution backend, not the orchestration model
- if a local endpoint is unstable, keep the same project contract and switch to a cloud profile instead of rewriting the workflow
