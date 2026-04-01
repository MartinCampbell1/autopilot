"use client";

import { useCallback, useEffect, type Dispatch, type SetStateAction } from "react";
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
  ProjectSummary,
} from "@/lib/types";

type UseControlPlaneDataLoaderArgs = {
  selectedSessionId: string;
  setHealth: Dispatch<SetStateAction<AccountHealth | null>>;
  setProjects: Dispatch<SetStateAction<ProjectSummary[]>>;
  setControlPasses: Dispatch<SetStateAction<OrchestratorControlPassRecord[]>>;
  setControlSummary: Dispatch<SetStateAction<OrchestratorControlPassSummary | null>>;
  setSessions: Dispatch<SetStateAction<OrchestratorSessionRecord[]>>;
  setSessionSummary: Dispatch<SetStateAction<OrchestratorSessionSummary | null>>;
  setControlProfiles: Dispatch<SetStateAction<OrchestratorSessionControlProfile[]>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setSelectedSession: Dispatch<SetStateAction<OrchestratorSessionDetail | null>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedPassId: Dispatch<SetStateAction<string>>;
};

export function useControlPlaneDataLoader({
  selectedSessionId,
  setHealth,
  setProjects,
  setControlPasses,
  setControlSummary,
  setSessions,
  setSessionSummary,
  setControlProfiles,
  setErrorMessage,
  setSelectedSession,
  setSelectedRunId,
  setSelectedPassId,
}: UseControlPlaneDataLoaderArgs) {
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

  useSSE(
    useCallback(() => {
      void loadOverview();
      if (selectedSessionId) {
        void loadSessionDetail(selectedSessionId).catch(() => {
          // Keep current detail state on transient SSE fetch failures.
        });
      }
    }, [loadOverview, loadSessionDetail, selectedSessionId])
  );

  return {
    loadOverview,
    loadSessionDetail,
    loadAgentDetail,
  };
}
