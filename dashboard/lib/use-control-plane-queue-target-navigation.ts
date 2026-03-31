"use client";

import { useCallback } from "react";
import { agentTimelineEntryKey } from "@/lib/control-plane-linking";
import type {
  AgentTimelineEntry,
  QueueAdvanceTarget,
  SessionLineageEntry,
} from "@/lib/control-plane-models";

type UseControlPlaneQueueTargetNavigationArgs = {
  focusSessionLineageEntry: (entry: SessionLineageEntry, filter: string) => void;
  restoreAgentTimelineEntryVisibility: (entryKey: string) => void;
  revealAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  inspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
};

export function useControlPlaneQueueTargetNavigation({
  focusSessionLineageEntry,
  restoreAgentTimelineEntryVisibility,
  revealAgentTimelineEntry,
  inspectAgentTimelineEntry,
}: UseControlPlaneQueueTargetNavigationArgs) {
  const openSessionQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "session-lineage") return;
      focusSessionLineageEntry(target.entry, target.filter);
    },
    [focusSessionLineageEntry]
  );

  const openAgentQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "agent-timeline") return;
      restoreAgentTimelineEntryVisibility(agentTimelineEntryKey(target.entry));
      revealAgentTimelineEntry(target.entry);
      inspectAgentTimelineEntry(target.entry);
    },
    [inspectAgentTimelineEntry, restoreAgentTimelineEntryVisibility, revealAgentTimelineEntry]
  );

  return {
    openSessionQueueAdvanceTarget,
    openAgentQueueAdvanceTarget,
  };
}
