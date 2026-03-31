"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";
import { type SanitizedLineageQueueState, buildScopedStorageKey, emptySnoozedVisibilityRecord, emptyVisibilityKeysRecord } from "@/lib/control-plane-operator-state";
import type { PendingLineageAutoAdvance } from "@/lib/use-control-plane-actions";
import { buildQueueAdvanceFeedback, describeSessionQueueAdvanceReason, nextSessionLineageQueueEntry } from "@/lib/control-plane-triage";
import { sessionQueueAdvanceTarget } from "@/lib/control-plane-linking";
import { SESSION_LINEAGE_QUEUE_KEYS, type LineageQueueKind, type SessionLineageEntry } from "@/lib/control-plane-models";

const LINEAGE_QUEUE_STORAGE_PREFIX = "control-plane:lineage-queue:";

type UseControlPlaneSessionLineageQueuesArgs = {
  attentionSessionLineageEntries: SessionLineageEntry[];
  decisionSessionLineageEntries: SessionLineageEntry[];
  selectedSessionLineageEntry: SessionLineageEntry | null;
  sessionLineageFilter: string;
  currentSessionLineageQueue: LineageQueueKind | "";
  selectedSessionId: string;
  persistedLineageQueueState: SanitizedLineageQueueState<LineageQueueKind>;
  pendingLineageAutoAdvance: PendingLineageAutoAdvance | null;
  setDismissedLineageQueueKeys: Dispatch<SetStateAction<Record<LineageQueueKind, string[]>>>;
  setSnoozedLineageQueueUntil: Dispatch<
    SetStateAction<Record<LineageQueueKind, Record<string, number>>>
  >;
  setLineageQueueNow: Dispatch<SetStateAction<number>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setExpandedSessionLineageQueues: Dispatch<SetStateAction<LineageQueueKind[]>>;
  setSessionQueueAdvanceFeedback: Dispatch<
    SetStateAction<ReturnType<typeof buildQueueAdvanceFeedback> | null>
  >;
  setPendingLineageAutoAdvance: Dispatch<SetStateAction<PendingLineageAutoAdvance | null>>;
  setSessionLineageFilter: Dispatch<SetStateAction<string>>;
  focusSessionLineageEntry: (entry: SessionLineageEntry, filter: string) => void;
};

export function useControlPlaneSessionLineageQueues({
  attentionSessionLineageEntries,
  decisionSessionLineageEntries,
  selectedSessionLineageEntry,
  sessionLineageFilter,
  currentSessionLineageQueue,
  selectedSessionId,
  persistedLineageQueueState,
  pendingLineageAutoAdvance,
  setDismissedLineageQueueKeys,
  setSnoozedLineageQueueUntil,
  setLineageQueueNow,
  setNotice,
  setErrorMessage,
  setExpandedSessionLineageQueues,
  setSessionQueueAdvanceFeedback,
  setPendingLineageAutoAdvance,
  setSessionLineageFilter,
  focusSessionLineageEntry,
}: UseControlPlaneSessionLineageQueuesArgs) {
  const advanceSessionLineageQueue = useCallback(
    (filter: "attention" | "decisions") => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const previousEntry = selectedSessionLineageEntry;
      const nextEntry = nextSessionLineageQueueEntry(entries, selectedSessionLineageEntry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
          title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
          detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
          nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
          previousTarget: previousEntry
            ? sessionQueueAdvanceTarget(sessionLineageFilter, previousEntry)
            : null,
          reasonDetails: nextReason,
        })
      );
      focusSessionLineageEntry(nextEntry, filter);
    },
    [
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      focusSessionLineageEntry,
      selectedSessionLineageEntry,
      sessionLineageFilter,
      setSessionQueueAdvanceFeedback,
    ]
  );

  const advanceSessionLineageQueueFromEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry | null) => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const nextEntry = nextSessionLineageQueueEntry(entries, entry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
          title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
          detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
          nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
          previousTarget: entry ? sessionQueueAdvanceTarget(filter, entry) : null,
          reasonDetails: nextReason,
        })
      );
      focusSessionLineageEntry(nextEntry, filter);
    },
    [
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      focusSessionLineageEntry,
      setSessionQueueAdvanceFeedback,
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
          previousEntry: entry,
          previousFilter: filter,
        });
      }
    },
    [
      selectedSessionLineageEntry,
      setDismissedLineageQueueKeys,
      setLineageQueueNow,
      setPendingLineageAutoAdvance,
    ]
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
    [
      selectedSessionLineageEntry,
      setLineageQueueNow,
      setPendingLineageAutoAdvance,
      setSnoozedLineageQueueUntil,
    ]
  );

  const restoreSessionLineageQueue = useCallback(
    (filter: LineageQueueKind) => {
      setDismissedLineageQueueKeys((current) => ({
        ...current,
        [filter]: [],
      }));
      setSnoozedLineageQueueUntil((current) => ({
        ...current,
        [filter]: {},
      }));
      setLineageQueueNow(Date.now());
    },
    [setDismissedLineageQueueKeys, setLineageQueueNow, setSnoozedLineageQueueUntil]
  );

  const resetSessionLineageQueuePreferences = useCallback(() => {
    setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
    setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
    setLineageQueueNow(Date.now());
    setNotice("Session lineage queue state reset.");
    setErrorMessage("");
    if (selectedSessionId && typeof window !== "undefined") {
      window.localStorage.removeItem(
        buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId)
      );
    }
  }, [
    selectedSessionId,
    setDismissedLineageQueueKeys,
    setErrorMessage,
    setLineageQueueNow,
    setNotice,
    setSnoozedLineageQueueUntil,
  ]);

  const toggleSessionLineageQueueExpansion = useCallback(
    (filter: LineageQueueKind) => {
      setExpandedSessionLineageQueues((current) =>
        current.includes(filter)
          ? current.filter((key) => key !== filter)
          : [...current, filter]
      );
    },
    [setExpandedSessionLineageQueues]
  );

  const expandAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, [setExpandedSessionLineageQueues]);

  const collapseAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([]);
  }, [setExpandedSessionLineageQueues]);

  const openCurrentSessionLineageQueue = useCallback(() => {
    if (!currentSessionLineageQueue) return;
    setExpandedSessionLineageQueues((current) =>
      current.includes(currentSessionLineageQueue)
        ? current
        : [...current, currentSessionLineageQueue]
    );
  }, [currentSessionLineageQueue, setExpandedSessionLineageQueues]);

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
  }, [persistedLineageQueueState, selectedSessionId, setErrorMessage, setNotice]);

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
      setSessionQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
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
        })
      );
      focusSessionLineageEntry(nextEntry, pendingLineageAutoAdvance.filter);
    } else {
      setSessionQueueAdvanceFeedback(
        buildQueueAdvanceFeedback({
          title: `${pendingLineageAutoAdvance.filter === "attention" ? "Attention" : "Decision"} queue cleared`,
          detail: `No remaining ${pendingLineageAutoAdvance.filter} items were available after the previous queue action.`,
          previousTarget: pendingLineageAutoAdvance.previousEntry
            ? sessionQueueAdvanceTarget(
                pendingLineageAutoAdvance.previousFilter,
                pendingLineageAutoAdvance.previousEntry
              )
            : null,
        })
      );
      setSessionLineageFilter(pendingLineageAutoAdvance.filter);
    }
  }, [
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    focusSessionLineageEntry,
    pendingLineageAutoAdvance,
    setPendingLineageAutoAdvance,
    setSessionLineageFilter,
    setSessionQueueAdvanceFeedback,
  ]);

  return {
    advanceSessionLineageQueue,
    advanceSessionLineageQueueFromEntry,
    dismissSessionLineageQueueEntry,
    snoozeSessionLineageQueueEntry,
    restoreSessionLineageQueue,
    resetSessionLineageQueuePreferences,
    toggleSessionLineageQueueExpansion,
    expandAllSessionLineageQueues,
    collapseAllSessionLineageQueues,
    openCurrentSessionLineageQueue,
    exportSessionLineageQueuePreferences,
  };
}
