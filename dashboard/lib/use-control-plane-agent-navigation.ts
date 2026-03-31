"use client";

import { useCallback, type Dispatch, type SetStateAction } from "react";
import { toStringValue } from "@/lib/control-plane-data";
import {
  agentTimelineEntryKey,
  resolveAgentTimelineRunLink,
} from "@/lib/control-plane-linking";
import type { AgentTimelineEntry, LinkedSelectionContext } from "@/lib/control-plane-models";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
} from "@/lib/types";

type UseControlPlaneAgentNavigationArgs = {
  linkedRuns: ExecutionAgentActionRunRecord[];
  selectedAgent: ExecutionRuntimeAgentDetail | null;
  selectedAgentId: string;
  syncLinkedSelection: (context: LinkedSelectionContext) => void;
  setAgentTimelineFilter: Dispatch<SetStateAction<string>>;
  setAgentTimelineSearch: Dispatch<SetStateAction<string>>;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
};

export function useControlPlaneAgentNavigation({
  linkedRuns,
  selectedAgent,
  selectedAgentId,
  syncLinkedSelection,
  setAgentTimelineFilter,
  setAgentTimelineSearch,
  setSelectedAgentTimelineKey,
}: UseControlPlaneAgentNavigationArgs) {
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
    [setAgentTimelineFilter, setAgentTimelineSearch, setSelectedAgentTimelineKey]
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
    [linkedRuns, selectedAgent, selectedAgentId, setSelectedAgentTimelineKey, syncLinkedSelection]
  );

  return {
    focusAgentTimeline,
    inspectAgentTimelineEntry,
  };
}
