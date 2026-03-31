import { useCallback, useEffect, useMemo, type Dispatch, type MutableRefObject, type SetStateAction } from "react";
import type { AgentTimelineEntry, SessionLineageEntry, TriageInboxFeedback, TriageInboxFeedbackGroup, TriageInboxItem } from "@/lib/control-plane-models";
import { agentTimelineEntryKey } from "@/lib/control-plane-linking";
import { agentTimelineEntryStatusClass, agentTimelinePriority, sessionLineagePriority } from "@/lib/control-plane-triage";
import { passStatusClass } from "@/lib/control-plane-ui";

type UseControlPlaneTriageInboxArgs = {
  nextAttentionSessionLineageEntry: SessionLineageEntry | null;
  attentionSessionLineageEntries: SessionLineageEntry[];
  selectedSessionLineageEntry: SessionLineageEntry | null;
  focusSessionLineageEntry: (entry: SessionLineageEntry, filter: string) => void;
  snoozeSessionLineageQueueEntry: (filter: "attention" | "decisions", entry: SessionLineageEntry, minutes?: number) => void;
  dismissSessionLineageQueueEntry: (filter: "attention" | "decisions", entry: SessionLineageEntry) => void;
  nextDecisionSessionLineageEntry: SessionLineageEntry | null;
  decisionSessionLineageEntries: SessionLineageEntry[];
  nextCriticalAgentTimelineEntry: AgentTimelineEntry | null;
  criticalAgentTimelineEntries: AgentTimelineEntry[];
  selectedAgentTimelineEntryKeyValue: string;
  inspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  snoozeAgentTimelineEntry: (entry: AgentTimelineEntry, minutes?: number) => void;
  dismissAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  nextHighAgentTimelineEntry: AgentTimelineEntry | null;
  highAgentTimelineEntries: AgentTimelineEntry[];
  selectedTriageInboxKey: string;
  setSelectedTriageInboxKey: Dispatch<SetStateAction<string>>;
  triageInboxFeedbackHistory: TriageInboxFeedback[];
  setTriageInboxFeedbackHistory: Dispatch<SetStateAction<TriageInboxFeedback[]>>;
  triageInboxFeedbackFilter: "all" | "success" | "info";
  setTriageInboxFeedbackFilter: Dispatch<SetStateAction<"all" | "success" | "info">>;
  setExpandedTriageInboxResultGroups: Dispatch<SetStateAction<string[]>>;
  selectedTriageInboxKeyRef: MutableRefObject<string>;
  selectedAgentId: string;
  selectedSessionId: string;
  recordTriageInboxFeedback: (
    itemKey: string,
    itemLabel: string,
    message: string,
    tone?: "info" | "success"
  ) => void;
  triageInboxFeedbackLimit: number;
};

export function useControlPlaneTriageInbox({
  nextAttentionSessionLineageEntry,
  attentionSessionLineageEntries,
  selectedSessionLineageEntry,
  focusSessionLineageEntry,
  snoozeSessionLineageQueueEntry,
  dismissSessionLineageQueueEntry,
  nextDecisionSessionLineageEntry,
  decisionSessionLineageEntries,
  nextCriticalAgentTimelineEntry,
  criticalAgentTimelineEntries,
  selectedAgentTimelineEntryKeyValue,
  inspectAgentTimelineEntry,
  snoozeAgentTimelineEntry,
  dismissAgentTimelineEntry,
  nextHighAgentTimelineEntry,
  highAgentTimelineEntries,
  selectedTriageInboxKey,
  setSelectedTriageInboxKey,
  triageInboxFeedbackHistory,
  setTriageInboxFeedbackHistory,
  triageInboxFeedbackFilter,
  setTriageInboxFeedbackFilter,
  setExpandedTriageInboxResultGroups,
  selectedTriageInboxKeyRef,
  selectedAgentId,
  selectedSessionId,
  recordTriageInboxFeedback,
  triageInboxFeedbackLimit,
}: UseControlPlaneTriageInboxArgs) {
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
    () => visibleTriageInboxFeedbackHistory.slice(1, triageInboxFeedbackLimit),
    [triageInboxFeedbackLimit, visibleTriageInboxFeedbackHistory]
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
  }, [selectedTriageInboxKey, selectedTriageInboxKeyRef]);
  useEffect(() => {
    setTriageInboxFeedbackHistory([]);
    setTriageInboxFeedbackFilter("all");
    setExpandedTriageInboxResultGroups([]);
  }, [selectedAgentId, selectedSessionId, setExpandedTriageInboxResultGroups, setTriageInboxFeedbackFilter, setTriageInboxFeedbackHistory]);
  useEffect(() => {
    const availableKeys = groupedRecentTriageInboxFeedback.map((group) => group.itemKey);
    setExpandedTriageInboxResultGroups((current) => {
      const next = current.filter((key) => availableKeys.includes(key));
      if (next.length > 0 || availableKeys.length === 0) return next;
      return [availableKeys[0]];
    });
  }, [groupedRecentTriageInboxFeedback, setExpandedTriageInboxResultGroups]);

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
  }, [setSelectedTriageInboxKey, triageInboxItems]);
  const inspectTriageInboxItem = useCallback((item: TriageInboxItem) => {
    setSelectedTriageInboxKey(item.key);
    item.onInspect();
  }, [setSelectedTriageInboxKey]);
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
    [nextTriageInboxCursorKey, setSelectedTriageInboxKey]
  );
  const snoozeTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} snoozed for 15m.`, "info");
      item.onSnooze();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback, setSelectedTriageInboxKey]
  );
  const dismissTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} dismissed from inbox.`, "info");
      item.onDismiss();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback, setSelectedTriageInboxKey]
  );
  const syncTriageInboxCursorToSelection = useCallback(() => {
    if (!syncedTriageInboxItem) return;
    setSelectedTriageInboxKey(syncedTriageInboxItem.key);
  }, [setSelectedTriageInboxKey, syncedTriageInboxItem]);
  const toggleTriageInboxResultGroup = useCallback((itemKey: string) => {
    if (!itemKey) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(itemKey)
        ? current.filter((key) => key !== itemKey)
        : [...current, itemKey]
    );
  }, [setExpandedTriageInboxResultGroups]);
  const expandAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups(
      groupedRecentTriageInboxFeedback.map((group) => group.itemKey)
    );
  }, [groupedRecentTriageInboxFeedback, setExpandedTriageInboxResultGroups]);
  const collapseAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups([]);
  }, [setExpandedTriageInboxResultGroups]);
  const openCurrentTriageInboxResultGroup = useCallback(() => {
    if (!currentTriageInboxFeedbackGroup) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(currentTriageInboxFeedbackGroup.itemKey)
        ? current
        : [...current, currentTriageInboxFeedbackGroup.itemKey]
    );
  }, [currentTriageInboxFeedbackGroup, setExpandedTriageInboxResultGroups]);

  useEffect(() => {
    if (!triageInboxItems.length) {
      setSelectedTriageInboxKey("");
      return;
    }
    setSelectedTriageInboxKey((current) => {
      if (triageInboxItems.some((item) => item.key === current)) return current;
      return triageInboxItems[0]?.key || "";
    });
  }, [setSelectedTriageInboxKey, triageInboxItems]);
  return {
    triageInboxItems,
    triageInboxItemCount,
    selectedTriageInboxItem,
    triageInboxFeedbackCounts,
    triageInboxFeedback,
    recentTriageInboxFeedback,
    groupedRecentTriageInboxFeedback,
    currentTriageInboxFeedbackGroup,
    syncedTriageInboxItem,
    advanceTriageInboxCursor,
    inspectTriageInboxItem,
    openTriageInboxHistoryGroup,
    inspectAndAdvanceTriageInboxItem,
    snoozeTriageInboxItem,
    dismissTriageInboxItem,
    syncTriageInboxCursorToSelection,
    toggleTriageInboxResultGroup,
    expandAllTriageInboxResultGroups,
    collapseAllTriageInboxResultGroups,
    openCurrentTriageInboxResultGroup,
  };
}
