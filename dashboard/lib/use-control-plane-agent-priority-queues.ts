"use client";

import { useCallback, useEffect, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import type { OperatorVisibilityState } from "@/lib/control-plane-operator-state";
import {
  buildScopedStorageKey,
  sanitizePersistedAgentTimelineState,
} from "@/lib/control-plane-operator-state";
import type { PendingAgentPriorityAutoAdvance } from "@/lib/use-control-plane-actions";
import {
  agentTimelinePriority,
  buildQueueAdvanceFeedback,
  describeAgentQueueAdvanceReason,
  nextTriageEntryByPriority,
} from "@/lib/control-plane-triage";
import { agentQueueAdvanceTarget, agentTimelineEntryKey } from "@/lib/control-plane-linking";
import {
  AGENT_PRIORITY_QUEUE_KEYS,
  type AgentPriorityQueueKind,
  type AgentTimelineEntry,
} from "@/lib/control-plane-models";

const AGENT_TIMELINE_STORAGE_PREFIX = "control-plane:agent-timeline:";

type UseControlPlaneAgentPriorityQueuesArgs = {
  selectedAgentId: string;
  selectedAgentTimelineEntryRef: MutableRefObject<AgentTimelineEntry | null>;
  filteredAgentTimelineEntries: AgentTimelineEntry[];
  criticalAgentTimelineEntries: AgentTimelineEntry[];
  highAgentTimelineEntries: AgentTimelineEntry[];
  currentAgentPriorityQueue: AgentPriorityQueueKind | "";
  dismissedAgentTimelineKeys: string[];
  snoozedAgentTimelineUntil: Record<string, number>;
  lineageQueueNow: number;
  pendingAgentPriorityAutoAdvance: PendingAgentPriorityAutoAdvance | null;
  setDismissedAgentTimelineKeys: Dispatch<SetStateAction<string[]>>;
  setSnoozedAgentTimelineUntil: Dispatch<SetStateAction<Record<string, number>>>;
  setLineageQueueNow: Dispatch<SetStateAction<number>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setExpandedAgentPriorityQueues: Dispatch<SetStateAction<AgentPriorityQueueKind[]>>;
  setPendingAgentPriorityAutoAdvance: Dispatch<
    SetStateAction<PendingAgentPriorityAutoAdvance | null>
  >;
  setAgentQueueAdvanceFeedback: Dispatch<
    SetStateAction<ReturnType<typeof buildQueueAdvanceFeedback> | null>
  >;
  inspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
};

export function useControlPlaneAgentPriorityQueues({
  selectedAgentId,
  selectedAgentTimelineEntryRef,
  filteredAgentTimelineEntries,
  criticalAgentTimelineEntries,
  highAgentTimelineEntries,
  currentAgentPriorityQueue,
  dismissedAgentTimelineKeys,
  snoozedAgentTimelineUntil,
  lineageQueueNow,
  pendingAgentPriorityAutoAdvance,
  setDismissedAgentTimelineKeys,
  setSnoozedAgentTimelineUntil,
  setLineageQueueNow,
  setNotice,
  setErrorMessage,
  setExpandedAgentPriorityQueues,
  setPendingAgentPriorityAutoAdvance,
  setAgentQueueAdvanceFeedback,
  inspectAgentTimelineEntry,
}: UseControlPlaneAgentPriorityQueuesArgs) {
  const toggleAgentPriorityQueueExpansion = useCallback(
    (priority: AgentPriorityQueueKind) => {
      setExpandedAgentPriorityQueues((current) =>
        current.includes(priority)
          ? current.filter((key) => key !== priority)
          : [...current, priority]
      );
    },
    [setExpandedAgentPriorityQueues]
  );

  const expandAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, [setExpandedAgentPriorityQueues]);

  const collapseAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([]);
  }, [setExpandedAgentPriorityQueues]);

  const openCurrentAgentPriorityQueue = useCallback(() => {
    if (!currentAgentPriorityQueue) return;
    setExpandedAgentPriorityQueues((current) =>
      current.includes(currentAgentPriorityQueue)
        ? current
        : [...current, currentAgentPriorityQueue]
    );
  }, [currentAgentPriorityQueue, setExpandedAgentPriorityQueues]);

  const dismissAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
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
    },
    [
      selectedAgentTimelineEntryRef,
      setDismissedAgentTimelineKeys,
      setLineageQueueNow,
      setPendingAgentPriorityAutoAdvance,
    ]
  );

  const snoozeAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry, minutes = 15) => {
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
    },
    [
      selectedAgentTimelineEntryRef,
      setLineageQueueNow,
      setPendingAgentPriorityAutoAdvance,
      setSnoozedAgentTimelineUntil,
    ]
  );

  const restoreAgentTimelineHidden = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
  }, [setDismissedAgentTimelineKeys, setLineageQueueNow, setSnoozedAgentTimelineUntil]);

  const resetAgentTimelinePreferences = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
    setNotice("Agent timeline state reset.");
    setErrorMessage("");
    if (selectedAgentId && typeof window !== "undefined") {
      window.localStorage.removeItem(
        buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId)
      );
    }
  }, [
    selectedAgentId,
    setDismissedAgentTimelineKeys,
    setErrorMessage,
    setLineageQueueNow,
    setNotice,
    setSnoozedAgentTimelineUntil,
  ]);

  const exportAgentTimelinePreferences = useCallback(async () => {
    if (!selectedAgentId) return;
    const timelineState: OperatorVisibilityState = sanitizePersistedAgentTimelineState(
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
  }, [
    dismissedAgentTimelineKeys,
    lineageQueueNow,
    selectedAgentId,
    setErrorMessage,
    setNotice,
    snoozedAgentTimelineUntil,
  ]);

  const advanceAgentPriorityQueueFromEntry = useCallback(
    (priority: AgentPriorityQueueKind, entry: AgentTimelineEntry | null) => {
      const nextEntry = nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        entry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        priority
      );
      if (!nextEntry) return;
      const nextReason = describeAgentQueueAdvanceReason(nextEntry);
      setAgentQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
          title: `${priority === "critical" ? "Critical" : "High"} queue advanced`,
          detail: `Selected "${nextEntry.title}" as the next ${priority} item.`,
          nextTarget: agentQueueAdvanceTarget(priority, nextEntry),
          previousTarget: entry ? agentQueueAdvanceTarget(priority, entry) : null,
          reasonDetails: nextReason,
        })
      );
      inspectAgentTimelineEntry(nextEntry);
    },
    [filteredAgentTimelineEntries, inspectAgentTimelineEntry, setAgentQueueAdvanceFeedback]
  );

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
      setAgentQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
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
        })
      );
      inspectAgentTimelineEntry(nextEntry);
    } else {
      setAgentQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
          title: `${pendingAgentPriorityAutoAdvance.priority === "critical" ? "Critical" : "High"} queue cleared`,
          detail: `No remaining ${pendingAgentPriorityAutoAdvance.priority} items were available after the previous queue action.`,
          previousTarget: pendingAgentPriorityAutoAdvance.previousEntry
            ? agentQueueAdvanceTarget(
                pendingAgentPriorityAutoAdvance.priority,
                pendingAgentPriorityAutoAdvance.previousEntry
              )
            : null,
        })
      );
    }
  }, [
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    inspectAgentTimelineEntry,
    pendingAgentPriorityAutoAdvance,
    setAgentQueueAdvanceFeedback,
    setPendingAgentPriorityAutoAdvance,
  ]);

  return {
    toggleAgentPriorityQueueExpansion,
    expandAllAgentPriorityQueues,
    collapseAllAgentPriorityQueues,
    openCurrentAgentPriorityQueue,
    dismissAgentTimelineEntry,
    snoozeAgentTimelineEntry,
    restoreAgentTimelineHidden,
    resetAgentTimelinePreferences,
    exportAgentTimelinePreferences,
    advanceAgentPriorityQueueFromEntry,
  };
}
