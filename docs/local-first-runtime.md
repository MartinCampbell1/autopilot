# Local-First Runtime Setup

Autopilot can now run the same workflow contract against local runtimes, not only managed cloud CLI accounts. This is the public Phase 2 portability surface.

## Supported Local Provider Families

- `openai_compatible`
  Use this for a local or self-hosted endpoint that exposes an OpenAI-compatible `/v1` API. Autopilot probes `GET /v1/models` and uses the first returned model when no explicit model override is provided.
- `local_command`
  Use this for a local executable or wrapper script. Autopilot can pass the prompt through `stdin`, `AUTOPILOT_PROMPT`, or inline argument templates such as `{prompt}`, `{model}`, and `{mode}`.

## Provider Contract

Each configured runtime lives under `providers:` in `~/.autopilot/config.yaml`.

Example: OpenAI-compatible local endpoint

```yaml
providers:
  - id: local-openai
    family: openai_compatible
    mode: local
    transport: http
    endpoint: http://127.0.0.1:11434/v1
    auth_strategy: none
    capabilities: [exec, review, critic]
```

Example: local command wrapper

```yaml
providers:
  - id: local-command
    family: local_command
    mode: local
    transport: command
    command:
      - /usr/local/bin/autopilot-local-runtime
      - --mode
      - "{mode}"
      - --model
      - "{model}"
    auth_strategy: none
    capabilities: [exec, review]
```

Notes:

- `id` is the stable runtime id surfaced in doctor, dashboard, and launch selection.
- `family` chooses the adapter implementation.
- `mode` should be `local` for local-first runtimes.
- `transport` is operator-visible and should match the real execution path: `http` or `command`.
- `auth_strategy` is usually `none` for fully local runtimes. If your compatible endpoint requires a bearer token, keep the endpoint local but expose the token through `OPENAI_API_KEY` or `AUTOPILOT_PROVIDER_API_KEY`.
- `capabilities` should reflect what the runtime can safely do. `critic` is supported for `openai_compatible`; `local_command` can support it if your wrapper handles review prompts correctly.

## Runtime Profiles

Runtime profiles are independent from providers. They describe sandboxing, network, filesystem policy, and default tools.

Example:

```yaml
runtime_profiles:
  - id: local
    sandbox_mode: host
    network_policy: local-only
    filesystem_policy: workspace-write
    default_tools: [shell, git]
  - id: hybrid
    sandbox_mode: host
    network_policy: mixed
    filesystem_policy: workspace-write
    default_tools: [shell, git, browser]
```

## Verification Path

After editing `~/.autopilot/config.yaml`, validate the runtime contract:

```bash
./.venv/bin/autopilot doctor /path/to/project --refresh
./.venv/bin/autopilot status
./.venv/bin/autopilot live --once
```

What to expect:

- `doctor` should show the configured provider contract and runtime profiles.
- `openai_compatible` should report a healthy endpoint if `/v1/models` is reachable.
- `local_command` should report a ready runtime if the configured executable resolves on `PATH` or as an absolute path.
- stateless local runtimes intentionally reject `autopilot login <provider>` and session import.

## Launch Path

Once the provider contract is valid:

1. Open the intake dashboard.
2. Choose a launch preset.
3. Choose `Execution Provider`.
4. Choose `Runtime Profile`.
5. Launch the project.

Autopilot persists the selected `provider`, `provider_config_id`, and `runtime_profile_id` into the launch contract, so the same orchestration logic can run against cloud or local runtimes without rewriting planner logic.

## Local Command Integration Notes

`local_command` is intended for wrapper scripts that translate Autopilot prompts into another local runtime. The wrapper receives:

- `AUTOPILOT_PROMPT`
- `AUTOPILOT_MODE`
- `AUTOPILOT_MODEL` when a model override is present
- the full provider contract in `AUTOPILOT_PROVIDER_CONFIG_JSON`

If your command args contain `{prompt}`, `{model}`, or `{mode}`, Autopilot substitutes those tokens inline. If `{prompt}` is not present, Autopilot also sends the prompt over `stdin`.
