"use client";

import { useCallback, useEffect, useRef, type Dispatch, type SetStateAction } from "react";
import {
  fetchAccountsHealth,
  fetchExecutionPlaneAgentDetail,
  fetchExecutionPlaneControlPassSummary,
  fetchExecutionPlaneControlPasses,
  fetchExecutionPlaneOrchestratorSession,
  fetchExecutionPlaneOrchestratorSessionControlProfiles,
  fetchExecutionPlaneOrchestratorSessions,
  fetchExecutionPlaneOrchestratorSessionSummary,
  fetchProjects,
} from "@/lib/api";
import { useSSE } from "@/lib/sse";
import type {
  AccountHealth,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
  OrchestratorSessionControlProfile,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  ExecutionRuntimeAgentDetail,
  ProjectSummary,
} from "@/lib/types";

const AGENT_ASYNC_REFRESH_EVENTS = new Set([
  "execution_plane_agent_action_run_recorded",
  "execution_plane_agent_action_run_pending_async",
  "execution_plane_agent_action_run_async_settled",
  "execution_plane_runtime_agent_task_started",
  "execution_plane_runtime_agent_task_completed",
  "execution_plane_runtime_agent_task_failed",
  "execution_plane_runtime_agent_task_cancelled",
]);

const OVERVIEW_REFRESH_EVENTS = new Set([
  "project_created",
  "project_archived",
  "run_started",
  "run_finished",
  "run_failed",
  "paused",
  "resumed",
  "budget_paused",
  "interrupt_paused",
  "execution_plane_orchestrator_session_created",
  "execution_plane_orchestrator_session_updated",
  "execution_plane_orchestrator_session_recommendation_applied",
  "execution_plane_orchestrator_session_control_plan_applied",
  "execution_plane_orchestrator_session_control_pass_recorded",
  "execution_plane_agent_action_pending_approval",
  "execution_plane_agent_action_executed",
  "execution_plane_agent_action_run_recorded",
  "tool_permission_runtime_pending",
  "tool_permission_runtime_resolved",
]);

const SESSION_REFRESH_EVENTS = new Set([
  ...OVERVIEW_REFRESH_EVENTS,
  ...AGENT_ASYNC_REFRESH_EVENTS,
]);

const CONTROL_PLANE_SSE_EVENT_TYPES = Array.from(
  new Set([...OVERVIEW_REFRESH_EVENTS, ...SESSION_REFRESH_EVENTS])
);

const REFRESH_COALESCE_DELAY_MS = 300;

type UseControlPlaneDataLoaderArgs = {
  selectedSessionId: string;
  selectedAgentId: string;
  setHealth: Dispatch<SetStateAction<AccountHealth | null>>;
  setProjects: Dispatch<SetStateAction<ProjectSummary[]>>;
  setControlPasses: Dispatch<SetStateAction<OrchestratorControlPassRecord[]>>;
  setControlSummary: Dispatch<SetStateAction<OrchestratorControlPassSummary | null>>;
  setSessions: Dispatch<SetStateAction<OrchestratorSessionRecord[]>>;
  setSessionSummary: Dispatch<SetStateAction<OrchestratorSessionSummary | null>>;
  setControlProfiles: Dispatch<SetStateAction<OrchestratorSessionControlProfile[]>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setSelectedSession: Dispatch<SetStateAction<OrchestratorSessionDetail | null>>;
  setSelectedAgent: Dispatch<SetStateAction<ExecutionRuntimeAgentDetail | null>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedPassId: Dispatch<SetStateAction<string>>;
};

export function useControlPlaneDataLoader({
  selectedSessionId,
  selectedAgentId,
  setHealth,
  setProjects,
  setControlPasses,
  setControlSummary,
  setSessions,
  setSessionSummary,
  setControlProfiles,
  setErrorMessage,
  setSelectedSession,
  setSelectedAgent,
  setSelectedRunId,
  setSelectedPassId,
}: UseControlPlaneDataLoaderArgs) {
  const selectedSessionIdRef = useRef(selectedSessionId);
  const selectedAgentIdRef = useRef(selectedAgentId);
  const overviewRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sessionRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const agentRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const scheduleOverviewRefreshRef = useRef<() => void>(() => {});
  const scheduleSessionRefreshRef = useRef<() => void>(() => {});
  const scheduleAgentRefreshRef = useRef<() => void>(() => {});
  const overviewRefreshInFlightRef = useRef(false);
  const sessionRefreshInFlightRef = useRef(false);
  const agentRefreshInFlightRef = useRef(false);
  const overviewRefreshQueuedRef = useRef(false);
  const sessionRefreshQueuedRef = useRef(false);
  const agentRefreshQueuedRef = useRef(false);

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId;
  }, [selectedSessionId]);

  useEffect(() => {
    selectedAgentIdRef.current = selectedAgentId;
  }, [selectedAgentId]);

  const loadOverview = useCallback(async () => {
    try {
      const [
        healthData,
        projectData,
        controlPassData,
        controlPassSummaryData,
        sessionData,
        sessionSummaryData,
        profileData,
      ] = await Promise.all([
        fetchAccountsHealth(),
        fetchProjects(false),
        fetchExecutionPlaneControlPasses(),
        fetchExecutionPlaneControlPassSummary(),
        fetchExecutionPlaneOrchestratorSessions(),
        fetchExecutionPlaneOrchestratorSessionSummary(),
        fetchExecutionPlaneOrchestratorSessionControlProfiles(),
      ]);
      setHealth(healthData);
      setProjects((projectData.projects || []) as ProjectSummary[]);
      setControlPasses((controlPassData.control_passes || []) as OrchestratorControlPassRecord[]);
      setControlSummary(controlPassSummaryData);
      setSessions((sessionData.sessions || []) as OrchestratorSessionRecord[]);
      setSessionSummary(sessionSummaryData);
      setControlProfiles((profileData.profiles || []) as OrchestratorSessionControlProfile[]);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load control plane.");
    }
  }, [
    setControlPasses,
    setControlProfiles,
    setControlSummary,
    setErrorMessage,
    setHealth,
    setProjects,
    setSessionSummary,
    setSessions,
  ]);

  const loadSessionDetail = useCallback(
    async (sessionId: string) => {
      const detail = await fetchExecutionPlaneOrchestratorSession(sessionId, { eventLimit: 12 });
      setSelectedSession(detail);
      setSelectedRunId((current) => {
        if (current && detail.runs.some((run) => run.id === current)) {
          return current;
        }
        return detail.runs[0]?.id ?? "";
      });
      setSelectedPassId((current) => {
        if (current && detail.control_passes.some((controlPass) => controlPass.id === current)) {
          return current;
        }
        return detail.control_passes[0]?.id ?? current;
      });
      return detail;
    },
    [setSelectedPassId, setSelectedRunId, setSelectedSession]
  );

  const loadAgentDetail = useCallback(async (runtimeAgentId: string) => {
    return fetchExecutionPlaneAgentDetail(runtimeAgentId, { eventLimit: 12 });
  }, []);

  const scheduleOverviewRefresh = useCallback(() => {
    if (overviewRefreshTimerRef.current) {
      return;
    }
    overviewRefreshTimerRef.current = setTimeout(() => {
      overviewRefreshTimerRef.current = null;
      if (overviewRefreshInFlightRef.current) {
        overviewRefreshQueuedRef.current = true;
        return;
      }
      overviewRefreshInFlightRef.current = true;
      void loadOverview().finally(() => {
        overviewRefreshInFlightRef.current = false;
        if (overviewRefreshQueuedRef.current) {
          overviewRefreshQueuedRef.current = false;
          scheduleOverviewRefreshRef.current();
        }
      });
    }, REFRESH_COALESCE_DELAY_MS);
  }, [loadOverview]);

  const scheduleSessionRefresh = useCallback(() => {
    if (sessionRefreshTimerRef.current) {
      return;
    }
    sessionRefreshTimerRef.current = setTimeout(() => {
      sessionRefreshTimerRef.current = null;
      const sessionId = selectedSessionIdRef.current;
      if (!sessionId) {
        return;
      }
      if (sessionRefreshInFlightRef.current) {
        sessionRefreshQueuedRef.current = true;
        return;
      }
      sessionRefreshInFlightRef.current = true;
      void loadSessionDetail(sessionId)
        .catch(() => {
          // Keep current detail state on transient SSE fetch failures.
        })
        .finally(() => {
          sessionRefreshInFlightRef.current = false;
          if (sessionRefreshQueuedRef.current) {
            sessionRefreshQueuedRef.current = false;
            scheduleSessionRefreshRef.current();
          }
        });
    }, REFRESH_COALESCE_DELAY_MS);
  }, [loadSessionDetail]);

  const scheduleAgentRefresh = useCallback(() => {
    if (agentRefreshTimerRef.current) {
      return;
    }
    agentRefreshTimerRef.current = setTimeout(() => {
      agentRefreshTimerRef.current = null;
      const runtimeAgentId = selectedAgentIdRef.current;
      if (!runtimeAgentId) {
        return;
      }
      if (agentRefreshInFlightRef.current) {
        agentRefreshQueuedRef.current = true;
        return;
      }
      agentRefreshInFlightRef.current = true;
      void loadAgentDetail(runtimeAgentId)
        .then((detail) => {
          setSelectedAgent(detail);
        })
        .catch(() => {
          // Keep current agent state on transient SSE fetch failures.
        })
        .finally(() => {
          agentRefreshInFlightRef.current = false;
          if (agentRefreshQueuedRef.current) {
            agentRefreshQueuedRef.current = false;
            scheduleAgentRefreshRef.current();
          }
        });
    }, REFRESH_COALESCE_DELAY_MS);
  }, [loadAgentDetail, setSelectedAgent]);

  useEffect(() => {
    scheduleOverviewRefreshRef.current = scheduleOverviewRefresh;
  }, [scheduleOverviewRefresh]);

  useEffect(() => {
    scheduleSessionRefreshRef.current = scheduleSessionRefresh;
  }, [scheduleSessionRefresh]);

  useEffect(() => {
    scheduleAgentRefreshRef.current = scheduleAgentRefresh;
  }, [scheduleAgentRefresh]);

  useEffect(() => {
    const initialLoad = setTimeout(() => {
      void loadOverview();
    }, 0);
    const interval = setInterval(() => {
      void loadOverview();
    }, 15000);
    return () => {
      clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, [loadOverview]);

  useEffect(() => {
    return () => {
      if (overviewRefreshTimerRef.current) clearTimeout(overviewRefreshTimerRef.current);
      if (sessionRefreshTimerRef.current) clearTimeout(sessionRefreshTimerRef.current);
      if (agentRefreshTimerRef.current) clearTimeout(agentRefreshTimerRef.current);
    };
  }, []);

  useSSE(
    useCallback((event) => {
      if (OVERVIEW_REFRESH_EVENTS.has(event)) {
        scheduleOverviewRefresh();
      }
      if (SESSION_REFRESH_EVENTS.has(event)) {
        scheduleSessionRefresh();
      }
      if (AGENT_ASYNC_REFRESH_EVENTS.has(event)) {
        scheduleAgentRefresh();
      }
    }, [
      scheduleAgentRefresh,
      scheduleOverviewRefresh,
      scheduleSessionRefresh,
    ]),
    {
      eventTypes: CONTROL_PLANE_SSE_EVENT_TYPES,
    }
  );

  return {
    loadOverview,
    loadSessionDetail,
    loadAgentDetail,
  };
}
