# Execution Brief Bridge

`Execution Brief` is the minimal handoff object between a portfolio/research system such as `Quorum` and the `Autopilot` execution engine.

## Why it exists

`Quorum` is good at:

- discovering ideas
- ranking them
- debating them
- pivoting them
- choosing which opportunity deserves execution

`Autopilot` is good at:

- turning a scoped brief into a PRD
- breaking the PRD into stories
- executing stories with worker + critic loops
- running multiple story teams in sequence or in parallel

The bridge between them should be a typed artifact, not an unstructured chat transcript.

## Minimal flow

1. `Quorum` produces an `Execution Brief`
2. `Autopilot` receives it via `POST /api/projects/from-execution-brief`
3. `Autopilot` also exposes a stable external alias via `POST /api/execution-plane/projects/from-brief`
4. `Autopilot` renders the brief into a planner-friendly spec
5. `Autopilot` uses the existing PRD generation pipeline
6. `Autopilot` creates the local project
7. `Autopilot` persists the typed brief at `.agents/tasks/execution-brief.json`
8. `Autopilot` optionally launches execution immediately

## Endpoints

### Get the schema

`GET /api/projects/execution-brief/schema`

Returns the JSON schema generated from the `ExecutionBrief` model.

### Create a project from a brief

`POST /api/projects/from-execution-brief`

Compatibility endpoint for the dashboard.

### Stable execution-plane ingest

`POST /api/execution-plane/projects/from-brief`

FounderOS-facing stable ingest endpoint. Returns a typed execution-plane project snapshot plus the generated PRD.

Request shape:

```json
{
  "brief": {
    "title": "GraphRAG Copilot",
    "thesis": "Build a niche affiliate GraphRAG copilot for paid media buyers.",
    "summary": "Execution-ready hypothesis after ranking and tournament review.",
    "tags": ["affiliate", "graphrag", "ai"],
    "founder": {
      "mode": "solo_ai_augmented",
      "strengths": ["python", "agents", "graphs"],
      "constraints": ["ship in 30 days"]
    },
    "market": {
      "icp": "affiliate operators and media buyers",
      "pain": "fragmented affiliate intel and no structured retrieval",
      "wedge": "existing research corpus plus graph retrieval"
    },
    "execution": {
      "mvp_scope": ["ingest corpus", "graph retrieval", "chat workflow"],
      "required_connectors": ["web_docs", "github"],
      "existing_repos": ["/abs/path/to/repo"]
    },
    "monetization": {
      "revenue_model": "subscription",
      "pricing_hint": "$99-$199/mo",
      "time_to_first_dollar": "2-4 weeks"
    },
    "evaluation": {
      "success_metrics": ["3 paid pilots"],
      "kill_criteria": ["no ICP pull after 10 demos"]
    },
    "initiative": {
      "id": "init_founderos_1",
      "title": "FounderOS Execution Plane",
      "stage": "mvp",
      "hypothesis_id": "hyp_founderos_1",
      "track": "core"
    },
    "orchestration": {
      "orchestrator": "founderos",
      "run_id": "run_123",
      "initiative_ref": "founderos/init_founderos_1",
      "project_ref": "founderos/proj_abc",
      "requested_launch_preset": "parallel"
    },
    "provenance": {
      "source_system": "quorum",
      "source_mode": "tournament",
      "source_session_id": "sess_123"
    }
  },
  "project_path": "/abs/path/to/new-project",
  "priority": "high",
  "launch": true,
  "launch_profile": {
    "preset": "parallel",
    "story_execution_mode": "team",
    "project_concurrency_mode": "parallel",
    "max_parallel_stories": 2
  }
}
```

### List execution projects

`GET /api/execution-plane/projects`

Returns stable execution-plane snapshots with:

- initiative mapping
- orchestration metadata
- runtime status
- story progress
- budget state

### Get one execution project

`GET /api/execution-plane/projects/{project_id}`

Returns the richer execution-plane view including:

- persisted brief payload
- phases and stories
- runtime-control inspection
- timeline

### Read execution events

`GET /api/execution-plane/events`

Supports filtering by:

- `project_id`
- `initiative_id`
- `orchestrator`

Project-scoped alias:

`GET /api/execution-plane/projects/{project_id}/events`

### Read execution issues

`GET /api/execution-plane/issues`

Project-scoped aliases:

- `GET /api/execution-plane/projects/{project_id}/issues`
- `GET /api/execution-plane/issues/{issue_id}`
- `POST /api/execution-plane/issues/{issue_id}/resolve`

### Command policy

Project-scoped endpoints:

- `GET /api/execution-plane/projects/{project_id}/command-policy`
- `PATCH /api/execution-plane/projects/{project_id}/command-policy`

### Explicit external commands

`POST /api/execution-plane/projects/{project_id}/commands/{command}`

Supported commands:

- `launch`
- `pause`
- `resume`
- `archive`
- `update_budget_policy`

## What this enables next

This is the first building block for a higher-level control plane:

- `Quorum` as portfolio brain
- `Autopilot` as execution plant
- a future dashboard that shows research, ranking, execution, and reinvest/kill decisions in one place
