"use client";

import { useMemo } from "react";
import {
  approvalMatchesSearch,
  controlPassMatchesSearch,
  eventMatchesSearch,
  issueMatchesSearch,
  runMatchesSearch,
  sessionMatchesSearch,
} from "@/lib/control-plane-data";
import { sessionEventKey, withSelectedItem } from "@/lib/control-plane-linking";
import { matchesEventFilter, matchesRunFilter } from "@/lib/control-plane-triage";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  OrchestratorControlPassRecord,
  OrchestratorSessionControlProfile,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  ProjectSummary,
} from "@/lib/types";

type UseControlPlaneSessionOverviewModelArgs = {
  projects: ProjectSummary[];
  controlPasses: OrchestratorControlPassRecord[];
  controlProfiles: OrchestratorSessionControlProfile[];
  sessions: OrchestratorSessionRecord[];
  selectedSession: OrchestratorSessionDetail | null;
  selectedPassId: string;
  selectedRunId: string;
  selectedRunResultIndex: number;
  selectedSessionApprovalId: string;
  selectedSessionIssueId: string;
  selectedSessionEventKey: string;
  historySearch: string;
  entitySearch: string;
  runFilter: string;
  eventFilter: string;
};

export function useControlPlaneSessionOverviewModel({
  projects,
  controlPasses,
  controlProfiles,
  sessions,
  selectedSession,
  selectedPassId,
  selectedRunId,
  selectedRunResultIndex,
  selectedSessionApprovalId,
  selectedSessionIssueId,
  selectedSessionEventKey,
  historySearch,
  entitySearch,
  runFilter,
  eventFilter,
}: UseControlPlaneSessionOverviewModelArgs) {
  const visibleProjects = useMemo(
    () => projects.filter((project) => !project.archived),
    [projects]
  );

  const filteredControlPassHistory = useMemo(
    () => controlPasses.filter((controlPass) => controlPassMatchesSearch(controlPass, historySearch)),
    [controlPasses, historySearch]
  );

  const recentControlPasses = useMemo(
    () => filteredControlPassHistory.slice(0, 8),
    [filteredControlPassHistory]
  );

  const filteredSessionHistory = useMemo(
    () => sessions.filter((session) => sessionMatchesSearch(session, historySearch)),
    [historySearch, sessions]
  );

  const recentSessions = useMemo(
    () => filteredSessionHistory.slice(0, 6),
    [filteredSessionHistory]
  );

  const sortedProfiles = useMemo(
    () =>
      [...controlProfiles].sort((left, right) => {
        if (left.default) return -1;
        if (right.default) return 1;
        return left.name.localeCompare(right.name);
      }),
    [controlProfiles]
  );

  const selectedPass = useMemo(() => {
    if (!selectedPassId) return null;
    const fromSession =
      selectedSession?.control_passes.find((controlPass) => controlPass.id === selectedPassId) ?? null;
    return fromSession ?? controlPasses.find((controlPass) => controlPass.id === selectedPassId) ?? null;
  }, [controlPasses, selectedPassId, selectedSession]);

  const linkedApprovals = useMemo<ExecutionApprovalRecord[]>(
    () =>
      [...(selectedSession?.approvals || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );

  const linkedRuns = useMemo<ExecutionAgentActionRunRecord[]>(
    () =>
      [...(selectedSession?.runs || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );

  const filteredRuns = useMemo(
    () => linkedRuns.filter((run) => matchesRunFilter(run, runFilter) && runMatchesSearch(run, entitySearch)),
    [entitySearch, linkedRuns, runFilter]
  );

  const linkedIssues = useMemo<ExecutionIssueRecord[]>(
    () =>
      [...(selectedSession?.issues || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );

  const approvalById = useMemo(() => {
    const index = new Map<string, ExecutionApprovalRecord>();
    linkedApprovals.forEach((approval) => {
      index.set(approval.id, approval);
    });
    return index;
  }, [linkedApprovals]);

  const issueById = useMemo(() => {
    const index = new Map<string, ExecutionIssueRecord>();
    linkedIssues.forEach((issue) => {
      index.set(issue.id, issue);
    });
    return index;
  }, [linkedIssues]);

  const linkedAgentIds = useMemo(() => {
    const ids = [
      ...(selectedSession?.linked_runtime_agent_ids || []),
      ...linkedRuns.flatMap((run) => run.runtime_agent_ids || []),
      ...linkedApprovals.flatMap((approval) => approval.runtime_agent_ids || []),
      ...linkedIssues.flatMap((issue) =>
        issue.runtime_agent_ids.length > 0
          ? issue.runtime_agent_ids
          : issue.runtime_agent_id
            ? [issue.runtime_agent_id]
            : []
      ),
    ].filter(Boolean);
    return [...new Set(ids)];
  }, [linkedApprovals, linkedIssues, linkedRuns, selectedSession]);

  const filteredApprovals = useMemo(
    () => linkedApprovals.filter((approval) => approvalMatchesSearch(approval, entitySearch)),
    [entitySearch, linkedApprovals]
  );

  const filteredIssues = useMemo(
    () => linkedIssues.filter((issue) => issueMatchesSearch(issue, entitySearch)),
    [entitySearch, linkedIssues]
  );

  const selectedSessionApproval = useMemo(
    () => linkedApprovals.find((approval) => approval.id === selectedSessionApprovalId) ?? null,
    [linkedApprovals, selectedSessionApprovalId]
  );

  const selectedSessionIssue = useMemo(
    () => linkedIssues.find((issue) => issue.id === selectedSessionIssueId) ?? null,
    [linkedIssues, selectedSessionIssueId]
  );

  const selectedSessionEvent = useMemo(
    () =>
      (selectedSession?.events || []).find(
        (event) => sessionEventKey(event) === selectedSessionEventKey
      ) ?? null,
    [selectedSession, selectedSessionEventKey]
  );

  const visibleSessionApprovals = useMemo(
    () => withSelectedItem(filteredApprovals, selectedSessionApproval, 6, (approval) => approval.id),
    [filteredApprovals, selectedSessionApproval]
  );

  const visibleSessionIssues = useMemo(
    () => withSelectedItem(filteredIssues, selectedSessionIssue, 6, (issue) => issue.id),
    [filteredIssues, selectedSessionIssue]
  );

  const selectedRun = useMemo(() => {
    if (!selectedRunId) return null;
    return linkedRuns.find((run) => run.id === selectedRunId) ?? null;
  }, [linkedRuns, selectedRunId]);

  const filteredEvents = useMemo(
    () =>
      (selectedSession?.events || []).filter(
        (event) => matchesEventFilter(event, eventFilter) && eventMatchesSearch(event, entitySearch)
      ),
    [entitySearch, eventFilter, selectedSession]
  );

  const visibleSessionEvents = useMemo(() => {
    const recentEvents = filteredEvents.slice(-6).reverse();
    if (!selectedSessionEvent) return recentEvents;
    const selectedKey = sessionEventKey(selectedSessionEvent);
    if (!selectedKey || recentEvents.some((event) => sessionEventKey(event) === selectedKey)) {
      return recentEvents;
    }
    return [selectedSessionEvent, ...recentEvents.slice(0, 5)];
  }, [filteredEvents, selectedSessionEvent]);

  const selectedRunResult = useMemo(() => {
    if (!selectedRun) return null;
    return selectedRun.results[selectedRunResultIndex] ?? selectedRun.results[0] ?? null;
  }, [selectedRun, selectedRunResultIndex]);

  const selectedControl = selectedSession?.control ?? null;

  return {
    visibleProjects,
    filteredControlPassHistory,
    recentControlPasses,
    filteredSessionHistory,
    recentSessions,
    sortedProfiles,
    selectedPass,
    linkedApprovals,
    linkedRuns,
    filteredRuns,
    linkedIssues,
    approvalById,
    issueById,
    linkedAgentIds,
    filteredApprovals,
    filteredIssues,
    selectedSessionApproval,
    selectedSessionIssue,
    selectedSessionEvent,
    visibleSessionApprovals,
    visibleSessionIssues,
    selectedRun,
    filteredEvents,
    visibleSessionEvents,
    selectedRunResult,
    selectedControl,
  };
}
