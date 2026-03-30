"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import {
  SummaryStat,
} from "@/components/control-plane-display";
import { ControlPlaneWorkspaceSection } from "@/components/control-plane-workspace-section";
import {
  type QueueAdvanceFeedback,
  type QueueAdvanceFocusDelta,
  type QueueAdvanceFocusSummary,
  type QueueAdvanceNoticeActionProps,
  type QueueAdvanceReasonDetails,
  type QueueAdvanceSignal,
} from "@/components/queue-advance-notice";
import { SessionDrilldownSection } from "@/components/session-drilldown-section";
import { SelectedOutcomeInspector } from "@/components/selected-outcome-inspector";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  applyExecutionPlaneOrchestratorSessionControlPlan,
  applyExecutionPlaneOrchestratorSessionRecommendation,
  applyExecutionPlaneApproval,
  approveExecutionPlaneApproval,
  executeExecutionPlaneAgentAction,
  fetchAccountsHealth,
  fetchExecutionPlaneAgentDetail,
  fetchExecutionPlaneControlPassSummary,
  fetchExecutionPlaneControlPasses,
  fetchExecutionPlaneOrchestratorSession,
  fetchExecutionPlaneOrchestratorSessionControlProfiles,
  fetchExecutionPlaneOrchestratorSessions,
  fetchExecutionPlaneOrchestratorSessionSummary,
  fetchProjects,
  rejectExecutionPlaneApproval,
  resolveExecutionPlaneIssue,
} from "@/lib/api";
import { approvalStatusClass, controlStateClass, passStatusClass } from "@/lib/control-plane-ui";
import { useSSE } from "@/lib/sse";
import type {
  AccountHealth,
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
  ExecutionPlaneCountMap,
  ExecutionIssueRecord,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
  OrchestratorSessionControlProfile,
  OrchestratorSessionControlRecommendation,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  ProjectSummary,
} from "@/lib/types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const DEFAULT_CONTROL_ACTOR = "dashboard-control-plane";
const LINEAGE_QUEUE_STORAGE_PREFIX = "control-plane:lineage-queue:";
const AGENT_TIMELINE_STORAGE_PREFIX = "control-plane:agent-timeline:";
const SESSION_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:session-queue-focus:";
const AGENT_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:agent-queue-focus:";
const TRIAGE_INBOX_FEEDBACK_LIMIT = 5;
const SESSION_LINEAGE_QUEUE_KEYS: LineageQueueKind[] = ["attention", "decisions"];
const AGENT_PRIORITY_QUEUE_KEYS = ["critical", "high"] as const;

type AgentScopedOutcome = {
  run: ExecutionAgentActionRunRecord;
  result: Record<string, unknown>;
  resultIndex: number;
  timestamp: string;
  runtimeAgentIds: string[];
};

type AgentTimelineEntry = {
  kind: "approval" | "issue" | "event";
  id: string;
  timestamp: string;
  status: string;
  title: string;
  subtitle: string;
  message: string;
  approval?: ExecutionApprovalRecord;
  issue?: ExecutionIssueRecord;
  event?: Record<string, unknown>;
};

type PendingAgentTimelineTarget = {
  runtimeAgentId: string;
  runId: string;
  approvalId: string;
  issueId: string;
};

type LinkedSelectionContext = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

type SessionContextKind = "" | "approval" | "issue" | "event";
type LineageQueueKind = "attention" | "decisions";
type TriagePriority = "critical" | "high" | "normal";
type OperatorVisibilityState = {
  dismissed: string[];
  snoozedUntil: Record<string, number>;
};
type PersistedLineageQueueState = {
  dismissed?: Partial<Record<LineageQueueKind, string[]>>;
  snoozedUntil?: Partial<Record<LineageQueueKind, Record<string, number>>>;
};
type PersistedAgentTimelineState = {
  dismissed?: string[];
  snoozedUntil?: Record<string, number>;
};
type SessionLineageEntry = {
  key: string;
  runId: string;
  resultIndex: number;
  timestamp: string;
  status: string;
  title: string;
  subtitle: string;
  message: string;
  approvalId: string;
  issueId: string;
  eventKey: string;
  eventName: string;
  runtimeAgentId: string;
  projectId: string;
  projectName: string;
  storyId: number | null;
  storyTitle: string;
  event: Record<string, unknown> | null;
};
type SessionLineageTrait = {
  key: string;
  label: string;
  className: string;
};
type TriageInboxItem = {
  key: string;
  label: string;
  queueDetail: string;
  title: string;
  subtitle: string;
  timestamp: string;
  status: string;
  statusClassName: string;
  priority: TriagePriority;
  syncedWithSelection: boolean;
  onInspect: () => void;
  onSnooze: () => void;
  onDismiss: () => void;
};
type TriageInboxFeedback = {
  itemKey: string;
  itemLabel: string;
  message: string;
  tone: "info" | "success";
  timestamp: string;
};
type TriageInboxFeedbackGroup = {
  itemKey: string;
  itemLabel: string;
  entries: TriageInboxFeedback[];
  isActive: boolean;
};
type SessionQueueAdvanceTarget = {
  kind: "session-lineage";
  filter: string;
  entry: SessionLineageEntry;
};
type AgentQueueAdvanceTarget = {
  kind: "agent-timeline";
  priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number];
  entry: AgentTimelineEntry;
};
type QueueAdvanceTarget = SessionQueueAdvanceTarget | AgentQueueAdvanceTarget;

function agentTimelineEntryKey(entry: AgentTimelineEntry): string {
  return `${entry.kind}:${entry.id}`;
}

function domSafeToken(value: string): string {
  return encodeURIComponent(value);
}

function sessionEventKey(event: Record<string, unknown>, fallback = ""): string {
  return `${toStringValue(event.event, "event")}:${toStringValue(event.timestamp, fallback || "unknown")}`;
}

function sessionContextRowDomId(kind: "approval" | "issue" | "event", key: string): string {
  return key ? `session-context-row-${kind}-${domSafeToken(key)}` : "";
}

function agentTimelineRowDomId(runtimeAgentId: string, key: string): string {
  return runtimeAgentId && key
    ? `agent-timeline-row-${domSafeToken(runtimeAgentId)}-${domSafeToken(key)}`
    : "";
}

function sessionQueueAdvanceTarget(
  filter: string,
  entry: SessionLineageEntry
): SessionQueueAdvanceTarget {
  return {
    kind: "session-lineage",
    filter,
    entry,
  };
}

function agentQueueAdvanceTarget(
  priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number],
  entry: AgentTimelineEntry
): AgentQueueAdvanceTarget {
  return {
    kind: "agent-timeline",
    priority,
    entry,
  };
}

function scrollToDomId(id: string): boolean {
  if (!id || typeof document === "undefined") return false;
  const node = document.getElementById(id);
  if (!node) return false;
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  return true;
}

function withSelectedItem<T>(
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

function resolveAgentTimelineRunLink(
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

function resolveAgentTimelineEntryFromTarget(
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

function resolveRunLinkFromContext(
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

function resolveSessionEventFromContext(
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

function formatTimestamp(value?: string | null): string {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return DATE_FORMATTER.format(date);
}

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toNullableNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function normalizeSearchQuery(value: string): string {
  return value.trim().toLowerCase();
}

function searchText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.toLowerCase();
  if (typeof value === "number" || typeof value === "boolean") return String(value).toLowerCase();
  if (Array.isArray(value)) return value.map((item) => searchText(item)).join(" ");
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>)
      .map((item) => searchText(item))
      .join(" ");
  }
  return String(value).toLowerCase();
}

function matchesSearch(values: unknown[], query: string): boolean {
  const normalized = normalizeSearchQuery(query);
  if (!normalized) return true;
  return values.some((value) => searchText(value).includes(normalized));
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function toStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => toStringValue(item)).filter(Boolean)
    : [];
}

function extractRunId(value: unknown): string {
  const record = asRecord(value);
  if (!record) return "";
  return toStringValue(asRecord(record.run)?.id);
}

function extractLatestRunIdFromAppliedSteps(value: Array<Record<string, unknown>>): string {
  for (const step of [...value].reverse()) {
    const runId = extractRunId(step.result);
    if (runId) return runId;
  }
  return "";
}

function formatScopeList(values: string[], fallback: string): string {
  return values.length ? values.join(", ") : fallback;
}

function outcomeProjectId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return (
    toStringValue(action?.project_id) ||
    toStringValue(project?.id)
  );
}

function outcomeProjectName(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return (
    toStringValue(action?.project_name) ||
    toStringValue(project?.name) ||
    outcomeProjectId(result)
  );
}

function outcomeStoryId(result: Record<string, unknown>): number | null {
  const action = asRecord(result.action);
  return toNullableNumber(action?.story_id);
}

function outcomeStoryTitle(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.story_title);
}

function outcomeRuntimeAgentId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.runtime_agent_id);
}

function outcomeRuntimeAgentIds(result: Record<string, unknown>): string[] {
  const action = asRecord(result.action);
  const linkedIds = toStringArray(action?.runtime_agent_ids);
  const singleId = toStringValue(action?.runtime_agent_id);
  return [...new Set([...linkedIds, ...(singleId ? [singleId] : [])])];
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function eventFamily(eventName: string): string {
  if (!eventName) return "other";
  if (
    eventName.includes("approval") ||
    eventName.includes("issue") ||
    eventName.includes("budget_paused")
  ) {
    return "decisions";
  }
  if (
    eventName.startsWith("execution_plane_orchestrator_session") ||
    eventName.includes("control_pass")
  ) {
    return "control";
  }
  if (
    eventName.includes("agent_action") ||
    eventName.includes("agent_batch") ||
    eventName.includes("action_run")
  ) {
    return "actions";
  }
  return "runtime";
}

function matchesRunFilter(run: ExecutionAgentActionRunRecord, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "execute") return !run.dry_run;
  if (filter === "preview") return run.dry_run;
  if (filter === "attention") {
    return (
      run.status === "error" ||
      run.status === "partial" ||
      run.results.some((result) =>
        ["error", "pending_approval", "not_executable"].includes(toStringValue(result.status))
      )
    );
  }
  return true;
}

function matchesEventFilter(event: Record<string, unknown>, filter: string): boolean {
  if (filter === "all") return true;
  const name = toStringValue(event.event);
  const status = toStringValue(event.status);
  if (filter === "attention") {
    return ["error", "partial", "pending_approval", "failed"].includes(status);
  }
  return eventFamily(name) === filter;
}

function matchesAgentOutcomeFilter(outcome: AgentScopedOutcome, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "execute") return !outcome.run.dry_run;
  if (filter === "preview") return outcome.run.dry_run;
  if (filter === "attention") {
    const status = toStringValue(outcome.result.status);
    return ["error", "partial", "pending_approval", "not_executable", "failed"].includes(status);
  }
  return true;
}

function matchesAgentTimelineFilter(entry: AgentTimelineEntry, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "approvals") return entry.kind === "approval";
  if (filter === "issues") return entry.kind === "issue";
  if (filter === "events") return entry.kind === "event";
  if (filter === "attention") {
    if (entry.kind === "approval") {
      return ["pending", "approved"].includes(entry.status);
    }
    if (entry.kind === "issue") {
      return entry.status === "open";
    }
    return ["error", "partial", "pending_approval", "failed"].includes(entry.status);
  }
  return true;
}

function isAttentionLineageEntry(entry: SessionLineageEntry): boolean {
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  return (
    Boolean(entry.issueId) ||
    ["error", "partial", "pending_approval", "failed", "rejected", "blocked", "not_executable"].includes(
      status
    ) ||
    ["error", "partial", "pending_approval", "failed"].includes(eventStatus)
  );
}

function matchesSessionLineageFilter(entry: SessionLineageEntry, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "attention") {
    return isAttentionLineageEntry(entry);
  }
  if (filter === "decisions") return Boolean(entry.approvalId || entry.issueId);
  if (filter === "agent-linked") return Boolean(entry.runtimeAgentId);
  return true;
}

function sessionLineageTraits(entry: SessionLineageEntry | null): SessionLineageTrait[] {
  if (!entry) return [];
  return [
    isAttentionLineageEntry(entry)
      ? { key: "attention", label: "Attention", className: "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]" }
      : null,
    entry.approvalId || entry.issueId
      ? { key: "decision", label: "Decision-linked", className: "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]" }
      : null,
    entry.eventKey
      ? { key: "event", label: "Event-linked", className: "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]" }
      : null,
    entry.runtimeAgentId
      ? { key: "agent", label: "Agent-linked", className: "border-[#e5e5e3] bg-white text-[#37352f]" }
      : null,
  ].filter(Boolean) as SessionLineageTrait[];
}

function triagePriorityRank(priority: TriagePriority): number {
  switch (priority) {
    case "critical":
      return 0;
    case "high":
      return 1;
    default:
      return 2;
  }
}

function triagePriorityLabel(priority: TriagePriority): string {
  switch (priority) {
    case "critical":
      return "Critical";
    case "high":
      return "High";
    default:
      return "Normal";
  }
}

function sessionLineageFilterLabel(filter: string): string {
  switch (filter) {
    case "attention":
      return "Attention";
    case "decisions":
      return "Decisions";
    case "agent-linked":
      return "Agent-linked";
    default:
      return "All";
  }
}

function sessionLineageFilterClass(filter: string): string {
  switch (filter) {
    case "attention":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "decisions":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "agent-linked":
      return "border-[#e5e5e3] bg-white text-[#37352f]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function agentTimelineFilterLabel(filter: string): string {
  switch (filter) {
    case "approvals":
      return "Approvals";
    case "issues":
      return "Issues";
    case "events":
      return "Events";
    case "attention":
      return "Attention";
    default:
      return "All";
  }
}

function agentTimelineFilterClass(filter: string): string {
  switch (filter) {
    case "approvals":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "issues":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "events":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "attention":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function queueAdvanceSignal(
  key: string,
  label: string,
  className: string,
  focusFilter?: string
): QueueAdvanceSignal {
  return { key, label, className, focusFilter };
}

function buildQueueAdvanceFeedback(args: {
  title: string;
  detail: string;
  nextTarget?: QueueAdvanceTarget | null;
  previousTarget?: QueueAdvanceTarget | null;
  reasonDetails?: QueueAdvanceReasonDetails | null;
}): QueueAdvanceFeedback<QueueAdvanceTarget> {
  return {
    title: args.title,
    detail: args.detail,
    timestamp: new Date().toISOString(),
    nextTarget: args.nextTarget,
    previousTarget: args.previousTarget,
    reason: args.reasonDetails?.reason,
    reasonPriority: args.reasonDetails?.priority,
    signals: args.reasonDetails?.signals,
  };
}

function buildQueueAdvanceFocusSummary(args: {
  activeFilter: string;
  total: number;
  visible: number;
  labelForFilter: (filter: string) => string;
  classForFilter: (filter: string) => string;
  noun: string;
  scopeLabel: string;
}): QueueAdvanceFocusSummary {
  const { activeFilter, total, visible, labelForFilter, classForFilter, noun, scopeLabel } = args;
  const label = labelForFilter(activeFilter);
  return {
    label,
    detail:
      activeFilter === "all"
        ? `Showing ${visible} of ${total} ${noun} in the full ${scopeLabel} slice.`
        : `Showing ${visible} of ${total} ${noun} in the ${label.toLowerCase()} slice.`,
    activeFilter,
    badgeClassName: classForFilter(activeFilter),
  };
}

function sessionLineagePriority(entry: SessionLineageEntry): TriagePriority {
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  if (
    entry.issueId ||
    ["error", "failed", "blocked", "rejected", "not_executable"].includes(status) ||
    ["error", "failed"].includes(eventStatus)
  ) {
    return "critical";
  }
  if (entry.approvalId || isAttentionLineageEntry(entry)) {
    return "high";
  }
  return "normal";
}

function agentTimelinePriority(entry: AgentTimelineEntry): TriagePriority {
  const status = entry.status.toLowerCase();
  if (entry.kind === "issue" && status === "open") {
    return "critical";
  }
  if (entry.kind === "event" && ["error", "failed"].includes(status)) {
    return "critical";
  }
  if (entry.kind === "approval" && ["pending", "approved"].includes(status)) {
    return "high";
  }
  if (entry.kind === "event" && ["partial", "pending_approval", "blocked", "rejected"].includes(status)) {
    return "high";
  }
  return "normal";
}

function agentTimelineEntryStatusClass(entry: AgentTimelineEntry): string {
  if (entry.kind === "approval") {
    return approvalStatusClass(entry.status);
  }
  if (entry.kind === "issue") {
    return passStatusClass(entry.status === "open" ? "partial" : "ok");
  }
  return passStatusClass(entry.status);
}

function describeSessionQueueAdvanceReason(entry: SessionLineageEntry): QueueAdvanceReasonDetails {
  const priority = sessionLineagePriority(entry);
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  if (entry.issueId) {
    return {
      priority,
      reason: "Issue-linked chain stays at the front because it still represents an unresolved execution problem.",
      signals: [
        queueAdvanceSignal(
          "issue",
          "Issue-linked",
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "decisions"
        ),
      ],
    };
  }
  if (["error", "failed", "blocked", "rejected", "not_executable"].includes(status)) {
    return {
      priority,
      reason: `Run status "${status}" keeps this chain at ${triagePriorityLabel(priority).toLowerCase()} priority.`,
      signals: [
        queueAdvanceSignal(
          "run-status",
          `Run ${status}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
      ],
    };
  }
  if (["error", "failed"].includes(eventStatus)) {
    return {
      priority,
      reason: `Linked event status "${eventStatus}" keeps this chain elevated for operator attention.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${eventStatus}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
        queueAdvanceSignal(
          "event-linked",
          "Event-linked",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "all"
        ),
      ],
    };
  }
  if (entry.approvalId) {
    return {
      priority,
      reason: "Approval-linked chain remains next because it still needs an operator decision or apply step.",
      signals: [
        queueAdvanceSignal(
          "approval",
          "Approval-linked",
          "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]",
          "decisions"
        ),
      ],
    };
  }
  if (isAttentionLineageEntry(entry)) {
    return {
      priority,
      reason: "Attention signals on this chain still outweigh normal queue items after the previous transition.",
      signals: [
        queueAdvanceSignal(
          "attention",
          "Attention",
          "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]",
          "attention"
        ),
      ],
    };
  }
  if (entry.runtimeAgentId) {
    return {
      priority,
      reason: "Agent-linked context keeps this chain visible as the next operational handoff point.",
      signals: [
        queueAdvanceSignal(
          "agent",
          "Agent-linked",
          "border-[#e5e5e3] bg-white text-[#37352f]",
          "agent-linked"
        ),
      ],
    };
  }
  return {
    priority,
    reason: "This is the next visible queue item after the previous action completed.",
    signals: [
      queueAdvanceSignal(
        "queue-order",
        "Queue order",
        "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]",
        "all"
      ),
    ],
  };
}

function describeAgentQueueAdvanceReason(entry: AgentTimelineEntry): QueueAdvanceReasonDetails {
  const priority = agentTimelinePriority(entry);
  const status = entry.status.toLowerCase();
  if (entry.kind === "issue" && status === "open") {
    return {
      priority,
      reason: "Open issue keeps this agent item at the front because it still blocks or degrades execution.",
      signals: [
        queueAdvanceSignal(
          "issue",
          "Open issue",
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "issues"
        ),
      ],
    };
  }
  if (entry.kind === "event" && ["error", "failed"].includes(status)) {
    return {
      priority,
      reason: `Failed runtime event "${status}" keeps this agent item at ${triagePriorityLabel(priority).toLowerCase()} priority.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${status}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
        queueAdvanceSignal(
          "runtime-event",
          "Runtime event",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "events"
        ),
      ],
    };
  }
  if (entry.kind === "approval" && ["pending", "approved"].includes(status)) {
    return {
      priority,
      reason: `Approval status "${status}" keeps this agent item active until it is reviewed or applied.`,
      signals: [
        queueAdvanceSignal(
          "approval-status",
          `Approval ${status}`,
          "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]",
          "approvals"
        ),
      ],
    };
  }
  if (entry.kind === "event" && ["partial", "pending_approval", "blocked", "rejected"].includes(status)) {
    return {
      priority,
      reason: `Runtime event status "${status}" still needs operator attention before the agent can move cleanly.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${status}`,
          "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]",
          "attention"
        ),
        queueAdvanceSignal(
          "runtime-event",
          "Runtime event",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "events"
        ),
      ],
    };
  }
  return {
    priority,
    reason: "This is the next visible agent timeline item after the previous queue transition.",
    signals: [
      queueAdvanceSignal(
        "queue-order",
        "Queue order",
        "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]",
        "all"
      ),
    ],
  };
}

function countTriagePriorities<T>(
  entries: T[],
  getPriority: (entry: T) => TriagePriority
): Record<TriagePriority, number> {
  return entries.reduce<Record<TriagePriority, number>>(
    (acc, entry) => {
      const priority = getPriority(entry);
      acc[priority] += 1;
      return acc;
    },
    {
      critical: 0,
      high: 0,
      normal: 0,
    }
  );
}

function nextBestTriageItem<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string,
  getPriority: (entry: T) => TriagePriority
): T | null {
  if (!entries.length) return null;
  const rankedEntries = entries
    .map((entry, index) => ({ entry, index }))
    .sort(
      (left, right) =>
        triagePriorityRank(getPriority(left.entry)) - triagePriorityRank(getPriority(right.entry)) ||
        left.index - right.index
    )
    .map(({ entry }) => entry);
  if (!current) return rankedEntries[0] ?? null;
  const currentIndex = rankedEntries.findIndex((entry) => getKey(entry) === getKey(current));
  if (currentIndex === -1) return rankedEntries[0] ?? null;
  return rankedEntries[currentIndex + 1] ?? rankedEntries[0] ?? null;
}

function triageQueuePosition<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string
): number {
  if (!current) return -1;
  return entries.findIndex((entry) => getKey(entry) === getKey(current));
}

function nextTriageEntryByPriority<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string,
  getPriority: (entry: T) => TriagePriority,
  priority: TriagePriority
): T | null {
  const queue = entries.filter((entry) => getPriority(entry) === priority);
  if (!queue.length) return null;
  if (!current || getPriority(current) !== priority) {
    return queue[0] ?? null;
  }
  const currentIndex = queue.findIndex((entry) => getKey(entry) === getKey(current));
  if (currentIndex === -1) return queue[0] ?? null;
  return queue[currentIndex + 1] ?? queue[0] ?? null;
}

function nextSessionLineageQueueEntry(
  entries: SessionLineageEntry[],
  current: SessionLineageEntry | null
): SessionLineageEntry | null {
  if (!entries.length) return null;
  if (!current) return entries[0];
  const currentIndex = entries.findIndex((entry) => entry.key === current.key);
  if (currentIndex === -1) return entries[0];
  return entries[currentIndex + 1] ?? entries[0];
}

function sessionLineageQueuePosition(
  entries: SessionLineageEntry[],
  current: SessionLineageEntry | null
): number {
  if (!current) return -1;
  return entries.findIndex((entry) => entry.key === current.key);
}

function emptyDismissedLineageQueueKeys(): Record<LineageQueueKind, string[]> {
  return {
    attention: [],
    decisions: [],
  };
}

function emptySnoozedLineageQueueUntil(): Record<LineageQueueKind, Record<string, number>> {
  return {
    attention: {},
    decisions: {},
  };
}

function sanitizeOperatorVisibilityState(
  value:
    | {
        dismissed?: unknown;
        snoozedUntil?: unknown;
      }
    | null
    | undefined,
  now: number
): OperatorVisibilityState {
  const dismissed = Array.isArray(value?.dismissed)
    ? [...new Set(value.dismissed.filter((entry): entry is string => typeof entry === "string"))]
    : [];
  const snoozedUntil: Record<string, number> = {};
  const rawSnoozed = asRecord(value?.snoozedUntil);
  if (rawSnoozed) {
    Object.entries(rawSnoozed).forEach(([entryKey, until]) => {
      if (!entryKey) return;
      if (typeof until !== "number" || !Number.isFinite(until)) return;
      if (until <= now) return;
      snoozedUntil[entryKey] = until;
    });
  }
  return {
    dismissed,
    snoozedUntil,
  };
}

function isOperatorVisibilityStateEmpty(state: OperatorVisibilityState): boolean {
  return state.dismissed.length === 0 && Object.keys(state.snoozedUntil).length === 0;
}

function sanitizePersistedLineageQueueState(
  value: PersistedLineageQueueState | null | undefined,
  now: number
): {
  dismissed: Record<LineageQueueKind, string[]>;
  snoozedUntil: Record<LineageQueueKind, Record<string, number>>;
} {
  const dismissed = emptyDismissedLineageQueueKeys();
  const snoozedUntil = emptySnoozedLineageQueueUntil();
  const kinds: LineageQueueKind[] = ["attention", "decisions"];

  kinds.forEach((kind) => {
    const sanitized = sanitizeOperatorVisibilityState(
      {
        dismissed: value?.dismissed?.[kind],
        snoozedUntil: value?.snoozedUntil?.[kind],
      },
      now
    );
    dismissed[kind] = sanitized.dismissed;
    snoozedUntil[kind] = sanitized.snoozedUntil;
  });

  return {
    dismissed,
    snoozedUntil,
  };
}

function isPersistedLineageQueueStateEmpty(state: {
  dismissed: Record<LineageQueueKind, string[]>;
  snoozedUntil: Record<LineageQueueKind, Record<string, number>>;
}): boolean {
  return (
    isOperatorVisibilityStateEmpty({
      dismissed: state.dismissed.attention,
      snoozedUntil: state.snoozedUntil.attention,
    }) &&
    isOperatorVisibilityStateEmpty({
      dismissed: state.dismissed.decisions,
      snoozedUntil: state.snoozedUntil.decisions,
    })
  );
}

function lineageQueueStorageKey(sessionId: string): string {
  return `${LINEAGE_QUEUE_STORAGE_PREFIX}${sessionId}`;
}

function sanitizePersistedAgentTimelineState(
  value: PersistedAgentTimelineState | null | undefined,
  now: number
): {
  dismissed: string[];
  snoozedUntil: Record<string, number>;
} {
  return sanitizeOperatorVisibilityState(value, now);
}

function isPersistedAgentTimelineStateEmpty(state: {
  dismissed: string[];
  snoozedUntil: Record<string, number>;
}): boolean {
  return isOperatorVisibilityStateEmpty(state);
}

function agentTimelineStorageKey(runtimeAgentId: string): string {
  return `${AGENT_TIMELINE_STORAGE_PREFIX}${runtimeAgentId}`;
}

function sessionQueueFocusStorageKey(sessionId: string): string {
  return `${SESSION_QUEUE_FOCUS_STORAGE_PREFIX}${sessionId}`;
}

function agentQueueFocusStorageKey(runtimeAgentId: string): string {
  return `${AGENT_QUEUE_FOCUS_STORAGE_PREFIX}${runtimeAgentId}`;
}

function sanitizeQueueAdvanceFocusDelta(
  value: QueueAdvanceFocusDelta | null | undefined
): QueueAdvanceFocusDelta | null {
  if (!value || typeof value !== "object") return null;
  const fromLabel = toStringValue(value.fromLabel);
  const toLabel = toStringValue(value.toLabel);
  const timestamp = toStringValue(value.timestamp);
  const fromCount = Number(value.fromCount);
  const toCount = Number(value.toCount);
  if (!fromLabel || !toLabel || !timestamp) return null;
  if (!Number.isFinite(fromCount) || !Number.isFinite(toCount)) return null;
  return {
    fromLabel,
    toLabel,
    fromCount,
    toCount,
    timestamp,
  };
}

function buildQueueAdvanceFocusDelta(
  fromLabel: string,
  toLabel: string,
  fromCount: number,
  toCount: number
): QueueAdvanceFocusDelta {
  return {
    fromLabel,
    toLabel,
    fromCount,
    toCount,
    timestamp: new Date().toISOString(),
  };
}

function readPersistedQueueAdvanceFocusDelta(storageKey: string): QueueAdvanceFocusDelta | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(storageKey);
  if (!raw) return null;
  try {
    return sanitizeQueueAdvanceFocusDelta(JSON.parse(raw) as QueueAdvanceFocusDelta);
  } catch {
    return null;
  }
}

function persistQueueAdvanceFocusDelta(
  storageKey: string,
  value: QueueAdvanceFocusDelta | null | undefined
): void {
  if (typeof window === "undefined") return;
  const sanitized = sanitizeQueueAdvanceFocusDelta(value);
  if (!sanitized) {
    window.localStorage.removeItem(storageKey);
    return;
  }
  window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
}

function buildQueueAdvanceNoticeActionProps(args: {
  feedback: QueueAdvanceFeedback<QueueAdvanceTarget> | null;
  onOpenTarget: (target: QueueAdvanceTarget | null | undefined) => void;
  onSignalClick?: ((signal: QueueAdvanceSignal) => void) | undefined;
  onResetFocus?: (() => void) | undefined;
  onOpenMatchingQueue?: (() => void) | undefined;
}): QueueAdvanceNoticeActionProps {
  const { feedback, onOpenTarget, onSignalClick, onResetFocus, onOpenMatchingQueue } = args;
  return {
    onOpenSelectedNext: feedback?.nextTarget
      ? () => {
          onOpenTarget(feedback.nextTarget);
        }
      : undefined,
    onReopenPrevious: feedback?.previousTarget
      ? () => {
          onOpenTarget(feedback.previousTarget);
        }
      : undefined,
    onSignalClick: feedback?.nextTarget ? onSignalClick : undefined,
    onResetFocus,
    onOpenMatchingQueue,
  };
}

function visibleEntriesByOperatorVisibilityState<T>(
  entries: T[],
  getKey: (entry: T) => string,
  state: OperatorVisibilityState,
  now: number
): T[] {
  return entries.filter((entry) => {
    const entryKey = getKey(entry);
    if (!entryKey) return true;
    if (state.dismissed.includes(entryKey)) return false;
    const snoozedUntil = state.snoozedUntil[entryKey] ?? 0;
    return snoozedUntil <= now;
  });
}

function runMatchesSearch(run: ExecutionAgentActionRunRecord, query: string): boolean {
  return matchesSearch(
    [
      run.id,
      run.run_kind,
      run.actor,
      run.mode,
      run.reason,
      run.policy_profile,
      run.status,
      run.project_ids,
      run.initiative_ids,
      run.orchestrators,
      run.runtime_agent_ids,
      run.selection,
      run.summary,
      run.results,
    ],
    query
  );
}

function approvalMatchesSearch(approval: ExecutionApprovalRecord, query: string): boolean {
  return matchesSearch(
    [
      approval.id,
      approval.action,
      approval.status,
      approval.reason,
      approval.project_id,
      approval.project_name,
      approval.issue_id,
      approval.runtime_agent_ids,
      approval.policy_reasons,
      approval.payload,
    ],
    query
  );
}

function issueMatchesSearch(issue: ExecutionIssueRecord, query: string): boolean {
  return matchesSearch(
    [
      issue.id,
      issue.title,
      issue.description,
      issue.root_cause,
      issue.category,
      issue.severity,
      issue.status,
      issue.project_id,
      issue.project_name,
      issue.related_command,
      issue.runtime_agent_id,
      issue.runtime_agent_ids,
      issue.approval_id,
      issue.context,
    ],
    query
  );
}

function eventMatchesSearch(event: Record<string, unknown>, query: string): boolean {
  return matchesSearch(
    [
      event.event,
      event.status,
      event.message,
      event.project_id,
      event.story_id,
      event.orchestrator_session_id,
      event,
    ],
    query
  );
}

function sessionMatchesSearch(session: OrchestratorSessionRecord, query: string): boolean {
  return matchesSearch(
    [
      session.id,
      session.title,
      session.orchestrator,
      session.actor,
      session.status,
      session.reason,
      session.initiative_id,
      session.project_ids,
      session.linked_run_ids,
      session.linked_control_pass_ids,
      session.linked_approval_ids,
      session.linked_issue_ids,
      session.linked_runtime_agent_ids,
      session.context,
    ],
    query
  );
}

function controlPassMatchesSearch(controlPass: OrchestratorControlPassRecord, query: string): boolean {
  return matchesSearch(
    [
      controlPass.id,
      controlPass.orchestrator_session_id,
      controlPass.actor,
      controlPass.reason,
      controlPass.profile,
      controlPass.recommendation_kinds,
      controlPass.project_ids,
      controlPass.initiative_id,
      controlPass.orchestrator,
      controlPass.status,
      controlPass.summary,
      controlPass.control_before,
      controlPass.control_after,
    ],
    query
  );
}

function describeRunResult(result: Record<string, unknown>): {
  title: string;
  subtitle: string;
  message: string;
} {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const approval = asRecord(result.approval);
  const issue = asRecord(result.issue);
  const actionKey = toStringValue(action?.action_key);
  const command = toStringValue(action?.command);
  const kind = toStringValue(action?.kind);
  const actionType = toStringValue(action?.action_type, "operation");
  const title =
    actionKey || command || kind || toStringValue(result.status, "run-result");
  const subtitleParts = [
    actionType,
    toStringValue(result.planned_mode),
    toStringValue(result.status),
  ].filter(Boolean);
  const message =
    toStringValue(result.message) ||
    toStringValue(commandResult?.message) ||
    (approval ? `Approval ${toStringValue(approval.id, "created")}` : "") ||
    (issue ? `Issue ${toStringValue(issue.id, "linked")}` : "") ||
    "No additional result message.";
  return {
    title,
    subtitle: subtitleParts.join(" · "),
    message,
  };
}

export default function ControlPlanePage() {
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [controlPasses, setControlPasses] = useState<OrchestratorControlPassRecord[]>([]);
  const [controlSummary, setControlSummary] = useState<OrchestratorControlPassSummary | null>(null);
  const [sessions, setSessions] = useState<OrchestratorSessionRecord[]>([]);
  const [sessionSummary, setSessionSummary] = useState<OrchestratorSessionSummary | null>(null);
  const [controlProfiles, setControlProfiles] = useState<OrchestratorSessionControlProfile[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRunResultIndex, setSelectedRunResultIndex] = useState(0);
  const [selectedPassId, setSelectedPassId] = useState("");
  const [selectedSession, setSelectedSession] = useState<OrchestratorSessionDetail | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<ExecutionRuntimeAgentDetail | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [runFilter, setRunFilter] = useState("all");
  const [eventFilter, setEventFilter] = useState("all");
  const [sessionLineageFilter, setSessionLineageFilter] = useState("all");
  const [agentActivityFilter, setAgentActivityFilter] = useState("all");
  const [agentActivitySearch, setAgentActivitySearch] = useState("");
  const [agentTimelineFilter, setAgentTimelineFilter] = useState("all");
  const [agentTimelineSearch, setAgentTimelineSearch] = useState("");
  const [selectedAgentTimelineKey, setSelectedAgentTimelineKey] = useState("");
  const [pendingAgentTimelineTarget, setPendingAgentTimelineTarget] =
    useState<PendingAgentTimelineTarget | null>(null);
  const [dismissedAgentTimelineKeys, setDismissedAgentTimelineKeys] = useState<string[]>([]);
  const [snoozedAgentTimelineUntil, setSnoozedAgentTimelineUntil] = useState<Record<string, number>>(
    {}
  );
  const [pendingAgentPriorityAutoAdvance, setPendingAgentPriorityAutoAdvance] = useState<{
    priority: "critical" | "high";
    previousKey: string;
    previousEntry: AgentTimelineEntry | null;
  } | null>(null);
  const [pendingLineageAutoAdvance, setPendingLineageAutoAdvance] = useState<{
    filter: "attention" | "decisions";
    previousKey: string;
    previousEntry: SessionLineageEntry | null;
    previousFilter: string;
  } | null>(null);
  const [dismissedLineageQueueKeys, setDismissedLineageQueueKeys] = useState<
    Record<LineageQueueKind, string[]>
  >({
    attention: [],
    decisions: [],
  });
  const [snoozedLineageQueueUntil, setSnoozedLineageQueueUntil] = useState<
    Record<LineageQueueKind, Record<string, number>>
  >({
    attention: {},
    decisions: {},
  });
  const [lineageQueueNow, setLineageQueueNow] = useState(() => Date.now());
  const [pendingSessionRowDomId, setPendingSessionRowDomId] = useState("");
  const [pendingAgentTimelineRowDomId, setPendingAgentTimelineRowDomId] = useState("");
  const [selectedSessionApprovalId, setSelectedSessionApprovalId] = useState("");
  const [selectedSessionIssueId, setSelectedSessionIssueId] = useState("");
  const [selectedSessionEventKey, setSelectedSessionEventKey] = useState("");
  const [selectedSessionContextKind, setSelectedSessionContextKind] =
    useState<SessionContextKind>("");
  const [selectedTriageInboxKey, setSelectedTriageInboxKey] = useState("");
  const [sessionQueueAdvanceFeedback, setSessionQueueAdvanceFeedback] =
    useState<QueueAdvanceFeedback<QueueAdvanceTarget> | null>(null);
  const [agentQueueAdvanceFeedback, setAgentQueueAdvanceFeedback] =
    useState<QueueAdvanceFeedback<QueueAdvanceTarget> | null>(null);
  const [sessionQueueFocusDelta, setSessionQueueFocusDelta] =
    useState<QueueAdvanceFocusDelta | null>(null);
  const [agentQueueFocusDelta, setAgentQueueFocusDelta] =
    useState<QueueAdvanceFocusDelta | null>(null);
  const [triageInboxFeedbackHistory, setTriageInboxFeedbackHistory] = useState<
    TriageInboxFeedback[]
  >([]);
  const [triageInboxFeedbackFilter, setTriageInboxFeedbackFilter] = useState<
    "all" | "success" | "info"
  >("all");
  const [expandedTriageInboxResultGroups, setExpandedTriageInboxResultGroups] = useState<string[]>(
    []
  );
  const [expandedSessionLineageQueues, setExpandedSessionLineageQueues] = useState<
    LineageQueueKind[]
  >([...SESSION_LINEAGE_QUEUE_KEYS]);
  const [expandedAgentPriorityQueues, setExpandedAgentPriorityQueues] = useState<
    Array<(typeof AGENT_PRIORITY_QUEUE_KEYS)[number]>
  >([...AGENT_PRIORITY_QUEUE_KEYS]);
  const [historySearch, setHistorySearch] = useState("");
  const [entitySearch, setEntitySearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [busyActionKey, setBusyActionKey] = useState("");
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [hydratedAgentTimelineStorageKey, setHydratedAgentTimelineStorageKey] = useState("");
  const [hydratedLineageQueueSessionId, setHydratedLineageQueueSessionId] = useState("");
  const [hydratedSessionQueueFocusStorageKey, setHydratedSessionQueueFocusStorageKey] =
    useState("");
  const [hydratedAgentQueueFocusStorageKey, setHydratedAgentQueueFocusStorageKey] =
    useState("");
  const selectedSessionLineageEntryRef = useRef<SessionLineageEntry | null>(null);
  const selectedAgentTimelineEntryRef = useRef<AgentTimelineEntry | null>(null);
  const selectedTriageInboxKeyRef = useRef("");
  const sessionLineageFilterRef = useRef("all");

  const loadOverview = useCallback(async () => {
    try {
      const [
        healthData,
        projectData,
        controlPassData,
        controlPassSummaryData,
        sessionData,
        sessionSummaryData,
        profileData,
      ] = await Promise.all([
        fetchAccountsHealth(),
        fetchProjects(false),
        fetchExecutionPlaneControlPasses(),
        fetchExecutionPlaneControlPassSummary(),
        fetchExecutionPlaneOrchestratorSessions(),
        fetchExecutionPlaneOrchestratorSessionSummary(),
        fetchExecutionPlaneOrchestratorSessionControlProfiles(),
      ]);
      setHealth(healthData);
      setProjects((projectData.projects || []) as ProjectSummary[]);
      setControlPasses((controlPassData.control_passes || []) as OrchestratorControlPassRecord[]);
      setControlSummary(controlPassSummaryData);
      setSessions((sessionData.sessions || []) as OrchestratorSessionRecord[]);
      setSessionSummary(sessionSummaryData);
      setControlProfiles((profileData.profiles || []) as OrchestratorSessionControlProfile[]);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load control plane.");
    }
  }, []);

  const loadSessionDetail = useCallback(async (sessionId: string) => {
    const detail = await fetchExecutionPlaneOrchestratorSession(sessionId, { eventLimit: 12 });
    setSelectedSession(detail);
    setSelectedRunId((current) => {
      if (current && detail.runs.some((run) => run.id === current)) {
        return current;
      }
      return detail.runs[0]?.id ?? "";
    });
    setSelectedPassId((current) => {
      if (current && detail.control_passes.some((controlPass) => controlPass.id === current)) {
        return current;
      }
      return detail.control_passes[0]?.id ?? current;
    });
    return detail;
  }, []);

  const loadAgentDetail = useCallback(async (runtimeAgentId: string) => {
    return fetchExecutionPlaneAgentDetail(runtimeAgentId, { eventLimit: 12 });
  }, []);

  useEffect(() => {
    void loadOverview();
    const interval = setInterval(() => {
      void loadOverview();
    }, 15000);
    return () => clearInterval(interval);
  }, [loadOverview]);

  useSSE(
    useCallback(() => {
      void loadOverview();
      if (selectedSessionId) {
        void loadSessionDetail(selectedSessionId).catch(() => {
          // Keep current detail state on transient SSE fetch failures.
        });
      }
    }, [loadOverview, loadSessionDetail, selectedSessionId])
  );

  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId("");
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSession(null);
      return;
    }
    setSelectedSessionId((current) =>
      sessions.some((session) => session.id === current) ? current : sessions[0].id
    );
  }, [sessions]);
  useEffect(() => {
    const interval = setInterval(() => {
      setLineageQueueNow(Date.now());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (controlPasses.length === 0) {
      setSelectedPassId("");
      return;
    }
    setSelectedPassId((current) =>
      controlPasses.some((controlPass) => controlPass.id === current)
        ? current
        : controlPasses[0].id
    );
  }, [controlPasses]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionEventKey("");
      setSelectedSessionContextKind("");
      setEntitySearch("");
      setSelectedSession(null);
      return;
    }

    let cancelled = false;
    setSessionLoading(true);
    fetchExecutionPlaneOrchestratorSession(selectedSessionId, { eventLimit: 12 })
      .then((detail) => {
        if (cancelled) return;
        setSelectedSession(detail);
        setSelectedRunId((current) => {
          if (current && detail.runs.some((run) => run.id === current)) {
            return current;
          }
          return detail.runs[0]?.id ?? "";
        });
        setSelectedPassId((current) => {
          if (current && detail.control_passes.some((controlPass) => controlPass.id === current)) {
            return current;
          }
          return detail.control_passes[0]?.id ?? current;
        });
        setErrorMessage("");
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedSession(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load orchestrator session detail."
        );
      })
      .finally(() => {
        if (!cancelled) setSessionLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  useEffect(() => {
    setEntitySearch("");
    setSelectedSessionApprovalId("");
    setSelectedSessionIssueId("");
    setSelectedSessionEventKey("");
    setSelectedSessionContextKind("");
    setSessionQueueAdvanceFeedback(null);
    setSessionQueueFocusDelta(null);
    setPendingLineageAutoAdvance(null);
    setLineageQueueNow(Date.now());
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setDismissedLineageQueueKeys(emptyDismissedLineageQueueKeys());
      setSnoozedLineageQueueUntil(emptySnoozedLineageQueueUntil());
      setHydratedLineageQueueSessionId("");
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    setHydratedLineageQueueSessionId("");

    if (typeof window === "undefined") {
      setDismissedLineageQueueKeys(emptyDismissedLineageQueueKeys());
      setSnoozedLineageQueueUntil(emptySnoozedLineageQueueUntil());
      setHydratedLineageQueueSessionId(selectedSessionId);
      return;
    }

    const storageKey = lineageQueueStorageKey(selectedSessionId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedLineageQueueState | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedLineageQueueState;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedLineageQueueState(parsed, now);
    setDismissedLineageQueueKeys(sanitized.dismissed);
    setSnoozedLineageQueueUntil(sanitized.snoozedUntil);
    setHydratedLineageQueueSessionId(selectedSessionId);

    if (isPersistedLineageQueueStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId || hydratedLineageQueueSessionId !== selectedSessionId) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedLineageQueueState(
      {
        dismissed: dismissedLineageQueueKeys,
        snoozedUntil: snoozedLineageQueueUntil,
      },
      lineageQueueNow
    );
    const storageKey = lineageQueueStorageKey(selectedSessionId);

    if (isPersistedLineageQueueStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedLineageQueueKeys,
    hydratedLineageQueueSessionId,
    lineageQueueNow,
    selectedSessionId,
    snoozedLineageQueueUntil,
  ]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSessionQueueFocusDelta(null);
      setHydratedSessionQueueFocusStorageKey("");
      return;
    }

    const storageKey = sessionQueueFocusStorageKey(selectedSessionId);
    setHydratedSessionQueueFocusStorageKey("");

    if (typeof window === "undefined") {
      setHydratedSessionQueueFocusStorageKey(storageKey);
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setSessionQueueFocusDelta(sanitized);
    setHydratedSessionQueueFocusStorageKey(storageKey);
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) return;
    const storageKey = sessionQueueFocusStorageKey(selectedSessionId);
    if (hydratedSessionQueueFocusStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, sessionQueueFocusDelta);
  }, [
    hydratedSessionQueueFocusStorageKey,
    selectedSessionId,
    sessionQueueFocusDelta,
  ]);

  useEffect(() => {
    if (!selectedSession) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }

    const sessionRuns = (selectedSession.runs || []) as ExecutionAgentActionRunRecord[];
    const currentRun = sessionRuns.find((run) => run.id === selectedRunId) ?? sessionRuns[0] ?? null;
    const currentRunResult =
      currentRun?.results[selectedRunResultIndex] ??
      currentRun?.results[0] ??
      null;
    const sessionApprovals = selectedSession.approvals || [];
    const sessionIssues = selectedSession.issues || [];
    const candidateIds = [
      currentRunResult && typeof currentRunResult === "object"
        ? outcomeRuntimeAgentId(currentRunResult as Record<string, unknown>)
        : "",
      ...selectedSession.linked_runtime_agent_ids,
      ...sessionRuns.flatMap((run) => run.runtime_agent_ids || []),
      ...sessionApprovals.flatMap((approval) => approval.runtime_agent_ids || []),
      ...sessionIssues.flatMap((issue) =>
        issue.runtime_agent_ids.length > 0
          ? issue.runtime_agent_ids
          : issue.runtime_agent_id
            ? [issue.runtime_agent_id]
            : []
      ),
    ].filter(Boolean);
    const uniqueIds = [...new Set(candidateIds)];
    if (!uniqueIds.length) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }
    setSelectedAgentId((current) => (current && uniqueIds.includes(current) ? current : uniqueIds[0]));
  }, [selectedRunId, selectedRunResultIndex, selectedSession]);

  useEffect(() => {
    if (!selectedAgentId) {
      setSelectedAgent(null);
      return;
    }
    let cancelled = false;
    setAgentLoading(true);
    loadAgentDetail(selectedAgentId)
      .then((detail) => {
        if (cancelled) return;
        setSelectedAgent(detail);
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedAgent(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load runtime agent detail."
        );
      })
      .finally(() => {
        if (!cancelled) setAgentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadAgentDetail, selectedAgentId]);

  useEffect(() => {
    setSelectedRunResultIndex(0);
  }, [selectedRunId]);

  useEffect(() => {
    setAgentActivityFilter("all");
    setAgentActivitySearch("");
    setAgentTimelineFilter("all");
    setAgentTimelineSearch("");
    setSelectedAgentTimelineKey("");
    setAgentQueueAdvanceFeedback(null);
    setAgentQueueFocusDelta(null);
    setPendingAgentPriorityAutoAdvance(null);
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      setHydratedAgentTimelineStorageKey("");
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    setHydratedAgentTimelineStorageKey("");

    if (typeof window === "undefined") {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      setHydratedAgentTimelineStorageKey(agentTimelineStorageKey(selectedAgentId));
      return;
    }

    const storageKey = agentTimelineStorageKey(selectedAgentId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedAgentTimelineState | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedAgentTimelineState;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedAgentTimelineState(parsed, now);
    setDismissedAgentTimelineKeys(sanitized.dismissed);
    setSnoozedAgentTimelineUntil(sanitized.snoozedUntil);
    setHydratedAgentTimelineStorageKey(storageKey);

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = agentTimelineStorageKey(selectedAgentId);
    if (hydratedAgentTimelineStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedAgentTimelineState(
      {
        dismissed: dismissedAgentTimelineKeys,
        snoozedUntil: snoozedAgentTimelineUntil,
      },
      lineageQueueNow
    );

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedAgentTimelineKeys,
    hydratedAgentTimelineStorageKey,
    lineageQueueNow,
    selectedAgentId,
    snoozedAgentTimelineUntil,
  ]);

  useEffect(() => {
    if (!selectedAgentId) {
      setAgentQueueFocusDelta(null);
      setHydratedAgentQueueFocusStorageKey("");
      return;
    }

    const storageKey = agentQueueFocusStorageKey(selectedAgentId);
    setHydratedAgentQueueFocusStorageKey("");

    if (typeof window === "undefined") {
      setHydratedAgentQueueFocusStorageKey(storageKey);
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setAgentQueueFocusDelta(sanitized);
    setHydratedAgentQueueFocusStorageKey(storageKey);
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = agentQueueFocusStorageKey(selectedAgentId);
    if (hydratedAgentQueueFocusStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, agentQueueFocusDelta);
  }, [
    agentQueueFocusDelta,
    hydratedAgentQueueFocusStorageKey,
    selectedAgentId,
  ]);

  useEffect(() => {
    const visibleRuns = ((selectedSession?.runs || []) as ExecutionAgentActionRunRecord[]).filter(
      (run) => matchesRunFilter(run, runFilter) && runMatchesSearch(run, entitySearch)
    );
    if (!visibleRuns.length) {
      return;
    }
    if (!selectedRunId || !visibleRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(visibleRuns[0].id);
    }
  }, [entitySearch, runFilter, selectedRunId, selectedSession]);

  useEffect(() => {
    const currentRuns = (selectedSession?.runs || []) as ExecutionAgentActionRunRecord[];
    const currentRun = currentRuns.find((run) => run.id === selectedRunId) ?? null;
    if (!currentRun) {
      setSelectedRunResultIndex(0);
      return;
    }
    if (selectedRunResultIndex >= currentRun.results.length) {
      setSelectedRunResultIndex(0);
    }
  }, [selectedRunId, selectedRunResultIndex, selectedSession]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
    } finally {
      setRefreshing(false);
    }
  };

  const refreshAfterMutation = useCallback(
    async (sessionId: string) => {
      await loadOverview();
      await loadSessionDetail(sessionId);
    },
    [loadOverview, loadSessionDetail]
  );

  const focusRuntimeAgent = useCallback((runtimeAgentId: string, syncSearch = false) => {
    if (!runtimeAgentId) return;
    setSelectedAgentId(runtimeAgentId);
    if (syncSearch) {
      setEntitySearch(runtimeAgentId);
    }
  }, []);

  const focusAgentTimeline = useCallback(
    (
      filter: string,
      options?: {
        entry?: AgentTimelineEntry | null;
        search?: string;
      }
    ) => {
      setAgentTimelineFilter(filter);
      setAgentTimelineSearch(options?.search ?? "");
      setSelectedAgentTimelineKey(options?.entry ? agentTimelineEntryKey(options.entry) : "");
    },
    []
  );

  const refreshAfterAgentMutation = useCallback(
    async (runtimeAgentId: string) => {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
      await loadAgentDetail(runtimeAgentId).then((detail) => {
        setSelectedAgent(detail);
      });
    },
    [loadAgentDetail, loadOverview, loadSessionDetail, selectedSessionId]
  );
  const recordTriageInboxFeedback = useCallback(
    (
      itemKey: string,
      itemLabel: string,
      message: string,
      tone: "info" | "success" = "success"
    ) => {
      if (!itemKey || !itemLabel || !message) return;
      const feedback: TriageInboxFeedback = {
        itemKey,
        itemLabel,
        message,
        tone,
        timestamp: new Date().toISOString(),
      };
      setTriageInboxFeedbackHistory((current) => {
        const deduped = current.filter(
          (entry) =>
            !(
              entry.itemKey === feedback.itemKey &&
              entry.itemLabel === feedback.itemLabel &&
              entry.message === feedback.message &&
              entry.tone === feedback.tone
            )
        );
        return [feedback, ...deduped].slice(0, TRIAGE_INBOX_FEEDBACK_LIMIT);
      });
    },
    []
  );

  const runDecisionAction = useCallback(
    async (
      actionKey: string,
      task: () => Promise<string>,
      options?: { autoAdvanceQueue?: boolean }
    ) => {
      if (!selectedSessionId) return;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");
      const currentTriageInboxKey = selectedTriageInboxKeyRef.current;
      const currentLineageEntry = selectedSessionLineageEntryRef.current;
      const currentLineageFilter = sessionLineageFilterRef.current;
      const currentAgentEntry = selectedAgentTimelineEntryRef.current;
      let autoAdvanceFilter: "attention" | "decisions" | "" = "";
      let autoAdvanceAgentPriority: "critical" | "high" | "" = "";
      if (options?.autoAdvanceQueue && currentLineageEntry) {
        if (currentLineageFilter === "attention" || currentLineageFilter === "decisions") {
          autoAdvanceFilter = currentLineageFilter;
        } else if (matchesSessionLineageFilter(currentLineageEntry, "attention")) {
          autoAdvanceFilter = "attention";
        } else if (matchesSessionLineageFilter(currentLineageEntry, "decisions")) {
          autoAdvanceFilter = "decisions";
        }
      }
      if (options?.autoAdvanceQueue && currentAgentEntry) {
        const priority = agentTimelinePriority(currentAgentEntry);
        if (priority === "critical" || priority === "high") {
          autoAdvanceAgentPriority = priority;
        }
      }
      try {
        const message = await task();
        setNotice(message);
        if (currentTriageInboxKey) {
          const itemLabel =
            currentTriageInboxKey === "session-attention"
              ? "Session Attention"
              : currentTriageInboxKey === "session-decisions"
                ? "Session Decision"
                : currentTriageInboxKey === "agent-critical"
                  ? "Agent Critical"
                  : currentTriageInboxKey === "agent-high"
                    ? "Agent High"
                    : "";
          recordTriageInboxFeedback(currentTriageInboxKey, itemLabel, message, "success");
        }
        if (autoAdvanceFilter && currentLineageEntry) {
          setPendingLineageAutoAdvance({
            filter: autoAdvanceFilter,
            previousKey: currentLineageEntry.key,
            previousEntry: currentLineageEntry,
            previousFilter: currentLineageFilter || autoAdvanceFilter,
          });
        }
        if (autoAdvanceAgentPriority && currentAgentEntry) {
          setPendingAgentPriorityAutoAdvance({
            priority: autoAdvanceAgentPriority,
            previousKey: agentTimelineEntryKey(currentAgentEntry),
            previousEntry: currentAgentEntry,
          });
        }
        await refreshAfterMutation(selectedSessionId);
        if (selectedAgentId) {
          const detail = await loadAgentDetail(selectedAgentId);
          setSelectedAgent(detail);
        }
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply linked decision action."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      loadAgentDetail,
      recordTriageInboxFeedback,
      refreshAfterMutation,
      selectedAgentId,
      selectedSessionId,
    ]
  );

  const applyRecommendation = async (recommendation: OrchestratorSessionControlRecommendation) => {
    if (!selectedSessionId) return;
    const actionKey = `recommendation:${recommendation.kind}`;
    setBusyActionKey(actionKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await applyExecutionPlaneOrchestratorSessionRecommendation(selectedSessionId, {
        recommendationKind: recommendation.kind,
        actor: DEFAULT_CONTROL_ACTOR,
        reason: `Dashboard applied session recommendation ${recommendation.kind}`,
      });
      const runId = extractRunId(payload.result);
      if (runId) setSelectedRunId(runId);
      setNotice(
        `${payload.recommendation.title || recommendation.kind} finished with status ${payload.status}.`
      );
      await refreshAfterMutation(selectedSessionId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to apply session recommendation."
      );
    } finally {
      setBusyActionKey("");
    }
  };

  const approveApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-approve:${approval.id}`,
      async () => {
        const payload = await approveExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard approved ${approval.action} for session ${selectedSessionId}`,
        });
        return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const rejectApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-reject:${approval.id}`,
      async () => {
        const payload = await rejectExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard rejected ${approval.action} for session ${selectedSessionId}`,
        });
        return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const applyApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-apply:${approval.id}`,
      async () => {
        const payload = await applyExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard applied ${approval.action} for session ${selectedSessionId}`,
        });
        return toStringValue(
          payload.command_result.message,
          `Approval ${payload.approval.id} applied successfully.`
        );
      },
      { autoAdvanceQueue: true }
    );
  };

  const resolveIssue = async (issue: ExecutionIssueRecord) => {
    await runDecisionAction(
      `issue-resolve:${issue.id}`,
      async () => {
        const payload = await resolveExecutionPlaneIssue(issue.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard resolved issue ${issue.id} for session ${selectedSessionId}`,
        });
        return `Issue ${payload.issue.id} marked ${payload.issue.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const runAgentSuggestedCommand = async (
    command: Record<string, unknown>,
    mode: "execute_now" | "request_approval"
  ) => {
    if (!selectedAgent) return;
    const commandName = toStringValue(command.command);
    if (!commandName) return;
    const actionKey = `${selectedAgent.runtime_agent_id}:command:${commandName}`;
    const busyKey = `agent-command:${selectedAgent.runtime_agent_id}:${commandName}:${mode}`;
    setBusyActionKey(busyKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await executeExecutionPlaneAgentAction({
        actionKey,
        orchestratorSessionId: selectedSessionId,
        actor: DEFAULT_CONTROL_ACTOR,
        mode,
        reason: `Dashboard ${mode === "execute_now" ? "executed" : "requested approval for"} agent command ${commandName}`,
      });
      const runId = extractRunId(payload);
      if (runId) setSelectedRunId(runId);
      if (payload.approval?.id) {
        setEntitySearch(payload.approval.id);
      }
      setNotice(
        payload.message ||
          toStringValue(payload.command_result?.message) ||
          `Agent command ${commandName} finished with status ${payload.status}.`
      );
      await refreshAfterAgentMutation(selectedAgent.runtime_agent_id);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to execute runtime agent command."
      );
    } finally {
      setBusyActionKey("");
    }
  };

  const applyControlPlan = async (profile: OrchestratorSessionControlProfile) => {
    if (!selectedSessionId) return;
    const actionKey = `profile:${profile.name}`;
    setBusyActionKey(actionKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await applyExecutionPlaneOrchestratorSessionControlPlan(selectedSessionId, {
        profile: profile.name,
        actor: DEFAULT_CONTROL_ACTOR,
        reason: `Dashboard executed ${profile.name} control pass`,
      });
      const runId = extractLatestRunIdFromAppliedSteps(payload.applied);
      if (runId) setSelectedRunId(runId);
      setNotice(
        `Control profile ${payload.profile.name} recorded pass ${payload.control_pass.id} with status ${payload.status}.`
      );
      setSelectedPassId(payload.control_pass.id);
      await refreshAfterMutation(selectedSessionId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to apply session control profile."
      );
    } finally {
      setBusyActionKey("");
    }
  };

  const visibleProjects = useMemo(
    () => projects.filter((project) => !project.archived),
    [projects]
  );
  const filteredControlPassHistory = useMemo(
    () => controlPasses.filter((controlPass) => controlPassMatchesSearch(controlPass, historySearch)),
    [controlPasses, historySearch]
  );
  const recentControlPasses = useMemo(
    () => filteredControlPassHistory.slice(0, 8),
    [filteredControlPassHistory]
  );
  const filteredSessionHistory = useMemo(
    () => sessions.filter((session) => sessionMatchesSearch(session, historySearch)),
    [historySearch, sessions]
  );
  const recentSessions = useMemo(() => filteredSessionHistory.slice(0, 6), [filteredSessionHistory]);
  const sortedProfiles = useMemo(
    () =>
      [...controlProfiles].sort((left, right) => {
        if (left.default) return -1;
        if (right.default) return 1;
        return left.name.localeCompare(right.name);
      }),
    [controlProfiles]
  );
  const selectedPass = useMemo(() => {
    if (!selectedPassId) return null;
    const fromSession =
      selectedSession?.control_passes.find((controlPass) => controlPass.id === selectedPassId) ?? null;
    return fromSession ?? controlPasses.find((controlPass) => controlPass.id === selectedPassId) ?? null;
  }, [controlPasses, selectedPassId, selectedSession]);
  const linkedApprovals = useMemo(
    () =>
      [...(selectedSession?.approvals || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );
  const linkedRuns = useMemo<ExecutionAgentActionRunRecord[]>(
    () =>
      [...(selectedSession?.runs || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );
  const filteredRuns = useMemo(
    () => linkedRuns.filter((run) => matchesRunFilter(run, runFilter) && runMatchesSearch(run, entitySearch)),
    [entitySearch, linkedRuns, runFilter]
  );
  const linkedIssues = useMemo(
    () =>
      [...(selectedSession?.issues || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );
  const approvalById = useMemo(() => {
    const index = new Map<string, ExecutionApprovalRecord>();
    linkedApprovals.forEach((approval) => {
      index.set(approval.id, approval);
    });
    return index;
  }, [linkedApprovals]);
  const issueById = useMemo(() => {
    const index = new Map<string, ExecutionIssueRecord>();
    linkedIssues.forEach((issue) => {
      index.set(issue.id, issue);
    });
    return index;
  }, [linkedIssues]);
  const linkedAgentIds = useMemo(() => {
    const ids = [
      ...(selectedSession?.linked_runtime_agent_ids || []),
      ...linkedRuns.flatMap((run) => run.runtime_agent_ids || []),
      ...linkedApprovals.flatMap((approval) => approval.runtime_agent_ids || []),
      ...linkedIssues.flatMap((issue) =>
        issue.runtime_agent_ids.length > 0
          ? issue.runtime_agent_ids
          : issue.runtime_agent_id
            ? [issue.runtime_agent_id]
            : []
      ),
    ].filter(Boolean);
    return [...new Set(ids)];
  }, [linkedApprovals, linkedIssues, linkedRuns, selectedSession]);
  const filteredApprovals = useMemo(
    () => linkedApprovals.filter((approval) => approvalMatchesSearch(approval, entitySearch)),
    [entitySearch, linkedApprovals]
  );
  const filteredIssues = useMemo(
    () => linkedIssues.filter((issue) => issueMatchesSearch(issue, entitySearch)),
    [entitySearch, linkedIssues]
  );
  const selectedSessionApproval = useMemo(
    () => linkedApprovals.find((approval) => approval.id === selectedSessionApprovalId) ?? null,
    [linkedApprovals, selectedSessionApprovalId]
  );
  const selectedSessionIssue = useMemo(
    () => linkedIssues.find((issue) => issue.id === selectedSessionIssueId) ?? null,
    [linkedIssues, selectedSessionIssueId]
  );
  const selectedSessionEvent = useMemo(
    () =>
      (selectedSession?.events || []).find(
        (event) => sessionEventKey(event) === selectedSessionEventKey
      ) ?? null,
    [selectedSession, selectedSessionEventKey]
  );
  const visibleSessionApprovals = useMemo(
    () => withSelectedItem(filteredApprovals, selectedSessionApproval, 6, (approval) => approval.id),
    [filteredApprovals, selectedSessionApproval]
  );
  const visibleSessionIssues = useMemo(
    () => withSelectedItem(filteredIssues, selectedSessionIssue, 6, (issue) => issue.id),
    [filteredIssues, selectedSessionIssue]
  );
  const selectedRun = useMemo(() => {
    if (!selectedRunId) return null;
    return linkedRuns.find((run) => run.id === selectedRunId) ?? null;
  }, [linkedRuns, selectedRunId]);
  const filteredEvents = useMemo(
    () =>
      (selectedSession?.events || []).filter(
      (event) => matchesEventFilter(event, eventFilter) && eventMatchesSearch(event, entitySearch)
      ),
    [entitySearch, eventFilter, selectedSession]
  );
  const visibleSessionEvents = useMemo(() => {
    const recentEvents = filteredEvents.slice(-6).reverse();
    if (!selectedSessionEvent) return recentEvents;
    const selectedKey = sessionEventKey(selectedSessionEvent);
    if (!selectedKey || recentEvents.some((event) => sessionEventKey(event) === selectedKey)) {
      return recentEvents;
    }
    return [selectedSessionEvent, ...recentEvents.slice(0, 5)];
  }, [filteredEvents, selectedSessionEvent]);
  const selectedRunResult = useMemo(() => {
    if (!selectedRun) return null;
    return selectedRun.results[selectedRunResultIndex] ?? selectedRun.results[0] ?? null;
  }, [selectedRun, selectedRunResultIndex]);
  const sessionLineageEntries = useMemo(() => {
    const entries: SessionLineageEntry[] = [];
    linkedRuns.forEach((run) => {
      run.results.forEach((result, resultIndex) => {
        const approvalId = toStringValue(asRecord(result.approval)?.id);
        const issueId = toStringValue(asRecord(result.issue)?.id);
        const linkedApproval = approvalId ? approvalById.get(approvalId) ?? null : null;
        const linkedIssue = issueId ? issueById.get(issueId) ?? null : null;
        const runtimeAgentId =
          outcomeRuntimeAgentId(result) ||
          linkedApproval?.runtime_agent_ids[0] ||
          linkedIssue?.runtime_agent_ids[0] ||
          linkedIssue?.runtime_agent_id ||
          "";
        const relatedEventMatch = resolveSessionEventFromContext(selectedSession?.events || [], {
          runId: run.id,
          approvalId,
          issueId,
          runtimeAgentId,
        });
        const details = describeRunResult(result);
        const projectId = outcomeProjectId(result);
        const projectName = outcomeProjectName(result);
        const storyId = outcomeStoryId(result);
        const storyTitle = outcomeStoryTitle(result);
        const timestamp =
          toStringValue(relatedEventMatch?.event?.timestamp) ||
          run.completed_at ||
          run.updated_at ||
          run.created_at;
        entries.push({
          key: `${run.id}:${resultIndex}`,
          runId: run.id,
          resultIndex,
          timestamp,
          status: toStringValue(result.status, run.status || "unknown"),
          title: details.title,
          subtitle: details.subtitle,
          message: details.message,
          approvalId,
          issueId,
          eventKey: relatedEventMatch?.key || "",
          eventName: toStringValue(relatedEventMatch?.event?.event),
          runtimeAgentId,
          projectId,
          projectName,
          storyId,
          storyTitle,
          event: relatedEventMatch?.event || null,
        });
      });
    });
    return entries.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        right.runId.localeCompare(left.runId) ||
        left.resultIndex - right.resultIndex
    );
  }, [approvalById, issueById, linkedRuns, selectedSession]);
  const selectedSessionLineageEntry = useMemo(() => {
    if (selectedRunId) {
      return (
        sessionLineageEntries.find(
          (entry) => entry.runId === selectedRunId && entry.resultIndex === selectedRunResultIndex
        ) ?? null
      );
    }
    return sessionLineageEntries[0] ?? null;
  }, [selectedRunId, selectedRunResultIndex, sessionLineageEntries]);
  const filteredSessionLineageEntries = useMemo(
    () =>
      sessionLineageEntries.filter((entry) =>
        matchesSessionLineageFilter(entry, sessionLineageFilter)
      ),
    [sessionLineageEntries, sessionLineageFilter]
  );
  const sessionLineagePriorityCounts = useMemo(
    () => countTriagePriorities(filteredSessionLineageEntries, sessionLineagePriority),
    [filteredSessionLineageEntries]
  );
  const nextBestSessionLineageEntry = useMemo(
    () =>
      nextBestTriageItem(
        filteredSessionLineageEntries,
        selectedSessionLineageEntry,
        (entry) => entry.key,
        sessionLineagePriority
      ),
    [filteredSessionLineageEntries, selectedSessionLineageEntry]
  );
  const selectedSessionLineagePriority = useMemo(
    () =>
      selectedSessionLineageEntry ? sessionLineagePriority(selectedSessionLineageEntry) : null,
    [selectedSessionLineageEntry]
  );
  const visibleSessionLineageEntries = useMemo(
    () =>
      withSelectedItem(
        filteredSessionLineageEntries,
        selectedSessionLineageEntry,
        6,
        (entry) => entry.key
      ),
    [filteredSessionLineageEntries, selectedSessionLineageEntry]
  );
  const sessionLineageStatusCounts = useMemo(
    () =>
      sessionLineageEntries.reduce<ExecutionPlaneCountMap>((acc, entry) => {
        acc[entry.status] = (acc[entry.status] || 0) + 1;
        return acc;
      }, {}),
    [sessionLineageEntries]
  );
  const sessionLineageDecisionCount = useMemo(
    () =>
      sessionLineageEntries.filter((entry) => entry.approvalId || entry.issueId).length,
    [sessionLineageEntries]
  );
  const sessionLineageAttentionCount = useMemo(
    () =>
      sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "attention")).length,
    [sessionLineageEntries]
  );
  const sessionLineageEventCount = useMemo(
    () => sessionLineageEntries.filter((entry) => entry.eventKey).length,
    [sessionLineageEntries]
  );
  const sessionLineageAgentCount = useMemo(
    () => new Set(sessionLineageEntries.map((entry) => entry.runtimeAgentId).filter(Boolean)).size,
    [sessionLineageEntries]
  );
  const sessionLineageAgentLinkedCount = useMemo(
    () => sessionLineageEntries.filter((entry) => entry.runtimeAgentId).length,
    [sessionLineageEntries]
  );
  const sessionLineageFilterCounts = useMemo<Record<string, number>>(
    () => ({
      all: sessionLineageEntries.length,
      attention: sessionLineageAttentionCount,
      decisions: sessionLineageDecisionCount,
      "agent-linked": sessionLineageAgentLinkedCount,
    }),
    [
      sessionLineageAgentLinkedCount,
      sessionLineageAttentionCount,
      sessionLineageDecisionCount,
      sessionLineageEntries.length,
    ]
  );
  const latestAgentLinkedLineageEntry = useMemo(
    () => sessionLineageEntries.find((entry) => matchesSessionLineageFilter(entry, "agent-linked")) ?? null,
    [sessionLineageEntries]
  );
  const attentionSessionLineageSourceEntries = useMemo(
    () => sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "attention")),
    [sessionLineageEntries]
  );
  const decisionSessionLineageSourceEntries = useMemo(
    () => sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "decisions")),
    [sessionLineageEntries]
  );
  const attentionOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedLineageQueueKeys.attention,
          snoozedUntil: snoozedLineageQueueUntil.attention,
        },
        lineageQueueNow
      ),
    [dismissedLineageQueueKeys.attention, lineageQueueNow, snoozedLineageQueueUntil.attention]
  );
  const decisionOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedLineageQueueKeys.decisions,
          snoozedUntil: snoozedLineageQueueUntil.decisions,
        },
        lineageQueueNow
      ),
    [dismissedLineageQueueKeys.decisions, lineageQueueNow, snoozedLineageQueueUntil.decisions]
  );
  const attentionSessionLineageEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        attentionSessionLineageSourceEntries,
        (entry) => entry.key,
        attentionOperatorVisibilityState,
        lineageQueueNow
      ),
    [
      attentionOperatorVisibilityState,
      attentionSessionLineageSourceEntries,
      lineageQueueNow,
    ]
  );
  const decisionSessionLineageEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        decisionSessionLineageSourceEntries,
        (entry) => entry.key,
        decisionOperatorVisibilityState,
        lineageQueueNow
      ),
    [
      decisionOperatorVisibilityState,
      decisionSessionLineageSourceEntries,
      lineageQueueNow,
    ]
  );
  const attentionSessionLineageQueue = useMemo(
    () => attentionSessionLineageEntries.slice(0, 3),
    [attentionSessionLineageEntries]
  );
  const decisionSessionLineageQueue = useMemo(
    () => decisionSessionLineageEntries.slice(0, 3),
    [decisionSessionLineageEntries]
  );
  const attentionQueuePosition = useMemo(
    () => sessionLineageQueuePosition(attentionSessionLineageEntries, selectedSessionLineageEntry),
    [attentionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const decisionQueuePosition = useMemo(
    () => sessionLineageQueuePosition(decisionSessionLineageEntries, selectedSessionLineageEntry),
    [decisionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const nextAttentionSessionLineageEntry = useMemo(
    () =>
      nextSessionLineageQueueEntry(
        attentionSessionLineageEntries,
        selectedSessionLineageEntry
      ),
    [attentionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const nextDecisionSessionLineageEntry = useMemo(
    () =>
      nextSessionLineageQueueEntry(
        decisionSessionLineageEntries,
        selectedSessionLineageEntry
      ),
    [decisionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const currentSessionLineageQueue = useMemo<LineageQueueKind | "">(() => {
    if (selectedSessionLineageEntry) {
      if (attentionSessionLineageEntries.some((entry) => entry.key === selectedSessionLineageEntry.key)) {
        return "attention";
      }
      if (decisionSessionLineageEntries.some((entry) => entry.key === selectedSessionLineageEntry.key)) {
        return "decisions";
      }
    }
    if (sessionLineageFilter === "attention" && attentionSessionLineageEntries.length) {
      return "attention";
    }
    if (sessionLineageFilter === "decisions" && decisionSessionLineageEntries.length) {
      return "decisions";
    }
    if (attentionSessionLineageEntries.length) return "attention";
    if (decisionSessionLineageEntries.length) return "decisions";
    return "";
  }, [
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    selectedSessionLineageEntry,
    sessionLineageFilter,
  ]);
  const hiddenAttentionQueueCount = useMemo(
    () => Math.max(attentionSessionLineageSourceEntries.length - attentionSessionLineageEntries.length, 0),
    [attentionSessionLineageEntries.length, attentionSessionLineageSourceEntries.length]
  );
  const hiddenDecisionQueueCount = useMemo(
    () => Math.max(decisionSessionLineageSourceEntries.length - decisionSessionLineageEntries.length, 0),
    [decisionSessionLineageEntries.length, decisionSessionLineageSourceEntries.length]
  );
  const persistedLineageQueueState = useMemo(
    () => ({
      dismissed: {
        attention: attentionOperatorVisibilityState.dismissed,
        decisions: decisionOperatorVisibilityState.dismissed,
      },
      snoozedUntil: {
        attention: attentionOperatorVisibilityState.snoozedUntil,
        decisions: decisionOperatorVisibilityState.snoozedUntil,
      },
    }),
    [attentionOperatorVisibilityState, decisionOperatorVisibilityState]
  );
  const persistedDismissedLineageQueueCount = useMemo(
    () =>
      persistedLineageQueueState.dismissed.attention.length +
      persistedLineageQueueState.dismissed.decisions.length,
    [persistedLineageQueueState]
  );
  const persistedSnoozedLineageQueueCount = useMemo(
    () =>
      Object.keys(persistedLineageQueueState.snoozedUntil.attention).length +
      Object.keys(persistedLineageQueueState.snoozedUntil.decisions).length,
    [persistedLineageQueueState]
  );
  const hasPersistedLineageQueuePreferences = useMemo(
    () => !isPersistedLineageQueueStateEmpty(persistedLineageQueueState),
    [persistedLineageQueueState]
  );
  const selectedSessionLineageTraits = useMemo(() => {
    return sessionLineageTraits(selectedSessionLineageEntry);
  }, [selectedSessionLineageEntry]);
  useEffect(() => {
    selectedSessionLineageEntryRef.current = selectedSessionLineageEntry;
  }, [selectedSessionLineageEntry]);
  useEffect(() => {
    sessionLineageFilterRef.current = sessionLineageFilter;
  }, [sessionLineageFilter]);
  const syncLinkedSelection = useCallback(
    (context: LinkedSelectionContext) => {
      const approvalId = toStringValue(context.approvalId);
      const issueId = toStringValue(context.issueId);
      const resolvedRunLink = resolveRunLinkFromContext(linkedRuns, context);
      const runId = resolvedRunLink?.run.id || toStringValue(context.runId);
      const resultIndex =
        resolvedRunLink?.resultIndex ??
        (typeof context.resultIndex === "number" ? context.resultIndex : 0);
      const resolvedRunResult =
        resolvedRunLink && resolvedRunLink.run.results[resolvedRunLink.resultIndex]
          ? asRecord(resolvedRunLink.run.results[resolvedRunLink.resultIndex])
          : null;
      const runtimeAgentId =
        toStringValue(context.runtimeAgentId) ||
        outcomeRuntimeAgentId(resolvedRunResult || {}) ||
        toStringValue(context.event?.runtime_agent_id) ||
        toStringArray(context.event?.runtime_agent_ids)[0];
      const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
        ...context,
        runId,
        approvalId,
        issueId,
        runtimeAgentId,
      });

      setSelectedSessionApprovalId(approvalId);
      setSelectedSessionIssueId(issueId);
      setSelectedSessionEventKey(matchedEvent?.key || "");
      setSelectedSessionContextKind(
        context.event ? "event" : issueId ? "issue" : approvalId ? "approval" : matchedEvent ? "event" : ""
      );

      if (runId) {
        setSelectedRunId(runId);
        setSelectedRunResultIndex(resultIndex);
      }

      if (runtimeAgentId) {
        setSelectedAgentId(runtimeAgentId);
        setAgentTimelineFilter("all");
        setAgentTimelineSearch("");
        setSelectedAgentTimelineKey("");
        setPendingAgentTimelineTarget({
          runtimeAgentId,
          runId,
          approvalId,
          issueId,
        });
      }
    },
    [linkedRuns, selectedSession]
  );
  const inspectSessionLineageEntry = useCallback(
    (entry: SessionLineageEntry) => {
      syncLinkedSelection({
        runId: entry.runId,
        resultIndex: entry.resultIndex,
        approvalId: entry.approvalId,
        issueId: entry.issueId,
        runtimeAgentId: entry.runtimeAgentId,
        event: entry.event,
      });
    },
    [syncLinkedSelection]
  );
  const focusSessionLineageEntry = useCallback(
    (entry: SessionLineageEntry, filter: string) => {
      setSessionLineageFilter(filter);
      inspectSessionLineageEntry(entry);
    },
    [inspectSessionLineageEntry]
  );
  const advanceSessionLineageQueue = useCallback(
    (filter: "attention" | "decisions") => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const previousEntry = selectedSessionLineageEntry;
      const nextEntry = nextSessionLineageQueueEntry(entries, selectedSessionLineageEntry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
        nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
        previousTarget: previousEntry
          ? sessionQueueAdvanceTarget(sessionLineageFilter, previousEntry)
          : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, filter);
    },
    [
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      focusSessionLineageEntry,
      sessionLineageFilter,
      selectedSessionLineageEntry,
    ]
  );
  const advanceSessionLineageQueueFromEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry | null) => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const nextEntry = nextSessionLineageQueueEntry(entries, entry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
        nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
        previousTarget: entry ? sessionQueueAdvanceTarget(filter, entry) : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, filter);
    },
    [attentionSessionLineageEntries, decisionSessionLineageEntries, focusSessionLineageEntry]
  );
  const dismissSessionLineageQueueEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry) => {
      setDismissedLineageQueueKeys((current) => ({
        ...current,
        [filter]: current[filter].includes(entry.key)
          ? current[filter]
          : [...current[filter], entry.key],
      }));
      setLineageQueueNow(Date.now());
      if (selectedSessionLineageEntry?.key === entry.key) {
        setPendingLineageAutoAdvance({
          filter,
          previousKey: entry.key,
          previousEntry: entry,
          previousFilter: filter,
        });
      }
    },
    [selectedSessionLineageEntry]
  );
  const snoozeSessionLineageQueueEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry, minutes = 15) => {
      const snoozedUntil = Date.now() + minutes * 60 * 1000;
      setSnoozedLineageQueueUntil((current) => ({
        ...current,
        [filter]: {
          ...current[filter],
          [entry.key]: snoozedUntil,
        },
      }));
      setLineageQueueNow(Date.now());
      if (selectedSessionLineageEntry?.key === entry.key) {
        setPendingLineageAutoAdvance({
          filter,
          previousKey: entry.key,
          previousEntry: entry,
          previousFilter: filter,
        });
      }
    },
    [selectedSessionLineageEntry]
  );
  const restoreSessionLineageQueue = useCallback((filter: LineageQueueKind) => {
    setDismissedLineageQueueKeys((current) => ({
      ...current,
      [filter]: [],
    }));
    setSnoozedLineageQueueUntil((current) => ({
      ...current,
      [filter]: {},
    }));
    setLineageQueueNow(Date.now());
  }, []);
  const resetSessionLineageQueuePreferences = useCallback(() => {
    setDismissedLineageQueueKeys(emptyDismissedLineageQueueKeys());
    setSnoozedLineageQueueUntil(emptySnoozedLineageQueueUntil());
    setLineageQueueNow(Date.now());
    setNotice("Session lineage queue state reset.");
    setErrorMessage("");
    if (selectedSessionId && typeof window !== "undefined") {
      window.localStorage.removeItem(lineageQueueStorageKey(selectedSessionId));
    }
  }, [selectedSessionId]);
  const toggleSessionLineageQueueExpansion = useCallback((filter: LineageQueueKind) => {
    setExpandedSessionLineageQueues((current) =>
      current.includes(filter)
        ? current.filter((key) => key !== filter)
        : [...current, filter]
    );
  }, []);
  const expandAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, []);
  const collapseAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([]);
  }, []);
  const openCurrentSessionLineageQueue = useCallback(() => {
    if (!currentSessionLineageQueue) return;
    setExpandedSessionLineageQueues((current) =>
      current.includes(currentSessionLineageQueue)
        ? current
        : [...current, currentSessionLineageQueue]
    );
  }, [currentSessionLineageQueue]);
  const exportSessionLineageQueuePreferences = useCallback(async () => {
    if (!selectedSessionId) return;
    const payload = {
      sessionId: selectedSessionId,
      exportedAt: new Date().toISOString(),
      queueState: persistedLineageQueueState,
    };
    const serialized = JSON.stringify(payload, null, 2);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(serialized);
        setNotice("Copied session lineage queue state.");
        setErrorMessage("");
        return;
      }
      setErrorMessage("Clipboard is unavailable in this environment.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to copy session lineage queue state."
      );
    }
  }, [persistedLineageQueueState, selectedSessionId]);
  const dismissAgentTimelineEntry = useCallback((entry: AgentTimelineEntry) => {
    const entryKey = agentTimelineEntryKey(entry);
    setDismissedAgentTimelineKeys((current) =>
      current.includes(entryKey) ? current : [...current, entryKey]
    );
    setLineageQueueNow(Date.now());
    const currentEntry = selectedAgentTimelineEntryRef.current;
    if (currentEntry && agentTimelineEntryKey(currentEntry) === entryKey) {
      const priority = agentTimelinePriority(entry);
      if (priority === "critical" || priority === "high") {
        setPendingAgentPriorityAutoAdvance({
          priority,
          previousKey: entryKey,
          previousEntry: entry,
        });
      }
    }
  }, []);
  const snoozeAgentTimelineEntry = useCallback((entry: AgentTimelineEntry, minutes = 15) => {
    const entryKey = agentTimelineEntryKey(entry);
    const snoozedUntil = Date.now() + minutes * 60 * 1000;
    setSnoozedAgentTimelineUntil((current) => ({
      ...current,
      [entryKey]: snoozedUntil,
    }));
    setLineageQueueNow(Date.now());
    const currentEntry = selectedAgentTimelineEntryRef.current;
    if (currentEntry && agentTimelineEntryKey(currentEntry) === entryKey) {
      const priority = agentTimelinePriority(entry);
      if (priority === "critical" || priority === "high") {
        setPendingAgentPriorityAutoAdvance({
          priority,
          previousKey: entryKey,
          previousEntry: entry,
        });
      }
    }
  }, []);
  const restoreAgentTimelineHidden = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
  }, []);
  const resetAgentTimelinePreferences = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
    setNotice("Agent timeline state reset.");
    setErrorMessage("");
    if (selectedAgentId && typeof window !== "undefined") {
      window.localStorage.removeItem(agentTimelineStorageKey(selectedAgentId));
    }
  }, [selectedAgentId]);
  const exportAgentTimelinePreferences = useCallback(async () => {
    if (!selectedAgentId) return;
    const timelineState = sanitizePersistedAgentTimelineState(
      {
        dismissed: dismissedAgentTimelineKeys,
        snoozedUntil: snoozedAgentTimelineUntil,
      },
      lineageQueueNow
    );
    const payload = {
      runtimeAgentId: selectedAgentId,
      exportedAt: new Date().toISOString(),
      timelineState,
    };
    const serialized = JSON.stringify(payload, null, 2);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(serialized);
        setNotice("Copied agent timeline state.");
        setErrorMessage("");
        return;
      }
      setErrorMessage("Clipboard is unavailable in this environment.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to copy agent timeline state."
      );
    }
  }, [dismissedAgentTimelineKeys, lineageQueueNow, selectedAgentId, snoozedAgentTimelineUntil]);
  useEffect(() => {
    if (!pendingLineageAutoAdvance) return;
    const entries =
      pendingLineageAutoAdvance.filter === "attention"
        ? attentionSessionLineageEntries
        : decisionSessionLineageEntries;
    const currentIndex = entries.findIndex(
      (entry) => entry.key === pendingLineageAutoAdvance.previousKey
    );
    const nextEntry =
      currentIndex === -1 ? (entries[0] ?? null) : (entries[currentIndex + 1] ?? entries[0] ?? null);
    setPendingLineageAutoAdvance(null);
    if (nextEntry) {
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingLineageAutoAdvance.filter === "attention" ? "Attention" : "Decision"} queue auto-advanced`,
        detail: `Moved to "${nextEntry.title}" after the previous queue action completed.`,
        nextTarget: sessionQueueAdvanceTarget(pendingLineageAutoAdvance.filter, nextEntry),
        previousTarget: pendingLineageAutoAdvance.previousEntry
          ? sessionQueueAdvanceTarget(
              pendingLineageAutoAdvance.previousFilter,
              pendingLineageAutoAdvance.previousEntry
            )
          : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, pendingLineageAutoAdvance.filter);
    } else {
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingLineageAutoAdvance.filter === "attention" ? "Attention" : "Decision"} queue cleared`,
        detail: `No remaining ${pendingLineageAutoAdvance.filter} items were available after the previous queue action.`,
        previousTarget: pendingLineageAutoAdvance.previousEntry
          ? sessionQueueAdvanceTarget(
              pendingLineageAutoAdvance.previousFilter,
              pendingLineageAutoAdvance.previousEntry
            )
          : null,
      }));
      setSessionLineageFilter(pendingLineageAutoAdvance.filter);
    }
  }, [
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    focusSessionLineageEntry,
    pendingLineageAutoAdvance,
  ]);
  useEffect(() => {
    if (!selectedRun || !selectedRunResult) {
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionEventKey("");
      return;
    }
    const approvalId = toStringValue(asRecord(selectedRunResult.approval)?.id);
    const issueId = toStringValue(asRecord(selectedRunResult.issue)?.id);
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
    const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
      runId: selectedRun.id,
      approvalId,
      issueId,
      runtimeAgentId,
    });

    setSelectedSessionApprovalId(approvalId);
    setSelectedSessionIssueId(issueId);
    setSelectedSessionEventKey(matchedEvent?.key || "");
    setSelectedSessionContextKind((current) => {
      if (current === "event" && matchedEvent) return "event";
      if (current === "issue" && issueId) return "issue";
      if (current === "approval" && approvalId) return "approval";
      if (issueId) return "issue";
      if (approvalId) return "approval";
      if (matchedEvent) return "event";
      return "";
    });

    if (runtimeAgentId) {
      setPendingAgentTimelineTarget({
        runtimeAgentId,
        runId: selectedRun.id,
        approvalId,
        issueId,
      });
    }
  }, [selectedRun, selectedRunResult, selectedSession]);
  const openSelectedRunResultInTimeline = useCallback(() => {
    if (!selectedRun || !selectedRunResult) return;
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
    if (!runtimeAgentId) {
      setErrorMessage("Selected outcome is not linked to a runtime agent.");
      return;
    }

    setErrorMessage("");
    setAgentTimelineFilter("all");
    setAgentTimelineSearch("");
    setSelectedAgentTimelineKey("");
    setSelectedAgentId(runtimeAgentId);
    setPendingAgentTimelineTarget({
      runtimeAgentId,
      runId: selectedRun.id,
      approvalId: toStringValue(asRecord(selectedRunResult.approval)?.id),
      issueId: toStringValue(asRecord(selectedRunResult.issue)?.id),
    });
  }, [selectedRun, selectedRunResult]);
  const agentScopedRuns = useMemo(() => {
    if (!selectedAgentId) return [] as ExecutionAgentActionRunRecord[];
    return linkedRuns.filter((run) => {
      if (run.runtime_agent_ids.includes(selectedAgentId)) return true;
      if (toStringValue(run.selection.runtime_agent_id) === selectedAgentId) return true;
      return run.results.some((result) => {
        const record = asRecord(result);
        return record ? outcomeRuntimeAgentIds(record).includes(selectedAgentId) : false;
      });
    });
  }, [linkedRuns, selectedAgentId]);
  const agentScopedOutcomes = useMemo(() => {
    if (!selectedAgentId) return [] as AgentScopedOutcome[];
    const outcomes: AgentScopedOutcome[] = [];
    agentScopedRuns.forEach((run) => {
      const defaultToRunScope = run.runtime_agent_ids.length === 1 && run.runtime_agent_ids[0] === selectedAgentId;
      run.results.forEach((rawResult, resultIndex) => {
        const result = asRecord(rawResult);
        if (!result) return;
        const runtimeAgentIds = outcomeRuntimeAgentIds(result);
        if (!runtimeAgentIds.includes(selectedAgentId) && !defaultToRunScope) {
          return;
        }
        outcomes.push({
          run,
          result,
          resultIndex,
          timestamp: run.completed_at || run.updated_at || run.created_at,
          runtimeAgentIds,
        });
      });
    });
    return outcomes.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        right.run.created_at.localeCompare(left.run.created_at) ||
        left.resultIndex - right.resultIndex
    );
  }, [agentScopedRuns, selectedAgentId]);
  const filteredAgentScopedRuns = useMemo(
    () =>
      agentScopedRuns.filter(
        (run) =>
          matchesRunFilter(run, agentActivityFilter) &&
          runMatchesSearch(run, agentActivitySearch)
      ),
    [agentActivityFilter, agentActivitySearch, agentScopedRuns]
  );
  const filteredAgentScopedOutcomes = useMemo(
    () =>
      agentScopedOutcomes.filter(
        (outcome) =>
          matchesAgentOutcomeFilter(outcome, agentActivityFilter) &&
          matchesSearch(
            [
              outcome.run.id,
              outcome.run.actor,
              outcome.run.mode,
              outcome.run.reason,
              outcome.runtimeAgentIds,
              outcome.result,
              describeRunResult(outcome.result),
            ],
            agentActivitySearch
          )
      ),
    [agentActivityFilter, agentActivitySearch, agentScopedOutcomes]
  );
  const agentTimelineEntries = useMemo(() => {
    if (!selectedAgent) return [] as AgentTimelineEntry[];
    const entries: AgentTimelineEntry[] = [];

    selectedAgent.approvals.forEach((approval) => {
      entries.push({
        kind: "approval",
        id: approval.id,
        timestamp:
          approval.applied_at ||
          approval.decided_at ||
          approval.updated_at ||
          approval.created_at,
        status: approval.status,
        title: approval.action || approval.id,
        subtitle: approval.project_name || approval.project_id,
        message: approval.reason || "No approval reason provided.",
        approval,
      });
    });

    selectedAgent.issues.forEach((issue) => {
      entries.push({
        kind: "issue",
        id: issue.id,
        timestamp: issue.resolved_at || issue.updated_at || issue.created_at,
        status: issue.status,
        title: issue.title || issue.root_cause || issue.category || issue.id,
        subtitle: issue.category || issue.severity || issue.project_name || issue.project_id,
        message: issue.description || issue.root_cause || "No issue detail provided.",
        issue,
      });
    });

    selectedAgent.events.forEach((event, index) => {
      entries.push({
        kind: "event",
        id: `${toStringValue(event.event, "event")}:${toStringValue(event.timestamp, String(index))}`,
        timestamp: toStringValue(event.timestamp),
        status: toStringValue(event.status, "unknown"),
        title: toStringValue(event.event, "unknown_event"),
        subtitle: eventFamily(toStringValue(event.event)),
        message: toStringValue(event.message, "No event message"),
        event,
      });
    });

    return entries.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        left.kind.localeCompare(right.kind) ||
        left.id.localeCompare(right.id)
    );
  }, [selectedAgent]);
  const agentTimelineOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedAgentTimelineKeys,
          snoozedUntil: snoozedAgentTimelineUntil,
        },
        lineageQueueNow
      ),
    [dismissedAgentTimelineKeys, lineageQueueNow, snoozedAgentTimelineUntil]
  );
  const activeAgentTimelineEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        agentTimelineEntries,
        agentTimelineEntryKey,
        agentTimelineOperatorVisibilityState,
        lineageQueueNow
      ),
    [agentTimelineEntries, agentTimelineOperatorVisibilityState, lineageQueueNow]
  );
  const filteredAgentTimelineEntries = useMemo(
    () =>
      activeAgentTimelineEntries.filter(
        (entry) =>
          matchesAgentTimelineFilter(entry, agentTimelineFilter) &&
          matchesSearch(
            [
              entry.kind,
              entry.id,
              entry.status,
              entry.title,
              entry.subtitle,
              entry.message,
              entry.approval,
              entry.issue,
              entry.event,
            ],
            agentTimelineSearch
          )
    ),
    [activeAgentTimelineEntries, agentTimelineFilter, agentTimelineSearch]
  );
  const agentTimelineFilterCounts = useMemo<Record<string, number>>(
    () => ({
      all: activeAgentTimelineEntries.length,
      approvals: activeAgentTimelineEntries.filter((entry) => entry.kind === "approval").length,
      issues: activeAgentTimelineEntries.filter((entry) => entry.kind === "issue").length,
      events: activeAgentTimelineEntries.filter((entry) => entry.kind === "event").length,
      attention: activeAgentTimelineEntries.filter((entry) =>
        matchesAgentTimelineFilter(entry, "attention")
      ).length,
    }),
    [activeAgentTimelineEntries]
  );
  const sessionQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!sessionQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: sessionLineageFilter,
      total: sessionLineageEntries.length,
      visible: filteredSessionLineageEntries.length,
      labelForFilter: sessionLineageFilterLabel,
      classForFilter: sessionLineageFilterClass,
      noun: "lineage chains",
      scopeLabel: "session",
    });
  }, [
    filteredSessionLineageEntries.length,
    sessionLineageEntries.length,
    sessionLineageFilter,
    sessionQueueAdvanceFeedback,
  ]);
  const agentQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!agentQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: agentTimelineFilter,
      total: activeAgentTimelineEntries.length,
      visible: filteredAgentTimelineEntries.length,
      labelForFilter: agentTimelineFilterLabel,
      classForFilter: agentTimelineFilterClass,
      noun: "active timeline items",
      scopeLabel: "agent",
    });
  }, [
    activeAgentTimelineEntries.length,
    agentQueueAdvanceFeedback,
    agentTimelineFilter,
    filteredAgentTimelineEntries.length,
  ]);
  useEffect(() => {
    if (!filteredAgentTimelineEntries.length) {
      setSelectedAgentTimelineKey("");
      return;
    }
    setSelectedAgentTimelineKey((current) =>
      current && filteredAgentTimelineEntries.some((entry) => agentTimelineEntryKey(entry) === current)
        ? current
        : agentTimelineEntryKey(filteredAgentTimelineEntries[0])
    );
  }, [filteredAgentTimelineEntries]);
  const selectedAgentTimelineEntry = useMemo(
    () =>
      filteredAgentTimelineEntries.find(
        (entry) => agentTimelineEntryKey(entry) === selectedAgentTimelineKey
      ) ?? filteredAgentTimelineEntries[0] ?? null,
    [filteredAgentTimelineEntries, selectedAgentTimelineKey]
  );
  useEffect(() => {
    selectedAgentTimelineEntryRef.current = selectedAgentTimelineEntry;
  }, [selectedAgentTimelineEntry]);
  const visibleAgentTimelineEntries = useMemo(
    () =>
      withSelectedItem(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        6,
        agentTimelineEntryKey
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const latestAgentApprovalEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "approval") ?? null,
    [activeAgentTimelineEntries]
  );
  const latestAgentIssueEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "issue") ?? null,
    [activeAgentTimelineEntries]
  );
  const latestAgentEventEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "event") ?? null,
    [activeAgentTimelineEntries]
  );
  const hiddenAgentTimelineEntryCount = useMemo(
    () => Math.max(agentTimelineEntries.length - activeAgentTimelineEntries.length, 0),
    [activeAgentTimelineEntries.length, agentTimelineEntries.length]
  );
  const persistedAgentTimelineState = useMemo(
    () => agentTimelineOperatorVisibilityState,
    [agentTimelineOperatorVisibilityState]
  );
  const persistedDismissedAgentTimelineCount = useMemo(
    () => persistedAgentTimelineState.dismissed.length,
    [persistedAgentTimelineState]
  );
  const persistedSnoozedAgentTimelineCount = useMemo(
    () => Object.keys(persistedAgentTimelineState.snoozedUntil).length,
    [persistedAgentTimelineState]
  );
  const hasPersistedAgentTimelinePreferences = useMemo(
    () => !isPersistedAgentTimelineStateEmpty(persistedAgentTimelineState),
    [persistedAgentTimelineState]
  );
  const selectedAgentTimelineRunLink = useMemo(
    () =>
      selectedAgentTimelineEntry
        ? resolveAgentTimelineRunLink(selectedAgentTimelineEntry, linkedRuns)
        : null,
    [linkedRuns, selectedAgentTimelineEntry]
  );
  const agentTimelinePriorityCounts = useMemo(
    () => countTriagePriorities(filteredAgentTimelineEntries, agentTimelinePriority),
    [filteredAgentTimelineEntries]
  );
  const nextBestAgentTimelineEntry = useMemo(
    () =>
      nextBestTriageItem(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const selectedAgentTimelinePriority = useMemo(
    () => (selectedAgentTimelineEntry ? agentTimelinePriority(selectedAgentTimelineEntry) : null),
    [selectedAgentTimelineEntry]
  );
  const currentAgentPriorityQueue = useMemo<
    (typeof AGENT_PRIORITY_QUEUE_KEYS)[number] | ""
  >(() => {
    if (selectedAgentTimelinePriority === "critical" || selectedAgentTimelinePriority === "high") {
      return selectedAgentTimelinePriority;
    }
    if (filteredAgentTimelineEntries.some((entry) => agentTimelinePriority(entry) === "critical")) {
      return "critical";
    }
    if (filteredAgentTimelineEntries.some((entry) => agentTimelinePriority(entry) === "high")) {
      return "high";
    }
    return "";
  }, [
    filteredAgentTimelineEntries,
    selectedAgentTimelinePriority,
  ]);
  const criticalAgentTimelineEntries = useMemo(
    () =>
      filteredAgentTimelineEntries.filter(
        (entry) => agentTimelinePriority(entry) === "critical"
      ),
    [filteredAgentTimelineEntries]
  );
  const highAgentTimelineEntries = useMemo(
    () =>
      filteredAgentTimelineEntries.filter((entry) => agentTimelinePriority(entry) === "high"),
    [filteredAgentTimelineEntries]
  );
  const criticalAgentTimelineQueue = useMemo(
    () => criticalAgentTimelineEntries.slice(0, 2),
    [criticalAgentTimelineEntries]
  );
  const highAgentTimelineQueue = useMemo(
    () => highAgentTimelineEntries.slice(0, 2),
    [highAgentTimelineEntries]
  );
  const criticalAgentTimelinePosition = useMemo(
    () =>
      triageQueuePosition(
        criticalAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey
      ),
    [criticalAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const highAgentTimelinePosition = useMemo(
    () =>
      triageQueuePosition(
        highAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey
      ),
    [highAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const nextCriticalAgentTimelineEntry = useMemo(
    () =>
      nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        "critical"
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const nextHighAgentTimelineEntry = useMemo(
    () =>
      nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        "high"
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const toggleAgentPriorityQueueExpansion = useCallback(
    (priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number]) => {
      setExpandedAgentPriorityQueues((current) =>
        current.includes(priority)
          ? current.filter((key) => key !== priority)
          : [...current, priority]
      );
    },
    []
  );
  const expandAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, []);
  const collapseAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([]);
  }, []);
  const openCurrentAgentPriorityQueue = useCallback(() => {
    if (!currentAgentPriorityQueue) return;
    setExpandedAgentPriorityQueues((current) =>
      current.includes(currentAgentPriorityQueue)
        ? current
        : [...current, currentAgentPriorityQueue]
    );
  }, [currentAgentPriorityQueue]);
  const selectedAgentTimelineEntryKeyValue = selectedAgentTimelineEntry
    ? agentTimelineEntryKey(selectedAgentTimelineEntry)
    : "";
  const inspectAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
      const relatedRunLink = resolveAgentTimelineRunLink(entry, linkedRuns);
      setSelectedAgentTimelineKey(agentTimelineEntryKey(entry));
      syncLinkedSelection({
        runId:
          relatedRunLink?.run.id ||
          toStringValue(entry.event?.agent_action_run_id) ||
          toStringValue(entry.event?.run_id),
        resultIndex: relatedRunLink?.resultIndex,
        approvalId:
          entry.approval?.id ||
          entry.issue?.approval_id ||
          toStringValue(entry.event?.approval_id),
        issueId: entry.issue?.id || toStringValue(entry.event?.issue_id),
        runtimeAgentId: selectedAgent?.runtime_agent_id || selectedAgentId,
        event: entry.event || null,
      });
    },
    [linkedRuns, selectedAgent, selectedAgentId, syncLinkedSelection]
  );
  const advanceAgentPriorityQueueFromEntry = useCallback(
    (
      priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number],
      entry: AgentTimelineEntry | null
    ) => {
      const nextEntry = nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        entry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        priority
      );
      if (!nextEntry) return;
      const nextReason = describeAgentQueueAdvanceReason(nextEntry);
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${priority === "critical" ? "Critical" : "High"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${priority} item.`,
        nextTarget: agentQueueAdvanceTarget(priority, nextEntry),
        previousTarget: entry ? agentQueueAdvanceTarget(priority, entry) : null,
        reasonDetails: nextReason,
      }));
      inspectAgentTimelineEntry(nextEntry);
    },
    [filteredAgentTimelineEntries, inspectAgentTimelineEntry]
  );
  const restoreAgentTimelineEntryVisibility = useCallback((entryKey: string) => {
    if (!entryKey) return;
    setDismissedAgentTimelineKeys((current) => current.filter((key) => key !== entryKey));
    setSnoozedAgentTimelineUntil((current) => {
      if (!(entryKey in current)) return current;
      const next = { ...current };
      delete next[entryKey];
      return next;
    });
    setLineageQueueNow(Date.now());
  }, []);
  const revealAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
      const entryKey = agentTimelineEntryKey(entry);
      setAgentTimelineFilter("all");
      setAgentTimelineSearch("");
      setSelectedAgentTimelineKey(entryKey);
      if (selectedAgentId) {
        setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, entryKey));
      }
    },
    [selectedAgentId]
  );
  const findSessionLineageEntryInSession = useCallback((entry: SessionLineageEntry) => {
    setEntitySearch(entry.runId || entry.issueId || entry.approvalId || entry.title);
    if (entry.runId) {
      setSelectedRunId(entry.runId);
      setSelectedRunResultIndex(entry.resultIndex);
    }
  }, []);
  const revealSessionLineageEntryInTimeline = useCallback(
    (entry: SessionLineageEntry) => {
      syncLinkedSelection({
        runId: entry.runId,
        resultIndex: entry.resultIndex,
        approvalId: entry.approvalId,
        issueId: entry.issueId,
        runtimeAgentId: entry.runtimeAgentId,
        event: entry.event,
      });
    },
    [syncLinkedSelection]
  );
  const findAgentTimelineEntryInSession = useCallback(
    (entry: AgentTimelineEntry) => {
      const relatedRunLink = resolveAgentTimelineRunLink(entry, linkedRuns);
      const approvalId =
        entry.approval?.id ||
        entry.issue?.approval_id ||
        toStringValue(entry.event?.approval_id);
      const issueId = entry.issue?.id || toStringValue(entry.event?.issue_id);
      const eventToken =
        toStringValue(entry.event?.event) ||
        toStringValue(entry.event?.message) ||
        entry.id;

      if (relatedRunLink) {
        setEntitySearch(relatedRunLink.run.id || approvalId || issueId || eventToken);
        setSelectedRunId(relatedRunLink.run.id);
        setSelectedRunResultIndex(relatedRunLink.resultIndex);
        return;
      }

      setEntitySearch(approvalId || issueId || eventToken);
    },
    [linkedRuns]
  );
  const openSessionQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "session-lineage") return;
      focusSessionLineageEntry(target.entry, target.filter);
    },
    [focusSessionLineageEntry]
  );
  const openAgentQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "agent-timeline") return;
      restoreAgentTimelineEntryVisibility(agentTimelineEntryKey(target.entry));
      revealAgentTimelineEntry(target.entry);
      inspectAgentTimelineEntry(target.entry);
    },
    [inspectAgentTimelineEntry, restoreAgentTimelineEntryVisibility, revealAgentTimelineEntry]
  );
  const applySessionQueueFocus = useCallback(
    (nextFilter: string, entry?: SessionLineageEntry | null) => {
      setSessionQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          sessionLineageFilterLabel(sessionLineageFilter),
          sessionLineageFilterLabel(nextFilter),
          sessionLineageFilterCounts[sessionLineageFilter] ?? sessionLineageEntries.length,
          sessionLineageFilterCounts[nextFilter] ?? sessionLineageEntries.length
        )
      );
      if (entry) {
        focusSessionLineageEntry(entry, nextFilter);
        return;
      }
      setSessionLineageFilter(nextFilter);
    },
    [
      focusSessionLineageEntry,
      sessionLineageEntries.length,
      sessionLineageFilter,
      sessionLineageFilterCounts,
    ]
  );
  const applyAgentQueueFocus = useCallback(
    (nextFilter: string, entry?: AgentTimelineEntry | null) => {
      setAgentQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          agentTimelineFilterLabel(agentTimelineFilter),
          agentTimelineFilterLabel(nextFilter),
          agentTimelineFilterCounts[agentTimelineFilter] ?? activeAgentTimelineEntries.length,
          agentTimelineFilterCounts[nextFilter] ?? activeAgentTimelineEntries.length
        )
      );
      focusAgentTimeline(nextFilter, entry ? { entry } : undefined);
      if (entry) {
        inspectAgentTimelineEntry(entry);
      }
    },
    [
      activeAgentTimelineEntries.length,
      agentTimelineFilter,
      agentTimelineFilterCounts,
      focusAgentTimeline,
      inspectAgentTimelineEntry,
    ]
  );
  const focusSessionQueueAdvanceSignal = useCallback(
    (signal: QueueAdvanceSignal) => {
      const target = sessionQueueAdvanceFeedback?.nextTarget;
      if (!target || target.kind !== "session-lineage") return;
      applySessionQueueFocus(signal.focusFilter || target.filter, target.entry);
    },
    [applySessionQueueFocus, sessionQueueAdvanceFeedback]
  );
  const focusAgentQueueAdvanceSignal = useCallback(
    (signal: QueueAdvanceSignal) => {
      const target = agentQueueAdvanceFeedback?.nextTarget;
      if (!target || target.kind !== "agent-timeline") return;
      applyAgentQueueFocus(signal.focusFilter || "all", target.entry);
    },
    [agentQueueAdvanceFeedback, applyAgentQueueFocus]
  );
  const sessionQueueAdvanceNoticeActions = useMemo(
    () =>
      buildQueueAdvanceNoticeActionProps({
        feedback: sessionQueueAdvanceFeedback,
        onOpenTarget: openSessionQueueAdvanceTarget,
        onSignalClick: focusSessionQueueAdvanceSignal,
        onResetFocus: () => {
          applySessionQueueFocus(
            "all",
            sessionQueueAdvanceFeedback?.nextTarget?.kind === "session-lineage"
              ? sessionQueueAdvanceFeedback.nextTarget.entry
              : null
          );
        },
        onOpenMatchingQueue: currentSessionLineageQueue
          ? () => {
              openCurrentSessionLineageQueue();
            }
          : undefined,
      }),
    [
      applySessionQueueFocus,
      currentSessionLineageQueue,
      focusSessionQueueAdvanceSignal,
      openCurrentSessionLineageQueue,
      openSessionQueueAdvanceTarget,
      sessionQueueAdvanceFeedback,
    ]
  );
  const agentQueueAdvanceNoticeActions = useMemo(
    () =>
      buildQueueAdvanceNoticeActionProps({
        feedback: agentQueueAdvanceFeedback,
        onOpenTarget: openAgentQueueAdvanceTarget,
        onSignalClick: focusAgentQueueAdvanceSignal,
        onResetFocus: () => {
          applyAgentQueueFocus(
            "all",
            agentQueueAdvanceFeedback?.nextTarget?.kind === "agent-timeline"
              ? agentQueueAdvanceFeedback.nextTarget.entry
              : undefined
          );
        },
        onOpenMatchingQueue: currentAgentPriorityQueue
          ? () => {
              openCurrentAgentPriorityQueue();
            }
          : undefined,
      }),
    [
      agentQueueAdvanceFeedback,
      applyAgentQueueFocus,
      currentAgentPriorityQueue,
      focusAgentQueueAdvanceSignal,
      openAgentQueueAdvanceTarget,
      openCurrentAgentPriorityQueue,
    ]
  );
  const triageInboxItems = useMemo(
    () =>
      [
        nextAttentionSessionLineageEntry
          ? {
              key: "session-attention",
              label: "Session Attention",
              queueDetail: `${attentionSessionLineageEntries.length} queued`,
              title: nextAttentionSessionLineageEntry.title,
              subtitle: `run ${nextAttentionSessionLineageEntry.runId} · outcome ${nextAttentionSessionLineageEntry.resultIndex + 1}`,
              timestamp: nextAttentionSessionLineageEntry.timestamp,
              status: nextAttentionSessionLineageEntry.status,
              statusClassName: passStatusClass(nextAttentionSessionLineageEntry.status),
              priority: sessionLineagePriority(nextAttentionSessionLineageEntry),
              syncedWithSelection:
                selectedSessionLineageEntry?.key === nextAttentionSessionLineageEntry.key,
              onInspect: () => {
                focusSessionLineageEntry(nextAttentionSessionLineageEntry, "attention");
              },
              onSnooze: () => {
                snoozeSessionLineageQueueEntry("attention", nextAttentionSessionLineageEntry);
              },
              onDismiss: () => {
                dismissSessionLineageQueueEntry("attention", nextAttentionSessionLineageEntry);
              },
            }
          : null,
        nextDecisionSessionLineageEntry
          ? {
              key: "session-decisions",
              label: "Session Decision",
              queueDetail: `${decisionSessionLineageEntries.length} queued`,
              title: nextDecisionSessionLineageEntry.title,
              subtitle: `run ${nextDecisionSessionLineageEntry.runId} · outcome ${nextDecisionSessionLineageEntry.resultIndex + 1}`,
              timestamp: nextDecisionSessionLineageEntry.timestamp,
              status: nextDecisionSessionLineageEntry.status,
              statusClassName: passStatusClass(nextDecisionSessionLineageEntry.status),
              priority: sessionLineagePriority(nextDecisionSessionLineageEntry),
              syncedWithSelection:
                selectedSessionLineageEntry?.key === nextDecisionSessionLineageEntry.key,
              onInspect: () => {
                focusSessionLineageEntry(nextDecisionSessionLineageEntry, "decisions");
              },
              onSnooze: () => {
                snoozeSessionLineageQueueEntry("decisions", nextDecisionSessionLineageEntry);
              },
              onDismiss: () => {
                dismissSessionLineageQueueEntry("decisions", nextDecisionSessionLineageEntry);
              },
            }
          : null,
        nextCriticalAgentTimelineEntry
          ? {
              key: "agent-critical",
              label: "Agent Critical",
              queueDetail: `${criticalAgentTimelineEntries.length} queued`,
              title: nextCriticalAgentTimelineEntry.title,
              subtitle: `${nextCriticalAgentTimelineEntry.kind} · ${nextCriticalAgentTimelineEntry.subtitle || "No scope metadata"}`,
              timestamp: nextCriticalAgentTimelineEntry.timestamp,
              status: nextCriticalAgentTimelineEntry.status,
              statusClassName: agentTimelineEntryStatusClass(nextCriticalAgentTimelineEntry),
              priority: agentTimelinePriority(nextCriticalAgentTimelineEntry),
              syncedWithSelection:
                selectedAgentTimelineEntryKeyValue ===
                agentTimelineEntryKey(nextCriticalAgentTimelineEntry),
              onInspect: () => {
                inspectAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
              onSnooze: () => {
                snoozeAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
              onDismiss: () => {
                dismissAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
            }
          : null,
        nextHighAgentTimelineEntry
          ? {
              key: "agent-high",
              label: "Agent High",
              queueDetail: `${highAgentTimelineEntries.length} queued`,
              title: nextHighAgentTimelineEntry.title,
              subtitle: `${nextHighAgentTimelineEntry.kind} · ${nextHighAgentTimelineEntry.subtitle || "No scope metadata"}`,
              timestamp: nextHighAgentTimelineEntry.timestamp,
              status: nextHighAgentTimelineEntry.status,
              statusClassName: agentTimelineEntryStatusClass(nextHighAgentTimelineEntry),
              priority: agentTimelinePriority(nextHighAgentTimelineEntry),
              syncedWithSelection:
                selectedAgentTimelineEntryKeyValue ===
                agentTimelineEntryKey(nextHighAgentTimelineEntry),
              onInspect: () => {
                inspectAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
              onSnooze: () => {
                snoozeAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
              onDismiss: () => {
                dismissAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
            }
          : null,
      ].filter(Boolean) as TriageInboxItem[],
    [
      attentionSessionLineageEntries.length,
      criticalAgentTimelineEntries.length,
      decisionSessionLineageEntries.length,
      dismissAgentTimelineEntry,
      dismissSessionLineageQueueEntry,
      focusSessionLineageEntry,
      highAgentTimelineEntries.length,
      inspectAgentTimelineEntry,
      nextAttentionSessionLineageEntry,
      nextCriticalAgentTimelineEntry,
      nextDecisionSessionLineageEntry,
      nextHighAgentTimelineEntry,
      selectedAgentTimelineEntryKeyValue,
      selectedSessionLineageEntry,
      snoozeAgentTimelineEntry,
      snoozeSessionLineageQueueEntry,
    ]
  );
  const triageInboxItemCount = triageInboxItems.length;
  const selectedTriageInboxItem = useMemo(
    () =>
      triageInboxItems.find((item) => item.key === selectedTriageInboxKey) ??
      triageInboxItems[0] ??
      null,
    [triageInboxItems, selectedTriageInboxKey]
  );
  const triageInboxFeedbackCounts = useMemo(
    () => ({
      all: triageInboxFeedbackHistory.length,
      success: triageInboxFeedbackHistory.filter((feedback) => feedback.tone === "success").length,
      info: triageInboxFeedbackHistory.filter((feedback) => feedback.tone === "info").length,
    }),
    [triageInboxFeedbackHistory]
  );
  const visibleTriageInboxFeedbackHistory = useMemo(
    () =>
      triageInboxFeedbackFilter === "all"
        ? triageInboxFeedbackHistory
        : triageInboxFeedbackHistory.filter(
            (feedback) => feedback.tone === triageInboxFeedbackFilter
          ),
    [triageInboxFeedbackFilter, triageInboxFeedbackHistory]
  );
  const triageInboxFeedback = useMemo(
    () => visibleTriageInboxFeedbackHistory[0] ?? null,
    [visibleTriageInboxFeedbackHistory]
  );
  const recentTriageInboxFeedback = useMemo(
    () => visibleTriageInboxFeedbackHistory.slice(1, TRIAGE_INBOX_FEEDBACK_LIMIT),
    [visibleTriageInboxFeedbackHistory]
  );
  const groupedRecentTriageInboxFeedback = useMemo(() => {
    const groups = new Map<string, TriageInboxFeedbackGroup>();
    recentTriageInboxFeedback.forEach((feedback) => {
      const existing = groups.get(feedback.itemKey);
      if (existing) {
        existing.entries.push(feedback);
        return;
      }
      groups.set(feedback.itemKey, {
        itemKey: feedback.itemKey,
        itemLabel: feedback.itemLabel,
        entries: [feedback],
        isActive: triageInboxItems.some((item) => item.key === feedback.itemKey),
      });
    });
    return Array.from(groups.values());
  }, [recentTriageInboxFeedback, triageInboxItems]);
  const currentTriageInboxFeedbackGroup = useMemo(
    () =>
      selectedTriageInboxItem
        ? groupedRecentTriageInboxFeedback.find(
            (group) => group.itemKey === selectedTriageInboxItem.key
          ) ?? null
        : null,
    [groupedRecentTriageInboxFeedback, selectedTriageInboxItem]
  );
  useEffect(() => {
    selectedTriageInboxKeyRef.current = selectedTriageInboxKey;
  }, [selectedTriageInboxKey]);
  useEffect(() => {
    setTriageInboxFeedbackHistory([]);
    setTriageInboxFeedbackFilter("all");
    setExpandedTriageInboxResultGroups([]);
  }, [selectedAgentId, selectedSessionId]);
  useEffect(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, [selectedSessionId]);
  useEffect(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, [selectedAgentId]);
  useEffect(() => {
    const availableKeys = groupedRecentTriageInboxFeedback.map((group) => group.itemKey);
    setExpandedTriageInboxResultGroups((current) => {
      const next = current.filter((key) => availableKeys.includes(key));
      if (next.length > 0 || availableKeys.length === 0) return next;
      return [availableKeys[0]];
    });
  }, [groupedRecentTriageInboxFeedback]);
  const syncedTriageInboxItem = useMemo(
    () => triageInboxItems.find((item) => item.syncedWithSelection) ?? null,
    [triageInboxItems]
  );
  const nextTriageInboxCursorKey = useCallback(
    (currentKey: string) => {
      if (!triageInboxItems.length) return "";
      const currentIndex = triageInboxItems.findIndex((item) => item.key === currentKey);
      if (currentIndex === -1) return triageInboxItems[0]?.key || "";
      return triageInboxItems[currentIndex + 1]?.key || triageInboxItems[0]?.key || "";
    },
    [triageInboxItems]
  );
  const advanceTriageInboxCursor = useCallback(() => {
    if (!triageInboxItems.length) return;
    setSelectedTriageInboxKey((current) => {
      const currentIndex = triageInboxItems.findIndex((item) => item.key === current);
      if (currentIndex === -1) return triageInboxItems[0]?.key || "";
      return triageInboxItems[currentIndex + 1]?.key || triageInboxItems[0]?.key || "";
    });
  }, [triageInboxItems]);
  const inspectTriageInboxItem = useCallback((item: TriageInboxItem) => {
    setSelectedTriageInboxKey(item.key);
    item.onInspect();
  }, []);
  const openTriageInboxHistoryGroup = useCallback(
    (itemKey: string) => {
      const inboxItem = triageInboxItems.find((item) => item.key === itemKey);
      if (!inboxItem) return;
      inspectTriageInboxItem(inboxItem);
    },
    [inspectTriageInboxItem, triageInboxItems]
  );
  const inspectAndAdvanceTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      item.onInspect();
    },
    [nextTriageInboxCursorKey]
  );
  const snoozeTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} snoozed for 15m.`, "info");
      item.onSnooze();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback]
  );
  const dismissTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} dismissed from inbox.`, "info");
      item.onDismiss();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback]
  );
  const syncTriageInboxCursorToSelection = useCallback(() => {
    if (!syncedTriageInboxItem) return;
    setSelectedTriageInboxKey(syncedTriageInboxItem.key);
  }, [syncedTriageInboxItem]);
  const toggleTriageInboxResultGroup = useCallback((itemKey: string) => {
    if (!itemKey) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(itemKey)
        ? current.filter((key) => key !== itemKey)
        : [...current, itemKey]
    );
  }, []);
  const expandAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups(
      groupedRecentTriageInboxFeedback.map((group) => group.itemKey)
    );
  }, [groupedRecentTriageInboxFeedback]);
  const collapseAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups([]);
  }, []);
  const openCurrentTriageInboxResultGroup = useCallback(() => {
    if (!currentTriageInboxFeedbackGroup) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(currentTriageInboxFeedbackGroup.itemKey)
        ? current
        : [...current, currentTriageInboxFeedbackGroup.itemKey]
    );
  }, [currentTriageInboxFeedbackGroup]);
  useEffect(() => {
    if (!triageInboxItems.length) {
      setSelectedTriageInboxKey("");
      return;
    }
    setSelectedTriageInboxKey((current) => {
      if (triageInboxItems.some((item) => item.key === current)) return current;
      if (syncedTriageInboxItem) return syncedTriageInboxItem.key;
      return triageInboxItems[0].key;
    });
  }, [syncedTriageInboxItem, triageInboxItems]);
  useEffect(() => {
    if (!pendingAgentPriorityAutoAdvance) return;
    const entries =
      pendingAgentPriorityAutoAdvance.priority === "critical"
        ? criticalAgentTimelineEntries
        : highAgentTimelineEntries;
    const currentIndex = entries.findIndex(
      (entry) => agentTimelineEntryKey(entry) === pendingAgentPriorityAutoAdvance.previousKey
    );
    const nextEntry =
      currentIndex === -1 ? (entries[0] ?? null) : (entries[currentIndex + 1] ?? entries[0] ?? null);
    setPendingAgentPriorityAutoAdvance(null);
    if (nextEntry) {
      const nextReason = describeAgentQueueAdvanceReason(nextEntry);
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingAgentPriorityAutoAdvance.priority === "critical" ? "Critical" : "High"} queue auto-advanced`,
        detail: `Moved to "${nextEntry.title}" after the previous queue action completed.`,
        nextTarget: agentQueueAdvanceTarget(pendingAgentPriorityAutoAdvance.priority, nextEntry),
        previousTarget: pendingAgentPriorityAutoAdvance.previousEntry
          ? agentQueueAdvanceTarget(
              pendingAgentPriorityAutoAdvance.priority,
              pendingAgentPriorityAutoAdvance.previousEntry
            )
          : null,
        reasonDetails: nextReason,
      }));
      inspectAgentTimelineEntry(nextEntry);
    } else {
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingAgentPriorityAutoAdvance.priority === "critical" ? "Critical" : "High"} queue cleared`,
        detail: `No remaining ${pendingAgentPriorityAutoAdvance.priority} items were available after the previous queue action.`,
        previousTarget: pendingAgentPriorityAutoAdvance.previousEntry
          ? agentQueueAdvanceTarget(
              pendingAgentPriorityAutoAdvance.priority,
              pendingAgentPriorityAutoAdvance.previousEntry
            )
          : null,
      }));
    }
  }, [
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    inspectAgentTimelineEntry,
    pendingAgentPriorityAutoAdvance,
  ]);
  const selectedSessionContext = useMemo(() => {
    if (selectedSessionContextKind === "issue" && selectedSessionIssue) {
      return { kind: "issue" as const, issue: selectedSessionIssue };
    }
    if (selectedSessionContextKind === "approval" && selectedSessionApproval) {
      return { kind: "approval" as const, approval: selectedSessionApproval };
    }
    if (selectedSessionContextKind === "event" && selectedSessionEvent) {
      return { kind: "event" as const, event: selectedSessionEvent };
    }
    if (selectedSessionIssue) {
      return { kind: "issue" as const, issue: selectedSessionIssue };
    }
    if (selectedSessionApproval) {
      return { kind: "approval" as const, approval: selectedSessionApproval };
    }
    if (selectedSessionEvent) {
      return { kind: "event" as const, event: selectedSessionEvent };
    }
    return null;
  }, [
    selectedSessionApproval,
    selectedSessionContextKind,
    selectedSessionEvent,
    selectedSessionIssue,
  ]);
  const revealSelectedSessionContextRow = useCallback(() => {
    if (!selectedSessionContext) return;
    setEntitySearch("");
    if (selectedSessionContext.kind === "event") {
      setEventFilter("all");
      setPendingSessionRowDomId(
        sessionContextRowDomId("event", selectedSessionEventKey || sessionEventKey(selectedSessionContext.event))
      );
      return;
    }
    if (selectedSessionContext.kind === "approval") {
      setPendingSessionRowDomId(
        sessionContextRowDomId("approval", selectedSessionContext.approval.id)
      );
      return;
    }
    setPendingSessionRowDomId(sessionContextRowDomId("issue", selectedSessionContext.issue.id));
  }, [selectedSessionContext, selectedSessionEventKey]);
  const revealSelectedSessionContextInAgentTimeline = useCallback(() => {
    if (!selectedSessionContext) return;
    const approvalId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.id
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.approval_id
          : toStringValue(selectedSessionContext.event.approval_id);
    const issueId =
      selectedSessionContext.kind === "issue"
        ? selectedSessionContext.issue.id
        : selectedSessionContext.kind === "approval"
          ? selectedSessionContext.approval.issue_id
          : toStringValue(selectedSessionContext.event.issue_id);
    const runtimeAgentId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.runtime_agent_ids[0]
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.runtime_agent_ids[0] ||
            selectedSessionContext.issue.runtime_agent_id
          : toStringValue(selectedSessionContext.event.runtime_agent_id) ||
            toStringArray(selectedSessionContext.event.runtime_agent_ids)[0];

    if (!runtimeAgentId) {
      setErrorMessage("Selected session context is not linked to a runtime agent.");
      return;
    }

    setErrorMessage("");
    syncLinkedSelection({
      approvalId,
      issueId,
      runtimeAgentId,
      runId:
        selectedSessionContext.kind === "event"
          ? toStringValue(selectedSessionContext.event.agent_action_run_id) ||
            toStringValue(selectedSessionContext.event.run_id)
          : "",
      event: selectedSessionContext.kind === "event" ? selectedSessionContext.event : null,
    });
  }, [selectedSessionContext, syncLinkedSelection]);
  useEffect(() => {
    if (!pendingAgentTimelineTarget) return;
    if (!selectedAgentId || pendingAgentTimelineTarget.runtimeAgentId !== selectedAgentId) return;
    if (!selectedAgent) return;

    const matchedEntry = resolveAgentTimelineEntryFromTarget(
      agentTimelineEntries,
      pendingAgentTimelineTarget
    );
    if (matchedEntry) {
      const matchedKey = agentTimelineEntryKey(matchedEntry);
      setSelectedAgentTimelineKey(matchedKey);
      setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, matchedKey));
      setNotice("");
    } else {
      setNotice("Found runtime agent, but no linked timeline item was available for this outcome.");
    }
    setPendingAgentTimelineTarget(null);
  }, [agentTimelineEntries, pendingAgentTimelineTarget, selectedAgent, selectedAgentId]);
  useEffect(() => {
    if (!pendingSessionRowDomId) return;
    if (scrollToDomId(pendingSessionRowDomId)) {
      setPendingSessionRowDomId("");
    }
  }, [
    entitySearch,
    eventFilter,
    pendingSessionRowDomId,
    visibleSessionApprovals,
    visibleSessionEvents,
    visibleSessionIssues,
  ]);
  useEffect(() => {
    if (!pendingAgentTimelineRowDomId) return;
    if (scrollToDomId(pendingAgentTimelineRowDomId)) {
      setPendingAgentTimelineRowDomId("");
    }
  }, [pendingAgentTimelineRowDomId, selectedAgentId, visibleAgentTimelineEntries]);
  const selectedControl = selectedSession?.control ?? null;
  const loading = !controlSummary || !sessionSummary;

  if (loading) {
    return (
      <div className="flex min-h-screen bg-[#fafaf9]">
        <AppSidebar health={health} projects={visibleProjects} />
        <main className="flex flex-1 items-center justify-center pl-[260px] text-[14px] text-[#787774]">
          Loading control plane...
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={visibleProjects} />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 border-b border-[#e5e5e3] bg-white px-6 py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">FounderOS Execution Plane</p>
              <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[#37352f]">
                Control Plane
              </h1>
              <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[#6b6b6b]">
                Observe session-level orchestration passes, inspect current execution state, and
                apply FounderOS control recommendations directly from Autopilot.
              </p>
            </div>
            <div className="min-w-[280px] rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Latest control pass</span>
                <span className="font-semibold text-[#37352f]">
                  {formatTimestamp(controlSummary.latest_control_pass_at)}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Latest session</span>
                <span className="font-semibold text-[#37352f]">
                  {formatTimestamp(sessionSummary.latest_session_at)}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Selected session</span>
                <span className="font-mono text-[12px] font-semibold text-[#37352f]">
                  {selectedSessionId || "none"}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Control state</span>
                {selectedControl ? (
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControl.state)}`}
                  >
                    {selectedControl.state}
                  </Badge>
                ) : (
                  <span className="text-[#9b9a97]">No session selected</span>
                )}
              </div>
              <Button
                size="sm"
                className="mt-4 h-9 w-full rounded-lg bg-[#1a1a1a] text-[13px] hover:bg-[#333]"
                disabled={refreshing}
                onClick={() => {
                  void refresh();
                }}
              >
                {refreshing ? "Refreshing..." : "Refresh control plane"}
              </Button>
            </div>
          </div>
        </header>

        <div className="space-y-6 px-6 py-6">
          {notice && (
            <div className="rounded-xl border border-[#d6e9dc] bg-[#eef8f1] px-4 py-3 text-[13px] text-[#2b6e3f]">
              {notice}
            </div>
          )}
          {errorMessage && (
            <div className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] px-4 py-3 text-[13px] text-[#93370d]">
              {errorMessage}
            </div>
          )}

          <section className="grid gap-4 xl:grid-cols-4">
            <SummaryStat
              eyebrow="Control Passes"
              value={String(controlSummary.totals.control_passes)}
              detail={`${controlSummary.totals.ok} ok · ${controlSummary.totals.partial} partial · ${controlSummary.totals.error} error`}
            />
            <SummaryStat
              eyebrow="Coverage"
              value={`${controlSummary.totals.sessions} sessions`}
              detail={`${controlSummary.totals.projects} projects touched · ${controlSummary.totals.customized} customized passes`}
            />
            <SummaryStat
              eyebrow="Applied Steps"
              value={String(controlSummary.totals.applied_steps)}
              detail={`${controlSummary.totals.error_steps} error steps across persisted control passes`}
            />
            <SummaryStat
              eyebrow="Session Status"
              value={String(sessionSummary.totals.open)}
              detail={`${sessionSummary.totals.completed} completed · ${sessionSummary.totals.archived} archived`}
            />
          </section>

          <section className="rounded-2xl border border-[#e5e5e3] bg-white p-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                  History Search
                </p>
                <p className="mt-2 text-[13px] text-[#787774]">
                  Search recent sessions and control passes by session id, actor, profile, initiative, project, or linked entity ids.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredSessionHistory.length}/{sessions.length} sessions
                </Badge>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredControlPassHistory.length}/{controlPasses.length} passes
                </Badge>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              <Input
                value={historySearch}
                onChange={(event) => {
                  setHistorySearch(event.target.value);
                }}
                placeholder="session id, control pass id, actor, project, initiative, approval, issue..."
                className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                disabled={!historySearch.trim()}
                onClick={() => {
                  setHistorySearch("");
                }}
              >
                Clear search
              </Button>
            </div>
          </section>

          <ControlPlaneWorkspaceSection
            recentControlPasses={recentControlPasses}
            totalControlPassCount={controlPasses.length}
            selectedPassId={selectedPassId}
            formatTimestamp={formatTimestamp}
            toStringValue={toStringValue}
            toNumber={toNumber}
            onInspectControlPass={(controlPass) => {
              setSelectedPassId(controlPass.id);
              if (controlPass.orchestrator_session_id) {
                setSelectedSessionId(controlPass.orchestrator_session_id);
              }
            }}
            selectedActionRunCardProps={{
              selectedRun,
              selectedRunResultIndex,
              onSelectResult: setSelectedRunResultIndex,
              formatTimestamp,
              formatScopeList,
              describeRunResult,
              toNumber,
              toStringArray,
              toStringValue,
              asRecord,
              children:
                selectedRun && selectedRunResult ? (
                  <SelectedOutcomeInspector
                    selectedRun={selectedRun}
                    selectedRunResult={selectedRunResult}
                    selectedRunResultIndex={selectedRunResultIndex}
                    selectedSessionEvents={selectedSession?.events || []}
                    formatJson={formatJson}
                    asRecord={asRecord}
                    toStringValue={toStringValue}
                    sessionEventKey={sessionEventKey}
                    resolveSessionEventFromContext={resolveSessionEventFromContext}
                    outcomeProjectId={outcomeProjectId}
                    outcomeProjectName={outcomeProjectName}
                    outcomeStoryId={outcomeStoryId}
                    outcomeStoryTitle={outcomeStoryTitle}
                    outcomeRuntimeAgentId={outcomeRuntimeAgentId}
                    onOpenInAgentTimeline={openSelectedRunResultInTimeline}
                    onFocusRuntimeAgent={(runtimeAgentId) => {
                      focusRuntimeAgent(runtimeAgentId, true);
                    }}
                    onFindApproval={(approvalId) => {
                      setEntitySearch(approvalId);
                    }}
                    onFindIssue={(issueId) => {
                      setEntitySearch(issueId);
                    }}
                    onSelectRunOutcome={(runId, resultIndex) => {
                      setSelectedRunId(runId);
                      setSelectedRunResultIndex(resultIndex);
                    }}
                    onSyncLinkedSelection={syncLinkedSelection}
                  />
                ) : null,
            }}
            sessionLineageSectionProps={{
              hasSelectedSession: Boolean(selectedSession),
              sessionEventTotalCount: selectedSession?.events.length || 0,
              sessionLineageEntries,
              linkedRunCount: linkedRuns.length,
              linkedApprovalCount: linkedApprovals.length,
              linkedIssueCount: linkedIssues.length,
              linkedAgentCount: linkedAgentIds.length,
              sessionLineageDecisionCount: sessionLineageDecisionCount,
              sessionLineageEventCount: sessionLineageEventCount,
              sessionLineageAgentCount: sessionLineageAgentCount,
              sessionLineageStatusCounts,
              filteredSessionLineageEntriesCount: filteredSessionLineageEntries.length,
              sessionLineageFilter: sessionLineageFilter as
                | "all"
                | "attention"
                | "decisions"
                | "agent-linked",
              onSessionLineageFilterChange: (value) => {
                setSessionLineageFilter(value);
              },
              sessionLineageAttentionCount,
              sessionLineageAgentLinkedCount,
              persistedDismissedLineageQueueCount,
              persistedSnoozedLineageQueueCount,
              sessionLineagePriorityCounts,
              hasPersistedLineageQueuePreferences,
              onExportSessionLineageQueuePreferences: exportSessionLineageQueuePreferences,
              onResetSessionLineageQueuePreferences: resetSessionLineageQueuePreferences,
              selectedSessionLineageEntry,
              selectedSessionLineagePriority,
              selectedSessionLineageTraits,
              formatTimestamp,
              nextBestSessionLineageEntry,
              attentionSessionLineageEntries,
              decisionSessionLineageEntries,
              latestAgentLinkedLineageEntry,
              onInspectSessionLineageEntry: inspectSessionLineageEntry,
              onAdvanceSessionLineageQueue: advanceSessionLineageQueue,
              onFocusSessionLineageEntry: focusSessionLineageEntry,
              expandedSessionLineageQueues,
              currentSessionLineageQueue,
              onExpandAllSessionLineageQueues: expandAllSessionLineageQueues,
              onCollapseAllSessionLineageQueues: collapseAllSessionLineageQueues,
              onOpenCurrentSessionLineageQueue: openCurrentSessionLineageQueue,
              sessionQueueAdvanceFeedback,
              sessionQueueAdvanceFocusSummary,
              sessionQueueFocusDelta,
              sessionQueueAdvanceNoticeActions: sessionQueueAdvanceNoticeActions,
              attentionQueuePosition,
              hiddenAttentionQueueCount,
              attentionSessionLineageQueue,
              onToggleSessionLineageQueueExpansion: toggleSessionLineageQueueExpansion,
              onRestoreSessionLineageQueue: restoreSessionLineageQueue,
              sessionLineagePriority,
              sessionLineageTraits,
              onSnoozeSessionLineageQueueEntry: snoozeSessionLineageQueueEntry,
              onAdvanceSessionLineageQueueFromEntry: advanceSessionLineageQueueFromEntry,
              onDismissSessionLineageQueueEntry: dismissSessionLineageQueueEntry,
              onFindSessionLineageEntryInSession: findSessionLineageEntryInSession,
              onRevealSessionLineageEntryInTimeline: revealSessionLineageEntryInTimeline,
              decisionQueuePosition,
              hiddenDecisionQueueCount,
              decisionSessionLineageQueue,
              visibleSessionLineageEntries,
              onSelectRunOutcome: (runId, resultIndex) => {
                setSelectedRunId(runId);
                setSelectedRunResultIndex(resultIndex);
              },
            }}
            triageInboxSectionProps={{
              triageInboxItemCount,
              triageInboxItems,
              selectedTriageInboxItem,
              syncedTriageInboxItem,
              formatTimestamp,
              onInspectTriageInboxItem: inspectTriageInboxItem,
              onInspectAndAdvanceTriageInboxItem: inspectAndAdvanceTriageInboxItem,
              onAdvanceTriageInboxCursor: advanceTriageInboxCursor,
              onSyncTriageInboxCursorToSelection: syncTriageInboxCursorToSelection,
              triageInboxFeedbackHistoryCount: triageInboxFeedbackHistory.length,
              triageInboxFeedbackFilter,
              onTriageInboxFeedbackFilterChange: setTriageInboxFeedbackFilter,
              triageInboxFeedbackCounts,
              triageInboxFeedback,
              groupedRecentTriageInboxFeedback,
              recentTriageInboxFeedbackCount: recentTriageInboxFeedback.length,
              expandedTriageInboxResultGroups,
              currentTriageInboxFeedbackGroup,
              onExpandAllTriageInboxResultGroups: expandAllTriageInboxResultGroups,
              onCollapseAllTriageInboxResultGroups: collapseAllTriageInboxResultGroups,
              onOpenCurrentTriageInboxResultGroup: openCurrentTriageInboxResultGroup,
              onToggleTriageInboxResultGroup: toggleTriageInboxResultGroup,
              onOpenTriageInboxHistoryGroup: openTriageInboxHistoryGroup,
              onSnoozeTriageInboxItem: snoozeTriageInboxItem,
              onDismissTriageInboxItem: dismissTriageInboxItem,
            }}
            runtimeAgentSectionProps={{
              selectedAgentId,
              agentLoading,
              selectedAgent,
              busyActionKey,
              formatTimestamp,
              toNumber,
              toStringValue,
              onFocusRuntimeAgent: (runtimeAgentId) => {
                focusRuntimeAgent(runtimeAgentId, true);
              },
              onRunSuggestedCommand: (command, mode) => {
                void runAgentSuggestedCommand(command, mode);
              },
              activitySectionProps: selectedAgent
                ? {
                    selectedAgent,
                    agentScopedRuns,
                    agentActivitySearch,
                    onAgentActivitySearchChange: setAgentActivitySearch,
                    agentActivityFilter,
                    onAgentActivityFilterChange: setAgentActivityFilter,
                    filteredAgentScopedRuns,
                    selectedRunId,
                    selectedRunResultIndex,
                    onSelectRun: (runId, resultIndex) => {
                      setSelectedRunId(runId);
                      setSelectedRunResultIndex(resultIndex);
                    },
                    formatTimestamp,
                    toNumber,
                    describeRunResult,
                    agentScopedOutcomes,
                    filteredAgentScopedOutcomes,
                    outcomeProjectId,
                    outcomeStoryId,
                    toStringValue,
                    asRecord,
                    onFindOutcomeInSession: (runId, resultIndex) => {
                      setEntitySearch(runId);
                      setSelectedRunId(runId);
                      setSelectedRunResultIndex(resultIndex);
                    },
                  }
                : null,
              timelineSectionProps: selectedAgent
                ? {
                    selectedAgent,
                    activeAgentTimelineEntries,
                    hiddenAgentTimelineEntryCount,
                    agentTimelineSearch,
                    onAgentTimelineSearchChange: setAgentTimelineSearch,
                    agentTimelineFilter: agentTimelineFilter as
                      | "all"
                      | "approvals"
                      | "issues"
                      | "events"
                      | "attention",
                    onAgentTimelineFilterChange: (value) => {
                      setAgentTimelineFilter(value);
                    },
                    persistedDismissedAgentTimelineCount,
                    persistedSnoozedAgentTimelineCount,
                    agentTimelinePriorityCounts,
                    nextBestAgentTimelineEntry,
                    hasPersistedAgentTimelinePreferences,
                    onInspectAgentTimelineEntry: inspectAgentTimelineEntry,
                    onRestoreAgentTimelineHidden: restoreAgentTimelineHidden,
                    onExportAgentTimelinePreferences: exportAgentTimelinePreferences,
                    onResetAgentTimelinePreferences: resetAgentTimelinePreferences,
                    agentQueueAdvanceFeedback,
                    agentQueueAdvanceFocusSummary,
                    agentQueueFocusDelta,
                    agentQueueAdvanceNoticeActions: agentQueueAdvanceNoticeActions,
                    nextCriticalAgentTimelineEntry,
                    nextHighAgentTimelineEntry,
                    expandedAgentPriorityQueues,
                    currentAgentPriorityQueue,
                    onExpandAllAgentPriorityQueues: expandAllAgentPriorityQueues,
                    onCollapseAllAgentPriorityQueues: collapseAllAgentPriorityQueues,
                    onOpenCurrentAgentPriorityQueue: openCurrentAgentPriorityQueue,
                    criticalAgentTimelineQueue,
                    criticalAgentTimelineTotal: criticalAgentTimelineEntries.length,
                    criticalAgentTimelinePosition,
                    highAgentTimelineQueue,
                    highAgentTimelineTotal: highAgentTimelineEntries.length,
                    highAgentTimelinePosition,
                    onToggleAgentPriorityQueueExpansion: toggleAgentPriorityQueueExpansion,
                    filteredAgentTimelineEntriesCount: filteredAgentTimelineEntries.length,
                    visibleAgentTimelineEntries,
                    selectedAgentTimelineEntry,
                    selectedAgentTimelineRunLink,
                    selectedAgentTimelinePriority,
                    latestAgentIssueEntry,
                    latestAgentApprovalEntry,
                    latestAgentEventEntry,
                    busyActionKey,
                    formatTimestamp,
                    formatJson,
                    toStringValue,
                    toNullableNumber,
                    asRecord,
                    describeRunResult,
                    onSelectTimelineEntry: (entry) => {
                      setSelectedAgentTimelineKey(agentTimelineEntryKey(entry));
                    },
                    onSyncLinkedSelection: syncLinkedSelection,
                    onFocusRuntimeAgent: (runtimeAgentId) => {
                      focusRuntimeAgent(runtimeAgentId, true);
                    },
                    onSelectRun: (runId, resultIndex) => {
                      setSelectedRunId(runId);
                      setSelectedRunResultIndex(resultIndex);
                    },
                    onApproveApproval: (approval) => {
                      void approveApproval(approval);
                    },
                    onRejectApproval: (approval) => {
                      void rejectApproval(approval);
                    },
                    onApplyApproval: (approval) => {
                      void applyApproval(approval);
                    },
                    onResolveIssue: (issue) => {
                      void resolveIssue(issue);
                    },
                    onAdvanceCurrentPriorityQueue: (entry) => {
                      if (currentAgentPriorityQueue) {
                        advanceAgentPriorityQueueFromEntry(currentAgentPriorityQueue, entry);
                      }
                    },
                    onSearchEntity: setEntitySearch,
                    onFocusAgentTimeline: (filter, entry) => {
                      focusAgentTimeline(filter, entry ? { entry } : undefined);
                    },
                    onFilterSessionByToken: (value) => {
                      setEventFilter("all");
                      setEntitySearch(value);
                    },
                    onSnoozeAgentTimelineEntry: snoozeAgentTimelineEntry,
                    onDismissAgentTimelineEntry: dismissAgentTimelineEntry,
                    onAdvanceAgentPriorityQueueFromEntry: advanceAgentPriorityQueueFromEntry,
                    onFindAgentTimelineEntryInSession: findAgentTimelineEntryInSession,
                    onRevealAgentTimelineEntry: revealAgentTimelineEntry,
                    agentTimelineEntryKey,
                    agentTimelinePriority,
                    agentTimelineRowDomId,
                  }
                : null,
            }}
            controlPlaneOverviewSectionsProps={{
              controlSummary,
              recentSessions,
              totalSessionCount: sessions.length,
              selectedSessionId,
              onSelectSession: setSelectedSessionId,
              sessionSummary,
            }}
          />

          <SessionDrilldownSection
            selectedSessionId={selectedSessionId}
            sessionLoading={sessionLoading}
            selectedSession={selectedSession}
            controlSectionProps={
              selectedSession
                ? {
                    selectedSession,
                    selectedControl,
                    linkedAgentIds,
                    selectedAgentId,
                    onFocusRuntimeAgent: (runtimeAgentId) => {
                      focusRuntimeAgent(runtimeAgentId, true);
                    },
                    filteredRunsCount: filteredRuns.length,
                    linkedRunsCount: linkedRuns.length,
                    filteredEventsCount: filteredEvents.length,
                    filteredApprovalsCount: filteredApprovals.length,
                    linkedApprovalsCount: linkedApprovals.length,
                    filteredIssuesCount: filteredIssues.length,
                    linkedIssuesCount: linkedIssues.length,
                    entitySearch,
                    onEntitySearchChange: setEntitySearch,
                    onClearEntitySearch: () => {
                      setEntitySearch("");
                    },
                    sortedProfiles,
                    busyActionKey,
                    onApplyControlPlan: (profile) => {
                      void applyControlPlan(profile);
                    },
                    onApplyRecommendation: (recommendation) => {
                      void applyRecommendation(recommendation);
                    },
                  }
                : null
            }
            activitySectionProps={
              selectedSession
                ? {
                    selectedSession,
                    selectedControl,
                    linkedRuns,
                    runFilter: runFilter as "all" | "execute" | "preview" | "attention",
                    onRunFilterChange: setRunFilter,
                    getRunFilterCount: (filter) =>
                      linkedRuns.filter((run) => matchesRunFilter(run, filter)).length,
                    filteredRuns,
                    selectedRunId,
                    onSelectRun: setSelectedRunId,
                    onFocusRuntimeAgent: (runtimeAgentId) => {
                      focusRuntimeAgent(runtimeAgentId, true);
                    },
                    toNumber,
                    eventFilter: eventFilter as
                      | "all"
                      | "control"
                      | "actions"
                      | "decisions"
                      | "attention",
                    onEventFilterChange: setEventFilter,
                    getEventFilterCount: (filter) =>
                      (selectedSession.events || []).filter((event) =>
                        matchesEventFilter(event, filter)
                      ).length,
                    filteredEvents,
                    visibleSessionEvents,
                    selectedSessionEventKey,
                    toStringValue,
                    toStringArray,
                    toNullableNumber,
                    formatTimestamp,
                    eventFamily,
                    sessionEventKey,
                    sessionContextRowDomId,
                    onSyncLinkedSelection: syncLinkedSelection,
                    onSearchEntity: setEntitySearch,
                  }
                : null
            }
            selectedControlPassCardProps={{
              selectedPass,
              toStringValue,
              toNumber,
              onOpenSession: setSelectedSessionId,
            }}
            linkedDecisionsCardProps={{
              selectedSession,
              linkedApprovals,
              filteredApprovals,
              visibleSessionApprovals,
              selectedSessionApprovalId,
              linkedIssues,
              filteredIssues,
              visibleSessionIssues,
              selectedSessionIssueId,
              busyActionKey,
              formatTimestamp,
              sessionContextRowDomId,
              onSearchEntity: setEntitySearch,
              onFocusRuntimeAgent: (runtimeAgentId) => {
                focusRuntimeAgent(runtimeAgentId, true);
              },
              onInspectApproval: (approval) => {
                syncLinkedSelection({
                  approvalId: approval.id,
                  issueId: approval.issue_id,
                  runtimeAgentId: approval.runtime_agent_ids[0],
                });
              },
              onInspectIssue: (issue) => {
                syncLinkedSelection({
                  issueId: issue.id,
                  approvalId: issue.approval_id,
                  runtimeAgentId: issue.runtime_agent_ids[0] || issue.runtime_agent_id,
                });
              },
              onApproveApproval: (approval) => {
                void approveApproval(approval);
              },
              onRejectApproval: (approval) => {
                void rejectApproval(approval);
              },
              onApplyApproval: (approval) => {
                void applyApproval(approval);
              },
              onResolveIssue: (issue) => {
                void resolveIssue(issue);
              },
            }}
            selectedSessionContextCardProps={{
              selectedSession,
              selectedSessionContext,
              linkedRuns,
              busyActionKey,
              currentSessionLineageQueue,
              formatTimestamp,
              formatJson,
              toStringValue,
              toStringArray,
              toNullableNumber,
              asRecord,
              eventFamily,
              describeRunResult,
              resolveRunLinkFromContext,
              onRevealSessionRow: revealSelectedSessionContextRow,
              onRevealInAgentTimeline: revealSelectedSessionContextInAgentTimeline,
              onOpenRuntimeAgent: (runtimeAgentId) => {
                focusRuntimeAgent(runtimeAgentId, true);
              },
              onSyncLinkedSelection: syncLinkedSelection,
              onOpenRunOutcome: (runId, resultIndex) => {
                setSelectedRunId(runId);
                setSelectedRunResultIndex(resultIndex);
              },
              onApproveApproval: (approval) => {
                void approveApproval(approval);
              },
              onRejectApproval: (approval) => {
                void rejectApproval(approval);
              },
              onApplyApproval: (approval) => {
                void applyApproval(approval);
              },
              onResolveIssue: (issue) => {
                void resolveIssue(issue);
              },
              onAdvanceCurrentQueue:
                currentSessionLineageQueue && selectedSessionLineageEntry
                  ? () => {
                      advanceSessionLineageQueueFromEntry(
                        currentSessionLineageQueue,
                        selectedSessionLineageEntry
                      );
                    }
                  : null,
            }}
          />
        </div>
      </main>
    </div>
  );
}
