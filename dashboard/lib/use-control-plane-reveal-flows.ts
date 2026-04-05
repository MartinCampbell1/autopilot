"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";
import { toStringValue } from "@/lib/control-plane-data";
import {
  agentTimelineEntryKey,
  agentTimelineRowDomId,
  resolveAgentTimelineEntryFromTarget,
  resolveAgentTimelineRunLink,
} from "@/lib/control-plane-linking";
import type {
  AgentTimelineEntry,
  LinkedSelectionContext,
  PendingAgentTimelineTarget,
  SessionLineageEntry,
} from "@/lib/control-plane-models";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
} from "@/lib/types";

function scrollToDomId(id: string): boolean {
  if (!id || typeof document === "undefined") return false;
  const node = document.getElementById(id);
  if (!node) return false;
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  return true;
}

type UseControlPlaneRevealFlowsArgs = {
  selectedAgentId: string;
  selectedAgent: ExecutionRuntimeAgentDetail | null;
  linkedRuns: ExecutionAgentActionRunRecord[];
  syncLinkedSelection: (payload: LinkedSelectionContext) => void;
  agentTimelineEntries: AgentTimelineEntry[];
  visibleAgentTimelineEntries: AgentTimelineEntry[];
  pendingAgentTimelineTarget: PendingAgentTimelineTarget | null;
  setPendingAgentTimelineTarget: Dispatch<SetStateAction<PendingAgentTimelineTarget | null>>;
  pendingSessionRowDomId: string;
  setPendingSessionRowDomId: Dispatch<SetStateAction<string>>;
  pendingAgentTimelineRowDomId: string;
  setPendingAgentTimelineRowDomId: Dispatch<SetStateAction<string>>;
  setDismissedAgentTimelineKeys: Dispatch<SetStateAction<string[]>>;
  setSnoozedAgentTimelineUntil: Dispatch<SetStateAction<Record<string, number>>>;
  setLineageQueueNow: Dispatch<SetStateAction<number>>;
  setAgentTimelineFilter: Dispatch<SetStateAction<string>>;
  setAgentTimelineSearch: Dispatch<SetStateAction<string>>;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
  setEntitySearch: Dispatch<SetStateAction<string>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedRunResultIndex: Dispatch<SetStateAction<number>>;
  setNotice: Dispatch<SetStateAction<string>>;
};

export function useControlPlaneRevealFlows({
  selectedAgentId,
  selectedAgent,
  linkedRuns,
  syncLinkedSelection,
  agentTimelineEntries,
  visibleAgentTimelineEntries,
  pendingAgentTimelineTarget,
  setPendingAgentTimelineTarget,
  pendingSessionRowDomId,
  setPendingSessionRowDomId,
  pendingAgentTimelineRowDomId,
  setPendingAgentTimelineRowDomId,
  setDismissedAgentTimelineKeys,
  setSnoozedAgentTimelineUntil,
  setLineageQueueNow,
  setAgentTimelineFilter,
  setAgentTimelineSearch,
  setSelectedAgentTimelineKey,
  setEntitySearch,
  setSelectedRunId,
  setSelectedRunResultIndex,
  setNotice,
}: UseControlPlaneRevealFlowsArgs) {
  const restoreAgentTimelineEntryVisibility = useCallback((entryKey: string) => {
    if (!entryKey) return;
    setDismissedAgentTimelineKeys((current) => current.filter((key) => key !== entryKey));
    setSnoozedAgentTimelineUntil((current) => {
      if (!(entryKey in current)) return current;
      const next = { ...current };
      delete next[entryKey];
      return next;
    });
    setLineageQueueNow(Date.now());
  }, [setDismissedAgentTimelineKeys, setLineageQueueNow, setSnoozedAgentTimelineUntil]);

  const revealAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
      const entryKey = agentTimelineEntryKey(entry);
      setAgentTimelineFilter("all");
      setAgentTimelineSearch("");
      setSelectedAgentTimelineKey(entryKey);
      if (selectedAgentId) {
        setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, entryKey));
      }
    },
    [
      selectedAgentId,
      setAgentTimelineFilter,
      setAgentTimelineSearch,
      setPendingAgentTimelineRowDomId,
      setSelectedAgentTimelineKey,
    ]
  );

  const findSessionLineageEntryInSession = useCallback((entry: SessionLineageEntry) => {
    setEntitySearch(
      entry.toolPermissionRuntimeId ||
        entry.toolPermissionToolUseId ||
        entry.runId ||
        entry.issueId ||
        entry.approvalId ||
        entry.title
    );
    if (entry.runId) {
      setSelectedRunId(entry.runId);
      setSelectedRunResultIndex(entry.resultIndex);
    }
  }, [setEntitySearch, setSelectedRunId, setSelectedRunResultIndex]);

  const revealSessionLineageEntryInTimeline = useCallback(
    (entry: SessionLineageEntry) => {
      syncLinkedSelection({
        runId: entry.runId,
        resultIndex: entry.resultIndex,
        approvalId: entry.approvalId,
        issueId: entry.issueId,
        toolPermissionRuntimeId: entry.toolPermissionRuntimeId,
        runtimeAgentId: entry.runtimeAgentId,
        event: entry.event,
      });
    },
    [syncLinkedSelection]
  );

  const findAgentTimelineEntryInSession = useCallback(
    (entry: AgentTimelineEntry) => {
      const relatedRunLink = resolveAgentTimelineRunLink(entry, linkedRuns);
      const approvalId =
        entry.approval?.id ||
        entry.issue?.approval_id ||
        toStringValue(entry.event?.approval_id) ||
        toStringValue(entry.shadowAudit?.metadata?.approval_id);
      const issueId =
        entry.issue?.id ||
        toStringValue(entry.event?.issue_id) ||
        toStringValue(entry.shadowAudit?.metadata?.issue_id);
      const eventToken =
        entry.shadowAudit?.id ||
        entry.shadowAuditTaskId ||
        toStringValue(entry.event?.event) ||
        toStringValue(entry.event?.message) ||
        entry.id;

      if (relatedRunLink) {
        setEntitySearch(relatedRunLink.run.id || approvalId || issueId || eventToken);
        setSelectedRunId(relatedRunLink.run.id);
        setSelectedRunResultIndex(relatedRunLink.resultIndex);
        return;
      }

      setEntitySearch(approvalId || issueId || eventToken);
    },
    [linkedRuns, setEntitySearch, setSelectedRunId, setSelectedRunResultIndex]
  );

  useEffect(() => {
    if (!pendingAgentTimelineTarget) return;
    if (!selectedAgentId || pendingAgentTimelineTarget.runtimeAgentId !== selectedAgentId) return;
    if (!selectedAgent) return;

    const matchedEntry = resolveAgentTimelineEntryFromTarget(
      agentTimelineEntries,
      pendingAgentTimelineTarget
    );
    if (matchedEntry) {
      const matchedKey = agentTimelineEntryKey(matchedEntry);
      setSelectedAgentTimelineKey(matchedKey);
      setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, matchedKey));
      setNotice("");
    } else {
      setNotice("Found runtime agent, but no linked timeline item was available for this outcome.");
    }
    setPendingAgentTimelineTarget(null);
  }, [
    agentTimelineEntries,
    pendingAgentTimelineTarget,
    selectedAgent,
    selectedAgentId,
    setNotice,
    setPendingAgentTimelineRowDomId,
    setPendingAgentTimelineTarget,
    setSelectedAgentTimelineKey,
  ]);

  useEffect(() => {
    if (!pendingSessionRowDomId) return;
    if (scrollToDomId(pendingSessionRowDomId)) {
      setPendingSessionRowDomId("");
    }
  }, [pendingSessionRowDomId, setPendingSessionRowDomId]);

  useEffect(() => {
    if (!pendingAgentTimelineRowDomId) return;
    if (scrollToDomId(pendingAgentTimelineRowDomId)) {
      setPendingAgentTimelineRowDomId("");
    }
  }, [
    pendingAgentTimelineRowDomId,
    selectedAgentId,
    setPendingAgentTimelineRowDomId,
    visibleAgentTimelineEntries,
  ]);

  return {
    restoreAgentTimelineEntryVisibility,
    revealAgentTimelineEntry,
    findSessionLineageEntryInSession,
    revealSessionLineageEntryInTimeline,
    findAgentTimelineEntryInSession,
  };
}
