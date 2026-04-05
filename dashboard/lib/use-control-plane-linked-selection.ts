"use client";

import { useCallback, useEffect, useMemo, type Dispatch, type SetStateAction } from "react";
import {
  asRecord,
  outcomeRuntimeAgentId,
  toStringArray,
  toStringValue,
} from "@/lib/control-plane-data";
import {
  resolveRunLinkFromContext,
  resolveSessionEventFromContext,
  sessionContextRowDomId,
  sessionEventKey,
} from "@/lib/control-plane-linking";
import type {
  LinkedSelectionContext,
  PendingAgentTimelineTarget,
  SessionContextKind,
  SessionLineageEntry,
} from "@/lib/control-plane-models";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  ExecutionRuntimeAgentTaskRecord,
  ExecutionShadowAuditRecord,
  OrchestratorSessionDetail,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

export type SelectedSessionContextValue =
  | { kind: "approval"; approval: ExecutionApprovalRecord }
  | { kind: "issue"; issue: ExecutionIssueRecord }
  | { kind: "tool_permission_runtime"; runtime: ToolPermissionRuntimeRecord }
  | { kind: "async_task"; task: ExecutionRuntimeAgentTaskRecord }
  | { kind: "shadow_audit"; shadowAudit: ExecutionShadowAuditRecord }
  | { kind: "event"; event: Record<string, unknown> };

type UseControlPlaneLinkedSelectionArgs = {
  linkedRuns: ExecutionAgentActionRunRecord[];
  selectedSession: OrchestratorSessionDetail | null;
  selectedSessionApproval: ExecutionApprovalRecord | null;
  selectedSessionIssue: ExecutionIssueRecord | null;
  selectedSessionToolPermissionRuntime: ToolPermissionRuntimeRecord | null;
  selectedSessionAsyncTask: ExecutionRuntimeAgentTaskRecord | null;
  selectedSessionShadowAudit: ExecutionShadowAuditRecord | null;
  selectedSessionEvent: Record<string, unknown> | null;
  selectedSessionEventKey: string;
  selectedSessionContextKind: SessionContextKind;
  selectedRun: ExecutionAgentActionRunRecord | null;
  selectedRunResult: unknown;
  setSelectedSessionApprovalId: Dispatch<SetStateAction<string>>;
  setSelectedSessionIssueId: Dispatch<SetStateAction<string>>;
  setSelectedSessionToolPermissionRuntimeId: Dispatch<SetStateAction<string>>;
  setSelectedSessionAsyncTaskId: Dispatch<SetStateAction<string>>;
  setSelectedSessionShadowAuditId: Dispatch<SetStateAction<string>>;
  setSelectedSessionEventKey: Dispatch<SetStateAction<string>>;
  setSelectedSessionContextKind: Dispatch<SetStateAction<SessionContextKind>>;
  setSelectedRunId: Dispatch<SetStateAction<string>>;
  setSelectedRunResultIndex: Dispatch<SetStateAction<number>>;
  setSelectedAgentId: Dispatch<SetStateAction<string>>;
  setAgentTimelineFilter: Dispatch<SetStateAction<string>>;
  setAgentTimelineSearch: Dispatch<SetStateAction<string>>;
  setSelectedAgentTimelineKey: Dispatch<SetStateAction<string>>;
  setPendingAgentTimelineTarget: Dispatch<SetStateAction<PendingAgentTimelineTarget | null>>;
  setPendingSessionRowDomId: Dispatch<SetStateAction<string>>;
  setEntitySearch: Dispatch<SetStateAction<string>>;
  setEventFilter: Dispatch<SetStateAction<string>>;
  setErrorMessage: Dispatch<SetStateAction<string>>;
  setSessionLineageFilter: Dispatch<SetStateAction<string>>;
};

export function useControlPlaneLinkedSelection({
  linkedRuns,
  selectedSession,
  selectedSessionApproval,
  selectedSessionIssue,
  selectedSessionToolPermissionRuntime,
  selectedSessionAsyncTask,
  selectedSessionShadowAudit,
  selectedSessionEvent,
  selectedSessionEventKey,
  selectedSessionContextKind,
  selectedRun,
  selectedRunResult,
  setSelectedSessionApprovalId,
  setSelectedSessionIssueId,
  setSelectedSessionToolPermissionRuntimeId,
  setSelectedSessionAsyncTaskId,
  setSelectedSessionShadowAuditId,
  setSelectedSessionEventKey,
  setSelectedSessionContextKind,
  setSelectedRunId,
  setSelectedRunResultIndex,
  setSelectedAgentId,
  setAgentTimelineFilter,
  setAgentTimelineSearch,
  setSelectedAgentTimelineKey,
  setPendingAgentTimelineTarget,
  setPendingSessionRowDomId,
  setEntitySearch,
  setEventFilter,
  setErrorMessage,
  setSessionLineageFilter,
}: UseControlPlaneLinkedSelectionArgs) {
  const syncLinkedSelection = useCallback(
    (context: LinkedSelectionContext) => {
      const approvalId = toStringValue(context.approvalId);
      const issueId = toStringValue(context.issueId);
      const toolPermissionRuntimeId = toStringValue(context.toolPermissionRuntimeId);
      const asyncTaskId = toStringValue(context.asyncTaskId);
      const shadowAuditId = toStringValue(context.shadowAuditId);
      const resolvedRunLink = resolveRunLinkFromContext(linkedRuns, context);
      const runId = resolvedRunLink?.run.id || toStringValue(context.runId);
      const resultIndex =
        resolvedRunLink?.resultIndex ??
        (typeof context.resultIndex === "number" ? context.resultIndex : 0);
      const resolvedRunResult =
        resolvedRunLink && resolvedRunLink.run.results[resolvedRunLink.resultIndex]
          ? asRecord(resolvedRunLink.run.results[resolvedRunLink.resultIndex])
          : null;
      const runtimeAgentId =
        toStringValue(context.runtimeAgentId) ||
        outcomeRuntimeAgentId(resolvedRunResult || {}) ||
        toStringValue(context.event?.runtime_agent_id) ||
        toStringArray(context.event?.runtime_agent_ids)[0];
      const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
        ...context,
        runId,
        approvalId,
        issueId,
        runtimeAgentId,
      });

      if (shadowAuditId) {
        setSelectedSessionApprovalId("");
        setSelectedSessionIssueId("");
        setSelectedSessionToolPermissionRuntimeId("");
        setSelectedSessionAsyncTaskId("");
        setSelectedSessionShadowAuditId(shadowAuditId);
        setSelectedSessionEventKey("");
        setSelectedSessionContextKind("shadow_audit");
      } else if (toolPermissionRuntimeId) {
        setSelectedSessionApprovalId("");
        setSelectedSessionIssueId("");
        setSelectedSessionToolPermissionRuntimeId(toolPermissionRuntimeId);
        setSelectedSessionAsyncTaskId("");
        setSelectedSessionShadowAuditId("");
        setSelectedSessionEventKey("");
        setSelectedSessionContextKind("tool_permission_runtime");
      } else if (asyncTaskId) {
        setSelectedSessionApprovalId("");
        setSelectedSessionIssueId("");
        setSelectedSessionToolPermissionRuntimeId("");
        setSelectedSessionAsyncTaskId(asyncTaskId);
        setSelectedSessionShadowAuditId("");
        setSelectedSessionEventKey("");
        setSelectedSessionContextKind("async_task");
      } else {
        setSelectedSessionApprovalId(approvalId);
        setSelectedSessionIssueId(issueId);
        setSelectedSessionToolPermissionRuntimeId("");
        setSelectedSessionAsyncTaskId("");
        setSelectedSessionShadowAuditId("");
        setSelectedSessionEventKey(matchedEvent?.key || "");
        setSelectedSessionContextKind(
          context.event
            ? "event"
            : issueId
              ? "issue"
              : approvalId
                ? "approval"
                : matchedEvent
                  ? "event"
                  : ""
        );
      }

      if (runId) {
        setSelectedRunId(runId);
        setSelectedRunResultIndex(resultIndex);
      }

      if (runtimeAgentId) {
        setSelectedAgentId(runtimeAgentId);
        setAgentTimelineFilter("all");
        setAgentTimelineSearch("");
        setSelectedAgentTimelineKey("");
        setPendingAgentTimelineTarget({
          runtimeAgentId,
          runId,
          approvalId,
          issueId,
          shadowAuditId,
        });
      }
    },
    [
      linkedRuns,
      selectedSession,
      setAgentTimelineFilter,
      setAgentTimelineSearch,
      setPendingAgentTimelineTarget,
      setSelectedAgentId,
      setSelectedAgentTimelineKey,
      setSelectedRunId,
      setSelectedRunResultIndex,
      setSelectedSessionApprovalId,
      setSelectedSessionContextKind,
      setSelectedSessionEventKey,
      setSelectedSessionIssueId,
      setSelectedSessionAsyncTaskId,
      setSelectedSessionShadowAuditId,
      setSelectedSessionToolPermissionRuntimeId,
    ]
  );

  const inspectSessionLineageEntry = useCallback(
    (entry: SessionLineageEntry) => {
      syncLinkedSelection({
        runId: entry.runId,
        resultIndex: entry.resultIndex,
        approvalId: entry.approvalId,
        issueId: entry.issueId,
        toolPermissionRuntimeId: entry.toolPermissionRuntimeId,
        asyncTaskId: entry.asyncTaskId,
        shadowAuditId: entry.shadowAuditId,
        runtimeAgentId: entry.runtimeAgentId,
        event: entry.event,
      });
    },
    [syncLinkedSelection]
  );

  const focusSessionLineageEntry = useCallback(
    (entry: SessionLineageEntry, filter: string) => {
      setSessionLineageFilter(filter);
      inspectSessionLineageEntry(entry);
    },
    [inspectSessionLineageEntry, setSessionLineageFilter]
  );

  useEffect(() => {
    const selectedRunResultRecord = asRecord(selectedRunResult);
    if (!selectedRun || !selectedRunResultRecord) {
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionToolPermissionRuntimeId("");
      setSelectedSessionAsyncTaskId("");
      setSelectedSessionEventKey("");
      return;
    }

    const approvalId = toStringValue(asRecord(selectedRunResultRecord.approval)?.id);
    const issueId = toStringValue(asRecord(selectedRunResultRecord.issue)?.id);
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResultRecord);
    const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
      runId: selectedRun.id,
      approvalId,
      issueId,
      runtimeAgentId,
    });
    const preservesSelectedToolPermissionRuntime = Boolean(
      selectedSessionToolPermissionRuntime &&
        (
          (selectedSessionToolPermissionRuntime.approval_id &&
            selectedSessionToolPermissionRuntime.approval_id === approvalId) ||
          (selectedSessionToolPermissionRuntime.issue_id &&
            selectedSessionToolPermissionRuntime.issue_id === issueId)
        )
    );
    const preservesSelectedAsyncTask = Boolean(
      selectedSessionAsyncTask &&
        ((selectedSessionAsyncTask.agent_action_run_id &&
          selectedSessionAsyncTask.agent_action_run_id === selectedRun.id) ||
          (selectedSessionAsyncTask.approval_id &&
            selectedSessionAsyncTask.approval_id === approvalId) ||
          (selectedSessionAsyncTask.issue_id &&
            selectedSessionAsyncTask.issue_id === issueId))
    );
    const preservesSelectedShadowAudit = Boolean(
      selectedSessionShadowAudit && selectedSessionContextKind === "shadow_audit"
    );

    setSelectedSessionApprovalId(approvalId);
    setSelectedSessionIssueId(issueId);
    setSelectedSessionToolPermissionRuntimeId((current) =>
      preservesSelectedToolPermissionRuntime ? current : ""
    );
    setSelectedSessionAsyncTaskId((current) => (preservesSelectedAsyncTask ? current : ""));
    setSelectedSessionShadowAuditId((current) => (preservesSelectedShadowAudit ? current : ""));
    setSelectedSessionEventKey(matchedEvent?.key || "");
    setSelectedSessionContextKind((current) => {
      if (preservesSelectedShadowAudit && selectedSessionShadowAudit) {
        return "shadow_audit";
      }
      if (preservesSelectedToolPermissionRuntime && selectedSessionToolPermissionRuntime) {
        return "tool_permission_runtime";
      }
      if (preservesSelectedAsyncTask && selectedSessionAsyncTask) {
        return "async_task";
      }
      if (current === "event" && matchedEvent) return "event";
      if (current === "issue" && issueId) return "issue";
      if (current === "approval" && approvalId) return "approval";
      if (issueId) return "issue";
      if (approvalId) return "approval";
      if (matchedEvent) return "event";
      return "";
    });

    if (runtimeAgentId) {
      setPendingAgentTimelineTarget({
        runtimeAgentId,
        runId: selectedRun.id,
        approvalId,
        issueId,
        shadowAuditId: preservesSelectedShadowAudit ? selectedSessionShadowAudit?.id : "",
      });
    }
  }, [
    selectedRun,
    selectedRunResult,
    selectedSession,
    setPendingAgentTimelineTarget,
    setSelectedSessionApprovalId,
    setSelectedSessionContextKind,
    setSelectedSessionEventKey,
    setSelectedSessionIssueId,
    setSelectedSessionAsyncTaskId,
    setSelectedSessionShadowAuditId,
    setSelectedSessionToolPermissionRuntimeId,
    selectedSessionAsyncTask,
    selectedSessionContextKind,
    selectedSessionShadowAudit,
    selectedSessionToolPermissionRuntime,
  ]);

  const openSelectedRunResultInTimeline = useCallback(() => {
    const selectedRunResultRecord = asRecord(selectedRunResult);
    if (!selectedRun || !selectedRunResultRecord) return;
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResultRecord);
    if (!runtimeAgentId) {
      setErrorMessage("Selected outcome is not linked to a runtime agent.");
      return;
    }

    setErrorMessage("");
    setAgentTimelineFilter("all");
    setAgentTimelineSearch("");
    setSelectedAgentTimelineKey("");
    setSelectedAgentId(runtimeAgentId);
    setPendingAgentTimelineTarget({
      runtimeAgentId,
      runId: selectedRun.id,
      approvalId: toStringValue(asRecord(selectedRunResultRecord.approval)?.id),
      issueId: toStringValue(asRecord(selectedRunResultRecord.issue)?.id),
    });
  }, [
    selectedRun,
    selectedRunResult,
    setAgentTimelineFilter,
    setAgentTimelineSearch,
    setErrorMessage,
    setPendingAgentTimelineTarget,
    setSelectedAgentId,
    setSelectedAgentTimelineKey,
  ]);

  const selectedSessionContext = useMemo<SelectedSessionContextValue | null>(() => {
    if (selectedSessionContextKind === "issue" && selectedSessionIssue) {
      return { kind: "issue", issue: selectedSessionIssue };
    }
    if (selectedSessionContextKind === "approval" && selectedSessionApproval) {
      return { kind: "approval", approval: selectedSessionApproval };
    }
    if (
      selectedSessionContextKind === "tool_permission_runtime" &&
      selectedSessionToolPermissionRuntime
    ) {
      return { kind: "tool_permission_runtime", runtime: selectedSessionToolPermissionRuntime };
    }
    if (selectedSessionContextKind === "async_task" && selectedSessionAsyncTask) {
      return { kind: "async_task", task: selectedSessionAsyncTask };
    }
    if (selectedSessionContextKind === "shadow_audit" && selectedSessionShadowAudit) {
      return { kind: "shadow_audit", shadowAudit: selectedSessionShadowAudit };
    }
    if (selectedSessionContextKind === "event" && selectedSessionEvent) {
      return { kind: "event", event: selectedSessionEvent };
    }
    if (selectedSessionShadowAudit) {
      return { kind: "shadow_audit", shadowAudit: selectedSessionShadowAudit };
    }
    if (selectedSessionIssue) {
      return { kind: "issue", issue: selectedSessionIssue };
    }
    if (selectedSessionApproval) {
      return { kind: "approval", approval: selectedSessionApproval };
    }
    if (selectedSessionToolPermissionRuntime) {
      return { kind: "tool_permission_runtime", runtime: selectedSessionToolPermissionRuntime };
    }
    if (selectedSessionAsyncTask) {
      return { kind: "async_task", task: selectedSessionAsyncTask };
    }
    if (selectedSessionEvent) {
      return { kind: "event", event: selectedSessionEvent };
    }
    return null;
  }, [
    selectedSessionApproval,
    selectedSessionContextKind,
    selectedSessionEvent,
    selectedSessionIssue,
    selectedSessionAsyncTask,
    selectedSessionShadowAudit,
    selectedSessionToolPermissionRuntime,
  ]);

  const revealSelectedSessionContextRow = useCallback(() => {
    if (!selectedSessionContext) return;
    setEntitySearch("");
    if (selectedSessionContext.kind === "event") {
      setEventFilter("all");
      setPendingSessionRowDomId(
        sessionContextRowDomId(
          "event",
          selectedSessionEventKey || sessionEventKey(selectedSessionContext.event)
        )
      );
      return;
    }
    if (selectedSessionContext.kind === "approval") {
      setPendingSessionRowDomId(
        sessionContextRowDomId("approval", selectedSessionContext.approval.id)
      );
      return;
    }
    if (selectedSessionContext.kind === "tool_permission_runtime") {
      setPendingSessionRowDomId(
        sessionContextRowDomId("tool_permission_runtime", selectedSessionContext.runtime.id)
      );
      return;
    }
    if (selectedSessionContext.kind === "async_task") {
      setPendingSessionRowDomId(sessionContextRowDomId("async_task", selectedSessionContext.task.id));
      return;
    }
    if (selectedSessionContext.kind === "shadow_audit") {
      setPendingSessionRowDomId(
        sessionContextRowDomId("shadow_audit", selectedSessionContext.shadowAudit.id)
      );
      return;
    }
    setPendingSessionRowDomId(sessionContextRowDomId("issue", selectedSessionContext.issue.id));
  }, [
    selectedSessionContext,
    selectedSessionEventKey,
    setEntitySearch,
    setEventFilter,
    setPendingSessionRowDomId,
  ]);

  const revealSelectedSessionContextInAgentTimeline = useCallback(() => {
    if (!selectedSessionContext) return;
    const linkedShadowAuditTask =
      selectedSessionContext.kind === "shadow_audit"
        ? (selectedSession?.async_tasks || []).find(
            (task) =>
              task.id === selectedSessionContext.shadowAudit.source_id ||
              task.id === selectedSessionContext.shadowAudit.blocked_artifact_owner_id
          ) || null
        : null;
    const approvalId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.id
        : selectedSessionContext.kind === "tool_permission_runtime"
          ? selectedSessionContext.runtime.approval_id
          : selectedSessionContext.kind === "async_task"
            ? selectedSessionContext.task.approval_id
        : selectedSessionContext.kind === "shadow_audit"
          ? linkedShadowAuditTask?.approval_id ||
            toStringValue(selectedSessionContext.shadowAudit.metadata?.approval_id)
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.approval_id
          : toStringValue(selectedSessionContext.event.approval_id);
    const issueId =
      selectedSessionContext.kind === "issue"
        ? selectedSessionContext.issue.id
        : selectedSessionContext.kind === "tool_permission_runtime"
        ? selectedSessionContext.runtime.issue_id
        : selectedSessionContext.kind === "approval"
          ? selectedSessionContext.approval.issue_id
          : selectedSessionContext.kind === "async_task"
            ? selectedSessionContext.task.issue_id
          : selectedSessionContext.kind === "shadow_audit"
            ? linkedShadowAuditTask?.issue_id ||
              toStringValue(selectedSessionContext.shadowAudit.metadata?.issue_id)
          : toStringValue(selectedSessionContext.event.issue_id);
    const runtimeAgentId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.runtime_agent_ids[0]
        : selectedSessionContext.kind === "tool_permission_runtime"
          ? selectedSessionContext.runtime.runtime_agent_ids[0]
          : selectedSessionContext.kind === "async_task"
            ? selectedSessionContext.task.runtime_agent_ids[0] ||
              selectedSessionContext.task.runtime_agent_id
        : selectedSessionContext.kind === "shadow_audit"
          ? selectedSessionContext.shadowAudit.runtime_agent_ids[0] ||
            linkedShadowAuditTask?.runtime_agent_ids[0] ||
            linkedShadowAuditTask?.runtime_agent_id ||
            toStringValue(selectedSessionContext.shadowAudit.metadata?.runtime_agent_id) ||
            toStringArray(selectedSessionContext.shadowAudit.metadata?.runtime_agent_ids)[0]
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.runtime_agent_ids[0] ||
            selectedSessionContext.issue.runtime_agent_id
          : toStringValue(selectedSessionContext.event.runtime_agent_id) ||
            toStringArray(selectedSessionContext.event.runtime_agent_ids)[0];

    if (!runtimeAgentId) {
      setErrorMessage("Selected session context is not linked to a runtime agent.");
      return;
    }

    setErrorMessage("");
    syncLinkedSelection({
      approvalId,
      issueId,
      toolPermissionRuntimeId:
        selectedSessionContext.kind === "tool_permission_runtime"
          ? selectedSessionContext.runtime.id
          : "",
      asyncTaskId: selectedSessionContext.kind === "async_task" ? selectedSessionContext.task.id : "",
      shadowAuditId:
        selectedSessionContext.kind === "shadow_audit"
          ? selectedSessionContext.shadowAudit.id
          : "",
      runtimeAgentId,
      runId:
        selectedSessionContext.kind === "event"
          ? toStringValue(selectedSessionContext.event.agent_action_run_id) ||
            toStringValue(selectedSessionContext.event.run_id)
          : selectedSessionContext.kind === "async_task"
            ? selectedSessionContext.task.agent_action_run_id
          : selectedSessionContext.kind === "shadow_audit"
            ? linkedShadowAuditTask?.agent_action_run_id ||
              toStringValue(selectedSessionContext.shadowAudit.metadata?.agent_action_run_id) ||
              toStringValue(selectedSessionContext.shadowAudit.metadata?.run_id)
          : "",
      event: selectedSessionContext.kind === "event" ? selectedSessionContext.event : null,
    });
  }, [selectedSession, selectedSessionContext, setErrorMessage, syncLinkedSelection]);

  return {
    syncLinkedSelection,
    inspectSessionLineageEntry,
    focusSessionLineageEntry,
    openSelectedRunResultInTimeline,
    selectedSessionContext,
    revealSelectedSessionContextRow,
    revealSelectedSessionContextInAgentTimeline,
  };
}
