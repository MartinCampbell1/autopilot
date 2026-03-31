"use client";

import { useCallback, useMemo } from "react";
import type {
  QueueAdvanceFeedback,
  QueueAdvanceFocusDelta,
  QueueAdvanceFocusSummary,
  QueueAdvanceNoticeActionProps,
  QueueAdvanceSignal,
} from "@/components/queue-advance-notice";
import type {
  AgentTimelineEntry,
  QueueAdvanceTarget,
  SessionLineageEntry,
} from "@/lib/control-plane-models";
import { buildQueueAdvanceFocusDelta } from "@/lib/control-plane-operator-state";
import {
  agentTimelineFilterClass,
  agentTimelineFilterLabel,
  buildQueueAdvanceFocusSummary,
  buildQueueAdvanceNoticeActionProps,
  sessionLineageFilterClass,
  sessionLineageFilterLabel,
} from "@/lib/control-plane-triage";

type FocusAgentTimeline = (
  filter: string,
  options?: {
    entry?: AgentTimelineEntry | null;
    search?: string;
  }
) => void;

type UseControlPlaneQueueAdvanceArgs = {
  sessionLineageFilter: string;
  sessionLineageEntriesCount: number;
  filteredSessionLineageEntriesCount: number;
  sessionLineageFilterCounts: Record<string, number>;
  focusSessionLineageEntry: (entry: SessionLineageEntry, filter: string) => void;
  setSessionLineageFilter: (value: string) => void;
  sessionQueueAdvanceFeedback: QueueAdvanceFeedback<QueueAdvanceTarget> | null;
  setSessionQueueFocusDelta: (value: QueueAdvanceFocusDelta | null) => void;
  currentSessionLineageQueue: string;
  openCurrentSessionLineageQueue: () => void;
  openSessionQueueAdvanceTarget: (target: QueueAdvanceTarget | null | undefined) => void;
  agentTimelineFilter: string;
  activeAgentTimelineEntriesCount: number;
  filteredAgentTimelineEntriesCount: number;
  agentTimelineFilterCounts: Record<string, number>;
  focusAgentTimeline: FocusAgentTimeline;
  inspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  agentQueueAdvanceFeedback: QueueAdvanceFeedback<QueueAdvanceTarget> | null;
  setAgentQueueFocusDelta: (value: QueueAdvanceFocusDelta | null) => void;
  currentAgentPriorityQueue: string;
  openCurrentAgentPriorityQueue: () => void;
  openAgentQueueAdvanceTarget: (target: QueueAdvanceTarget | null | undefined) => void;
};

export function useControlPlaneQueueAdvance({
  sessionLineageFilter,
  sessionLineageEntriesCount,
  filteredSessionLineageEntriesCount,
  sessionLineageFilterCounts,
  focusSessionLineageEntry,
  setSessionLineageFilter,
  sessionQueueAdvanceFeedback,
  setSessionQueueFocusDelta,
  currentSessionLineageQueue,
  openCurrentSessionLineageQueue,
  openSessionQueueAdvanceTarget,
  agentTimelineFilter,
  activeAgentTimelineEntriesCount,
  filteredAgentTimelineEntriesCount,
  agentTimelineFilterCounts,
  focusAgentTimeline,
  inspectAgentTimelineEntry,
  agentQueueAdvanceFeedback,
  setAgentQueueFocusDelta,
  currentAgentPriorityQueue,
  openCurrentAgentPriorityQueue,
  openAgentQueueAdvanceTarget,
}: UseControlPlaneQueueAdvanceArgs) {
  const sessionQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!sessionQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: sessionLineageFilter,
      total: sessionLineageEntriesCount,
      visible: filteredSessionLineageEntriesCount,
      labelForFilter: sessionLineageFilterLabel,
      classForFilter: sessionLineageFilterClass,
      noun: "lineage chains",
      scopeLabel: "session",
    });
  }, [
    filteredSessionLineageEntriesCount,
    sessionLineageEntriesCount,
    sessionLineageFilter,
    sessionQueueAdvanceFeedback,
  ]);

  const agentQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!agentQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: agentTimelineFilter,
      total: activeAgentTimelineEntriesCount,
      visible: filteredAgentTimelineEntriesCount,
      labelForFilter: agentTimelineFilterLabel,
      classForFilter: agentTimelineFilterClass,
      noun: "active timeline items",
      scopeLabel: "agent",
    });
  }, [
    activeAgentTimelineEntriesCount,
    agentQueueAdvanceFeedback,
    agentTimelineFilter,
    filteredAgentTimelineEntriesCount,
  ]);

  const applySessionQueueFocus = useCallback(
    (nextFilter: string, entry?: SessionLineageEntry | null) => {
      setSessionQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          sessionLineageFilterLabel(sessionLineageFilter),
          sessionLineageFilterLabel(nextFilter),
          sessionLineageFilterCounts[sessionLineageFilter] ?? sessionLineageEntriesCount,
          sessionLineageFilterCounts[nextFilter] ?? sessionLineageEntriesCount
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
      sessionLineageEntriesCount,
      sessionLineageFilter,
      sessionLineageFilterCounts,
      setSessionLineageFilter,
      setSessionQueueFocusDelta,
    ]
  );

  const applyAgentQueueFocus = useCallback(
    (nextFilter: string, entry?: AgentTimelineEntry | null) => {
      setAgentQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          agentTimelineFilterLabel(agentTimelineFilter),
          agentTimelineFilterLabel(nextFilter),
          agentTimelineFilterCounts[agentTimelineFilter] ?? activeAgentTimelineEntriesCount,
          agentTimelineFilterCounts[nextFilter] ?? activeAgentTimelineEntriesCount
        )
      );
      focusAgentTimeline(nextFilter, entry ? { entry } : undefined);
      if (entry) {
        inspectAgentTimelineEntry(entry);
      }
    },
    [
      activeAgentTimelineEntriesCount,
      agentTimelineFilter,
      agentTimelineFilterCounts,
      focusAgentTimeline,
      inspectAgentTimelineEntry,
      setAgentQueueFocusDelta,
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

  const sessionQueueAdvanceNoticeActions = useMemo<QueueAdvanceNoticeActionProps>(
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

  const agentQueueAdvanceNoticeActions = useMemo<QueueAdvanceNoticeActionProps>(
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

  return {
    sessionQueueAdvanceFocusSummary,
    agentQueueAdvanceFocusSummary,
    applySessionQueueFocus,
    applyAgentQueueFocus,
    focusSessionQueueAdvanceSignal,
    focusAgentQueueAdvanceSignal,
    sessionQueueAdvanceNoticeActions,
    agentQueueAdvanceNoticeActions,
  };
}
