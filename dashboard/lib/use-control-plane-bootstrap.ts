"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";
import type { QueueAdvanceFeedback, QueueAdvanceFocusDelta } from "@/components/queue-advance-notice";
import { outcomeRuntimeAgentId } from "@/lib/control-plane-data";
import type {
  PendingAgentPriorityAutoAdvance,
  PendingLineageAutoAdvance,
} from "@/lib/use-control-plane-actions";
import type {
  QueueAdvanceTarget,
  SessionContextKind,
} from "@/lib/control-plane-models";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
  OrchestratorControlPassRecord,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
} from "@/lib/types";

type UseControlPlaneBootstrapArgs = {
  sessions: OrchestratorSessionRecord[];
  controlPasses: OrchestratorControlPassRecord[];
  selectedSessionId: string;
  selectedAgentId: string;
  selectedRunId: string;
  selectedRunResultIndex: number;
  selectedSession: OrchestratorSessionDetail | null;
  loadSessionDetail: (sessionId: string) => Promise<OrchestratorSessionDetail>;
  loadAgentDetail: (runtimeAgentId: string) => Promise<ExecutionRuntimeAgentDetail>;
  setSelectedSessionId: Dispatch<SetStateAction<string>>;
  setSelectedAgentId: Dispatch<SetStateAction<string>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedRunResultIndex: Dispatch<SetStateAction<number>>;
  setSelectedPassId: Dispatch<SetStateAction<string>>;
  setSelectedAgent: Dispatch<SetStateAction<ExecutionRuntimeAgentDetail | null>>;
  setSelectedSession: Dispatch<SetStateAction<OrchestratorSessionDetail | null>>;
  setSelectedSessionApprovalId: Dispatch<SetStateAction<string>>;
  setSelectedSessionIssueId: Dispatch<SetStateAction<string>>;
  setSelectedSessionEventKey: Dispatch<SetStateAction<string>>;
  setSelectedSessionContextKind: Dispatch<SetStateAction<SessionContextKind>>;
  setEntitySearch: Dispatch<SetStateAction<string>>;
  setSessionQueueAdvanceFeedback: Dispatch<
    SetStateAction<QueueAdvanceFeedback<QueueAdvanceTarget> | null>
  >;
  setSessionQueueFocusDelta: Dispatch<SetStateAction<QueueAdvanceFocusDelta | null>>;
  setPendingLineageAutoAdvance: Dispatch<SetStateAction<PendingLineageAutoAdvance | null>>;
  setLineageQueueNow: Dispatch<SetStateAction<number>>;
  setSessionLoading: Dispatch<SetStateAction<boolean>>;
  setAgentLoading: Dispatch<SetStateAction<boolean>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setAgentActivityFilter: Dispatch<SetStateAction<string>>;
  setAgentActivitySearch: Dispatch<SetStateAction<string>>;
  setAgentTimelineFilter: Dispatch<SetStateAction<string>>;
  setAgentTimelineSearch: Dispatch<SetStateAction<string>>;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
  setAgentQueueAdvanceFeedback: Dispatch<
    SetStateAction<QueueAdvanceFeedback<QueueAdvanceTarget> | null>
  >;
  setAgentQueueFocusDelta: Dispatch<SetStateAction<QueueAdvanceFocusDelta | null>>;
  setPendingAgentPriorityAutoAdvance: Dispatch<
    SetStateAction<PendingAgentPriorityAutoAdvance | null>
  >;
};

export function useControlPlaneBootstrap({
  sessions,
  controlPasses,
  selectedSessionId,
  selectedAgentId,
  selectedRunId,
  selectedRunResultIndex,
  selectedSession,
  loadSessionDetail,
  loadAgentDetail,
  setSelectedSessionId,
  setSelectedAgentId,
  setSelectedRunId,
  setSelectedRunResultIndex,
  setSelectedPassId,
  setSelectedAgent,
  setSelectedSession,
  setSelectedSessionApprovalId,
  setSelectedSessionIssueId,
  setSelectedSessionEventKey,
  setSelectedSessionContextKind,
  setEntitySearch,
  setSessionQueueAdvanceFeedback,
  setSessionQueueFocusDelta,
  setPendingLineageAutoAdvance,
  setLineageQueueNow,
  setSessionLoading,
  setAgentLoading,
  setErrorMessage,
  setAgentActivityFilter,
  setAgentActivitySearch,
  setAgentTimelineFilter,
  setAgentTimelineSearch,
  setSelectedAgentTimelineKey,
  setAgentQueueAdvanceFeedback,
  setAgentQueueFocusDelta,
  setPendingAgentPriorityAutoAdvance,
}: UseControlPlaneBootstrapArgs) {
  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId("");
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSession(null);
      return;
    }
    setSelectedSessionId((current) =>
      sessions.some((session) => session.id === current) ? current : sessions[0].id
    );
  }, [
    sessions,
    setSelectedAgent,
    setSelectedAgentId,
    setSelectedRunId,
    setSelectedSession,
    setSelectedSessionId,
  ]);

  useEffect(() => {
    if (controlPasses.length === 0) {
      setSelectedPassId("");
      return;
    }
    setSelectedPassId((current) =>
      controlPasses.some((controlPass) => controlPass.id === current)
        ? current
        : controlPasses[0].id
    );
  }, [controlPasses, setSelectedPassId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionEventKey("");
      setSelectedSessionContextKind("");
      setEntitySearch("");
      setSelectedSession(null);
      return;
    }

    let cancelled = false;
    setSessionLoading(true);
    loadSessionDetail(selectedSessionId)
      .then(() => {
        if (cancelled) return;
        setErrorMessage("");
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedSession(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load orchestrator session detail."
        );
      })
      .finally(() => {
        if (!cancelled) setSessionLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [
    loadSessionDetail,
    selectedSessionId,
    setEntitySearch,
    setErrorMessage,
    setSelectedAgent,
    setSelectedAgentId,
    setSelectedRunId,
    setSelectedSession,
    setSelectedSessionApprovalId,
    setSelectedSessionContextKind,
    setSelectedSessionEventKey,
    setSelectedSessionIssueId,
    setSessionLoading,
  ]);

  useEffect(() => {
    setEntitySearch("");
    setSelectedSessionApprovalId("");
    setSelectedSessionIssueId("");
    setSelectedSessionEventKey("");
    setSelectedSessionContextKind("");
    setSessionQueueAdvanceFeedback(null);
    setSessionQueueFocusDelta(null);
    setPendingLineageAutoAdvance(null);
    setLineageQueueNow(Date.now());
  }, [
    selectedSessionId,
    setEntitySearch,
    setLineageQueueNow,
    setPendingLineageAutoAdvance,
    setSelectedSessionApprovalId,
    setSelectedSessionContextKind,
    setSelectedSessionEventKey,
    setSelectedSessionIssueId,
    setSessionQueueAdvanceFeedback,
    setSessionQueueFocusDelta,
  ]);

  useEffect(() => {
    if (!selectedSession) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }

    const sessionRuns = (selectedSession.runs || []) as ExecutionAgentActionRunRecord[];
    const currentRun =
      sessionRuns.find((run) => run.id === selectedRunId) ?? sessionRuns[0] ?? null;
    const currentRunResult =
      currentRun?.results[selectedRunResultIndex] ?? currentRun?.results[0] ?? null;
    const sessionApprovals = selectedSession.approvals || [];
    const sessionIssues = selectedSession.issues || [];
    const candidateIds = [
      currentRunResult && typeof currentRunResult === "object"
        ? outcomeRuntimeAgentId(currentRunResult as Record<string, unknown>)
        : "",
      ...selectedSession.linked_runtime_agent_ids,
      ...sessionRuns.flatMap((run) => run.runtime_agent_ids || []),
      ...sessionApprovals.flatMap((approval) => approval.runtime_agent_ids || []),
      ...sessionIssues.flatMap((issue) =>
        issue.runtime_agent_ids.length > 0
          ? issue.runtime_agent_ids
          : issue.runtime_agent_id
            ? [issue.runtime_agent_id]
            : []
      ),
    ].filter(Boolean);
    const uniqueIds = [...new Set(candidateIds)];
    if (!uniqueIds.length) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }
    setSelectedAgentId((current) =>
      current && uniqueIds.includes(current) ? current : uniqueIds[0]
    );
  }, [
    selectedRunId,
    selectedRunResultIndex,
    selectedSession,
    setSelectedAgent,
    setSelectedAgentId,
  ]);

  useEffect(() => {
    if (!selectedAgentId) return;
    setAgentActivityFilter("all");
    setAgentActivitySearch("");
    setAgentTimelineFilter("all");
    setAgentTimelineSearch("");
    setSelectedAgentTimelineKey("");
    setAgentQueueAdvanceFeedback(null);
    setAgentQueueFocusDelta(null);
    setPendingAgentPriorityAutoAdvance(null);
  }, [
    selectedAgentId,
    setAgentActivityFilter,
    setAgentActivitySearch,
    setAgentQueueAdvanceFeedback,
    setAgentQueueFocusDelta,
    setAgentTimelineFilter,
    setAgentTimelineSearch,
    setPendingAgentPriorityAutoAdvance,
    setSelectedAgentTimelineKey,
  ]);

  useEffect(() => {
    setSelectedRunResultIndex(0);
  }, [selectedRunId, setSelectedRunResultIndex]);

  useEffect(() => {
    if (!selectedAgentId) {
      setSelectedAgent(null);
      return;
    }
    let cancelled = false;
    setAgentLoading(true);
    loadAgentDetail(selectedAgentId)
      .then((detail) => {
        if (cancelled) return;
        setSelectedAgent(detail);
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedAgent(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load runtime agent detail."
        );
      })
      .finally(() => {
        if (!cancelled) setAgentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    loadAgentDetail,
    selectedAgentId,
    setAgentLoading,
    setErrorMessage,
    setSelectedAgent,
  ]);

  const focusRuntimeAgent = useCallback(
    (runtimeAgentId: string, syncSearch = false) => {
      if (!runtimeAgentId) return;
      setSelectedAgentId(runtimeAgentId);
      if (syncSearch) {
        setEntitySearch(runtimeAgentId);
      }
    },
    [setEntitySearch, setSelectedAgentId]
  );

  return {
    focusRuntimeAgent,
  };
}
