"use client";

import {
  useEffect,
  useMemo,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import {
  AGENT_PRIORITY_QUEUE_KEYS,
  type AgentPriorityQueueKind,
  type AgentTimelineEntry,
} from "@/lib/control-plane-models";
import { agentTimelineEntryKey } from "@/lib/control-plane-linking";

type UseControlPlaneAgentTimelineSelectionArgs = {
  selectedAgentId: string;
  filteredAgentTimelineEntries: AgentTimelineEntry[];
  selectedAgentTimelineKey: string;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
  setExpandedAgentPriorityQueues: Dispatch<SetStateAction<AgentPriorityQueueKind[]>>;
  selectedAgentTimelineEntryRef: MutableRefObject<AgentTimelineEntry | null>;
};

export function useControlPlaneAgentTimelineSelection({
  selectedAgentId,
  filteredAgentTimelineEntries,
  selectedAgentTimelineKey,
  setSelectedAgentTimelineKey,
  setExpandedAgentPriorityQueues,
  selectedAgentTimelineEntryRef,
}: UseControlPlaneAgentTimelineSelectionArgs) {
  useEffect(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, [selectedAgentId, setExpandedAgentPriorityQueues]);

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
  }, [filteredAgentTimelineEntries, setSelectedAgentTimelineKey]);

  const selectedAgentTimelineEntry = useMemo(
    () =>
      filteredAgentTimelineEntries.find(
        (entry) => agentTimelineEntryKey(entry) === selectedAgentTimelineKey
      ) ?? filteredAgentTimelineEntries[0] ?? null,
    [filteredAgentTimelineEntries, selectedAgentTimelineKey]
  );

  useEffect(() => {
    selectedAgentTimelineEntryRef.current = selectedAgentTimelineEntry;
  }, [selectedAgentTimelineEntry, selectedAgentTimelineEntryRef]);

  return {
    selectedAgentTimelineEntry,
  };
}
