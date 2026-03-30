"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
type RelationshipTone = "run" | "outcome" | "approval" | "issue" | "event" | "agent";
type RelationshipStripItem = {
  key: string;
  label: string;
  tone: RelationshipTone;
  active?: boolean;
  onClick?: () => void;
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

function countEntries(
  value: ExecutionPlaneCountMap | undefined,
  limit = 4
): Array<[string, number]> {
  return Object.entries(value || {})
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit);
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

function triagePriorityClass(priority: TriagePriority): string {
  switch (priority) {
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "high":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
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

function passStatusClass(status: string): string {
  switch (status) {
    case "ok":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "partial":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "error":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "noop":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function sessionStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "completed":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "archived":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function controlStateClass(state: string): string {
  switch (state) {
    case "healthy":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "actionable":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "needs_approval":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "attention_required":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "closed":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function priorityClass(priority: string): string {
  switch (priority) {
    case "high":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "low":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function approvalStatusClass(status: string): string {
  switch (status) {
    case "pending":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "approved":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "rejected":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "applied":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function issueStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "resolved":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function issueSeverityClass(severity: string): string {
  switch (severity) {
    case "high":
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "low":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function recommendationActionLabel(recommendation: OrchestratorSessionControlRecommendation): string {
  const operationType = toStringValue(recommendation.operation.type);
  const operationMode = toStringValue(recommendation.operation.mode);
  if (operationType === "session_action_batch" && operationMode === "preview") return "Preview";
  if (operationType === "inspect_session_approvals") return "Inspect approvals";
  if (operationType === "inspect_session_issues") return "Inspect issues";
  if (operationType === "session_status_update") return "Complete session";
  return "Apply";
}

function relationshipToneClass(tone: RelationshipTone): string {
  switch (tone) {
    case "run":
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
    case "outcome":
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f] hover:bg-[#f3f3f1]";
    case "approval":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690] hover:bg-[#e3f2f8]";
    case "issue":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700] hover:bg-[#fff0d9]";
    case "event":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f] hover:bg-[#e4f3e8]";
    case "agent":
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]";
  }
}

function FilterChip({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <Button
      size="sm"
      variant="outline"
      className={`h-8 rounded-full px-3 text-[11px] ${
        active
          ? "border-[#1a1a1a] bg-[#1a1a1a] text-white hover:bg-[#333]"
          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
      }`}
      onClick={onClick}
    >
      {label}
      {typeof count === "number" ? ` · ${count}` : ""}
    </Button>
  );
}

function RelationshipStrip({
  label,
  items,
}: {
  label: string;
  items: RelationshipStripItem[];
}) {
  const visibleItems = items.filter((item) => item.label);
  if (visibleItems.length === 0) return null;

  return (
    <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
        {label}
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {visibleItems.map((item) =>
          item.onClick ? (
            <Button
              key={item.key}
              size="sm"
              variant="outline"
              className={`h-7 rounded-full px-2.5 text-[11px] ${
                item.active
                  ? "border-[#1a1a1a] bg-[#1a1a1a] text-white hover:bg-[#333]"
                  : relationshipToneClass(item.tone)
              }`}
              onClick={item.onClick}
            >
              {item.label}
            </Button>
          ) : (
            <Badge
              key={item.key}
              variant="outline"
              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                item.active
                  ? "border-[#1a1a1a] bg-[#1a1a1a] text-white"
                  : relationshipToneClass(item.tone).replace(" hover:bg-[#f7f7f5]", "").replace(" hover:bg-[#f3f3f1]", "").replace(" hover:bg-[#e3f2f8]", "").replace(" hover:bg-[#fff0d9]", "").replace(" hover:bg-[#e4f3e8]", "")
              }`}
            >
              {item.label}
            </Badge>
          )
        )}
      </div>
    </div>
  );
}

function BreakdownChips({
  label,
  values,
  emptyText,
}: {
  label: string;
  values: ExecutionPlaneCountMap | undefined;
  emptyText: string;
}) {
  const items = countEntries(values);

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-[#9b9a97]">{emptyText}</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {items.map(([key, value]) => (
            <Badge
              key={`${label}-${key}`}
              variant="outline"
              className="gap-1 rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[12px] font-medium text-[#37352f]"
            >
              <span>{key}</span>
              <span className="text-[#9b9a97]">{value}</span>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryStat({
  eyebrow,
  value,
  detail,
}: {
  eyebrow: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader className="gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{eyebrow}</p>
        <CardTitle className="text-[28px] font-semibold tracking-[-0.04em] text-[#37352f]">
          {value}
        </CardTitle>
        <CardDescription className="text-[13px] text-[#6b6b6b]">{detail}</CardDescription>
      </CardHeader>
    </Card>
  );
}

function SessionMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      <p className="mt-1 text-[16px] font-semibold text-[#37352f]">{value}</p>
      <p className="mt-1 text-[12px] text-[#787774]">{detail}</p>
    </div>
  );
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
  const [pendingLineageAutoAdvance, setPendingLineageAutoAdvance] = useState<{
    filter: "attention" | "decisions";
    previousKey: string;
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
  const [historySearch, setHistorySearch] = useState("");
  const [entitySearch, setEntitySearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [busyActionKey, setBusyActionKey] = useState("");
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [hydratedAgentTimelineStorageKey, setHydratedAgentTimelineStorageKey] = useState("");
  const [hydratedLineageQueueSessionId, setHydratedLineageQueueSessionId] = useState("");
  const selectedSessionLineageEntryRef = useRef<SessionLineageEntry | null>(null);
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
      const currentLineageEntry = selectedSessionLineageEntryRef.current;
      const currentLineageFilter = sessionLineageFilterRef.current;
      let autoAdvanceFilter: "attention" | "decisions" | "" = "";
      if (options?.autoAdvanceQueue && currentLineageEntry) {
        if (currentLineageFilter === "attention" || currentLineageFilter === "decisions") {
          autoAdvanceFilter = currentLineageFilter;
        } else if (matchesSessionLineageFilter(currentLineageEntry, "attention")) {
          autoAdvanceFilter = "attention";
        } else if (matchesSessionLineageFilter(currentLineageEntry, "decisions")) {
          autoAdvanceFilter = "decisions";
        }
      }
      try {
        const message = await task();
        setNotice(message);
        if (autoAdvanceFilter && currentLineageEntry) {
          setPendingLineageAutoAdvance({
            filter: autoAdvanceFilter,
            previousKey: currentLineageEntry.key,
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
      const nextEntry = nextSessionLineageQueueEntry(entries, selectedSessionLineageEntry);
      if (!nextEntry) return;
      focusSessionLineageEntry(nextEntry, filter);
    },
    [
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      focusSessionLineageEntry,
      selectedSessionLineageEntry,
    ]
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
  }, []);
  const snoozeAgentTimelineEntry = useCallback((entry: AgentTimelineEntry, minutes = 15) => {
    const entryKey = agentTimelineEntryKey(entry);
    const snoozedUntil = Date.now() + minutes * 60 * 1000;
    setSnoozedAgentTimelineUntil((current) => ({
      ...current,
      [entryKey]: snoozedUntil,
    }));
    setLineageQueueNow(Date.now());
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
      focusSessionLineageEntry(nextEntry, pendingLineageAutoAdvance.filter);
    } else {
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

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.9fr)]">
            <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <CardHeader>
                <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                  Recent Control Passes
                </CardTitle>
                <CardDescription className="text-[13px] text-[#787774]">
                  Latest session-level FounderOS control passes, now selectable for drill-down.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {recentControlPasses.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    {controlPasses.length
                      ? "No orchestrator control passes match the current history search."
                      : "No orchestrator control passes recorded yet."}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {recentControlPasses.map((controlPass) => {
                      const finalState = toStringValue(controlPass.summary.final_state, "unknown");
                      const stoppedReason = toStringValue(controlPass.summary.stopped_reason);
                      const appliedSteps = toNumber(controlPass.summary.applied, controlPass.applied.length);
                      const errorSteps = toNumber(controlPass.summary.errors, controlPass.errors.length);
                      const selected = selectedPassId === controlPass.id;

                      return (
                        <div
                          key={controlPass.id}
                          className={`rounded-2xl border p-4 ${
                            selected
                              ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                              : "border-[#ecebe8] bg-[#fbfbf9]"
                          }`}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                                  {controlPass.id}
                                </p>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(controlPass.status)}`}
                                >
                                  {controlPass.status}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  {controlPass.profile}
                                </Badge>
                              </div>
                              <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                Session{" "}
                                <span className="font-mono text-[#37352f]">
                                  {controlPass.orchestrator_session_id}
                                </span>
                                {" · "}
                                {controlPass.actor || "unknown actor"}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-[12px] text-[#9b9a97]">
                                {formatTimestamp(controlPass.created_at)}
                              </p>
                              <Button
                                size="sm"
                                variant={selected ? "default" : "outline"}
                                className={`mt-2 h-8 rounded-lg text-[12px] ${
                                  selected
                                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                }`}
                                onClick={() => {
                                  setSelectedPassId(controlPass.id);
                                  if (controlPass.orchestrator_session_id) {
                                    setSelectedSessionId(controlPass.orchestrator_session_id);
                                  }
                                }}
                              >
                                {selected ? "Selected" : "Inspect"}
                              </Button>
                            </div>
                          </div>

                          <div className="mt-4 grid gap-3 md:grid-cols-3">
                            <SessionMetric
                              label="Outcome"
                              value={finalState}
                              detail={`${appliedSteps} applied · ${errorSteps} errors`}
                            />
                            <SessionMetric
                              label="Coverage"
                              value={`${controlPass.project_ids.length} project${controlPass.project_ids.length === 1 ? "" : "s"}`}
                              detail={controlPass.initiative_id || "No initiative mapping"}
                            />
                            <SessionMetric
                              label="Reason"
                              value={stoppedReason || controlPass.reason || "No stop reason"}
                              detail={`${controlPass.recommendation_kinds.length} recommendation kind(s)`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Selected Action Run
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Inspect the latest session execution or preview run, including action outcomes.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedRun ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a linked action run to inspect selection scope and result details.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedRun.id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedRun.status)}`}
                            >
                              {selectedRun.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedRun.run_kind}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedRun.dry_run ? "preview" : "execute"}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            {selectedRun.actor || "unknown actor"}
                            {" · "}
                            {selectedRun.mode || "auto"}
                            {selectedRun.reason ? ` · ${selectedRun.reason}` : ""}
                          </p>
                        </div>
                        <p className="text-right text-[12px] text-[#9b9a97]">
                          {formatTimestamp(selectedRun.created_at)}
                          {selectedRun.completed_at
                            ? ` · completed ${formatTimestamp(selectedRun.completed_at)}`
                            : ""}
                        </p>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Selected"
                          value={String(toNumber(selectedRun.summary.selected_count))}
                          detail={`${toNumber(selectedRun.summary.processed_count, selectedRun.results.length)} processed`}
                        />
                        <SessionMetric
                          label="Scope"
                          value={`${selectedRun.project_ids.length} project${selectedRun.project_ids.length === 1 ? "" : "s"}`}
                          detail={selectedRun.policy_profile || "Custom policy"}
                        />
                        <SessionMetric
                          label="Initiatives"
                          value={String(selectedRun.initiative_ids.length)}
                          detail={formatScopeList(selectedRun.initiative_ids, "No initiative mapping")}
                        />
                        <SessionMetric
                          label="Runtime Agents"
                          value={String(selectedRun.runtime_agent_ids.length)}
                          detail={formatScopeList(selectedRun.runtime_agent_ids, "No agent linkage")}
                        />
                      </div>

                      <BreakdownChips
                        label="Result Statuses"
                        values={(selectedRun.summary.status_counts as ExecutionPlaneCountMap | undefined) || {}}
                        emptyText="No result statuses recorded."
                      />

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Selection Scope
                        </p>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <SessionMetric
                            label="Requested Keys"
                            value={String(toStringArray(selectedRun.selection.requested_action_keys).length)}
                            detail={formatScopeList(
                              toStringArray(selectedRun.selection.requested_action_keys).slice(0, 2),
                              "No explicit action keys"
                            )}
                          />
                          <SessionMetric
                            label="Selected Keys"
                            value={String(toStringArray(selectedRun.selection.selected_action_keys).length)}
                            detail={formatScopeList(
                              toStringArray(selectedRun.selection.selected_action_keys).slice(0, 2),
                              "No selected action keys"
                            )}
                          />
                        </div>
                        {(toStringValue(selectedRun.selection.project_id) ||
                          toStringValue(selectedRun.selection.initiative_id) ||
                          toStringValue(selectedRun.selection.orchestrator) ||
                          toStringValue(selectedRun.selection.runtime_agent_id)) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {toStringValue(selectedRun.selection.project_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                project {toStringValue(selectedRun.selection.project_id)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.initiative_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                initiative {toStringValue(selectedRun.selection.initiative_id)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.orchestrator) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                orchestrator {toStringValue(selectedRun.selection.orchestrator)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.runtime_agent_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                agent {toStringValue(selectedRun.selection.runtime_agent_id)}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Action Outcomes
                        </p>
                        {selectedRun.results.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No action results recorded.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedRun.results.slice(0, 8).map((result, index) => {
                              const details = describeRunResult(result);
                              const approval = asRecord(result.approval);
                              const issue = asRecord(result.issue);
                              const commandResult = asRecord(result.command_result);
                              const selected = selectedRunResultIndex === index;
                              return (
                                <div
                                  key={`${selectedRun.id}-result-${index}`}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-[13px] font-semibold text-[#37352f]">{details.title}</p>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(result.status, "unknown"))}`}
                                      >
                                        {toStringValue(result.status, "unknown")}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          setSelectedRunResultIndex(index);
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                  </div>
                                  <p className="mt-2 text-[12px] text-[#787774]">{details.subtitle}</p>
                                  <p className="mt-2 text-[12px] text-[#6b6b6b]">{details.message}</p>
                                  {(approval || issue || commandResult) && (
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {approval && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                        >
                                          approval {toStringValue(approval.id, "created")}
                                        </Badge>
                                      )}
                                      {issue && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                        >
                                          issue {toStringValue(issue.id, "linked")}
                                        </Badge>
                                      )}
                                      {commandResult && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          command {toStringValue(commandResult.status, "ok")}
                                        </Badge>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {selectedRunResult && (
                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          {(() => {
                            const actionPayload = asRecord(selectedRunResult.action);
                            const commandResultPayload = asRecord(selectedRunResult.command_result);
                            const projectId = outcomeProjectId(selectedRunResult);
                            const projectName = outcomeProjectName(selectedRunResult);
                            const storyId = outcomeStoryId(selectedRunResult);
                            const storyTitle = outcomeStoryTitle(selectedRunResult);
                            const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
                            const commandName = toStringValue(
                              actionPayload?.command,
                              toStringValue(commandResultPayload?.command)
                            );
                            const linkedApprovalId = toStringValue(asRecord(selectedRunResult.approval)?.id);
                            const linkedIssueId = toStringValue(asRecord(selectedRunResult.issue)?.id);
                            const linkedEvent =
                              resolveSessionEventFromContext(selectedSession?.events || [], {
                                runId: selectedRun.id,
                                approvalId: linkedApprovalId,
                                issueId: linkedIssueId,
                                runtimeAgentId,
                              })?.event ?? null;
                            const workspaceHref =
                              projectId && storyId
                                ? `/projects/${projectId}?storyId=${storyId}`
                                : projectId
                                  ? `/projects/${projectId}`
                                  : "";
                            return (
                              <>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Selected Outcome
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                              {runtimeAgentId && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    openSelectedRunResultInTimeline();
                                  }}
                                >
                                  Open in agent timeline
                                </Button>
                              )}
                              {runtimeAgentId && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    focusRuntimeAgent(runtimeAgentId, true);
                                  }}
                                >
                                  Find agent
                                </Button>
                              )}
                              {toStringValue(asRecord(selectedRunResult.approval)?.id) && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    setEntitySearch(toStringValue(asRecord(selectedRunResult.approval)?.id));
                                  }}
                                >
                                  Find approval
                                </Button>
                              )}
                              {toStringValue(asRecord(selectedRunResult.issue)?.id) && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    setEntitySearch(toStringValue(asRecord(selectedRunResult.issue)?.id));
                                  }}
                                >
                                  Find issue
                                </Button>
                              )}
                              {workspaceHref && (
                                <Link
                                  href={workspaceHref}
                                  className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                                >
                                  Open workspace
                                </Link>
                              )}
                              <Badge
                                variant="outline"
                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(selectedRunResult.status, "unknown"))}`}
                              >
                                {toStringValue(selectedRunResult.status, "unknown")}
                              </Badge>
                            </div>
                          </div>

                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <SessionMetric
                              label="Action"
                              value={toStringValue(
                                asRecord(selectedRunResult.action)?.action_key,
                                toStringValue(asRecord(selectedRunResult.action)?.command, "unknown")
                              )}
                              detail={toStringValue(
                                asRecord(selectedRunResult.action)?.action_type,
                                "No action type"
                              )}
                            />
                            <SessionMetric
                              label="Mode"
                              value={toStringValue(
                                selectedRunResult.planned_mode,
                                toStringValue(selectedRun.mode, "auto")
                              )}
                              detail={toStringValue(
                                asRecord(selectedRunResult.command_result)?.status,
                                "No command result"
                              )}
                            />
                          </div>

                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            <SessionMetric
                              label="Project"
                              value={projectName || "Unknown project"}
                              detail={projectId || "No project id in payload"}
                            />
                            <SessionMetric
                              label="Story"
                              value={storyTitle || (storyId ? `Story ${storyId}` : "No story context")}
                              detail={storyId ? `story_id ${storyId}` : "Outcome is not story-scoped"}
                            />
                            <SessionMetric
                              label="Command"
                              value={commandName || "No command recorded"}
                              detail={toStringValue(
                                commandResultPayload?.status,
                                toStringValue(selectedRunResult.planned_mode, "No command status")
                              )}
                            />
                            <SessionMetric
                              label="Runtime Agent"
                              value={runtimeAgentId || "No agent linkage"}
                              detail={toStringValue(actionPayload?.role, "No execution role")}
                            />
                          </div>

                          {(projectId || storyId || runtimeAgentId) && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              {projectId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  project {projectId}
                                </Badge>
                              )}
                              {storyId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                >
                                  story {storyId}
                                </Badge>
                              )}
                              {runtimeAgentId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  agent {runtimeAgentId}
                                </Badge>
                              )}
                            </div>
                          )}

                          <RelationshipStrip
                            label="Relationship Strip"
                            items={[
                              {
                                key: `run-${selectedRun.id}`,
                                label: `run ${selectedRun.id}`,
                                tone: "run",
                                onClick: () => {
                                  setSelectedRunId(selectedRun.id);
                                  setSelectedRunResultIndex(0);
                                },
                              },
                              {
                                key: `outcome-${selectedRun.id}-${selectedRunResultIndex}`,
                                label: `outcome ${selectedRunResultIndex + 1}`,
                                tone: "outcome",
                                active: true,
                                onClick: () => {
                                  setSelectedRunId(selectedRun.id);
                                  setSelectedRunResultIndex(selectedRunResultIndex);
                                },
                              },
                              linkedApprovalId
                                ? {
                                    key: `approval-${linkedApprovalId}`,
                                    label: `approval ${linkedApprovalId}`,
                                    tone: "approval" as const,
                                    onClick: () => {
                                      syncLinkedSelection({
                                        runId: selectedRun.id,
                                        resultIndex: selectedRunResultIndex,
                                        approvalId: linkedApprovalId,
                                        issueId: linkedIssueId,
                                        runtimeAgentId,
                                      });
                                    },
                                  }
                                : null,
                              linkedIssueId
                                ? {
                                    key: `issue-${linkedIssueId}`,
                                    label: `issue ${linkedIssueId}`,
                                    tone: "issue" as const,
                                    onClick: () => {
                                      syncLinkedSelection({
                                        runId: selectedRun.id,
                                        resultIndex: selectedRunResultIndex,
                                        approvalId: linkedApprovalId,
                                        issueId: linkedIssueId,
                                        runtimeAgentId,
                                      });
                                    },
                                  }
                                : null,
                              linkedEvent
                                ? {
                                    key: `event-${sessionEventKey(linkedEvent)}`,
                                    label: `event ${toStringValue(linkedEvent.event, "event")}`,
                                    tone: "event" as const,
                                    onClick: () => {
                                      syncLinkedSelection({
                                        runId: selectedRun.id,
                                        resultIndex: selectedRunResultIndex,
                                        approvalId: linkedApprovalId,
                                        issueId: linkedIssueId,
                                        runtimeAgentId,
                                        event: linkedEvent,
                                      });
                                    },
                                  }
                                : null,
                              runtimeAgentId
                                ? {
                                    key: `agent-${runtimeAgentId}`,
                                    label: `agent ${runtimeAgentId}`,
                                    tone: "agent" as const,
                                    onClick: () => {
                                      openSelectedRunResultInTimeline();
                                    },
                                  }
                                : null,
                            ].filter(Boolean) as RelationshipStripItem[]}
                          />

                          <p className="mt-4 text-[13px] leading-relaxed text-[#6b6b6b]">
                            {toStringValue(
                              selectedRunResult.message,
                              toStringValue(
                                asRecord(selectedRunResult.command_result)?.message,
                                "No additional outcome message."
                              )
                            )}
                          </p>

                          <div className="mt-4 space-y-3">
                            <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                Action Payload
                              </p>
                              <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
                                {formatJson(asRecord(selectedRunResult.action) || selectedRunResult)}
                              </pre>
                            </div>

                            {asRecord(selectedRunResult.command_result) && (
                              <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Command Result Payload
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
                                  {formatJson(asRecord(selectedRunResult.command_result))}
                                </pre>
                              </div>
                            )}

                            {asRecord(selectedRunResult.approval) && (
                              <div className="rounded-xl border border-[#d3e5ef] bg-[#eef7fb] p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#2a6690]">
                                  Linked Approval
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#2a6690]">
                                  {formatJson(asRecord(selectedRunResult.approval))}
                                </pre>
                              </div>
                            )}

                            {asRecord(selectedRunResult.issue) && (
                              <div className="rounded-xl border border-[#f4e0c4] bg-[#fff6e8] p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
                                  Linked Issue
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#9a6700]">
                                  {formatJson(asRecord(selectedRunResult.issue))}
                                </pre>
                              </div>
                            )}
                          </div>
                              </>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Session Lineage
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Run-linked picture of recent outcomes, decisions, events, and agents across the current session.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedSession ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a session to inspect recent lineage chains.
                    </div>
                  ) : sessionLineageEntries.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      No run-linked lineage recorded for this session yet.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Outcomes"
                          value={String(sessionLineageEntries.length)}
                          detail={`${linkedRuns.length} run${linkedRuns.length === 1 ? "" : "s"} linked`}
                        />
                        <SessionMetric
                          label="Decisions"
                          value={String(sessionLineageDecisionCount)}
                          detail={`${linkedApprovals.length} approvals · ${linkedIssues.length} issues`}
                        />
                        <SessionMetric
                          label="Events"
                          value={String(sessionLineageEventCount)}
                          detail={`${selectedSession.events.length} session event${selectedSession.events.length === 1 ? "" : "s"}`}
                        />
                        <SessionMetric
                          label="Agents"
                          value={String(sessionLineageAgentCount)}
                          detail={`${linkedAgentIds.length} linked agent${linkedAgentIds.length === 1 ? "" : "s"} in session`}
                        />
                      </div>

                      <BreakdownChips
                        label="Lineage Statuses"
                        values={sessionLineageStatusCounts}
                        emptyText="No lineage statuses recorded."
                      />

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Recent Chains
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredSessionLineageEntries.length}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <FilterChip
                            label="All"
                            active={sessionLineageFilter === "all"}
                            count={sessionLineageEntries.length}
                            onClick={() => {
                              setSessionLineageFilter("all");
                            }}
                          />
                          <FilterChip
                            label="Attention"
                            active={sessionLineageFilter === "attention"}
                            count={sessionLineageAttentionCount}
                            onClick={() => {
                              setSessionLineageFilter("attention");
                            }}
                          />
                          <FilterChip
                            label="Decisions"
                            active={sessionLineageFilter === "decisions"}
                            count={sessionLineageDecisionCount}
                            onClick={() => {
                              setSessionLineageFilter("decisions");
                            }}
                          />
                          <FilterChip
                            label="Agent-linked"
                            active={sessionLineageFilter === "agent-linked"}
                            count={sessionLineageAgentLinkedCount}
                            onClick={() => {
                              setSessionLineageFilter("agent-linked");
                            }}
                          />
                        </div>
                        <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                Operator State
                              </p>
                              <p className="mt-1 text-[12px] text-[#787774]">
                                {persistedDismissedLineageQueueCount} dismissed ·{" "}
                                {persistedSnoozedLineageQueueCount} snoozed persisted for this session
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {(["critical", "high", "normal"] as TriagePriority[]).map((priority) =>
                                  sessionLineagePriorityCounts[priority] ? (
                                    <Badge
                                      key={`session-lineage-priority-${priority}`}
                                      variant="outline"
                                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(priority)}`}
                                    >
                                      {priority} {sessionLineagePriorityCounts[priority]}
                                    </Badge>
                                  ) : null
                                )}
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                onClick={() => {
                                  void exportSessionLineageQueuePreferences();
                                }}
                                disabled={!hasPersistedLineageQueuePreferences}
                              >
                                Copy queue state
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                onClick={() => {
                                  resetSessionLineageQueuePreferences();
                                }}
                                disabled={!hasPersistedLineageQueuePreferences}
                              >
                                Reset queue state
                              </Button>
                            </div>
                          </div>
                        </div>
                        <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Active Focus
                            </p>
                            {selectedSessionLineageEntry ? (
                              <div className="flex flex-wrap items-center gap-2">
                                {selectedSessionLineagePriority ? (
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(selectedSessionLineagePriority)}`}
                                  >
                                    {selectedSessionLineagePriority}
                                  </Badge>
                                ) : null}
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  {formatTimestamp(selectedSessionLineageEntry.timestamp)}
                                </Badge>
                              </div>
                            ) : null}
                          </div>
                          {!selectedSessionLineageEntry ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">
                              Select a lineage chain to inspect its linked context.
                            </p>
                          ) : (
                            <>
                              <div className="mt-3 flex flex-wrap items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  run {selectedSessionLineageEntry.runId}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  outcome {selectedSessionLineageEntry.resultIndex + 1}
                                </Badge>
                                {selectedSessionLineageTraits.map((trait) => (
                                  <Badge
                                    key={trait.key}
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${trait.className}`}
                                  >
                                    {trait.label}
                                  </Badge>
                                ))}
                              </div>
                              <p className="mt-3 text-[12px] text-[#6b6b6b]">
                                {selectedSessionLineageEntry.title}
                                {selectedSessionLineageEntry.subtitle
                                  ? ` · ${selectedSessionLineageEntry.subtitle}`
                                  : ""}
                              </p>
                            </>
                          )}
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                if (nextBestSessionLineageEntry) {
                                  inspectSessionLineageEntry(nextBestSessionLineageEntry);
                                }
                              }}
                              disabled={!nextBestSessionLineageEntry}
                            >
                              Inspect next best
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                advanceSessionLineageQueue("attention");
                              }}
                              disabled={!attentionSessionLineageEntries.length}
                            >
                              Inspect next attention
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                advanceSessionLineageQueue("decisions");
                              }}
                              disabled={!decisionSessionLineageEntries.length}
                            >
                              Inspect next decision
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                if (latestAgentLinkedLineageEntry) {
                                  focusSessionLineageEntry(latestAgentLinkedLineageEntry, "agent-linked");
                                }
                              }}
                              disabled={!latestAgentLinkedLineageEntry}
                            >
                              Latest agent-linked
                            </Button>
                            {selectedSessionLineageEntry ? (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                onClick={() => {
                                  inspectSessionLineageEntry(selectedSessionLineageEntry);
                                }}
                              >
                                Re-open selection
                              </Button>
                            ) : null}
                          </div>
                        </div>
                        <div className="grid gap-3 xl:grid-cols-2">
                          <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Attention Queue
                                </p>
                                <p className="mt-1 text-[12px] text-[#787774]">
                                  {attentionQueuePosition >= 0
                                    ? `Selected ${attentionQueuePosition + 1} of ${attentionSessionLineageEntries.length}`
                                    : `${attentionSessionLineageEntries.length} queued`}
                                  {hiddenAttentionQueueCount
                                    ? ` · ${hiddenAttentionQueueCount} hidden`
                                    : ""}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  {sessionLineageAttentionCount}
                                </Badge>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    advanceSessionLineageQueue("attention");
                                  }}
                                  disabled={!attentionSessionLineageEntries.length}
                                >
                                  Inspect next
                                </Button>
                                {hiddenAttentionQueueCount ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      restoreSessionLineageQueue("attention");
                                    }}
                                  >
                                    Restore hidden
                                  </Button>
                                ) : null}
                              </div>
                            </div>
                            {!attentionSessionLineageQueue.length ? (
                              <p className="mt-3 text-[13px] text-[#9b9a97]">
                                No attention-linked chains in this session.
                              </p>
                            ) : (
                              <div className="mt-3 space-y-3">
                                {attentionSessionLineageQueue.map((entry) => {
                                  const selected = selectedSessionLineageEntry?.key === entry.key;
                                  const queueTraits = sessionLineageTraits(entry).filter(
                                    (trait) => trait.key !== "attention"
                                  );
                                  return (
                                    <div
                                      key={`attention-queue-${entry.key}`}
                                      className={`rounded-xl border p-3 ${
                                        selected
                                          ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                          : "border-[#ecebe8] bg-[#fbfbf9]"
                                      }`}
                                    >
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                          <p className="text-[13px] font-semibold text-[#37352f]">
                                            {entry.title}
                                          </p>
                                          <p className="mt-2 text-[12px] text-[#787774]">
                                            run {entry.runId} · outcome {entry.resultIndex + 1}
                                          </p>
                                        </div>
                                        <p className="text-[11px] text-[#9b9a97]">
                                          {formatTimestamp(entry.timestamp)}
                                        </p>
                                      </div>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(sessionLineagePriority(entry))}`}
                                        >
                                          {sessionLineagePriority(entry)}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(entry.status)}`}
                                        >
                                          {entry.status}
                                        </Badge>
                                        {queueTraits.slice(0, 2).map((trait) => (
                                          <Badge
                                            key={`${entry.key}-${trait.key}`}
                                            variant="outline"
                                            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${trait.className}`}
                                          >
                                            {trait.label}
                                          </Badge>
                                        ))}
                                      </div>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        <Button
                                          size="sm"
                                          variant={
                                            selected && sessionLineageFilter === "attention"
                                              ? "default"
                                              : "outline"
                                          }
                                          className={`h-7 rounded-lg px-2 text-[11px] ${
                                            selected && sessionLineageFilter === "attention"
                                              ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                              : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                          }`}
                                          onClick={() => {
                                            focusSessionLineageEntry(entry, "attention");
                                          }}
                                        >
                                          {selected && sessionLineageFilter === "attention"
                                            ? "Selected"
                                            : "Inspect"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          onClick={() => {
                                            snoozeSessionLineageQueueEntry("attention", entry);
                                          }}
                                        >
                                          Snooze 15m
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          onClick={() => {
                                            dismissSessionLineageQueueEntry("attention", entry);
                                          }}
                                        >
                                          Dismiss
                                        </Button>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                          <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Decision Queue
                                </p>
                                <p className="mt-1 text-[12px] text-[#787774]">
                                  {decisionQueuePosition >= 0
                                    ? `Selected ${decisionQueuePosition + 1} of ${decisionSessionLineageEntries.length}`
                                    : `${decisionSessionLineageEntries.length} queued`}
                                  {hiddenDecisionQueueCount
                                    ? ` · ${hiddenDecisionQueueCount} hidden`
                                    : ""}
                                </p>
                              </div>
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  {sessionLineageDecisionCount}
                                </Badge>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    advanceSessionLineageQueue("decisions");
                                  }}
                                  disabled={!decisionSessionLineageEntries.length}
                                >
                                  Inspect next
                                </Button>
                                {hiddenDecisionQueueCount ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      restoreSessionLineageQueue("decisions");
                                    }}
                                  >
                                    Restore hidden
                                  </Button>
                                ) : null}
                              </div>
                            </div>
                            {!decisionSessionLineageQueue.length ? (
                              <p className="mt-3 text-[13px] text-[#9b9a97]">
                                No decision-linked chains in this session.
                              </p>
                            ) : (
                              <div className="mt-3 space-y-3">
                                {decisionSessionLineageQueue.map((entry) => {
                                  const selected = selectedSessionLineageEntry?.key === entry.key;
                                  const queueTraits = sessionLineageTraits(entry).filter(
                                    (trait) => trait.key !== "decision"
                                  );
                                  return (
                                    <div
                                      key={`decision-queue-${entry.key}`}
                                      className={`rounded-xl border p-3 ${
                                        selected
                                          ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                          : "border-[#ecebe8] bg-[#fbfbf9]"
                                      }`}
                                    >
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                          <p className="text-[13px] font-semibold text-[#37352f]">
                                            {entry.title}
                                          </p>
                                          <p className="mt-2 text-[12px] text-[#787774]">
                                            run {entry.runId} · outcome {entry.resultIndex + 1}
                                          </p>
                                        </div>
                                        <p className="text-[11px] text-[#9b9a97]">
                                          {formatTimestamp(entry.timestamp)}
                                        </p>
                                      </div>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(sessionLineagePriority(entry))}`}
                                        >
                                          {sessionLineagePriority(entry)}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(entry.status)}`}
                                        >
                                          {entry.status}
                                        </Badge>
                                        {queueTraits.slice(0, 2).map((trait) => (
                                          <Badge
                                            key={`${entry.key}-${trait.key}`}
                                            variant="outline"
                                            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${trait.className}`}
                                          >
                                            {trait.label}
                                          </Badge>
                                        ))}
                                      </div>
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        <Button
                                          size="sm"
                                          variant={
                                            selected && sessionLineageFilter === "decisions"
                                              ? "default"
                                              : "outline"
                                          }
                                          className={`h-7 rounded-lg px-2 text-[11px] ${
                                            selected && sessionLineageFilter === "decisions"
                                              ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                              : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                          }`}
                                          onClick={() => {
                                            focusSessionLineageEntry(entry, "decisions");
                                          }}
                                        >
                                          {selected && sessionLineageFilter === "decisions"
                                            ? "Selected"
                                            : "Inspect"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          onClick={() => {
                                            snoozeSessionLineageQueueEntry("decisions", entry);
                                          }}
                                        >
                                          Snooze 15m
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          onClick={() => {
                                            dismissSessionLineageQueueEntry("decisions", entry);
                                          }}
                                        >
                                          Dismiss
                                        </Button>
                                      </div>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        </div>
                        {!filteredSessionLineageEntries.length ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            No lineage chains match the current focus mode.
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {visibleSessionLineageEntries.map((entry) => {
                              const selected =
                                selectedSessionLineageEntry?.key === entry.key;
                              const workspaceHref =
                                entry.projectId && entry.storyId
                                  ? `/projects/${entry.projectId}?storyId=${entry.storyId}`
                                  : entry.projectId
                                    ? `/projects/${entry.projectId}`
                                    : "";
                              return (
                                <div
                                  key={entry.key}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <p className="text-[13px] font-semibold text-[#37352f]">
                                        {entry.title}
                                      </p>
                                      <p className="mt-2 text-[12px] text-[#787774]">
                                        {entry.subtitle || "No outcome subtype"}
                                      </p>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(sessionLineagePriority(entry))}`}
                                      >
                                        {sessionLineagePriority(entry)}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(entry.status)}`}
                                      >
                                        {entry.status}
                                      </Badge>
                                      <p className="text-[11px] text-[#9b9a97]">
                                        {formatTimestamp(entry.timestamp)}
                                      </p>
                                    </div>
                                  </div>

                                  <RelationshipStrip
                                    label="Lineage Chain"
                                    items={[
                                      {
                                        key: `lineage-run-${entry.runId}`,
                                        label: `run ${entry.runId}`,
                                        tone: "run",
                                        onClick: () => {
                                          setSelectedRunId(entry.runId);
                                          setSelectedRunResultIndex(0);
                                        },
                                      },
                                      {
                                        key: `lineage-outcome-${entry.key}`,
                                        label: `outcome ${entry.resultIndex + 1}`,
                                        tone: "outcome",
                                        active: selected,
                                        onClick: () => inspectSessionLineageEntry(entry),
                                      },
                                      entry.approvalId
                                        ? {
                                            key: `lineage-approval-${entry.approvalId}`,
                                            label: `approval ${entry.approvalId}`,
                                            tone: "approval" as const,
                                            onClick: () => inspectSessionLineageEntry(entry),
                                          }
                                        : null,
                                      entry.issueId
                                        ? {
                                            key: `lineage-issue-${entry.issueId}`,
                                            label: `issue ${entry.issueId}`,
                                            tone: "issue" as const,
                                            onClick: () => inspectSessionLineageEntry(entry),
                                          }
                                        : null,
                                      entry.eventKey
                                        ? {
                                            key: `lineage-event-${entry.eventKey}`,
                                            label: `event ${entry.eventName || "event"}`,
                                            tone: "event" as const,
                                            onClick: () => inspectSessionLineageEntry(entry),
                                          }
                                        : null,
                                      entry.runtimeAgentId
                                        ? {
                                            key: `lineage-agent-${entry.runtimeAgentId}`,
                                            label: `agent ${entry.runtimeAgentId}`,
                                            tone: "agent" as const,
                                            onClick: () => inspectSessionLineageEntry(entry),
                                          }
                                        : null,
                                    ].filter(Boolean) as RelationshipStripItem[]}
                                  />

                                  <p className="mt-3 text-[12px] text-[#6b6b6b]">
                                    {entry.message}
                                  </p>

                                  <div className="mt-3 flex flex-wrap gap-2">
                                    <Button
                                      size="sm"
                                      variant={selected ? "default" : "outline"}
                                      className={`h-7 rounded-lg px-2 text-[11px] ${
                                        selected
                                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                      }`}
                                      onClick={() => {
                                        inspectSessionLineageEntry(entry);
                                      }}
                                    >
                                      {selected ? "Selected" : "Inspect chain"}
                                    </Button>
                                    {workspaceHref && (
                                      <Link
                                        href={workspaceHref}
                                        className="inline-flex h-7 items-center rounded-lg border border-[#e5e5e3] bg-white px-2 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                                      >
                                        Open workspace
                                      </Link>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Runtime Agent
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Agent-centric control view for the currently selected runtime agent.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedAgentId ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a linked runtime agent to inspect its current state and history.
                    </div>
                  ) : agentLoading || !selectedAgent ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Loading runtime agent detail...
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedAgent.runtime_agent_id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedAgent.status)}`}
                            >
                              {selectedAgent.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedAgent.attention.state)}`}
                            >
                              {selectedAgent.attention.state}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedAgent.role}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            {selectedAgent.project_name || selectedAgent.project_id}
                            {" · "}
                            {selectedAgent.story_title || `Story ${selectedAgent.story_id || "unknown"}`}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={
                              selectedAgent.story_id
                                ? `/projects/${selectedAgent.project_id}?storyId=${selectedAgent.story_id}`
                                : `/projects/${selectedAgent.project_id}`
                            }
                            className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                          >
                            Open workspace
                          </Link>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                            onClick={() => {
                              focusRuntimeAgent(selectedAgent.runtime_agent_id, true);
                            }}
                          >
                            Filter session
                          </Button>
                        </div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Open Issues"
                          value={String(selectedAgent.history.open_issue_count)}
                          detail={`${selectedAgent.history.issue_count} total issues`}
                        />
                        <SessionMetric
                          label="Pending Approvals"
                          value={String(selectedAgent.history.pending_approval_count)}
                          detail={`${selectedAgent.history.approval_count} total approvals`}
                        />
                        <SessionMetric
                          label="Events"
                          value={String(selectedAgent.history.event_count)}
                          detail={formatTimestamp(selectedAgent.history.last_event_at)}
                        />
                        <SessionMetric
                          label="Budget"
                          value={
                            selectedAgent.budget.tracked
                              ? `${toNumber(selectedAgent.budget.remaining, 0)} left`
                              : "Untracked"
                          }
                          detail={
                            selectedAgent.budget.tracked
                              ? `${selectedAgent.budget.used ?? 0}/${selectedAgent.budget.limit ?? 0} ${selectedAgent.budget.metric || ""}`.trim()
                              : "No tracked budget metric"
                          }
                        />
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Attention
                        </p>
                        <p className="mt-3 text-[13px] leading-relaxed text-[#6b6b6b]">
                          {selectedAgent.attention.recommended_action}
                        </p>
                        {selectedAgent.attention.reasons.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedAgent.attention.reasons.map((reason) => (
                              <Badge
                                key={`${selectedAgent.runtime_agent_id}-${reason}`}
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                {reason}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Agent Recommendations
                        </p>
                        {selectedAgent.recommendations.length === 0 && selectedAgent.suggested_commands.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No current agent recommendations.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedAgent.recommendations.slice(0, 3).map((recommendation, index) => (
                              <div
                                key={`${selectedAgent.runtime_agent_id}-rec-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(recommendation.title, toStringValue(recommendation.kind, "recommendation"))}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(recommendation.priority, "medium"))}`}
                                  >
                                    {toStringValue(recommendation.priority, "medium")}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                  {toStringValue(recommendation.reason, "No reason provided")}
                                </p>
                              </div>
                            ))}
                            {selectedAgent.suggested_commands.slice(0, 2).map((command, index) => (
                              <div
                                key={`${selectedAgent.runtime_agent_id}-cmd-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(command.title, toStringValue(command.command, "command"))}
                                  </p>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <Badge
                                      variant="outline"
                                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(command.priority, "medium"))}`}
                                    >
                                      {toStringValue(command.priority, "medium")}
                                    </Badge>
                                    {Boolean(command.approval_required) && (
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                      >
                                        approval required
                                      </Badge>
                                    )}
                                  </div>
                                </div>
                                <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                  {toStringValue(command.reason, "No reason provided")}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2">
                                  {!Boolean(command.approval_required) && (
                                    <Button
                                      size="sm"
                                      className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                      disabled={Boolean(busyActionKey)}
                                      onClick={() => {
                                        void runAgentSuggestedCommand(command, "execute_now");
                                      }}
                                    >
                                      {busyActionKey === `agent-command:${selectedAgent.runtime_agent_id}:${toStringValue(command.command)}:execute_now`
                                        ? "Executing..."
                                        : "Execute"}
                                    </Button>
                                  )}
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    disabled={Boolean(busyActionKey)}
                                    onClick={() => {
                                      void runAgentSuggestedCommand(command, "request_approval");
                                    }}
                                  >
                                    {busyActionKey === `agent-command:${selectedAgent.runtime_agent_id}:${toStringValue(command.command)}:request_approval`
                                      ? "Requesting..."
                                      : "Request approval"}
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="grid gap-4 lg:grid-cols-2">
                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Agent Action Runs
                            </p>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {agentScopedRuns.length} run{agentScopedRuns.length === 1 ? "" : "s"}
                            </Badge>
                          </div>
                          <div className="mt-3 space-y-3">
                            <Input
                              value={agentActivitySearch}
                              onChange={(event) => setAgentActivitySearch(event.target.value)}
                              placeholder="Search agent runs, outcomes, approvals, issues..."
                              className="h-9 rounded-xl border-[#e5e5e3] bg-white text-[13px] text-[#37352f] placeholder:text-[#9b9a97]"
                            />
                            <div className="flex flex-wrap gap-2">
                              {[
                                { value: "all", label: "All" },
                                { value: "execute", label: "Execute" },
                                { value: "preview", label: "Preview" },
                                { value: "attention", label: "Attention" },
                              ].map((option) => {
                                const selected = agentActivityFilter === option.value;
                                return (
                                  <Button
                                    key={`agent-activity-filter-${option.value}`}
                                    size="sm"
                                    variant={selected ? "default" : "outline"}
                                    className={`h-7 rounded-full px-3 text-[11px] ${
                                      selected
                                        ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                        : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                    }`}
                                    onClick={() => {
                                      setAgentActivityFilter(option.value);
                                    }}
                                  >
                                    {option.label}
                                  </Button>
                                );
                              })}
                            </div>
                          </div>
                          {filteredAgentScopedRuns.length === 0 ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">
                              No agent runs match the current filters.
                            </p>
                          ) : (
                            <div className="mt-3 space-y-3">
                              {filteredAgentScopedRuns.slice(0, 4).map((run) => {
                                const selected = selectedRunId === run.id;
                                return (
                                  <div
                                    key={`${selectedAgent.runtime_agent_id}-run-${run.id}`}
                                    className={`rounded-xl border p-3 ${
                                      selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                                    }`}
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <p className="font-mono text-[11px] text-[#37352f]">{run.id}</p>
                                      <div className="flex flex-wrap items-center gap-2">
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(run.status)}`}
                                        >
                                          {run.status}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {run.dry_run ? "preview" : "execute"}
                                        </Badge>
                                      </div>
                                    </div>
                                    <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                      {run.actor || "unknown actor"}
                                      {" · "}
                                      {formatTimestamp(run.created_at)}
                                    </p>
                                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                                      <SessionMetric
                                        label="Outcomes"
                                        value={String(run.results.length)}
                                        detail={`${toNumber(run.summary.processed_count, run.results.length)} processed`}
                                      />
                                      <SessionMetric
                                        label="Policy"
                                        value={run.policy_profile || "Custom"}
                                        detail={run.mode || "auto"}
                                      />
                                    </div>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          setSelectedRunId(run.id);
                                          setSelectedRunResultIndex(0);
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect run"}
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>

                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Recent Outcomes
                            </p>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {agentScopedOutcomes.length} outcome{agentScopedOutcomes.length === 1 ? "" : "s"}
                            </Badge>
                          </div>
                          {filteredAgentScopedOutcomes.length === 0 ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">
                              No agent outcomes match the current filters.
                            </p>
                          ) : (
                            <div className="mt-3 space-y-3">
                              {filteredAgentScopedOutcomes.slice(0, 4).map((entry) => {
                                const details = describeRunResult(entry.result);
                                const selected =
                                  selectedRunId === entry.run.id && selectedRunResultIndex === entry.resultIndex;
                                const projectId = outcomeProjectId(entry.result);
                                const storyId = outcomeStoryId(entry.result);
                                const linkedApprovalId = toStringValue(asRecord(entry.result.approval)?.id);
                                const linkedIssueId = toStringValue(asRecord(entry.result.issue)?.id);
                                return (
                                  <div
                                    key={`${entry.run.id}-result-${entry.resultIndex}`}
                                    className={`rounded-xl border p-3 ${
                                      selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                                    }`}
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <p className="text-[13px] font-semibold text-[#37352f]">{details.title}</p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(entry.result.status, "unknown"))}`}
                                      >
                                        {toStringValue(entry.result.status, "unknown")}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[12px] text-[#787774]">
                                      {details.subtitle || "No outcome subtype"}
                                      {" · "}
                                      {formatTimestamp(entry.timestamp)}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#6b6b6b]">{details.message}</p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {projectId && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          project {projectId}
                                        </Badge>
                                      )}
                                      {storyId && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                        >
                                          story {storyId}
                                        </Badge>
                                      )}
                                      {linkedApprovalId && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                        >
                                          approval {linkedApprovalId}
                                        </Badge>
                                      )}
                                      {linkedIssueId && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                        >
                                          issue {linkedIssueId}
                                        </Badge>
                                      )}
                                    </div>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          setSelectedRunId(entry.run.id);
                                          setSelectedRunResultIndex(entry.resultIndex);
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect outcome"}
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                        onClick={() => {
                                          setEntitySearch(entry.run.id);
                                          setSelectedRunId(entry.run.id);
                                          setSelectedRunResultIndex(entry.resultIndex);
                                        }}
                                      >
                                        Find in session
                                      </Button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Agent Timeline
                            </p>
                            <p className="mt-1 text-[13px] text-[#787774]">
                              Unified approvals, issues, and runtime events for this agent. Detailed history lives here.
                            </p>
                          </div>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {activeAgentTimelineEntries.length} active
                            {hiddenAgentTimelineEntryCount ? ` · ${hiddenAgentTimelineEntryCount} hidden` : ""}
                          </Badge>
                        </div>

                        <div className="mt-3 space-y-3">
                          <Input
                            value={agentTimelineSearch}
                            onChange={(event) => setAgentTimelineSearch(event.target.value)}
                            placeholder="Search approvals, issues, and agent events..."
                            className="h-9 rounded-xl border-[#e5e5e3] bg-white text-[13px] text-[#37352f] placeholder:text-[#9b9a97]"
                          />
                          <div className="flex flex-wrap gap-2">
                            {[
                              { value: "all", label: "All" },
                              { value: "approvals", label: "Approvals" },
                              { value: "issues", label: "Issues" },
                              { value: "events", label: "Events" },
                              { value: "attention", label: "Attention" },
                            ].map((option) => {
                              const selected = agentTimelineFilter === option.value;
                              return (
                                <Button
                                  key={`agent-timeline-filter-${option.value}`}
                                  size="sm"
                                  variant={selected ? "default" : "outline"}
                                  className={`h-7 rounded-full px-3 text-[11px] ${
                                    selected
                                      ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                      : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                  }`}
                                  onClick={() => {
                                    setAgentTimelineFilter(option.value);
                                  }}
                                >
                                  {option.label}
                                </Button>
                              );
                            })}
                          </div>
                          <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Operator State
                                </p>
                                <p className="mt-1 text-[12px] text-[#787774]">
                                  {persistedDismissedAgentTimelineCount} dismissed ·{" "}
                                  {persistedSnoozedAgentTimelineCount} snoozed persisted for this agent
                                </p>
                                <div className="mt-2 flex flex-wrap gap-2">
                                  {(["critical", "high", "normal"] as TriagePriority[]).map((priority) =>
                                    agentTimelinePriorityCounts[priority] ? (
                                      <Badge
                                        key={`agent-timeline-priority-${priority}`}
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(priority)}`}
                                      >
                                        {priority} {agentTimelinePriorityCounts[priority]}
                                      </Badge>
                                    ) : null
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    if (nextBestAgentTimelineEntry) {
                                      inspectAgentTimelineEntry(nextBestAgentTimelineEntry);
                                    }
                                  }}
                                  disabled={!nextBestAgentTimelineEntry}
                                >
                                  Inspect next best
                                </Button>
                                {hiddenAgentTimelineEntryCount ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      restoreAgentTimelineHidden();
                                    }}
                                  >
                                    Restore hidden
                                  </Button>
                                ) : null}
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    void exportAgentTimelinePreferences();
                                  }}
                                  disabled={!hasPersistedAgentTimelinePreferences}
                                >
                                  Copy timeline state
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    resetAgentTimelinePreferences();
                                  }}
                                  disabled={!hasPersistedAgentTimelinePreferences}
                                >
                                  Reset timeline state
                                </Button>
                              </div>
                            </div>
                          </div>
                          <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Priority Queue
                                </p>
                                <p className="mt-1 text-[12px] text-[#787774]">
                                  Next-best triage for the current agent timeline slice.
                                </p>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#f0d0c9] bg-[#fff0ed] px-2 text-[11px] text-[#93370d] hover:bg-[#ffe5df]"
                                  onClick={() => {
                                    if (nextCriticalAgentTimelineEntry) {
                                      inspectAgentTimelineEntry(nextCriticalAgentTimelineEntry);
                                    }
                                  }}
                                  disabled={!nextCriticalAgentTimelineEntry}
                                >
                                  Inspect next critical
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-lg border-[#f4e0c4] bg-[#fff6e8] px-2 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                  onClick={() => {
                                    if (nextHighAgentTimelineEntry) {
                                      inspectAgentTimelineEntry(nextHighAgentTimelineEntry);
                                    }
                                  }}
                                  disabled={!nextHighAgentTimelineEntry}
                                >
                                  Inspect next high
                                </Button>
                              </div>
                            </div>
                            <div className="mt-3 grid gap-3 xl:grid-cols-2">
                              {[
                                {
                                  key: "critical",
                                  label: "Critical Queue",
                                  entries: criticalAgentTimelineQueue,
                                  total: criticalAgentTimelineEntries.length,
                                  position: criticalAgentTimelinePosition,
                                  buttonLabel: "Inspect next critical",
                                  nextEntry: nextCriticalAgentTimelineEntry,
                                  buttonClassName:
                                    "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d] hover:bg-[#ffe5df]",
                                },
                                {
                                  key: "high",
                                  label: "High Queue",
                                  entries: highAgentTimelineQueue,
                                  total: highAgentTimelineEntries.length,
                                  position: highAgentTimelinePosition,
                                  buttonLabel: "Inspect next high",
                                  nextEntry: nextHighAgentTimelineEntry,
                                  buttonClassName:
                                    "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700] hover:bg-[#fff0d9]",
                                },
                              ].map((queue) => (
                                <div
                                  key={`agent-priority-queue-${queue.key}`}
                                  className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div>
                                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                        {queue.label}
                                      </p>
                                      <p className="mt-1 text-[12px] text-[#787774]">
                                        {queue.position >= 0
                                          ? `Selected ${queue.position + 1} of ${queue.total}`
                                          : `${queue.total} queued`}
                                      </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(queue.key as TriagePriority)}`}
                                      >
                                        {queue.total}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className={`h-7 rounded-lg px-2 text-[11px] ${queue.buttonClassName}`}
                                        onClick={() => {
                                          if (queue.nextEntry) {
                                            inspectAgentTimelineEntry(queue.nextEntry);
                                          }
                                        }}
                                        disabled={!queue.nextEntry}
                                      >
                                        {queue.buttonLabel}
                                      </Button>
                                    </div>
                                  </div>
                                  {!queue.entries.length ? (
                                    <p className="mt-3 text-[12px] text-[#9b9a97]">
                                      No {queue.key} entries in the current slice.
                                    </p>
                                  ) : (
                                    <div className="mt-3 space-y-2">
                                      {queue.entries.map((entry) => {
                                        const selected =
                                          selectedAgentTimelineEntry &&
                                          agentTimelineEntryKey(selectedAgentTimelineEntry) ===
                                            agentTimelineEntryKey(entry);
                                        return (
                                          <div
                                            key={`agent-priority-${queue.key}-${agentTimelineEntryKey(entry)}`}
                                            className={`rounded-lg border p-2.5 ${
                                              selected
                                                ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                                : "border-[#ecebe8] bg-white"
                                            }`}
                                          >
                                            <div className="flex flex-wrap items-start justify-between gap-2">
                                              <div>
                                                <p className="text-[12px] font-semibold text-[#37352f]">
                                                  {entry.title}
                                                </p>
                                                <p className="mt-1 text-[11px] text-[#787774]">
                                                  {entry.kind} · {entry.subtitle || "No scope metadata"}
                                                </p>
                                              </div>
                                              <p className="text-[11px] text-[#9b9a97]">
                                                {formatTimestamp(entry.timestamp)}
                                              </p>
                                            </div>
                                            <div className="mt-2 flex flex-wrap items-center gap-2">
                                              <Badge
                                                variant="outline"
                                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
                                                  entry.kind === "approval"
                                                    ? approvalStatusClass(entry.status)
                                                    : entry.kind === "issue"
                                                      ? passStatusClass(entry.status === "open" ? "partial" : "ok")
                                                      : passStatusClass(entry.status)
                                                }`}
                                              >
                                                {entry.status}
                                              </Badge>
                                              <Button
                                                size="sm"
                                                variant={selected ? "default" : "outline"}
                                                className={`h-7 rounded-lg px-2 text-[11px] ${
                                                  selected
                                                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                                }`}
                                                onClick={() => {
                                                  inspectAgentTimelineEntry(entry);
                                                }}
                                              >
                                                {selected ? "Selected" : "Inspect"}
                                              </Button>
                                            </div>
                                          </div>
                                        );
                                      })}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>

                        {filteredAgentTimelineEntries.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            No timeline entries match the current filters.
                          </p>
                        ) : (
                          <div className="mt-4 grid gap-4 lg:grid-cols-2">
                            <div className="space-y-3">
                            {visibleAgentTimelineEntries.map((entry) => {
                              const selected =
                                selectedAgentTimelineEntry &&
                                agentTimelineEntryKey(selectedAgentTimelineEntry) ===
                                  agentTimelineEntryKey(entry);
                              const eventApprovalId = toStringValue(entry.event?.approval_id);
                              const eventIssueId = toStringValue(entry.event?.issue_id);
                              const eventToken =
                                toStringValue(entry.event?.event) ||
                                toStringValue(entry.event?.message) ||
                                entry.id;

                              return (
                                <div
                                  key={`${selectedAgent.runtime_agent_id}-timeline-${entry.kind}-${entry.id}`}
                                  id={agentTimelineRowDomId(
                                    selectedAgent.runtime_agent_id,
                                    agentTimelineEntryKey(entry)
                                  )}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                                      >
                                        {entry.kind}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(agentTimelinePriority(entry))}`}
                                      >
                                        {agentTimelinePriority(entry)}
                                      </Badge>
                                      <p className="text-[13px] font-semibold text-[#37352f]">
                                        {entry.title}
                                      </p>
                                    </div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
                                          entry.kind === "approval"
                                            ? approvalStatusClass(entry.status)
                                            : entry.kind === "issue"
                                              ? passStatusClass(entry.status === "open" ? "partial" : "ok")
                                              : passStatusClass(entry.status)
                                        }`}
                                      >
                                        {entry.status}
                                      </Badge>
                                      <p className="text-[11px] text-[#9b9a97]">{formatTimestamp(entry.timestamp)}</p>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          inspectAgentTimelineEntry(entry);
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                  </div>

                                  <p className="mt-2 text-[12px] text-[#787774]">{entry.subtitle}</p>
                                  <p className="mt-2 text-[12px] text-[#6b6b6b]">{entry.message}</p>

                                  <div className="mt-3 flex flex-wrap gap-2">
                                    {entry.approval?.status === "pending" && (
                                      <>
                                        <Button
                                          size="sm"
                                          className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void approveApproval(entry.approval!);
                                          }}
                                        >
                                          {busyActionKey === `approval-approve:${entry.approval.id}` ? "Approving..." : "Approve"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void rejectApproval(entry.approval!);
                                          }}
                                        >
                                          {busyActionKey === `approval-reject:${entry.approval.id}` ? "Rejecting..." : "Reject"}
                                        </Button>
                                      </>
                                    )}
                                    {entry.approval?.status === "approved" && (
                                      <Button
                                        size="sm"
                                        className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void applyApproval(entry.approval!);
                                        }}
                                      >
                                        {busyActionKey === `approval-apply:${entry.approval.id}` ? "Applying..." : "Apply"}
                                      </Button>
                                    )}
                                    {entry.issue?.status === "open" && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void resolveIssue(entry.issue!);
                                        }}
                                      >
                                        {busyActionKey === `issue-resolve:${entry.issue.id}` ? "Resolving..." : "Resolve"}
                                      </Button>
                                    )}
                                    {(entry.approval?.id || entry.issue?.id) && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                        onClick={() => {
                                          setEntitySearch(entry.approval?.id || entry.issue?.id || "");
                                        }}
                                      >
                                        Find in session
                                      </Button>
                                    )}
                                    {eventApprovalId && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                        onClick={() => {
                                          setEntitySearch(eventApprovalId);
                                        }}
                                      >
                                        Find approval
                                      </Button>
                                    )}
                                    {eventIssueId && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                        onClick={() => {
                                          setEntitySearch(eventIssueId);
                                        }}
                                      >
                                        Find issue
                                      </Button>
                                    )}
                                    {entry.kind === "event" && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                        onClick={() => {
                                          setEventFilter("all");
                                          setEntitySearch(eventToken);
                                        }}
                                      >
                                        Filter session
                                      </Button>
                                    )}
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                      onClick={() => {
                                        snoozeAgentTimelineEntry(entry);
                                      }}
                                    >
                                      Snooze 15m
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                      onClick={() => {
                                        dismissAgentTimelineEntry(entry);
                                      }}
                                    >
                                      Dismiss
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                            </div>

                            {selectedAgentTimelineEntry && (
                              <div className="rounded-xl border border-[#ecebe8] bg-white p-4">
                                {(() => {
                                  const entry = selectedAgentTimelineEntry;
                                  const workspaceProjectId =
                                    entry.approval?.project_id ||
                                    entry.issue?.project_id ||
                                    toStringValue(entry.event?.project_id);
                                  const workspaceStoryId =
                                    entry.issue?.story_id ?? toNullableNumber(entry.event?.story_id);
                                  const workspaceHref =
                                    workspaceProjectId && workspaceStoryId
                                      ? `/projects/${workspaceProjectId}?storyId=${workspaceStoryId}`
                                      : workspaceProjectId
                                        ? `/projects/${workspaceProjectId}`
                                        : "";
                                  const relatedApprovalId =
                                    entry.approval?.id ||
                                    entry.issue?.approval_id ||
                                    toStringValue(entry.event?.approval_id);
                                  const relatedIssueId =
                                    entry.issue?.id || toStringValue(entry.event?.issue_id);
                                  const relatedRunLink = selectedAgentTimelineRunLink;
                                  const relatedRunResult =
                                    relatedRunLink && relatedRunLink.run.results[relatedRunLink.resultIndex]
                                      ? asRecord(relatedRunLink.run.results[relatedRunLink.resultIndex])
                                      : null;
                                  const relatedRunOutcome = relatedRunResult
                                    ? describeRunResult(relatedRunResult)
                                    : null;
                                  const payload =
                                    entry.approval || entry.issue || entry.event || {
                                      id: entry.id,
                                      kind: entry.kind,
                                      timestamp: entry.timestamp,
                                      status: entry.status,
                                      title: entry.title,
                                      subtitle: entry.subtitle,
                                      message: entry.message,
                                    };

                                  return (
                                    <>
                                      <div className="flex flex-wrap items-center justify-between gap-3">
                                        <div>
                                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                            Selected Timeline Item
                                          </p>
                                          <p className="mt-2 text-[14px] font-semibold text-[#37352f]">
                                            {entry.title}
                                          </p>
                                        </div>
                                        <div className="flex flex-wrap items-center gap-2">
                                          <Badge
                                            variant="outline"
                                            className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                                          >
                                            {entry.kind}
                                          </Badge>
                                          {selectedAgentTimelinePriority ? (
                                            <Badge
                                              variant="outline"
                                              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(selectedAgentTimelinePriority)}`}
                                            >
                                              {selectedAgentTimelinePriority}
                                            </Badge>
                                          ) : null}
                                          <Badge
                                            variant="outline"
                                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
                                              entry.kind === "approval"
                                                ? approvalStatusClass(entry.status)
                                                : entry.kind === "issue"
                                                  ? passStatusClass(entry.status === "open" ? "partial" : "ok")
                                                  : passStatusClass(entry.status)
                                            }`}
                                          >
                                            {entry.status}
                                          </Badge>
                                        </div>
                                      </div>

                                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                        <SessionMetric
                                          label="Timestamp"
                                          value={formatTimestamp(entry.timestamp)}
                                          detail={entry.id}
                                        />
                                        <SessionMetric
                                          label="Scope"
                                          value={entry.subtitle || "No scope metadata"}
                                          detail={workspaceProjectId || "No project linkage"}
                                        />
                                        <SessionMetric
                                          label="Related Run"
                                          value={relatedRunLink?.run.id || "No linked run"}
                                          detail={
                                            relatedRunLink
                                              ? `${relatedRunLink.run.run_kind} · ${relatedRunLink.run.status}`
                                              : "No related action run found"
                                          }
                                        />
                                        <SessionMetric
                                          label="Outcome"
                                          value={
                                            relatedRunResult
                                              ? toStringValue(
                                                  relatedRunResult.status,
                                                  `result #${relatedRunLink?.resultIndex ?? 0}`
                                                )
                                              : "No linked outcome"
                                          }
                                          detail={
                                            relatedRunOutcome?.title ||
                                            (relatedRunLink ? "Related run found without a specific outcome match" : "No outcome linkage")
                                          }
                                        />
                                      </div>

                                      <RelationshipStrip
                                        label="Relationship Strip"
                                        items={[
                                          {
                                            key: `timeline-${entry.kind}-${entry.id}`,
                                            label: `${entry.kind} ${entry.id}`,
                                            tone:
                                              entry.kind === "approval"
                                                ? "approval"
                                                : entry.kind === "issue"
                                                  ? "issue"
                                                  : "event",
                                            active: true,
                                            onClick: () => {
                                              setSelectedAgentTimelineKey(agentTimelineEntryKey(entry));
                                            },
                                          },
                                          relatedRunLink
                                            ? {
                                                key: `run-${relatedRunLink.run.id}`,
                                                label: `run ${relatedRunLink.run.id}`,
                                                tone: "run" as const,
                                                onClick: () => {
                                                  setSelectedRunId(relatedRunLink.run.id);
                                                  setSelectedRunResultIndex(0);
                                                },
                                              }
                                            : null,
                                          relatedRunLink && relatedRunResult
                                            ? {
                                                key: `outcome-${relatedRunLink.run.id}-${relatedRunLink.resultIndex}`,
                                                label: `outcome ${relatedRunLink.resultIndex + 1}`,
                                                tone: "outcome" as const,
                                                onClick: () => {
                                                  setSelectedRunId(relatedRunLink.run.id);
                                                  setSelectedRunResultIndex(relatedRunLink.resultIndex);
                                                },
                                              }
                                            : null,
                                          relatedApprovalId && entry.kind !== "approval"
                                            ? {
                                                key: `approval-${relatedApprovalId}`,
                                                label: `approval ${relatedApprovalId}`,
                                                tone: "approval" as const,
                                                onClick: () => {
                                                  syncLinkedSelection({
                                                    runId: relatedRunLink?.run.id,
                                                    resultIndex: relatedRunLink?.resultIndex,
                                                    approvalId: relatedApprovalId,
                                                    issueId: relatedIssueId,
                                                    runtimeAgentId: selectedAgent.runtime_agent_id,
                                                    event: entry.event || null,
                                                  });
                                                },
                                              }
                                            : null,
                                          relatedIssueId && entry.kind !== "issue"
                                            ? {
                                                key: `issue-${relatedIssueId}`,
                                                label: `issue ${relatedIssueId}`,
                                                tone: "issue" as const,
                                                onClick: () => {
                                                  syncLinkedSelection({
                                                    runId: relatedRunLink?.run.id,
                                                    resultIndex: relatedRunLink?.resultIndex,
                                                    approvalId: relatedApprovalId,
                                                    issueId: relatedIssueId,
                                                    runtimeAgentId: selectedAgent.runtime_agent_id,
                                                    event: entry.event || null,
                                                  });
                                                },
                                              }
                                            : null,
                                          {
                                            key: `agent-${selectedAgent.runtime_agent_id}`,
                                            label: `agent ${selectedAgent.runtime_agent_id}`,
                                            tone: "agent",
                                            onClick: () => {
                                              focusRuntimeAgent(selectedAgent.runtime_agent_id, true);
                                            },
                                          },
                                        ].filter(Boolean) as RelationshipStripItem[]}
                                      />

                                      <p className="mt-4 text-[13px] leading-relaxed text-[#6b6b6b]">
                                        {entry.message}
                                      </p>

                                      <div className="mt-4 flex flex-wrap gap-2">
                                        {entry.approval?.status === "pending" && (
                                          <>
                                            <Button
                                              size="sm"
                                              className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                              disabled={Boolean(busyActionKey)}
                                              onClick={() => {
                                                void approveApproval(entry.approval!);
                                              }}
                                            >
                                              {busyActionKey === `approval-approve:${entry.approval.id}` ? "Approving..." : "Approve"}
                                            </Button>
                                            <Button
                                              size="sm"
                                              variant="outline"
                                              className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                              disabled={Boolean(busyActionKey)}
                                              onClick={() => {
                                                void rejectApproval(entry.approval!);
                                              }}
                                            >
                                              {busyActionKey === `approval-reject:${entry.approval.id}` ? "Rejecting..." : "Reject"}
                                            </Button>
                                          </>
                                        )}
                                        {entry.approval?.status === "approved" && (
                                          <Button
                                            size="sm"
                                            className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                            disabled={Boolean(busyActionKey)}
                                            onClick={() => {
                                              void applyApproval(entry.approval!);
                                            }}
                                          >
                                            {busyActionKey === `approval-apply:${entry.approval.id}` ? "Applying..." : "Apply"}
                                          </Button>
                                        )}
                                        {entry.issue?.status === "open" && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            disabled={Boolean(busyActionKey)}
                                            onClick={() => {
                                              void resolveIssue(entry.issue!);
                                            }}
                                          >
                                            {busyActionKey === `issue-resolve:${entry.issue.id}` ? "Resolving..." : "Resolve"}
                                          </Button>
                                        )}
                                        {relatedApprovalId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(relatedApprovalId);
                                            }}
                                          >
                                            Find approval
                                          </Button>
                                        )}
                                        {relatedIssueId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                                            onClick={() => {
                                              setEntitySearch(relatedIssueId);
                                            }}
                                          >
                                            Find issue
                                          </Button>
                                        )}
                                        {workspaceHref && (
                                          <Link
                                            href={workspaceHref}
                                            className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                                          >
                                            Open workspace
                                          </Link>
                                        )}
                                        {relatedRunLink && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              setSelectedRunId(relatedRunLink.run.id);
                                              setSelectedRunResultIndex(0);
                                            }}
                                          >
                                            Open related run
                                          </Button>
                                        )}
                                        {relatedRunLink && relatedRunResult && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setSelectedRunId(relatedRunLink.run.id);
                                              setSelectedRunResultIndex(relatedRunLink.resultIndex);
                                            }}
                                          >
                                            Open related outcome
                                          </Button>
                                        )}
                                      </div>

                                      <div className="mt-4 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                          Payload
                                        </p>
                                        <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                                          {formatJson(payload)}
                                        </pre>
                                      </div>
                                    </>
                                  );
                                })()}
                              </div>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="grid gap-4 lg:grid-cols-3">
                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Issues Summary
                          </p>
                          <div className="mt-3 grid gap-3">
                            <SessionMetric
                              label="Open Issues"
                              value={String(selectedAgent.history.open_issue_count)}
                              detail={`${selectedAgent.history.issue_count} total issues`}
                            />
                          </div>
                          {!latestAgentIssueEntry ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">No issue history for this agent.</p>
                          ) : (
                            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-mono text-[11px] text-[#37352f]">
                                  {latestAgentIssueEntry.issue?.id || latestAgentIssueEntry.id}
                                </p>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(latestAgentIssueEntry.status === "open" ? "partial" : "ok")}`}
                                >
                                  {latestAgentIssueEntry.status}
                                </Badge>
                              </div>
                              <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                {latestAgentIssueEntry.title}
                              </p>
                              <p className="mt-1 text-[11px] text-[#9b9a97]">
                                {formatTimestamp(latestAgentIssueEntry.timestamp)}
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    focusAgentTimeline("issues", { entry: latestAgentIssueEntry });
                                  }}
                                >
                                  Open in timeline
                                </Button>
                                {latestAgentIssueEntry.issue?.status === "open" && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    disabled={Boolean(busyActionKey)}
                                    onClick={() => {
                                      void resolveIssue(latestAgentIssueEntry.issue!);
                                    }}
                                  >
                                    {busyActionKey === `issue-resolve:${latestAgentIssueEntry.issue.id}` ? "Resolving..." : "Resolve"}
                                  </Button>
                                )}
                                {latestAgentIssueEntry.issue?.id && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                    onClick={() => {
                                      setEntitySearch(latestAgentIssueEntry.issue?.id || "");
                                    }}
                                  >
                                    Find in session
                                  </Button>
                                )}
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Approvals Summary
                          </p>
                          <div className="mt-3 grid gap-3">
                            <SessionMetric
                              label="Pending Approvals"
                              value={String(selectedAgent.history.pending_approval_count)}
                              detail={`${selectedAgent.history.approval_count} total approvals`}
                            />
                          </div>
                          {!latestAgentApprovalEntry ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">No approval history for this agent.</p>
                          ) : (
                            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-mono text-[11px] text-[#37352f]">
                                  {latestAgentApprovalEntry.approval?.id || latestAgentApprovalEntry.id}
                                </p>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${approvalStatusClass(latestAgentApprovalEntry.status)}`}
                                >
                                  {latestAgentApprovalEntry.status}
                                </Badge>
                              </div>
                              <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                {latestAgentApprovalEntry.title}
                              </p>
                              <p className="mt-1 text-[11px] text-[#9b9a97]">
                                {formatTimestamp(latestAgentApprovalEntry.timestamp)}
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    focusAgentTimeline("approvals", { entry: latestAgentApprovalEntry });
                                  }}
                                >
                                  Open in timeline
                                </Button>
                                {latestAgentApprovalEntry.approval?.status === "pending" && (
                                  <>
                                    <Button
                                      size="sm"
                                      className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                                      disabled={Boolean(busyActionKey)}
                                      onClick={() => {
                                        void approveApproval(latestAgentApprovalEntry.approval!);
                                      }}
                                    >
                                      {busyActionKey === `approval-approve:${latestAgentApprovalEntry.approval.id}` ? "Approving..." : "Approve"}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                      disabled={Boolean(busyActionKey)}
                                      onClick={() => {
                                        void rejectApproval(latestAgentApprovalEntry.approval!);
                                      }}
                                    >
                                      {busyActionKey === `approval-reject:${latestAgentApprovalEntry.approval.id}` ? "Rejecting..." : "Reject"}
                                    </Button>
                                  </>
                                )}
                                {latestAgentApprovalEntry.approval?.status === "approved" && (
                                  <Button
                                    size="sm"
                                    className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                                    disabled={Boolean(busyActionKey)}
                                    onClick={() => {
                                      void applyApproval(latestAgentApprovalEntry.approval!);
                                    }}
                                  >
                                    {busyActionKey === `approval-apply:${latestAgentApprovalEntry.approval.id}` ? "Applying..." : "Apply"}
                                  </Button>
                                )}
                                {latestAgentApprovalEntry.approval?.id && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                    onClick={() => {
                                      setEntitySearch(latestAgentApprovalEntry.approval?.id || "");
                                    }}
                                  >
                                    Find in session
                                  </Button>
                                )}
                              </div>
                            </div>
                          )}
                        </div>

                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Events Summary
                          </p>
                          <div className="mt-3 grid gap-3">
                            <SessionMetric
                              label="Events"
                              value={String(selectedAgent.history.event_count)}
                              detail={formatTimestamp(selectedAgent.history.last_event_at)}
                            />
                          </div>
                          {!latestAgentEventEntry ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">No event history for this agent.</p>
                          ) : (
                            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-mono text-[11px] text-[#37352f]">
                                  {latestAgentEventEntry.title}
                                </p>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(latestAgentEventEntry.status)}`}
                                >
                                  {latestAgentEventEntry.status}
                                </Badge>
                              </div>
                              <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                {latestAgentEventEntry.message}
                              </p>
                              <p className="mt-1 text-[11px] text-[#9b9a97]">
                                {formatTimestamp(latestAgentEventEntry.timestamp)}
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    focusAgentTimeline("events", { entry: latestAgentEventEntry });
                                  }}
                                >
                                  Open in timeline
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                  onClick={() => {
                                    focusAgentTimeline("attention");
                                  }}
                                >
                                  Show attention
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    setEventFilter("all");
                                    setEntitySearch(
                                      toStringValue(latestAgentEventEntry.event?.event) ||
                                        toStringValue(latestAgentEventEntry.event?.message) ||
                                        latestAgentEventEntry.id
                                    );
                                  }}
                                >
                                  Filter session
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Control Mix
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Top profile, final-state, and ownership slices from persisted orchestration passes.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <BreakdownChips
                    label="Profiles"
                    values={controlSummary.by_profile}
                    emptyText="No profiles recorded."
                  />
                  <BreakdownChips
                    label="Final States"
                    values={controlSummary.by_final_state}
                    emptyText="No final states recorded."
                  />
                  <BreakdownChips
                    label="Orchestrators"
                    values={controlSummary.by_orchestrator}
                    emptyText="No orchestrator labels recorded."
                  />
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Recent Sessions
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    External FounderOS orchestration sessions, now selectable for direct control.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {recentSessions.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-6 text-[13px] text-[#9b9a97]">
                      {sessions.length
                        ? "No orchestrator sessions match the current history search."
                        : "No orchestrator sessions recorded yet."}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentSessions.map((session) => {
                        const selected = selectedSessionId === session.id;

                        return (
                          <div
                            key={session.id}
                            className={`rounded-2xl border p-4 ${
                              selected
                                ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                                : "border-[#ecebe8] bg-[#fbfbf9]"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-[14px] font-semibold text-[#37352f]">
                                    {session.title || session.id}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(session.status)}`}
                                  >
                                    {session.status}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#787774]">
                                  {session.orchestrator || "unknown orchestrator"}
                                  {" · "}
                                  {session.actor || "unknown actor"}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="font-mono text-[11px] text-[#9b9a97]">{session.id}</p>
                                <Button
                                  size="sm"
                                  variant={selected ? "default" : "outline"}
                                  className={`mt-2 h-8 rounded-lg text-[12px] ${
                                    selected
                                      ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                      : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                  }`}
                                  onClick={() => {
                                    setSelectedSessionId(session.id);
                                  }}
                                >
                                  {selected ? "Selected" : "Open control"}
                                </Button>
                              </div>
                            </div>

                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              <SessionMetric
                                label="Scope"
                                value={`${session.project_ids.length} project${session.project_ids.length === 1 ? "" : "s"}`}
                                detail={session.initiative_id || "No initiative mapping"}
                              />
                              <SessionMetric
                                label="Linked Objects"
                                value={`${session.linked_control_pass_ids.length} passes`}
                                detail={`${session.linked_run_ids.length} runs · ${session.linked_issue_ids.length} issues`}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Session Overview
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Aggregate session lifecycle and actor coverage for the external orchestrator layer.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <BreakdownChips
                    label="Session Status"
                    values={sessionSummary.by_status}
                    emptyText="No session statuses recorded."
                  />
                  <BreakdownChips
                    label="Actors"
                    values={sessionSummary.by_actor}
                    emptyText="No actors recorded."
                  />
                  <BreakdownChips
                    label="Orchestrators"
                    values={sessionSummary.by_orchestrator}
                    emptyText="No orchestrators recorded."
                  />
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
            <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <CardHeader>
                <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                  Session Drill-Down
                </CardTitle>
                <CardDescription className="text-[13px] text-[#787774]">
                  Inspect the selected session, apply direct recommendations, or run a session-level
                  control pass profile from this panel.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!selectedSessionId ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    Select a recent session or control pass to inspect live control state.
                  </div>
                ) : sessionLoading || !selectedSession ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    Loading session detail...
                  </div>
                ) : (
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-[#37352f]">
                            {selectedSession.title || selectedSession.id}
                          </h2>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(selectedSession.status)}`}
                          >
                            {selectedSession.status}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControl?.state || "unknown")}`}
                          >
                            {selectedControl?.state || "unknown"}
                          </Badge>
                        </div>
                        <p className="mt-2 font-mono text-[12px] text-[#9b9a97]">{selectedSession.id}</p>
                        <p className="mt-2 text-[14px] text-[#6b6b6b]">
                          {selectedSession.orchestrator || "unknown orchestrator"}
                          {" · "}
                          {selectedSession.actor || "unknown actor"}
                          {selectedSession.reason ? ` · ${selectedSession.reason}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selectedSession.project_ids.map((projectId) => (
                          <Link
                            key={`${selectedSession.id}-${projectId}`}
                            href={`/projects/${projectId}`}
                            className="inline-flex h-8 items-center rounded-full border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                          >
                            {projectId}
                          </Link>
                        ))}
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-4">
                      <SessionMetric
                        label="Pending Approvals"
                        value={String(selectedSession.summary.pending_approval_count)}
                        detail={`${selectedSession.summary.approval_count} linked approvals`}
                      />
                      <SessionMetric
                        label="Open Issues"
                        value={String(selectedSession.summary.open_issue_count)}
                        detail={`${selectedSession.summary.issue_count} linked issues`}
                      />
                      <SessionMetric
                        label="Safe Actions"
                        value={String(selectedControl?.counts.safe_actions || 0)}
                        detail={`${selectedControl?.counts.approval_required_actions || 0} approval-gated`}
                      />
                      <SessionMetric
                        label="Control Passes"
                        value={String(selectedSession.summary.control_pass_count)}
                        detail={`${selectedSession.summary.run_count} linked runs`}
                      />
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Linked Runtime Agents
                        </p>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {linkedAgentIds.length}
                        </Badge>
                      </div>
                      {!linkedAgentIds.length ? (
                        <p className="mt-3 text-[13px] text-[#9b9a97]">No linked runtime agents in this session.</p>
                      ) : (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {linkedAgentIds.slice(0, 12).map((runtimeAgentId) => (
                            <Button
                              key={`${selectedSession.id}-${runtimeAgentId}`}
                              size="sm"
                              variant={selectedAgentId === runtimeAgentId ? "default" : "outline"}
                              className={`h-8 rounded-full px-3 text-[11px] ${
                                selectedAgentId === runtimeAgentId
                                  ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                  : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                              }`}
                              onClick={() => {
                                focusRuntimeAgent(runtimeAgentId, true);
                              }}
                            >
                              {runtimeAgentId}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Entity Search
                          </p>
                          <p className="mt-2 text-[13px] text-[#787774]">
                            Filter runs, events, approvals, and issues by id, runtime agent, command, story, or reason.
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredRuns.length}/{linkedRuns.length} runs
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredEvents.length}/{selectedSession.events.length} events
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredApprovals.length}/{linkedApprovals.length} approvals
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredIssues.length}/{linkedIssues.length} issues
                          </Badge>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <Input
                          value={entitySearch}
                          onChange={(event) => {
                            setEntitySearch(event.target.value);
                          }}
                          placeholder="approval id, issue id, runtime agent, action key, command, story..."
                          className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                          disabled={!entitySearch.trim()}
                          onClick={() => {
                            setEntitySearch("");
                          }}
                        >
                          Clear search
                        </Button>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Control Pass Profiles
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {sortedProfiles.map((profile) => {
                          const busy = busyActionKey === `profile:${profile.name}`;
                          return (
                            <Button
                              key={profile.name}
                              size="sm"
                              variant={profile.default ? "default" : "outline"}
                              className={`h-9 rounded-lg text-[12px] ${
                                profile.default
                                  ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                  : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                              }`}
                              disabled={Boolean(busyActionKey)}
                              onClick={() => {
                                void applyControlPlan(profile);
                              }}
                            >
                              {busy ? "Running..." : profile.name}
                            </Button>
                          );
                        })}
                      </div>
                      <div className="mt-3 space-y-2">
                        {sortedProfiles.map((profile) => (
                          <div
                            key={`${profile.name}-description`}
                            className="flex flex-wrap items-start justify-between gap-2 text-[12px] text-[#787774]"
                          >
                            <span className="font-medium text-[#37352f]">{profile.name}</span>
                            <span className="max-w-[75%] text-right">{profile.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Current Recommendations
                        </p>
                        <p className="text-[12px] text-[#787774]">
                          {selectedControl?.recommendations.length || 0} recommendation(s)
                        </p>
                      </div>
                      {!selectedControl?.recommendations.length ? (
                        <p className="mt-3 text-[13px] text-[#9b9a97]">
                          No current recommendations for this session.
                        </p>
                      ) : (
                        <div className="mt-3 space-y-3">
                          {selectedControl.recommendations.map((recommendation) => {
                            const busy = busyActionKey === `recommendation:${recommendation.kind}`;

                            return (
                              <div
                                key={recommendation.kind}
                                className="rounded-xl border border-[#ecebe8] bg-white p-4"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="text-[14px] font-semibold text-[#37352f]">
                                        {recommendation.title}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(recommendation.priority)}`}
                                      >
                                        {recommendation.priority}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {recommendation.kind}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">
                                      {recommendation.reason}
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {Object.entries(recommendation.counts || {}).map(([key, value]) => (
                                        <Badge
                                          key={`${recommendation.kind}-${key}`}
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {key}: {value}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                  <Button
                                    size="sm"
                                    className="h-9 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                    disabled={Boolean(busyActionKey)}
                                    onClick={() => {
                                      void applyRecommendation(recommendation);
                                    }}
                                  >
                                    {busy ? "Running..." : recommendationActionLabel(recommendation)}
                                  </Button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className="grid gap-4 xl:grid-cols-3">
                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Action Summary
                        </p>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <SessionMetric
                            label="Actions"
                            value={String(selectedControl?.action_summary.totals.actions || 0)}
                            detail={`${selectedControl?.action_summary.totals.suggested_commands || 0} commands · ${selectedControl?.action_summary.totals.recommendations || 0} recommendations`}
                          />
                          <SessionMetric
                            label="Projects"
                            value={String(selectedControl?.action_summary.totals.projects || 0)}
                            detail={`${selectedControl?.action_summary.totals.approval_required || 0} approval-required actions`}
                          />
                        </div>
                        <div className="mt-4 space-y-4">
                          <BreakdownChips
                            label="Action Types"
                            values={selectedControl?.action_summary.by_action_type}
                            emptyText="No action types recorded."
                          />
                          <BreakdownChips
                            label="Priorities"
                            values={selectedControl?.action_summary.by_priority}
                            emptyText="No priorities recorded."
                          />
                          <BreakdownChips
                            label="Commands"
                            values={selectedControl?.action_summary.by_command}
                            emptyText="No commands recorded."
                          />
                        </div>
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Action Runs
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {linkedRuns.length}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <FilterChip
                            label="All"
                            active={runFilter === "all"}
                            count={linkedRuns.length}
                            onClick={() => {
                              setRunFilter("all");
                            }}
                          />
                          <FilterChip
                            label="Execute"
                            active={runFilter === "execute"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "execute")).length}
                            onClick={() => {
                              setRunFilter("execute");
                            }}
                          />
                          <FilterChip
                            label="Preview"
                            active={runFilter === "preview"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "preview")).length}
                            onClick={() => {
                              setRunFilter("preview");
                            }}
                          />
                          <FilterChip
                            label="Attention"
                            active={runFilter === "attention"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "attention")).length}
                            onClick={() => {
                              setRunFilter("attention");
                            }}
                          />
                        </div>
                        {!filteredRuns.length ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedRuns.length
                              ? "No action runs match the current filter."
                              : "No linked action runs recorded yet."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {filteredRuns.slice(0, 6).map((run) => {
                              const selected = selectedRunId === run.id;
                              return (
                                <div
                                  key={`${selectedSession.id}-run-${run.id}`}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-mono text-[11px] text-[#37352f]">{run.id}</p>
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(run.status)}`}
                                        >
                                          {run.status}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {run.run_kind}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {run.dry_run ? "preview" : "execute"}
                                        </Badge>
                                      </div>
                                      <p className="mt-2 text-[12px] text-[#787774]">
                                        {run.mode || "auto"}
                                        {run.policy_profile ? ` · ${run.policy_profile}` : ""}
                                      </p>
                                      <p className="mt-2 text-[12px] text-[#9b9a97]">
                                        {toNumber(run.summary.selected_count)} selected ·{" "}
                                        {toNumber(run.summary.processed_count, run.results.length)} processed
                                      </p>
                                      {run.runtime_agent_ids.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-2">
                                          {run.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                                            <Button
                                              key={`${run.id}-${runtimeAgentId}`}
                                              size="sm"
                                              variant="outline"
                                              className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                              onClick={() => {
                                                focusRuntimeAgent(runtimeAgentId, true);
                                              }}
                                            >
                                              {runtimeAgentId}
                                            </Button>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                    <Button
                                      size="sm"
                                      variant={selected ? "default" : "outline"}
                                      className={`h-8 rounded-lg text-[12px] ${
                                        selected
                                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                      }`}
                                      onClick={() => {
                                        setSelectedRunId(run.id);
                                      }}
                                    >
                                      {selected ? "Selected" : "Inspect"}
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Latest Session Events
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredEvents.length}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <FilterChip
                            label="All"
                            active={eventFilter === "all"}
                            count={(selectedSession.events || []).length}
                            onClick={() => {
                              setEventFilter("all");
                            }}
                          />
                          <FilterChip
                            label="Control"
                            active={eventFilter === "control"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "control")).length}
                            onClick={() => {
                              setEventFilter("control");
                            }}
                          />
                          <FilterChip
                            label="Actions"
                            active={eventFilter === "actions"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "actions")).length}
                            onClick={() => {
                              setEventFilter("actions");
                            }}
                          />
                          <FilterChip
                            label="Decisions"
                            active={eventFilter === "decisions"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "decisions")).length}
                            onClick={() => {
                              setEventFilter("decisions");
                            }}
                          />
                          <FilterChip
                            label="Attention"
                            active={eventFilter === "attention"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "attention")).length}
                            onClick={() => {
                              setEventFilter("attention");
                            }}
                          />
                        </div>
                        {!filteredEvents.length ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {selectedSession.events.length
                              ? "No session events match the current filter."
                              : "No session events recorded yet."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {visibleSessionEvents.map((event, index) => (
                              (() => {
                                const eventApprovalId = toStringValue(event.approval_id);
                                const eventIssueId = toStringValue(event.issue_id);
                                const eventProjectId = toStringValue(event.project_id);
                                const eventRuntimeAgentIds = [
                                  toStringValue(event.runtime_agent_id),
                                  ...toStringArray(event.runtime_agent_ids),
                                ].filter(Boolean);
                                const eventKey = sessionEventKey(event, String(index));
                                const selected = selectedSessionEventKey === eventKey;
                                return (
                                  <div
                                    key={eventKey}
                                    id={sessionContextRowDomId("event", eventKey)}
                                    className={`rounded-xl border p-3 ${
                                      selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                                    }`}
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-mono text-[11px] text-[#37352f]">
                                          {toStringValue(event.event, "unknown_event")}
                                        </p>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {eventFamily(toStringValue(event.event))}
                                        </Badge>
                                      </div>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(toStringValue(event.status, "unknown"))}`}
                                      >
                                        {toStringValue(event.status, "unknown")}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          syncLinkedSelection({
                                            event,
                                            runId:
                                              toStringValue(event.agent_action_run_id) ||
                                              toStringValue(event.run_id),
                                            approvalId: eventApprovalId,
                                            issueId: eventIssueId,
                                            runtimeAgentId: eventRuntimeAgentIds[0],
                                          });
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {toStringValue(event.message, "No event message")}
                                    </p>
                                    {(eventProjectId ||
                                      toNullableNumber(event.story_id) ||
                                      eventApprovalId ||
                                      eventIssueId ||
                                      eventRuntimeAgentIds.length > 0) && (
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        {eventProjectId && (
                                          <Link
                                            href={`/projects/${eventProjectId}`}
                                            className="inline-flex h-7 items-center rounded-full border border-[#e5e5e3] bg-[#fafaf9] px-2.5 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                                          >
                                            project {eventProjectId}
                                          </Link>
                                        )}
                                        {toNullableNumber(event.story_id) && eventProjectId && (
                                          <Link
                                            href={`/projects/${eventProjectId}?storyId=${toNullableNumber(event.story_id)}`}
                                            className="inline-flex h-7 items-center rounded-full border border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] font-medium text-[#2a6690] transition-colors hover:bg-[#e3f2f8]"
                                          >
                                            story {toNullableNumber(event.story_id)}
                                          </Link>
                                        )}
                                        {eventApprovalId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(eventApprovalId);
                                            }}
                                          >
                                            approval {eventApprovalId}
                                          </Button>
                                        )}
                                        {eventIssueId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                            onClick={() => {
                                              setEntitySearch(eventIssueId);
                                            }}
                                          >
                                            issue {eventIssueId}
                                          </Button>
                                        )}
                                        {eventRuntimeAgentIds.slice(0, 2).map((runtimeAgentId) => (
                                          <Button
                                            key={`${toStringValue(event.event)}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                      </div>
                                    )}
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {formatTimestamp(toStringValue(event.timestamp))}
                                    </p>
                                  </div>
                                );
                              })()
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Selected Control Pass
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Inspect the pass currently selected from recent history or session-linked passes.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedPass ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a control pass to inspect applied steps and final state.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedPass.id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedPass.status)}`}
                            >
                              {selectedPass.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedPass.profile}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            Session {selectedPass.orchestrator_session_id} · {selectedPass.actor || "unknown actor"}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                          onClick={() => {
                            setSelectedSessionId(selectedPass.orchestrator_session_id);
                          }}
                        >
                          Open session
                        </Button>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Final State"
                          value={toStringValue(selectedPass.summary.final_state, "unknown")}
                          detail={toStringValue(selectedPass.summary.stopped_reason, "No stop reason")}
                        />
                        <SessionMetric
                          label="Applied"
                          value={String(toNumber(selectedPass.summary.applied, selectedPass.applied.length))}
                          detail={`${toNumber(selectedPass.summary.errors, selectedPass.errors.length)} error step(s)`}
                        />
                        <SessionMetric
                          label="Control Transition"
                          value={`${toStringValue(selectedPass.control_before.state, "unknown")} -> ${toStringValue(selectedPass.control_after.state, "unknown")}`}
                          detail={`${selectedPass.session_status_before || "unknown"} -> ${selectedPass.session_status_after || "unknown"} session status`}
                        />
                        <SessionMetric
                          label="Coverage"
                          value={`${selectedPass.project_ids.length} project${selectedPass.project_ids.length === 1 ? "" : "s"}`}
                          detail={selectedPass.initiative_id || "No initiative mapping"}
                        />
                      </div>

                      <BreakdownChips
                        label="Recommendation Kinds"
                        values={selectedPass.recommendation_kinds.reduce<ExecutionPlaneCountMap>((acc, kind) => {
                          acc[kind] = (acc[kind] || 0) + 1;
                          return acc;
                        }, {})}
                        emptyText="No recommendation kinds recorded."
                      />

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Applied Steps
                        </p>
                        {selectedPass.applied.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No applied steps recorded.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedPass.applied.map((step, index) => (
                              <div
                                key={`${selectedPass.id}-applied-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(step.title, toStringValue(step.recommendation_kind, "step"))}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(step.status, "ok"))}`}
                                  >
                                    {toStringValue(step.status, "ok")}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#787774]">
                                  {toStringValue(step.operation_type, "operation")}
                                  {toStringValue(step.operation_mode) ? ` · ${toStringValue(step.operation_mode)}` : ""}
                                </p>
                                <p className="mt-2 text-[12px] text-[#9b9a97]">
                                  {toStringValue(step.control_state_before, "unknown")}
                                  {" -> "}
                                  {toStringValue(step.control_state_after, "unknown")}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Errors
                        </p>
                        {selectedPass.errors.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No errors recorded for this pass.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedPass.errors.map((error, index) => (
                              <div
                                key={`${selectedPass.id}-error-${index}`}
                                className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] p-3"
                              >
                                <p className="text-[13px] font-semibold text-[#93370d]">
                                  {toStringValue(error.title, toStringValue(error.recommendation_kind, "error"))}
                                </p>
                                <p className="mt-2 text-[12px] text-[#93370d]">
                                  {toStringValue(error.error, "Unknown control-pass error")}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Linked Decisions
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Approvals and issues attached to the selected session, with direct control actions.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedSession ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a session to inspect pending approvals and issues.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Session Approvals
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredApprovals.length}
                          </Badge>
                        </div>
                        {filteredApprovals.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedApprovals.length
                              ? "No approvals match the current search."
                              : "No linked approvals."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {visibleSessionApprovals.map((approval) => {
                              const selected = selectedSessionApprovalId === approval.id;
                              return (
                              <div
                                key={`${selectedSession.id}-approval-${approval.id}`}
                                id={sessionContextRowDomId("approval", approval.id)}
                                className={`rounded-xl border p-3 ${
                                  selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                                }`}
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="font-mono text-[11px] text-[#37352f]">
                                        {approval.id}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${approvalStatusClass(approval.status)}`}
                                      >
                                        {approval.status}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {approval.action}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          syncLinkedSelection({
                                            approvalId: approval.id,
                                            issueId: approval.issue_id,
                                            runtimeAgentId: approval.runtime_agent_ids[0],
                                          });
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {approval.reason || `Approval requested for ${approval.action}.`}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      Requested by {approval.requested_by || "unknown"} · {formatTimestamp(approval.created_at)}
                                    </p>
                                    {(approval.policy_reasons.length > 0 || approval.issue_id || approval.runtime_agent_ids.length > 0) && (
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {approval.issue_id && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(approval.issue_id);
                                            }}
                                          >
                                            issue {approval.issue_id}
                                          </Button>
                                        )}
                                        {approval.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                                          <Button
                                            key={`${approval.id}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                        {approval.policy_reasons.slice(0, 3).map((reason) => (
                                          <Badge
                                            key={`${approval.id}-${reason}`}
                                            variant="outline"
                                            className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                          >
                                            {reason}
                                          </Badge>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {approval.status === "pending" && (
                                      <>
                                        <Button
                                          size="sm"
                                          className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void approveApproval(approval);
                                          }}
                                        >
                                          {busyActionKey === `approval-approve:${approval.id}` ? "Approving..." : "Approve"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void rejectApproval(approval);
                                          }}
                                        >
                                          {busyActionKey === `approval-reject:${approval.id}` ? "Rejecting..." : "Reject"}
                                        </Button>
                                      </>
                                    )}
                                    {approval.status === "approved" && (
                                      <Button
                                        size="sm"
                                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void applyApproval(approval);
                                        }}
                                      >
                                        {busyActionKey === `approval-apply:${approval.id}` ? "Applying..." : "Apply"}
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )})}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Session Issues
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredIssues.length}
                          </Badge>
                        </div>
                        {filteredIssues.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedIssues.length
                              ? "No issues match the current search."
                              : "No linked issues."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {visibleSessionIssues.map((issue) => {
                              const selected = selectedSessionIssueId === issue.id;
                              return (
                              <div
                                key={`${selectedSession.id}-issue-${issue.id}`}
                                id={sessionContextRowDomId("issue", issue.id)}
                                className={`rounded-xl border p-3 ${
                                  selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                                }`}
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="font-mono text-[11px] text-[#37352f]">
                                        {issue.id}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueStatusClass(issue.status)}`}
                                      >
                                        {issue.status}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issue.severity)}`}
                                      >
                                        {issue.severity}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {issue.category}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          syncLinkedSelection({
                                            issueId: issue.id,
                                            approvalId: issue.approval_id,
                                            runtimeAgentId:
                                              issue.runtime_agent_ids[0] || issue.runtime_agent_id,
                                          });
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {issue.title || "Issue requires review"}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {issue.root_cause || issue.description || "No root cause recorded"}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {formatTimestamp(issue.created_at)}
                                      {issue.related_command ? ` · command ${issue.related_command}` : ""}
                                    </p>
                                    {(issue.approval_id || issue.runtime_agent_ids.length > 0 || issue.runtime_agent_id) && (
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {issue.approval_id && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(issue.approval_id);
                                            }}
                                          >
                                            approval {issue.approval_id}
                                          </Button>
                                        )}
                                        {(issue.runtime_agent_ids.length > 0
                                          ? issue.runtime_agent_ids.slice(0, 2)
                                          : issue.runtime_agent_id
                                            ? [issue.runtime_agent_id]
                                            : []
                                        ).map((runtimeAgentId) => (
                                          <Button
                                            key={`${issue.id}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {issue.status === "open" && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void resolveIssue(issue);
                                        }}
                                      >
                                        {busyActionKey === `issue-resolve:${issue.id}` ? "Resolving..." : "Resolve"}
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              </div>
                            )})}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Selected Session Context
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Compact inspector for the currently selected session approval, issue, or event.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedSession ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a session to inspect linked context.
                    </div>
                  ) : !selectedSessionContext ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Pick an approval, issue, event, or outcome to open the unified context inspector.
                    </div>
                  ) : (
                    (() => {
                      const contextKind = selectedSessionContext.kind;
                      const approvalContext =
                        contextKind === "approval" ? selectedSessionContext.approval : null;
                      const issueContext =
                        contextKind === "issue" ? selectedSessionContext.issue : null;
                      const eventContext =
                        contextKind === "event" ? selectedSessionContext.event : null;
                      const relatedApprovalId =
                        approvalContext?.id ||
                        issueContext?.approval_id ||
                        toStringValue(eventContext?.approval_id);
                      const relatedIssueId =
                        issueContext?.id ||
                        approvalContext?.issue_id ||
                        toStringValue(eventContext?.issue_id);
                      const runtimeAgentId =
                        approvalContext?.runtime_agent_ids[0] ||
                        issueContext?.runtime_agent_ids[0] ||
                        issueContext?.runtime_agent_id ||
                        toStringValue(eventContext?.runtime_agent_id) ||
                        toStringArray(eventContext?.runtime_agent_ids)[0] ||
                        "";
                      const projectId = approvalContext?.project_id || issueContext?.project_id || toStringValue(eventContext?.project_id);
                      const storyId = issueContext?.story_id ?? toNullableNumber(eventContext?.story_id);
                      const workspaceHref =
                        projectId && storyId
                          ? `/projects/${projectId}?storyId=${storyId}`
                          : projectId
                            ? `/projects/${projectId}`
                            : "";
                      const relatedRunLink = resolveRunLinkFromContext(linkedRuns, {
                        approvalId: relatedApprovalId,
                        issueId: relatedIssueId,
                        runId:
                          toStringValue(eventContext?.agent_action_run_id) ||
                          toStringValue(eventContext?.run_id),
                        runtimeAgentId,
                        event: eventContext,
                      });
                      const relatedRunResult =
                        relatedRunLink && relatedRunLink.run.results[relatedRunLink.resultIndex]
                          ? asRecord(relatedRunLink.run.results[relatedRunLink.resultIndex])
                          : null;
                      const relatedOutcome = relatedRunResult
                        ? describeRunResult(relatedRunResult)
                        : null;
                      const title =
                        approvalContext?.action ||
                        issueContext?.title ||
                        issueContext?.root_cause ||
                        issueContext?.id ||
                        toStringValue(eventContext?.event, "unknown_event");
                      const subtitle =
                        approvalContext?.reason ||
                        issueContext?.root_cause ||
                        issueContext?.description ||
                        toStringValue(eventContext?.message, "No event message") ||
                        "No detail provided.";
                      const timestamp =
                        approvalContext?.applied_at ||
                        approvalContext?.decided_at ||
                        approvalContext?.updated_at ||
                        approvalContext?.created_at ||
                        issueContext?.resolved_at ||
                        issueContext?.updated_at ||
                        issueContext?.created_at ||
                        toStringValue(eventContext?.timestamp);
                      const status =
                        approvalContext?.status ||
                        issueContext?.status ||
                        toStringValue(eventContext?.status, "unknown");
                      const statusClass =
                        contextKind === "approval"
                          ? approvalStatusClass(status)
                          : contextKind === "issue"
                            ? issueStatusClass(status)
                            : passStatusClass(status);
                      const payload =
                        (approvalContext ? asRecord(approvalContext) : null) ||
                        (issueContext ? asRecord(issueContext) : null) ||
                        eventContext ||
                        {};
                      const contextId =
                        approvalContext?.id ||
                        issueContext?.id ||
                        toStringValue(eventContext?.id) ||
                        title;
                      const contextDetail =
                        approvalContext?.action ||
                        issueContext?.category ||
                        toStringValue(eventContext?.event, "event");
                      const runtimeAgentDetail =
                        approvalContext?.requested_by ||
                        issueContext?.related_command ||
                        toStringValue(eventContext?.orchestrator_session_id, "No session token");

                      return (
                        <div className="space-y-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                                >
                                  {contextKind}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusClass}`}
                                >
                                  {status}
                                </Badge>
                                {contextKind === "issue" && (
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issueContext?.severity || "unknown")}`}
                                  >
                                    {issueContext?.severity || "unknown"}
                                  </Badge>
                                )}
                                {contextKind === "event" && (
                                  <Badge
                                    variant="outline"
                                    className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                  >
                                    {eventFamily(toStringValue(eventContext?.event))}
                                  </Badge>
                                )}
                              </div>
                              <p className="mt-3 text-[14px] font-semibold text-[#37352f]">{title}</p>
                              <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">{subtitle}</p>
                            </div>
                            <p className="text-[12px] text-[#9b9a97]">{formatTimestamp(timestamp)}</p>
                          </div>

                          <div className="grid gap-3 sm:grid-cols-2">
                            <SessionMetric
                              label="ID"
                              value={contextId}
                              detail={contextDetail}
                            />
                            <SessionMetric
                              label="Related Run"
                              value={relatedRunLink?.run.id || "No linked run"}
                              detail={
                                relatedRunLink
                                  ? `${relatedRunLink.run.run_kind} · ${relatedRunLink.run.status}`
                                  : "No action run linkage"
                              }
                            />
                            <SessionMetric
                              label="Runtime Agent"
                              value={runtimeAgentId || "No agent linkage"}
                              detail={runtimeAgentDetail}
                            />
                            <SessionMetric
                              label="Workspace"
                              value={projectId || "No project linkage"}
                              detail={storyId ? `story ${storyId}` : "No story linkage"}
                            />
                          </div>

                          <RelationshipStrip
                            label="Relationship Strip"
                            items={[
                              {
                                key: `context-${contextKind}-${contextId}`,
                                label: `${contextKind} ${contextId}`,
                                tone:
                                  contextKind === "approval"
                                    ? "approval"
                                    : contextKind === "issue"
                                      ? "issue"
                                      : "event",
                                active: true,
                                onClick: () => {
                                  revealSelectedSessionContextRow();
                                },
                              },
                              relatedRunLink
                                ? {
                                    key: `run-${relatedRunLink.run.id}`,
                                    label: `run ${relatedRunLink.run.id}`,
                                    tone: "run" as const,
                                    onClick: () => {
                                      setSelectedRunId(relatedRunLink.run.id);
                                      setSelectedRunResultIndex(0);
                                    },
                                  }
                                : null,
                              relatedRunLink && relatedRunResult
                                ? {
                                    key: `outcome-${relatedRunLink.run.id}-${relatedRunLink.resultIndex}`,
                                    label: `outcome ${relatedRunLink.resultIndex + 1}`,
                                    tone: "outcome" as const,
                                    onClick: () => {
                                      setSelectedRunId(relatedRunLink.run.id);
                                      setSelectedRunResultIndex(relatedRunLink.resultIndex);
                                    },
                                  }
                                : null,
                              relatedApprovalId && contextKind !== "approval"
                                ? {
                                    key: `approval-${relatedApprovalId}`,
                                    label: `approval ${relatedApprovalId}`,
                                    tone: "approval" as const,
                                    onClick: () => {
                                      syncLinkedSelection({
                                        approvalId: relatedApprovalId,
                                        issueId: relatedIssueId,
                                        runtimeAgentId,
                                        event: eventContext,
                                      });
                                    },
                                  }
                                : null,
                              relatedIssueId && contextKind !== "issue"
                                ? {
                                    key: `issue-${relatedIssueId}`,
                                    label: `issue ${relatedIssueId}`,
                                    tone: "issue" as const,
                                    onClick: () => {
                                      syncLinkedSelection({
                                        approvalId: relatedApprovalId,
                                        issueId: relatedIssueId,
                                        runtimeAgentId,
                                        event: eventContext,
                                      });
                                    },
                                  }
                                : null,
                              runtimeAgentId
                                ? {
                                    key: `agent-${runtimeAgentId}`,
                                    label: `agent ${runtimeAgentId}`,
                                    tone: "agent" as const,
                                    onClick: () => {
                                      revealSelectedSessionContextInAgentTimeline();
                                    },
                                  }
                                : null,
                            ].filter(Boolean) as RelationshipStripItem[]}
                          />

                          {(projectId || storyId || runtimeAgentId || relatedApprovalId || relatedIssueId) && (
                            <div className="flex flex-wrap gap-2">
                              {projectId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  project {projectId}
                                </Badge>
                              )}
                              {storyId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                >
                                  story {storyId}
                                </Badge>
                              )}
                              {runtimeAgentId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  agent {runtimeAgentId}
                                </Badge>
                              )}
                              {relatedApprovalId && contextKind !== "approval" && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                >
                                  approval {relatedApprovalId}
                                </Badge>
                              )}
                              {relatedIssueId && contextKind !== "issue" && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                >
                                  issue {relatedIssueId}
                                </Badge>
                              )}
                            </div>
                          )}

                          <div className="flex flex-wrap gap-2">
                            {approvalContext?.status === "pending" && (
                              <>
                                <Button
                                  size="sm"
                                  className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                  disabled={Boolean(busyActionKey)}
                                  onClick={() => {
                                    void approveApproval(approvalContext);
                                  }}
                                >
                                  {busyActionKey === `approval-approve:${approvalContext.id}` ? "Approving..." : "Approve"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  disabled={Boolean(busyActionKey)}
                                  onClick={() => {
                                    void rejectApproval(approvalContext);
                                  }}
                                >
                                  {busyActionKey === `approval-reject:${approvalContext.id}` ? "Rejecting..." : "Reject"}
                                </Button>
                              </>
                            )}
                            {approvalContext?.status === "approved" && (
                              <Button
                                size="sm"
                                className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                disabled={Boolean(busyActionKey)}
                                onClick={() => {
                                  void applyApproval(approvalContext);
                                }}
                              >
                                {busyActionKey === `approval-apply:${approvalContext.id}` ? "Applying..." : "Apply"}
                              </Button>
                            )}
                            {issueContext?.status === "open" && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                disabled={Boolean(busyActionKey)}
                                onClick={() => {
                                  void resolveIssue(issueContext);
                                }}
                              >
                                {busyActionKey === `issue-resolve:${issueContext.id}` ? "Resolving..." : "Resolve"}
                              </Button>
                            )}
                            {runtimeAgentId && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                onClick={() => {
                                  focusRuntimeAgent(runtimeAgentId, true);
                                }}
                              >
                                Open agent
                              </Button>
                            )}
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                revealSelectedSessionContextRow();
                              }}
                            >
                              Reveal session row
                            </Button>
                            {runtimeAgentId && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                onClick={() => {
                                  revealSelectedSessionContextInAgentTimeline();
                                }}
                              >
                                Reveal in agent timeline
                              </Button>
                            )}
                            {relatedRunLink && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                onClick={() => {
                                  setSelectedRunId(relatedRunLink.run.id);
                                  setSelectedRunResultIndex(relatedRunLink.resultIndex);
                                }}
                              >
                                Open related outcome
                              </Button>
                            )}
                            {workspaceHref && (
                              <Link
                                href={workspaceHref}
                                className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                              >
                                Open workspace
                              </Link>
                            )}
                          </div>

                          {relatedOutcome && (
                            <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                Related Outcome
                              </p>
                              <p className="mt-2 text-[13px] font-semibold text-[#37352f]">
                                {relatedOutcome.title}
                              </p>
                              <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                {relatedOutcome.subtitle || "No outcome subtype"}
                              </p>
                              <p className="mt-2 text-[12px] text-[#6b6b6b]">{relatedOutcome.message}</p>
                            </div>
                          )}

                          <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Payload
                            </p>
                            <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                              {formatJson(payload)}
                            </pre>
                          </div>
                        </div>
                      );
                    })()
                  )}
                </CardContent>
              </Card>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}
