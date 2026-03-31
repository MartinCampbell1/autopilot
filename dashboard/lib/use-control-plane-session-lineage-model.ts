"use client";

import { useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import {
  asRecord,
  describeRunResult,
  outcomeProjectId,
  outcomeProjectName,
  outcomeRuntimeAgentId,
  outcomeStoryId,
  outcomeStoryTitle,
  toStringValue,
} from "@/lib/control-plane-data";
import {
  isPersistedLineageQueueStateEmpty,
  sanitizeOperatorVisibilityState,
  visibleEntriesByOperatorVisibilityState,
} from "@/lib/control-plane-operator-state";
import { resolveSessionEventFromContext, withSelectedItem } from "@/lib/control-plane-linking";
import {
  SESSION_LINEAGE_QUEUE_KEYS,
  type LineageQueueKind,
  type SessionLineageEntry,
} from "@/lib/control-plane-models";
import {
  countTriagePriorities,
  matchesSessionLineageFilter,
  nextBestTriageItem,
  nextSessionLineageQueueEntry,
  sessionLineagePriority,
  sessionLineageQueuePosition,
  sessionLineageTraits,
} from "@/lib/control-plane-triage";
import { useControlPlaneSessionLineageSelection } from "@/lib/use-control-plane-session-lineage-selection";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  ExecutionPlaneCountMap,
  OrchestratorSessionDetail,
} from "@/lib/types";

type UseControlPlaneSessionLineageModelArgs = {
  approvalById: Map<string, ExecutionApprovalRecord>;
  issueById: Map<string, ExecutionIssueRecord>;
  linkedRuns: ExecutionAgentActionRunRecord[];
  selectedSession: OrchestratorSessionDetail | null;
  selectedSessionId: string;
  selectedRunId: string;
  selectedRunResultIndex: number;
  sessionLineageFilter: string;
  dismissedLineageQueueKeys: Record<LineageQueueKind, string[]>;
  snoozedLineageQueueUntil: Record<LineageQueueKind, Record<string, number>>;
  lineageQueueNow: number;
  selectedSessionLineageEntryRef: MutableRefObject<SessionLineageEntry | null>;
  sessionLineageFilterRef: MutableRefObject<string>;
  setExpandedSessionLineageQueues: Dispatch<SetStateAction<LineageQueueKind[]>>;
};

export function useControlPlaneSessionLineageModel({
  approvalById,
  issueById,
  linkedRuns,
  selectedSession,
  selectedSessionId,
  selectedRunId,
  selectedRunResultIndex,
  sessionLineageFilter,
  dismissedLineageQueueKeys,
  snoozedLineageQueueUntil,
  lineageQueueNow,
  selectedSessionLineageEntryRef,
  sessionLineageFilterRef,
  setExpandedSessionLineageQueues,
}: UseControlPlaneSessionLineageModelArgs) {
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

  const { selectedSessionLineageEntry } = useControlPlaneSessionLineageSelection({
    selectedSessionId,
    selectedRunId,
    selectedRunResultIndex,
    sessionLineageEntries,
    sessionLineageFilter,
    selectedSessionLineageEntryRef,
    sessionLineageFilterRef,
    setExpandedSessionLineageQueues,
  });

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
    () => sessionLineageEntries.filter((entry) => entry.approvalId || entry.issueId).length,
    [sessionLineageEntries]
  );

  const sessionLineageAttentionCount = useMemo(
    () =>
      sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "attention"))
        .length,
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
    () =>
      sessionLineageEntries.find((entry) => matchesSessionLineageFilter(entry, "agent-linked")) ??
      null,
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
    [decisionOperatorVisibilityState, decisionSessionLineageSourceEntries, lineageQueueNow]
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
    () => nextSessionLineageQueueEntry(attentionSessionLineageEntries, selectedSessionLineageEntry),
    [attentionSessionLineageEntries, selectedSessionLineageEntry]
  );

  const nextDecisionSessionLineageEntry = useMemo(
    () => nextSessionLineageQueueEntry(decisionSessionLineageEntries, selectedSessionLineageEntry),
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
    () =>
      Math.max(
        attentionSessionLineageSourceEntries.length - attentionSessionLineageEntries.length,
        0
      ),
    [attentionSessionLineageEntries.length, attentionSessionLineageSourceEntries.length]
  );

  const hiddenDecisionQueueCount = useMemo(
    () =>
      Math.max(
        decisionSessionLineageSourceEntries.length - decisionSessionLineageEntries.length,
        0
      ),
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
    () =>
      !isPersistedLineageQueueStateEmpty(
        persistedLineageQueueState,
        SESSION_LINEAGE_QUEUE_KEYS
      ),
    [persistedLineageQueueState]
  );

  const selectedSessionLineageTraits = useMemo(
    () => sessionLineageTraits(selectedSessionLineageEntry),
    [selectedSessionLineageEntry]
  );

  return {
    sessionLineageEntries,
    selectedSessionLineageEntry,
    filteredSessionLineageEntries,
    sessionLineagePriorityCounts,
    nextBestSessionLineageEntry,
    selectedSessionLineagePriority,
    visibleSessionLineageEntries,
    sessionLineageStatusCounts,
    sessionLineageDecisionCount,
    sessionLineageAttentionCount,
    sessionLineageEventCount,
    sessionLineageAgentCount,
    sessionLineageAgentLinkedCount,
    sessionLineageFilterCounts,
    latestAgentLinkedLineageEntry,
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    attentionSessionLineageQueue,
    decisionSessionLineageQueue,
    attentionQueuePosition,
    decisionQueuePosition,
    nextAttentionSessionLineageEntry,
    nextDecisionSessionLineageEntry,
    currentSessionLineageQueue,
    hiddenAttentionQueueCount,
    hiddenDecisionQueueCount,
    persistedLineageQueueState,
    persistedDismissedLineageQueueCount,
    persistedSnoozedLineageQueueCount,
    hasPersistedLineageQueuePreferences,
    selectedSessionLineageTraits,
  };
}
