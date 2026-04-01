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

type EventRecord = Record<string, unknown>;

const AGENT_ASYNC_REFRESH_EVENTS = new Set([
  "execution_plane_agent_action_run_recorded",
  "execution_plane_agent_action_run_pending_async",
  "execution_plane_agent_action_run_async_settled",
  "execution_plane_runtime_agent_task_started",
  "execution_plane_runtime_agent_task_completed",
  "execution_plane_runtime_agent_task_failed",
  "execution_plane_runtime_agent_task_cancelled",
]);

const AGENT_DETAIL_REFRESH_EVENTS = new Set([
  ...AGENT_ASYNC_REFRESH_EVENTS,
  "execution_plane_agent_action_pending_approval",
  "execution_plane_agent_action_executed",
  "tool_permission_runtime_pending",
  "tool_permission_runtime_resolved",
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

const SESSION_DETAIL_REFRESH_EVENTS = new Set([
  "execution_plane_orchestrator_session_updated",
  "execution_plane_orchestrator_session_recommendation_applied",
  "execution_plane_orchestrator_session_control_plan_applied",
  "execution_plane_orchestrator_session_control_pass_recorded",
  "execution_plane_agent_action_pending_approval",
  "execution_plane_agent_action_executed",
  "execution_plane_agent_action_run_recorded",
  "execution_plane_agent_action_run_pending_async",
  "execution_plane_agent_action_run_async_settled",
  "execution_plane_runtime_agent_task_started",
  "execution_plane_runtime_agent_task_completed",
  "execution_plane_runtime_agent_task_failed",
  "execution_plane_runtime_agent_task_cancelled",
  "tool_permission_runtime_pending",
  "tool_permission_runtime_resolved",
]);

const CONTROL_PLANE_SSE_EVENT_TYPES = Array.from(
  new Set([
    ...OVERVIEW_REFRESH_EVENTS,
    ...SESSION_DETAIL_REFRESH_EVENTS,
    ...AGENT_DETAIL_REFRESH_EVENTS,
  ])
);

const REFRESH_COALESCE_DELAY_MS = 300;

function asEventRecord(value: unknown): EventRecord | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as EventRecord)
    : null;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => (typeof item === "string" ? item.trim() : "")).filter(Boolean)
    : [];
}

function eventReferencesSession(data: unknown, sessionId: string): boolean {
  const payload = asEventRecord(data);
  if (!payload || !sessionId) return false;
  return (
    stringValue(payload.orchestrator_session_id) === sessionId ||
    stringValue(payload.session_id) === sessionId
  );
}

function eventReferencesAgent(data: unknown, runtimeAgentId: string): boolean {
  const payload = asEventRecord(data);
  if (!payload || !runtimeAgentId) return false;
  if (stringValue(payload.runtime_agent_id) === runtimeAgentId) {
    return true;
  }
  return stringArray(payload.runtime_agent_ids).includes(runtimeAgentId);
}

function shouldRefreshSelectedSession(event: string, data: unknown, sessionId: string): boolean {
  if (!sessionId || !SESSION_DETAIL_REFRESH_EVENTS.has(event)) return false;
  if (eventReferencesSession(data, sessionId)) return true;
  return false;
}

function shouldRefreshSelectedAgent(event: string, data: unknown, runtimeAgentId: string): boolean {
  if (!runtimeAgentId || !AGENT_DETAIL_REFRESH_EVENTS.has(event)) return false;
  return eventReferencesAgent(data, runtimeAgentId);
}

function isNotFoundError(error: unknown): boolean {
  return error instanceof Error && /not found/i.test(error.message);
}

type UseControlPlaneDataLoaderArgs = {
  projects: ProjectSummary[];
  sessions: OrchestratorSessionRecord[];
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
  projects,
  sessions,
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
  const projectIdsRef = useRef<string[]>(projects.map((project) => project.id).filter(Boolean));
  const sessionIdsRef = useRef<string[]>(sessions.map((session) => session.id).filter(Boolean));
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
    projectIdsRef.current = projects.map((project) => project.id).filter(Boolean);
  }, [projects]);

  useEffect(() => {
    sessionIdsRef.current = sessions.map((session) => session.id).filter(Boolean);
  }, [sessions]);

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
      if (selectedSessionIdRef.current !== sessionId) {
        return detail;
      }
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

  const loadAgentDetail = useCallback(
    async (runtimeAgentId: string) => {
      const detail = await fetchExecutionPlaneAgentDetail(runtimeAgentId, { eventLimit: 12 });
      if (selectedAgentIdRef.current === runtimeAgentId) {
        setSelectedAgent(detail);
      }
      return detail;
    },
    [setSelectedAgent]
  );

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
        .catch((error) => {
          if (isNotFoundError(error) && selectedSessionIdRef.current === sessionId) {
            setSelectedSession(null);
            setSelectedRunId("");
            setSelectedPassId("");
            return;
          }
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
  }, [loadSessionDetail, setSelectedPassId, setSelectedRunId, setSelectedSession]);

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
        .catch((error) => {
          if (isNotFoundError(error) && selectedAgentIdRef.current === runtimeAgentId) {
            setSelectedAgent(null);
            return;
          }
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
      scheduleOverviewRefreshRef.current();
    }, 0);
    const interval = setInterval(() => {
      scheduleOverviewRefreshRef.current();
    }, 15000);
    return () => {
      clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (overviewRefreshTimerRef.current) clearTimeout(overviewRefreshTimerRef.current);
      if (sessionRefreshTimerRef.current) clearTimeout(sessionRefreshTimerRef.current);
      if (agentRefreshTimerRef.current) clearTimeout(agentRefreshTimerRef.current);
    };
  }, []);

  useSSE(
    useCallback((event, data) => {
      const payload = asEventRecord(data);
      const eventProjectId = stringValue(payload?.project_id);
      const eventSessionId =
        stringValue(payload?.orchestrator_session_id) || stringValue(payload?.session_id);
      const knownProjectIds = new Set(projectIdsRef.current);
      const knownSessionIds = new Set(sessionIdsRef.current);
      const shouldRefreshOverview =
        OVERVIEW_REFRESH_EVENTS.has(event) &&
        (
          event === "project_created" ||
          event === "project_archived" ||
          (eventProjectId && knownProjectIds.has(eventProjectId)) ||
          (eventSessionId && knownSessionIds.has(eventSessionId))
        );

      if (shouldRefreshOverview) {
        scheduleOverviewRefresh();
      }
      if (shouldRefreshSelectedSession(event, data, selectedSessionIdRef.current)) {
        scheduleSessionRefresh();
      }
      if (shouldRefreshSelectedAgent(event, data, selectedAgentIdRef.current)) {
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
