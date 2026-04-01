"use client";

import {
  useEffect,
  useMemo,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import {
  SESSION_LINEAGE_QUEUE_KEYS,
  type LineageQueueKind,
  type SessionLineageEntry,
} from "@/lib/control-plane-models";

type UseControlPlaneSessionLineageSelectionArgs = {
  selectedSessionId: string;
  selectedRunId: string;
  selectedRunResultIndex: number;
  selectedSessionToolPermissionRuntimeId: string;
  selectedSessionAsyncTaskId: string;
  sessionLineageEntries: SessionLineageEntry[];
  sessionLineageFilter: string;
  selectedSessionLineageEntryRef: MutableRefObject<SessionLineageEntry | null>;
  sessionLineageFilterRef: MutableRefObject<string>;
  setExpandedSessionLineageQueues: Dispatch<SetStateAction<LineageQueueKind[]>>;
};

export function useControlPlaneSessionLineageSelection({
  selectedSessionId,
  selectedRunId,
  selectedRunResultIndex,
  selectedSessionToolPermissionRuntimeId,
  selectedSessionAsyncTaskId,
  sessionLineageEntries,
  sessionLineageFilter,
  selectedSessionLineageEntryRef,
  sessionLineageFilterRef,
  setExpandedSessionLineageQueues,
}: UseControlPlaneSessionLineageSelectionArgs) {
  const selectedSessionLineageEntry = useMemo(() => {
    if (selectedSessionToolPermissionRuntimeId) {
      return (
        sessionLineageEntries.find(
          (entry) => entry.toolPermissionRuntimeId === selectedSessionToolPermissionRuntimeId
        ) ?? null
      );
    }
    if (selectedSessionAsyncTaskId) {
      return (
        sessionLineageEntries.find((entry) => entry.asyncTaskId === selectedSessionAsyncTaskId) ??
        null
      );
    }
    if (selectedRunId) {
      return (
        sessionLineageEntries.find(
          (entry) => entry.runId === selectedRunId && entry.resultIndex === selectedRunResultIndex
        ) ?? null
      );
    }
    return sessionLineageEntries[0] ?? null;
  }, [
    selectedRunId,
    selectedRunResultIndex,
    selectedSessionToolPermissionRuntimeId,
    selectedSessionAsyncTaskId,
    sessionLineageEntries,
  ]);

  useEffect(() => {
    selectedSessionLineageEntryRef.current = selectedSessionLineageEntry;
  }, [selectedSessionLineageEntry, selectedSessionLineageEntryRef]);

  useEffect(() => {
    sessionLineageFilterRef.current = sessionLineageFilter;
  }, [sessionLineageFilter, sessionLineageFilterRef]);

  useEffect(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, [selectedSessionId, setExpandedSessionLineageQueues]);

  return {
    selectedSessionLineageEntry,
  };
}
