# Product Comparison

Autopilot is built for founder-visible execution, not for hiding orchestration behind an opaque agent loop.

## Category Comparison

| Category | Primary job | Coordination model | Operator visibility | Delivery contract |
| --- | --- | --- | --- | --- |
| Autopilot | turn a brief or source item into tracked execution and final handoff | deterministic execution plane with explicit policies, previews, approvals, and gates | high: dashboard, CLI, trace, previews, approvals, delivery loop | `Execution Brief`, `TaskSource`, PR or handoff artifact |
| swarm tools | coordinate multiple autonomous agents toward a task | agent-to-agent collaboration and delegation | medium to low, varies by implementation | often task oriented, but not necessarily tied to one durable delivery contract |
| coding copilots | help one engineer write or review code interactively | human-driven prompt and edit loop | high in the editor, but usually local to one coding session | usually an interactive coding session, not a tracked source-to-delivery workflow |
| CI or job runners | execute fixed automation reliably | declarative jobs and scripts | high for logs, low for adaptive execution state | job definition and build output |

## When Autopilot Fits Best

Use Autopilot when you need:

- one source item or brief to stay visible through execution, review, and handoff
- deterministic orchestration instead of an LLM deciding the control plane
- preview and approval gates before risky changes are applied
- local-first or hybrid runtime portability without rewriting orchestration logic
- delivery state that founders and operators can inspect without reading raw agent logs

## When Another Category Fits Better

- Use a coding copilot when one engineer just needs faster interactive editing inside an IDE.
- Use a swarm tool when the main problem is coordinating many autonomous agents, not enforcing one operator-facing delivery contract.
- Use a CI runner when the task is fully scripted and does not need adaptive review, preview, or approval loops.
