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
  OrchestratorSessionDetail,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

export type SelectedSessionContextValue =
  | { kind: "approval"; approval: ExecutionApprovalRecord }
  | { kind: "issue"; issue: ExecutionIssueRecord }
  | { kind: "tool_permission_runtime"; runtime: ToolPermissionRuntimeRecord }
  | { kind: "event"; event: Record<string, unknown> };

type UseControlPlaneLinkedSelectionArgs = {
  linkedRuns: ExecutionAgentActionRunRecord[];
  selectedSession: OrchestratorSessionDetail | null;
  selectedSessionApproval: ExecutionApprovalRecord | null;
  selectedSessionIssue: ExecutionIssueRecord | null;
  selectedSessionToolPermissionRuntime: ToolPermissionRuntimeRecord | null;
  selectedSessionEvent: Record<string, unknown> | null;
  selectedSessionEventKey: string;
  selectedSessionContextKind: SessionContextKind;
  selectedRun: ExecutionAgentActionRunRecord | null;
  selectedRunResult: unknown;
  setSelectedSessionApprovalId: Dispatch<SetStateAction<string>>;
  setSelectedSessionIssueId: Dispatch<SetStateAction<string>>;
  setSelectedSessionToolPermissionRuntimeId: Dispatch<SetStateAction<string>>;
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
  selectedSessionEvent,
  selectedSessionEventKey,
  selectedSessionContextKind,
  selectedRun,
  selectedRunResult,
  setSelectedSessionApprovalId,
  setSelectedSessionIssueId,
  setSelectedSessionToolPermissionRuntimeId,
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

      if (toolPermissionRuntimeId) {
        setSelectedSessionApprovalId("");
        setSelectedSessionIssueId("");
        setSelectedSessionToolPermissionRuntimeId(toolPermissionRuntimeId);
        setSelectedSessionEventKey("");
        setSelectedSessionContextKind("tool_permission_runtime");
      } else {
        setSelectedSessionApprovalId(approvalId);
        setSelectedSessionIssueId(issueId);
        setSelectedSessionToolPermissionRuntimeId("");
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

    setSelectedSessionApprovalId(approvalId);
    setSelectedSessionIssueId(issueId);
    setSelectedSessionToolPermissionRuntimeId("");
    setSelectedSessionEventKey(matchedEvent?.key || "");
    setSelectedSessionContextKind((current) => {
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
    setSelectedSessionToolPermissionRuntimeId,
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
    if (selectedSessionContextKind === "event" && selectedSessionEvent) {
      return { kind: "event", event: selectedSessionEvent };
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
    if (selectedSessionEvent) {
      return { kind: "event", event: selectedSessionEvent };
    }
    return null;
  }, [
    selectedSessionApproval,
    selectedSessionContextKind,
    selectedSessionEvent,
    selectedSessionIssue,
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
    const approvalId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.id
        : selectedSessionContext.kind === "tool_permission_runtime"
          ? selectedSessionContext.runtime.approval_id
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
          : toStringValue(selectedSessionContext.event.issue_id);
    const runtimeAgentId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.runtime_agent_ids[0]
        : selectedSessionContext.kind === "tool_permission_runtime"
          ? selectedSessionContext.runtime.runtime_agent_ids[0]
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
      runtimeAgentId,
      runId:
        selectedSessionContext.kind === "event"
          ? toStringValue(selectedSessionContext.event.agent_action_run_id) ||
            toStringValue(selectedSessionContext.event.run_id)
          : "",
      event: selectedSessionContext.kind === "event" ? selectedSessionContext.event : null,
    });
  }, [selectedSessionContext, setErrorMessage, syncLinkedSelection]);

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
