# Extensions And Tool Contracts

Autopilot now exposes a public tool layer over the local connector registry. Operators still configure connectors, but product-facing API and dashboard surfaces can talk in terms of tools.

## Tool contract

Each tool in the capability catalog exposes:

- `tool_id`
- `kind`
- `transport`
- `scope`
- `approval_policy`
- `provider_compatibility`

These fields are derived from the connector registry and stay stable even when the underlying connector record carries extra implementation details.

Approval policy follows connector risk level:

- `low -> auto`
- `medium -> policy`
- `high -> manual`

## Extension registry

The capability catalog also exposes extension slots for:

- providers
- runtimes
- trackers
- notifiers

The shared lifecycle is:

1. `register`
2. `validate`
3. `expose`
4. `audit`

Today the provider and tool paths are the most mature public extension surfaces. Tracker and notifier slots are already visible in the registry and ship with built-in entries, but broader external packaging is still a later slice.

Tracker and notifier registrations now also have a config-driven path, so external teams can register them without editing core orchestration code.

## Example 1: add an HTTP API tool

Use the Settings page or write the same shape into `connectors.json`:

```json
{
  "id": "crm_api",
  "name": "CRM API",
  "connector_type": "http_api",
  "description": "Query the CRM for lead and account state.",
  "transport": "http",
  "tags": ["api", "integration", "backend"],
  "providers": ["codex", "claude", "ollama"],
  "risk_level": "medium",
  "scopes": ["network"],
  "enabled": true,
  "config": {
    "base_url": "https://crm.example.com",
    "auth_strategy": "bearer"
  }
}
```

This becomes a public tool contract with:

- `tool_id: crm_api`
- `kind: http_api`
- `scope: network`
- `approval_policy: policy`

## Example 2: add an MCP server tool

```json
{
  "id": "docs_context",
  "name": "Docs Context",
  "connector_type": "mcp_server",
  "description": "Expose internal docs through an MCP server.",
  "transport": "stdio",
  "tags": ["docs", "research"],
  "providers": ["codex", "claude", "gemini"],
  "risk_level": "low",
  "scopes": ["workspace"],
  "enabled": true,
  "config": {
    "command": "npx company-docs-mcp",
    "args": ["--stdio"]
  }
}
```

This shows up in the tool layer as an `mcp_server` tool with `approval_policy: auto`.

## Example 3: add a local provider contract

Add the provider to `config.yaml`:

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

Then validate it:

```bash
./.venv/bin/autopilot doctor /path/to/project --refresh
```

The provider becomes visible in:

- `/api/capabilities/catalog`
- `/api/capabilities/providers`
- `/api/capabilities/extensions`
- the Settings and Intake dashboards

## Example 4: register a tracker contract

Add a tracker in `config.yaml`:

```yaml
trackers:
  - id: linear
    display_name: Linear
    kind: issue_tracker
    transport: webhook
    endpoint: https://linear.example.com/hooks/autopilot
    auth_strategy: bearer
    event_kinds: [issue.created, issue.updated]
```

This tracker shows up in the extension registry and can ingest external items through:

```bash
curl -X POST http://127.0.0.1:8000/api/integrations/tracker-items \
  -H "Content-Type: application/json" \
  -d '{
    "tracker_id": "linear",
    "action": "issue.created",
    "item_kind": "issue",
    "item": {
      "external_id": "ENG-42",
      "title": "Ship notifier registry",
      "body": "- [ ] Surface configured channels"
    }
  }'
```

## Example 5: register a notifier channel

Add a notifier in `config.yaml`:

```yaml
notifications:
  - name: ops-webhook
    kind: webhook
    events: [run_failed, story_stuck]
    webhook_url: https://notify.example.com/autopilot
```

This channel keeps working as a real notification transport and now also appears in the extension registry with readiness and target metadata.

## What shows up at runtime

Project and story payloads now expose both:

- connector activation state
- derived tool activation state

That means operators can inspect the internal connector reason and the public tool-facing summary from the same run context without changing orchestration logic.
