import {
  asRecord,
  toStringArray,
  toStringValue,
} from "@/lib/control-plane-data";
import type {
  AgentPriorityQueueKind,
  AgentQueueAdvanceTarget,
  AgentTimelineEntry,
  LinkedSelectionContext,
  PendingAgentTimelineTarget,
  SessionLineageEntry,
  SessionQueueAdvanceTarget,
} from "@/lib/control-plane-models";
import type { ExecutionAgentActionRunRecord } from "@/lib/types";

function domSafeToken(value: string): string {
  return encodeURIComponent(value);
}

function findRunResultIndexByApprovalId(
  run: ExecutionAgentActionRunRecord,
  approvalId: string
): number {
  if (!approvalId) return -1;
  return run.results.findIndex(
    (result) => toStringValue(asRecord(asRecord(result)?.approval)?.id) === approvalId
  );
}

function findRunResultIndexByIssueId(
  run: ExecutionAgentActionRunRecord,
  issueId: string
): number {
  if (!issueId) return -1;
  return run.results.findIndex(
    (result) => toStringValue(asRecord(asRecord(result)?.issue)?.id) === issueId
  );
}

export function agentTimelineEntryKey(entry: AgentTimelineEntry): string {
  return `${entry.kind}:${entry.id}`;
}

export function sessionEventKey(event: Record<string, unknown>, fallback = ""): string {
  return `${toStringValue(event.event, "event")}:${toStringValue(event.timestamp, fallback || "unknown")}`;
}

export function sessionContextRowDomId(
  kind: "approval" | "issue" | "event" | "tool_permission_runtime",
  key: string
): string {
  return key ? `session-context-row-${kind}-${domSafeToken(key)}` : "";
}

export function agentTimelineRowDomId(runtimeAgentId: string, key: string): string {
  return runtimeAgentId && key
    ? `agent-timeline-row-${domSafeToken(runtimeAgentId)}-${domSafeToken(key)}`
    : "";
}

export function sessionQueueAdvanceTarget(
  filter: string,
  entry: SessionLineageEntry
): SessionQueueAdvanceTarget {
  return {
    kind: "session-lineage",
    filter,
    entry,
  };
}

export function agentQueueAdvanceTarget(
  priority: AgentPriorityQueueKind,
  entry: AgentTimelineEntry
): AgentQueueAdvanceTarget {
  return {
    kind: "agent-timeline",
    priority,
    entry,
  };
}

export function withSelectedItem<T>(
  items: T[],
  selected: T | null,
  limit: number,
  getKey: (item: T) => string
): T[] {
  const limited = items.slice(0, limit);
  if (!selected) return limited;
  const selectedKey = getKey(selected);
  if (!selectedKey || limited.some((item) => getKey(item) === selectedKey)) {
    return limited;
  }
  return [selected, ...limited.slice(0, Math.max(limit - 1, 0))];
}

export function resolveAgentTimelineRunLink(
  entry: AgentTimelineEntry,
  runs: ExecutionAgentActionRunRecord[]
): { run: ExecutionAgentActionRunRecord; resultIndex: number } | null {
  const linkedApprovalId =
    entry.approval?.id ||
    entry.issue?.approval_id ||
    toStringValue(entry.event?.approval_id);
  const linkedIssueId = entry.issue?.id || toStringValue(entry.event?.issue_id);
  const linkedRunId =
    toStringValue(entry.event?.agent_action_run_id) ||
    toStringValue(entry.event?.run_id);

  if (linkedRunId) {
    const directRun = runs.find((run) => run.id === linkedRunId);
    if (directRun) {
      const approvalIndex = findRunResultIndexByApprovalId(directRun, linkedApprovalId);
      if (approvalIndex >= 0) {
        return { run: directRun, resultIndex: approvalIndex };
      }
      const issueIndex = findRunResultIndexByIssueId(directRun, linkedIssueId);
      if (issueIndex >= 0) {
        return { run: directRun, resultIndex: issueIndex };
      }
      return { run: directRun, resultIndex: 0 };
    }
  }

  if (linkedApprovalId) {
    for (const run of runs) {
      const resultIndex = findRunResultIndexByApprovalId(run, linkedApprovalId);
      if (resultIndex >= 0) {
        return { run, resultIndex };
      }
    }
  }

  if (linkedIssueId) {
    for (const run of runs) {
      const resultIndex = findRunResultIndexByIssueId(run, linkedIssueId);
      if (resultIndex >= 0) {
        return { run, resultIndex };
      }
    }
  }

  return null;
}

export function resolveAgentTimelineEntryFromTarget(
  entries: AgentTimelineEntry[],
  target: PendingAgentTimelineTarget
): AgentTimelineEntry | null {
  if (target.approvalId) {
    const approvalEntry = entries.find(
      (entry) => entry.kind === "approval" && entry.approval?.id === target.approvalId
    );
    if (approvalEntry) return approvalEntry;
  }

  if (target.issueId) {
    const issueEntry = entries.find(
      (entry) => entry.kind === "issue" && entry.issue?.id === target.issueId
    );
    if (issueEntry) return issueEntry;
  }

  const eventMatches = entries.filter((entry) => entry.kind === "event");

  const exactEvent = eventMatches.find((entry) => {
    const eventRunId =
      toStringValue(entry.event?.agent_action_run_id) || toStringValue(entry.event?.run_id);
    const eventApprovalId = toStringValue(entry.event?.approval_id);
    const eventIssueId = toStringValue(entry.event?.issue_id);
    return (
      eventRunId === target.runId &&
      ((target.approvalId && eventApprovalId === target.approvalId) ||
        (target.issueId && eventIssueId === target.issueId))
    );
  });
  if (exactEvent) return exactEvent;

  if (target.approvalId) {
    const approvalEvent = eventMatches.find(
      (entry) => toStringValue(entry.event?.approval_id) === target.approvalId
    );
    if (approvalEvent) return approvalEvent;
  }

  if (target.issueId) {
    const issueEvent = eventMatches.find(
      (entry) => toStringValue(entry.event?.issue_id) === target.issueId
    );
    if (issueEvent) return issueEvent;
  }

  if (target.runId) {
    const runEvent = eventMatches.find((entry) => {
      const eventRunId =
        toStringValue(entry.event?.agent_action_run_id) || toStringValue(entry.event?.run_id);
      return eventRunId === target.runId;
    });
    if (runEvent) return runEvent;
  }

  return null;
}

export function resolveRunLinkFromContext(
  runs: ExecutionAgentActionRunRecord[],
  context: LinkedSelectionContext
): { run: ExecutionAgentActionRunRecord; resultIndex: number } | null {
  const linkedRunId = toStringValue(context.runId);
  const linkedApprovalId = toStringValue(context.approvalId);
  const linkedIssueId = toStringValue(context.issueId);

  if (linkedRunId) {
    const directRun = runs.find((run) => run.id === linkedRunId);
    if (directRun) {
      const approvalIndex = findRunResultIndexByApprovalId(directRun, linkedApprovalId);
      if (approvalIndex >= 0) {
        return { run: directRun, resultIndex: approvalIndex };
      }
      const issueIndex = findRunResultIndexByIssueId(directRun, linkedIssueId);
      if (issueIndex >= 0) {
        return { run: directRun, resultIndex: issueIndex };
      }
      if (typeof context.resultIndex === "number" && context.resultIndex >= 0) {
        return { run: directRun, resultIndex: context.resultIndex };
      }
      return { run: directRun, resultIndex: 0 };
    }
  }

  if (linkedApprovalId) {
    for (const run of runs) {
      const resultIndex = findRunResultIndexByApprovalId(run, linkedApprovalId);
      if (resultIndex >= 0) {
        return { run, resultIndex };
      }
    }
  }

  if (linkedIssueId) {
    for (const run of runs) {
      const resultIndex = findRunResultIndexByIssueId(run, linkedIssueId);
      if (resultIndex >= 0) {
        return { run, resultIndex };
      }
    }
  }

  return null;
}

export function resolveSessionEventFromContext(
  events: Record<string, unknown>[],
  context: LinkedSelectionContext
): { event: Record<string, unknown>; key: string } | null {
  const linkedRunId = toStringValue(context.runId);
  const linkedApprovalId = toStringValue(context.approvalId);
  const linkedIssueId = toStringValue(context.issueId);
  const linkedRuntimeAgentId =
    toStringValue(context.runtimeAgentId) ||
    toStringValue(context.event?.runtime_agent_id) ||
    toStringArray(context.event?.runtime_agent_ids)[0];

  if (context.event) {
    const exactEventKey = sessionEventKey(context.event);
    const exactEvent = events.find((event) => sessionEventKey(event) === exactEventKey);
    if (exactEvent) {
      return { event: exactEvent, key: exactEventKey };
    }
  }

  const exactMatch = events.find((event) => {
    const eventRunId =
      toStringValue(event.agent_action_run_id) || toStringValue(event.run_id);
    const eventApprovalId = toStringValue(event.approval_id);
    const eventIssueId = toStringValue(event.issue_id);
    return (
      eventRunId === linkedRunId &&
      ((linkedApprovalId && eventApprovalId === linkedApprovalId) ||
        (linkedIssueId && eventIssueId === linkedIssueId))
    );
  });
  if (exactMatch) {
    return { event: exactMatch, key: sessionEventKey(exactMatch) };
  }

  if (linkedApprovalId) {
    const approvalEvent = events.find(
      (event) => toStringValue(event.approval_id) === linkedApprovalId
    );
    if (approvalEvent) {
      return { event: approvalEvent, key: sessionEventKey(approvalEvent) };
    }
  }

  if (linkedIssueId) {
    const issueEvent = events.find((event) => toStringValue(event.issue_id) === linkedIssueId);
    if (issueEvent) {
      return { event: issueEvent, key: sessionEventKey(issueEvent) };
    }
  }

  if (linkedRunId) {
    const runEvent = events.find((event) => {
      const eventRunId =
        toStringValue(event.agent_action_run_id) || toStringValue(event.run_id);
      return eventRunId === linkedRunId;
    });
    if (runEvent) {
      return { event: runEvent, key: sessionEventKey(runEvent) };
    }
  }

  if (linkedRuntimeAgentId) {
    const agentEvent = events.find((event) => {
      const eventRuntimeAgentIds = [
        toStringValue(event.runtime_agent_id),
        ...toStringArray(event.runtime_agent_ids),
      ].filter(Boolean);
      return eventRuntimeAgentIds.includes(linkedRuntimeAgentId);
    });
    if (agentEvent) {
      return { event: agentEvent, key: sessionEventKey(agentEvent) };
    }
  }

  return null;
}
