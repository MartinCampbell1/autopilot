"use client";

import { useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import {
  asRecord,
  describeRunResult,
  eventFamily,
  matchesSearch,
  outcomeRuntimeAgentIds,
  runMatchesSearch,
  toStringValue,
} from "@/lib/control-plane-data";
import {
  isPersistedAgentTimelineStateEmpty,
  sanitizeOperatorVisibilityState,
  visibleEntriesByOperatorVisibilityState,
} from "@/lib/control-plane-operator-state";
import { agentTimelineEntryKey, resolveAgentTimelineRunLink, withSelectedItem } from "@/lib/control-plane-linking";
import {
  type AgentPriorityQueueKind,
  type AgentScopedOutcome,
  type AgentTimelineEntry,
} from "@/lib/control-plane-models";
import {
  agentTimelinePriority,
  countTriagePriorities,
  matchesAgentOutcomeFilter,
  matchesAgentTimelineFilter,
  matchesRunFilter,
  nextBestTriageItem,
  nextTriageEntryByPriority,
  triageQueuePosition,
} from "@/lib/control-plane-triage";
import { useControlPlaneAgentTimelineSelection } from "@/lib/use-control-plane-agent-timeline-selection";
import type { ExecutionAgentActionRunRecord, ExecutionRuntimeAgentDetail } from "@/lib/types";

type UseControlPlaneRuntimeAgentModelArgs = {
  selectedAgentId: string;
  selectedAgent: ExecutionRuntimeAgentDetail | null;
  linkedRuns: ExecutionAgentActionRunRecord[];
  agentActivityFilter: string;
  agentActivitySearch: string;
  agentTimelineFilter: string;
  agentTimelineSearch: string;
  dismissedAgentTimelineKeys: string[];
  snoozedAgentTimelineUntil: Record<string, number>;
  lineageQueueNow: number;
  selectedAgentTimelineKey: string;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
  setExpandedAgentPriorityQueues: Dispatch<SetStateAction<AgentPriorityQueueKind[]>>;
  selectedAgentTimelineEntryRef: MutableRefObject<AgentTimelineEntry | null>;
};

function shadowAuditSourceLabel(entry: AgentTimelineEntry["shadowAudit"]): string {
  const sourceName = (entry?.source_name || "").trim();
  if (sourceName) return sourceName;
  const sourceKind = (entry?.source_kind || "").trim();
  return sourceKind ? sourceKind.replaceAll("_", " ") : "shadow audit";
}

function shadowAuditBlockedOwnerLabel(entry: AgentTimelineEntry["shadowAudit"]): string {
  const ownerKind = (entry?.blocked_artifact_owner_kind || "").trim();
  if (!ownerKind) return "blocked handoff";
  return ownerKind.replaceAll("_", " ");
}

function shadowAuditMessage(entry: AgentTimelineEntry["shadowAudit"]): string {
  if (!entry) return "Blocked handoff requires explicit review.";
  if (entry.summary) return entry.summary;
  if (entry.findings.length > 0) return entry.findings.join(" · ");
  return "Blocked handoff requires explicit review.";
}

export function useControlPlaneRuntimeAgentModel({
  selectedAgentId,
  selectedAgent,
  linkedRuns,
  agentActivityFilter,
  agentActivitySearch,
  agentTimelineFilter,
  agentTimelineSearch,
  dismissedAgentTimelineKeys,
  snoozedAgentTimelineUntil,
  lineageQueueNow,
  selectedAgentTimelineKey,
  setSelectedAgentTimelineKey,
  setExpandedAgentPriorityQueues,
  selectedAgentTimelineEntryRef,
}: UseControlPlaneRuntimeAgentModelArgs) {
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
      const defaultToRunScope =
        run.runtime_agent_ids.length === 1 && run.runtime_agent_ids[0] === selectedAgentId;
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

    const shadowAuditEntries = new Map<string, AgentTimelineEntry>();
    const mergeShadowAuditEntry = (
      entry: NonNullable<ExecutionAgentActionRunRecord["shadow_audits"]>[number],
      options?: {
        runId?: string;
        taskId?: string;
      }
    ) => {
      const existing = shadowAuditEntries.get(entry.id);
      shadowAuditEntries.set(entry.id, {
        kind: "shadow_audit",
        id: entry.id,
        timestamp: entry.resolved_at || entry.updated_at || entry.created_at,
        status: entry.status,
        title: shadowAuditSourceLabel(entry),
        subtitle: `${entry.action || "review"} · ${shadowAuditBlockedOwnerLabel(entry)}`,
        message: shadowAuditMessage(entry),
        shadowAudit: entry,
        shadowAuditTaskId:
          existing?.shadowAuditTaskId ||
          options?.taskId ||
          (entry.blocked_artifact_owner_kind === "runtime_agent_task"
            ? entry.blocked_artifact_owner_id
            : ""),
        shadowAuditRunId:
          existing?.shadowAuditRunId ||
          options?.runId ||
          (entry.source_kind === "agent_action_run" ? entry.source_id : "") ||
          toStringValue(entry.metadata?.agent_action_run_id) ||
          toStringValue(entry.metadata?.run_id),
      });
    };

    agentScopedRuns.forEach((run) => {
      (run.shadow_audits || []).forEach((shadowAudit) => {
        mergeShadowAuditEntry(shadowAudit, { runId: run.id });
      });
    });

    (selectedAgent.async_tasks || []).forEach((task) => {
      (task.shadow_audits || []).forEach((shadowAudit) => {
        mergeShadowAuditEntry(shadowAudit, {
          runId: task.agent_action_run_id,
          taskId: task.id,
        });
      });
    });

    entries.push(...shadowAuditEntries.values());

    return entries.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        left.kind.localeCompare(right.kind) ||
        left.id.localeCompare(right.id)
    );
  }, [agentScopedRuns, selectedAgent]);

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
              entry.shadowAudit,
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
      shadow_audits: activeAgentTimelineEntries.filter((entry) => entry.kind === "shadow_audit")
        .length,
      attention: activeAgentTimelineEntries.filter((entry) =>
        matchesAgentTimelineFilter(entry, "attention")
      ).length,
    }),
    [activeAgentTimelineEntries]
  );

  const { selectedAgentTimelineEntry } = useControlPlaneAgentTimelineSelection({
    selectedAgentId,
    filteredAgentTimelineEntries,
    selectedAgentTimelineKey,
    setSelectedAgentTimelineKey,
    setExpandedAgentPriorityQueues,
    selectedAgentTimelineEntryRef,
  });

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
  const latestAgentShadowAuditEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "shadow_audit") ?? null,
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

  const currentAgentPriorityQueue = useMemo<AgentPriorityQueueKind | "">(() => {
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
  }, [filteredAgentTimelineEntries, selectedAgentTimelinePriority]);

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

  const selectedAgentTimelineEntryKeyValue = selectedAgentTimelineEntry
    ? agentTimelineEntryKey(selectedAgentTimelineEntry)
    : "";

  return {
    agentScopedRuns,
    agentScopedOutcomes,
    filteredAgentScopedRuns,
    filteredAgentScopedOutcomes,
    agentTimelineEntries,
    activeAgentTimelineEntries,
    filteredAgentTimelineEntries,
    agentTimelineFilterCounts,
    selectedAgentTimelineEntry,
    visibleAgentTimelineEntries,
    latestAgentApprovalEntry,
    latestAgentIssueEntry,
    latestAgentEventEntry,
    latestAgentShadowAuditEntry,
    hiddenAgentTimelineEntryCount,
    persistedAgentTimelineState,
    persistedDismissedAgentTimelineCount,
    persistedSnoozedAgentTimelineCount,
    hasPersistedAgentTimelinePreferences,
    selectedAgentTimelineRunLink,
    agentTimelinePriorityCounts,
    nextBestAgentTimelineEntry,
    selectedAgentTimelinePriority,
    currentAgentPriorityQueue,
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    criticalAgentTimelineQueue,
    highAgentTimelineQueue,
    criticalAgentTimelinePosition,
    highAgentTimelinePosition,
    nextCriticalAgentTimelineEntry,
    nextHighAgentTimelineEntry,
    selectedAgentTimelineEntryKeyValue,
  };
}
