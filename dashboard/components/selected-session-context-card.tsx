"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { RelationshipStrip, SessionMetric, type RelationshipStripItem } from "@/components/control-plane-display";
import { approvalStatusClass, issueSeverityClass, issueStatusClass, passStatusClass } from "@/lib/control-plane-ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ShadowAuditReviewSheet } from "@/components/shadow-audit-review-sheet";
import { useShadowAuditReviewController } from "@/lib/use-shadow-audit-review-controller";
import {
  fetchExecutionPlaneRuntimeAgentTaskOutput,
  fetchExecutionPlaneRuntimeAgentTaskTranscript,
} from "@/lib/api";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  ExecutionShadowAuditRecord,
  ExecutionRuntimeAgentTaskRecord,
  ExecutionRuntimeAgentTaskOutputArtifact,
  ExecutionRuntimeAgentTaskTranscriptArtifact,
  OrchestratorSessionDetail,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

type SelectedSessionContextValue =
  | { kind: "approval"; approval: ExecutionApprovalRecord }
  | { kind: "issue"; issue: ExecutionIssueRecord }
  | { kind: "tool_permission_runtime"; runtime: ToolPermissionRuntimeRecord }
  | { kind: "async_task"; task: ExecutionRuntimeAgentTaskRecord }
  | { kind: "shadow_audit"; shadowAudit: ExecutionShadowAuditRecord }
  | { kind: "event"; event: Record<string, unknown> };

function formatToolPermissionStage(value?: string | null): string {
  const normalized = (value || "").trim();
  if (normalized === "pending_user") return "Waiting for user";
  if (normalized === "pending_hook") return "Waiting for hook";
  if (normalized === "pending_classifier") return "Waiting for classifier";
  return normalized ? normalized.replaceAll("_", " ") : "Pending";
}

function extractToolPermissionMessage(runtime: ToolPermissionRuntimeRecord): string {
  const pendingStage = (runtime.pending_stage || "").trim();
  const stagePayload =
    pendingStage && runtime.payload && typeof runtime.payload === "object" && !Array.isArray(runtime.payload)
      ? runtime.payload[pendingStage]
      : null;
  if (
    stagePayload
    && typeof stagePayload === "object"
    && !Array.isArray(stagePayload)
    && typeof (stagePayload as Record<string, unknown>).message === "string"
    && (stagePayload as Record<string, string>).message
  ) {
    return (stagePayload as Record<string, string>).message;
  }
  return runtime.message || "Tool permission request is waiting for review.";
}

function shadowAuditSourceLabel(audit: ExecutionShadowAuditRecord): string {
  const sourceName = (audit.source_name || "").trim();
  if (sourceName) return sourceName;
  const sourceKind = (audit.source_kind || "").trim();
  if (!sourceKind) return "shadow audit";
  return sourceKind.replaceAll("_", " ");
}

type RelatedRunLink = {
  run: ExecutionAgentActionRunRecord;
  resultIndex: number;
};

type RunLinkResolverContext = {
  approvalId?: string;
  issueId?: string;
  runId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
  resultIndex?: number;
};

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type LinkedSelectionPayload = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  toolPermissionRuntimeId?: string;
  asyncTaskId?: string;
  shadowAuditId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

type SelectedSessionContextCardProps = {
  selectedSession: OrchestratorSessionDetail | null;
  selectedSessionContext: SelectedSessionContextValue | null;
  linkedRuns: ExecutionAgentActionRunRecord[];
  busyActionKey: string;
  currentSessionLineageQueue: "" | "attention" | "decisions" | null;
  formatTimestamp: (value?: string | null) => string;
  formatJson: (value: unknown) => string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toStringArray: (value: unknown) => string[];
  toNullableNumber: (value: unknown) => number | null;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  eventFamily: (eventName: string) => string;
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  resolveRunLinkFromContext: (
    runs: ExecutionAgentActionRunRecord[],
    context: RunLinkResolverContext
  ) => RelatedRunLink | null;
  onCopyLink: () => void;
  onRevealSessionRow: () => void;
  onRevealInAgentTimeline: () => void;
  onOpenRuntimeAgent: (runtimeAgentId: string) => void;
  onSyncLinkedSelection: (payload: LinkedSelectionPayload) => void;
  onOpenRunOutcome: (runId: string, resultIndex: number) => void;
  onApproveApproval: (approval: ExecutionApprovalRecord) => void;
  onRejectApproval: (approval: ExecutionApprovalRecord) => void;
  onApplyApproval: (approval: ExecutionApprovalRecord) => void;
  onResolveIssue: (issue: ExecutionIssueRecord) => void;
  onAllowToolPermissionRuntime: (runtime: ToolPermissionRuntimeRecord) => void;
  onDenyToolPermissionRuntime: (runtime: ToolPermissionRuntimeRecord) => void;
  onResolveShadowAudit?: (audit: ExecutionShadowAuditRecord) => void;
  onLoadAsyncTaskOutputArtifact?: (
    task: ExecutionRuntimeAgentTaskRecord
  ) => Promise<ExecutionRuntimeAgentTaskOutputArtifact>;
  onLoadAsyncTaskTranscriptArtifact?: (
    task: ExecutionRuntimeAgentTaskRecord
  ) => Promise<ExecutionRuntimeAgentTaskTranscriptArtifact>;
  onRefreshAsyncTask?: (task: ExecutionRuntimeAgentTaskRecord) => void;
  onWaitForAsyncTaskSettlement?: (task: ExecutionRuntimeAgentTaskRecord) => void;
  onCancelAsyncTask?: (task: ExecutionRuntimeAgentTaskRecord) => void;
  onAdvanceCurrentQueue?: (() => void) | null;
};

export function SelectedSessionContextCard({
  selectedSession,
  selectedSessionContext,
  linkedRuns,
  busyActionKey,
  currentSessionLineageQueue,
  formatTimestamp,
  formatJson,
  toStringValue,
  toStringArray,
  toNullableNumber,
  asRecord,
  eventFamily,
  describeRunResult,
  resolveRunLinkFromContext,
  onCopyLink,
  onRevealSessionRow,
  onRevealInAgentTimeline,
  onOpenRuntimeAgent,
  onSyncLinkedSelection,
  onOpenRunOutcome,
  onApproveApproval,
  onRejectApproval,
  onApplyApproval,
  onResolveIssue,
  onAllowToolPermissionRuntime,
  onDenyToolPermissionRuntime,
  onResolveShadowAudit,
  onLoadAsyncTaskOutputArtifact,
  onLoadAsyncTaskTranscriptArtifact,
  onRefreshAsyncTask,
  onWaitForAsyncTaskSettlement,
  onCancelAsyncTask,
  onAdvanceCurrentQueue,
}: SelectedSessionContextCardProps) {
  const selectedAsyncTaskContext =
    selectedSessionContext?.kind === "async_task" ? selectedSessionContext.task : null;
  const selectedShadowAuditContext =
    selectedSessionContext?.kind === "shadow_audit" ? selectedSessionContext.shadowAudit : null;
  const selectedAsyncTaskResetKey =
    selectedAsyncTaskContext
      ? [
          selectedAsyncTaskContext.id,
          selectedAsyncTaskContext.status,
          selectedAsyncTaskContext.updated_at,
          selectedAsyncTaskContext.output_artifact_ref || "",
          selectedAsyncTaskContext.transcript_artifact_ref || "",
        ].join(":")
      : "";
  const [autoOpenedSessionShadowAuditKey, setAutoOpenedSessionShadowAuditKey] = useState("");
  const [taskOutputArtifact, setTaskOutputArtifact] =
    useState<ExecutionRuntimeAgentTaskOutputArtifact | null>(null);
  const [taskTranscriptArtifact, setTaskTranscriptArtifact] =
    useState<ExecutionRuntimeAgentTaskTranscriptArtifact | null>(null);
  const [taskOutputError, setTaskOutputError] = useState("");
  const [taskTranscriptError, setTaskTranscriptError] = useState("");
  const [loadingTaskOutput, setLoadingTaskOutput] = useState(false);
  const [loadingTaskTranscript, setLoadingTaskTranscript] = useState(false);
  const [showTaskOutput, setShowTaskOutput] = useState(false);
  const [showTaskTranscript, setShowTaskTranscript] = useState(false);
  const taskOutputShadowAudits = useMemo(
    () =>
      selectedAsyncTaskContext
        ? (taskOutputArtifact?.shadow_audits || []).filter(
            (audit) => audit.open || audit.status === "open"
          )
        : [],
    [selectedAsyncTaskContext, taskOutputArtifact]
  );
  const syncTaskOutputShadowAuditSelection = useCallback(
    (audit: ExecutionShadowAuditRecord) => {
      if (!selectedAsyncTaskContext) return;
      onSyncLinkedSelection({
        shadowAuditId: audit.id,
        asyncTaskId: selectedAsyncTaskContext.id,
        runId: selectedAsyncTaskContext.agent_action_run_id,
        approvalId: selectedAsyncTaskContext.approval_id,
        issueId: selectedAsyncTaskContext.issue_id,
        runtimeAgentId:
          audit.runtime_agent_ids[0] ||
          selectedAsyncTaskContext.runtime_agent_ids[0] ||
          selectedAsyncTaskContext.runtime_agent_id,
      });
    },
    [onSyncLinkedSelection, selectedAsyncTaskContext]
  );
  const {
    queueAudits: taskOutputQueueAudits,
    queueOpen: taskOutputQueueOpen,
    setQueueOpen: setTaskOutputQueueOpen,
    activeQueueAudit: activeTaskOutputQueueAudit,
    activeQueueAuditIndex: activeTaskOutputQueueAuditIndex,
    reviewQueueLabel: taskOutputReviewQueueLabel,
    openReviewQueue: openTaskOutputShadowAuditQueue,
    handleSelectNextQueuedAudit: handleSelectNextTaskOutputQueuedAudit,
    handleSelectPreviousQueuedAudit: handleSelectPreviousTaskOutputQueuedAudit,
    handleResolveQueuedShadowAudit: handleResolveTaskOutputQueuedShadowAudit,
  } = useShadowAuditReviewController({
    audits: taskOutputShadowAudits,
    onInspectShadowAudit: syncTaskOutputShadowAuditSelection,
    onResolveShadowAudit,
    singleReviewLabel: "Inspect review",
  });
  const sessionContextShadowAudits = useMemo(() => {
    const openSessionShadowAudits = (selectedSession?.shadow_audits || []).filter(
      (audit) => audit.open || audit.status === "open"
    );
    if (!selectedShadowAuditContext) return openSessionShadowAudits;
    if (openSessionShadowAudits.some((audit) => audit.id === selectedShadowAuditContext.id)) {
      return openSessionShadowAudits;
    }
    return [selectedShadowAuditContext, ...openSessionShadowAudits];
  }, [selectedSession?.shadow_audits, selectedShadowAuditContext]);
  const resolveLinkedShadowAuditTask = useCallback(
    (audit: ExecutionShadowAuditRecord) =>
      (selectedSession?.async_tasks || []).find(
      (task) => task.id === audit.source_id || task.id === audit.blocked_artifact_owner_id
      ) || null,
    [selectedSession?.async_tasks]
  );
  const syncSessionShadowAuditSelection = useCallback(
    (audit: ExecutionShadowAuditRecord) => {
      const linkedTask = resolveLinkedShadowAuditTask(audit);
      onSyncLinkedSelection({
        shadowAuditId: audit.id,
        asyncTaskId: linkedTask?.id,
        runId: linkedTask?.agent_action_run_id,
        approvalId:
          linkedTask?.approval_id || toStringValue(audit.metadata?.approval_id) || undefined,
        issueId: linkedTask?.issue_id || toStringValue(audit.metadata?.issue_id) || undefined,
        runtimeAgentId:
          audit.runtime_agent_ids[0] ||
          linkedTask?.runtime_agent_ids[0] ||
          linkedTask?.runtime_agent_id ||
          toStringValue(audit.metadata?.runtime_agent_id) ||
          toStringArray(audit.metadata?.runtime_agent_ids)[0],
      });
    },
    [onSyncLinkedSelection, resolveLinkedShadowAuditTask, toStringArray, toStringValue]
  );
  const {
    queueAudits: sessionContextQueueAudits,
    queueOpen: sessionContextQueueOpen,
    setQueueOpen: setSessionContextQueueOpen,
    activeQueueAudit: activeSessionContextQueueAudit,
    activeQueueAuditIndex: activeSessionContextQueueAuditIndex,
    reviewQueueLabel: sessionContextReviewQueueLabel,
    openReviewQueue: openSessionContextShadowAuditQueue,
    handleSelectNextQueuedAudit: handleSelectNextSessionContextQueuedAudit,
    handleSelectPreviousQueuedAudit: handleSelectPreviousSessionContextQueuedAudit,
    handleResolveQueuedShadowAudit: handleResolveSessionContextQueuedShadowAudit,
  } = useShadowAuditReviewController({
    audits: sessionContextShadowAudits,
    onInspectShadowAudit: syncSessionShadowAuditSelection,
    onResolveShadowAudit,
  });

  useEffect(() => {
    setTaskOutputArtifact(null);
    setTaskTranscriptArtifact(null);
    setTaskOutputError("");
    setTaskTranscriptError("");
    setLoadingTaskOutput(false);
    setLoadingTaskTranscript(false);
    setShowTaskOutput(false);
    setShowTaskTranscript(false);
  }, [selectedAsyncTaskResetKey]);
  useEffect(() => {
    if (selectedSessionContext?.kind === "shadow_audit" && selectedShadowAuditContext) return;
    setAutoOpenedSessionShadowAuditKey("");
  }, [selectedSessionContext?.kind, selectedShadowAuditContext]);
  useEffect(() => {
    if (!selectedShadowAuditContext) return;
    const autoOpenKey = `${selectedSession?.id || ""}:${selectedShadowAuditContext.id}`;
    if (autoOpenedSessionShadowAuditKey === autoOpenKey) return;
    openSessionContextShadowAuditQueue(selectedShadowAuditContext.id);
    setAutoOpenedSessionShadowAuditKey(autoOpenKey);
  }, [
    autoOpenedSessionShadowAuditKey,
    openSessionContextShadowAuditQueue,
    selectedSession?.id,
    selectedShadowAuditContext,
  ]);

  async function handleTaskOutputToggle(task: ExecutionRuntimeAgentTaskRecord) {
    const taskId = task.id;
    if (!taskId) return;
    if (showTaskOutput) {
      setShowTaskOutput(false);
      return;
    }
    setShowTaskOutput(true);
    if (taskOutputArtifact || loadingTaskOutput) return;
    setLoadingTaskOutput(true);
    setTaskOutputError("");
    try {
      setTaskOutputArtifact(
        await (onLoadAsyncTaskOutputArtifact
          ? onLoadAsyncTaskOutputArtifact(task)
          : fetchExecutionPlaneRuntimeAgentTaskOutput(taskId))
      );
    } catch (error) {
      setTaskOutputError(error instanceof Error ? error.message : "Failed to load task output.");
    } finally {
      setLoadingTaskOutput(false);
    }
  }

  async function handleTaskTranscriptToggle(task: ExecutionRuntimeAgentTaskRecord) {
    const taskId = task.id;
    if (!taskId) return;
    if (showTaskTranscript) {
      setShowTaskTranscript(false);
      return;
    }
    setShowTaskTranscript(true);
    if (taskTranscriptArtifact || loadingTaskTranscript) return;
    setLoadingTaskTranscript(true);
    setTaskTranscriptError("");
    try {
      setTaskTranscriptArtifact(
        await (onLoadAsyncTaskTranscriptArtifact
          ? onLoadAsyncTaskTranscriptArtifact(task)
          : fetchExecutionPlaneRuntimeAgentTaskTranscript(taskId))
      );
    } catch (error) {
      setTaskTranscriptError(error instanceof Error ? error.message : "Failed to load task transcript.");
    } finally {
      setLoadingTaskTranscript(false);
    }
  }

  function shadowAuditStatusClass(status: string): string {
    switch (status) {
      case "open":
        return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
      case "resolved":
        return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
      default:
        return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
    }
  }

  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Selected Session Context
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Compact inspector for the currently selected session approval, issue, shadow audit, or event.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedSession ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a session to inspect linked context.
          </div>
        ) : !selectedSessionContext ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Pick an approval, issue, shadow audit, tool-permission runtime, event, or outcome to open the unified context inspector.
          </div>
        ) : (
          (() => {
            const contextKind = selectedSessionContext.kind;
            const approvalContext =
              contextKind === "approval" ? selectedSessionContext.approval : null;
            const issueContext = contextKind === "issue" ? selectedSessionContext.issue : null;
            const runtimeContext =
              contextKind === "tool_permission_runtime" ? selectedSessionContext.runtime : null;
            const asyncTaskContext =
              contextKind === "async_task" ? selectedSessionContext.task : null;
            const shadowAuditContext = selectedShadowAuditContext;
            const eventContext = contextKind === "event" ? selectedSessionContext.event : null;
            const linkedShadowAuditTask =
              shadowAuditContext
                ? resolveLinkedShadowAuditTask(shadowAuditContext)
                : null;
            const relatedApprovalId =
              approvalContext?.id ||
              asyncTaskContext?.approval_id ||
              linkedShadowAuditTask?.approval_id ||
              runtimeContext?.approval_id ||
              issueContext?.approval_id ||
              toStringValue(shadowAuditContext?.metadata?.approval_id) ||
              toStringValue(eventContext?.approval_id);
            const relatedIssueId =
              issueContext?.id ||
              asyncTaskContext?.issue_id ||
              linkedShadowAuditTask?.issue_id ||
              runtimeContext?.issue_id ||
              approvalContext?.issue_id ||
              toStringValue(shadowAuditContext?.metadata?.issue_id) ||
              toStringValue(eventContext?.issue_id);
            const runtimeAgentId =
              approvalContext?.runtime_agent_ids[0] ||
              asyncTaskContext?.runtime_agent_ids[0] ||
              asyncTaskContext?.runtime_agent_id ||
              shadowAuditContext?.runtime_agent_ids[0] ||
              linkedShadowAuditTask?.runtime_agent_ids[0] ||
              linkedShadowAuditTask?.runtime_agent_id ||
              runtimeContext?.runtime_agent_ids[0] ||
              issueContext?.runtime_agent_ids[0] ||
              issueContext?.runtime_agent_id ||
              toStringValue(shadowAuditContext?.metadata?.runtime_agent_id) ||
              toStringArray(shadowAuditContext?.metadata?.runtime_agent_ids)[0] ||
              toStringValue(eventContext?.runtime_agent_id) ||
              toStringArray(eventContext?.runtime_agent_ids)[0] ||
              "";
            const projectId =
              approvalContext?.project_id ||
              asyncTaskContext?.project_id ||
              shadowAuditContext?.project_id ||
              linkedShadowAuditTask?.project_id ||
              runtimeContext?.project_id ||
              issueContext?.project_id ||
              toStringValue(eventContext?.project_id);
            const storyId =
              issueContext?.story_id ??
              toNullableNumber(asyncTaskContext?.metadata?.story_id) ??
              toNullableNumber(linkedShadowAuditTask?.metadata?.story_id) ??
              toNullableNumber(shadowAuditContext?.metadata?.story_id) ??
              toNullableNumber(runtimeContext?.metadata?.story_id) ??
              toNullableNumber(runtimeContext?.payload?.story_id) ??
              toNullableNumber(eventContext?.story_id);
            const workspaceHref =
              projectId && storyId
                ? `/projects/${projectId}?storyId=${storyId}`
                : projectId
                  ? `/projects/${projectId}`
                  : "";
            const relatedRunLink = resolveRunLinkFromContext(linkedRuns, {
              approvalId: relatedApprovalId,
              issueId: relatedIssueId,
              runId:
                asyncTaskContext?.agent_action_run_id ||
                linkedShadowAuditTask?.agent_action_run_id ||
                toStringValue(shadowAuditContext?.metadata?.agent_action_run_id) ||
                toStringValue(shadowAuditContext?.metadata?.run_id) ||
                toStringValue(eventContext?.agent_action_run_id) ||
                toStringValue(eventContext?.run_id),
              runtimeAgentId,
              event: eventContext,
            });
            const relatedRunResult =
              relatedRunLink && relatedRunLink.run.results[relatedRunLink.resultIndex]
                ? asRecord(relatedRunLink.run.results[relatedRunLink.resultIndex])
                : null;
            const relatedOutcome = relatedRunResult
              ? describeRunResult(relatedRunResult)
              : null;
            const title =
              approvalContext?.action ||
              asyncTaskContext?.title ||
              asyncTaskContext?.command ||
              (shadowAuditContext ? shadowAuditSourceLabel(shadowAuditContext) : "") ||
              runtimeContext?.tool_name ||
              issueContext?.title ||
              issueContext?.root_cause ||
              issueContext?.id ||
              toStringValue(eventContext?.event, "unknown_event");
            const subtitle =
              approvalContext?.reason ||
              asyncTaskContext?.result_summary ||
              asyncTaskContext?.reason ||
              asyncTaskContext?.placeholder_result ||
              shadowAuditContext?.summary ||
              (runtimeContext ? extractToolPermissionMessage(runtimeContext) : "") ||
              issueContext?.root_cause ||
              issueContext?.description ||
              toStringValue(eventContext?.message, "No event message") ||
              "No detail provided.";
            const timestamp =
              approvalContext?.applied_at ||
              approvalContext?.decided_at ||
              approvalContext?.updated_at ||
              approvalContext?.created_at ||
              asyncTaskContext?.completed_at ||
              asyncTaskContext?.updated_at ||
              asyncTaskContext?.created_at ||
              shadowAuditContext?.resolved_at ||
              shadowAuditContext?.updated_at ||
              shadowAuditContext?.created_at ||
              runtimeContext?.resolved_at ||
              runtimeContext?.updated_at ||
              runtimeContext?.created_at ||
              issueContext?.resolved_at ||
              issueContext?.updated_at ||
              issueContext?.created_at ||
              toStringValue(eventContext?.timestamp);
            const status =
              approvalContext?.status ||
              asyncTaskContext?.status ||
              shadowAuditContext?.status ||
              runtimeContext?.status ||
              issueContext?.status ||
              toStringValue(eventContext?.status, "unknown");
            const statusClass =
              contextKind === "approval"
                ? approvalStatusClass(status)
                : contextKind === "issue"
                  ? issueStatusClass(status)
                  : contextKind === "shadow_audit"
                    ? shadowAuditStatusClass(status)
                  : passStatusClass(status);
            const payload =
              (approvalContext ? asRecord(approvalContext) : null) ||
              (asyncTaskContext ? asRecord(asyncTaskContext) : null) ||
              (shadowAuditContext ? asRecord(shadowAuditContext) : null) ||
              (runtimeContext ? asRecord(runtimeContext) : null) ||
              (issueContext ? asRecord(issueContext) : null) ||
              eventContext ||
              {};
            const contextId =
              approvalContext?.id ||
              asyncTaskContext?.id ||
              shadowAuditContext?.id ||
              runtimeContext?.id ||
              issueContext?.id ||
              toStringValue(eventContext?.id) ||
              title;
            const contextDetail =
              approvalContext?.action ||
              (asyncTaskContext
                ? `${asyncTaskContext.command || "task"} · ${asyncTaskContext.status || "running"}`
                : "") ||
              (shadowAuditContext
                ? `${shadowAuditSourceLabel(shadowAuditContext)}${
                    shadowAuditContext.blocked_artifact_owner_id
                      ? ` · blocked ${shadowAuditContext.blocked_artifact_owner_kind || "artifact"} ${shadowAuditContext.blocked_artifact_owner_id}`
                      : ""
                  }`
                : "") ||
              (runtimeContext
                ? `${runtimeContext.tool_name || "tool"} · ${formatToolPermissionStage(runtimeContext.pending_stage)}`
                : "") ||
              issueContext?.category ||
              toStringValue(eventContext?.event, "event");
            const runtimeAgentDetail =
              approvalContext?.requested_by ||
              (asyncTaskContext
                ? `${asyncTaskContext.actor || "unknown actor"}${
                    asyncTaskContext.resume_contract
                      ? ` · resume ${asyncTaskContext.resume_contract.command}`
                      : ""
                  }`
                : "") ||
              (shadowAuditContext
                ? `${shadowAuditContext.action || "quarantine"}${
                    shadowAuditContext.source_name ? ` · ${shadowAuditContext.source_name}` : ""
                  }`
                : "") ||
              (runtimeContext
                ? `${formatToolPermissionStage(runtimeContext.pending_stage)}${
                    runtimeContext.resolved_source ? ` · ${runtimeContext.resolved_source}` : ""
                  }`
                : "") ||
              issueContext?.related_command ||
              toStringValue(eventContext?.orchestrator_session_id, "No session token");

            return (
              <div className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                      >
                        {contextKind}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusClass}`}
                      >
                        {status}
                      </Badge>
                      {contextKind === "issue" && (
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issueContext?.severity || "unknown")}`}
                        >
                          {issueContext?.severity || "unknown"}
                        </Badge>
                      )}
                      {contextKind === "tool_permission_runtime" && runtimeContext && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                        >
                          {formatToolPermissionStage(runtimeContext.pending_stage)}
                        </Badge>
                      )}
                      {contextKind === "event" && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {eventFamily(toStringValue(eventContext?.event))}
                        </Badge>
                      )}
                      {contextKind === "async_task" && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                        >
                          {asyncTaskContext?.command || "background task"}
                        </Badge>
                      )}
                      {contextKind === "shadow_audit" && shadowAuditContext && (
                        <>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                          >
                            {shadowAuditSourceLabel(shadowAuditContext)}
                          </Badge>
                          {shadowAuditContext.blocked_artifact_owner_id ? (
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              blocked {shadowAuditContext.blocked_artifact_owner_kind || "artifact"}{" "}
                              {shadowAuditContext.blocked_artifact_owner_id}
                            </Badge>
                          ) : null}
                        </>
                      )}
                    </div>
                    <p className="mt-3 text-[14px] font-semibold text-[#37352f]">{title}</p>
                    <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">{subtitle}</p>
                  </div>
                  <div className="flex flex-wrap items-start justify-end gap-2">
                    <p className="text-[12px] text-[#9b9a97]">{formatTimestamp(timestamp)}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={onCopyLink}
                    >
                      Copy context link
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <SessionMetric label="ID" value={contextId} detail={contextDetail} />
                  <SessionMetric
                    label="Related Run"
                    value={relatedRunLink?.run.id || "No linked run"}
                    detail={
                      relatedRunLink
                        ? `${relatedRunLink.run.run_kind} · ${relatedRunLink.run.status}`
                        : "No action run linkage"
                    }
                  />
                  <SessionMetric
                    label="Runtime Agent"
                    value={runtimeAgentId || "No agent linkage"}
                    detail={runtimeAgentDetail}
                  />
                  <SessionMetric
                    label="Workspace"
                    value={projectId || "No project linkage"}
                    detail={storyId ? `story ${storyId}` : "No story linkage"}
                  />
                </div>

                <RelationshipStrip
                  label="Relationship Strip"
                  items={[
                    {
                      key: `context-${contextKind}-${contextId}`,
                      label:
                        contextKind === "tool_permission_runtime"
                          ? `tool permission ${contextId}`
                          : contextKind === "async_task"
                            ? `async task ${contextId}`
                            : contextKind === "shadow_audit"
                              ? `shadow audit ${contextId}`
                          : `${contextKind} ${contextId}`,
                      tone:
                        contextKind === "approval"
                          ? "approval"
                          : contextKind === "issue"
                            ? "issue"
                            : contextKind === "tool_permission_runtime"
                              ? "approval"
                            : contextKind === "shadow_audit"
                              ? "event"
                            : contextKind === "async_task"
                              ? "event"
                            : "event",
                      active: true,
                      onClick: onRevealSessionRow,
                    },
                    relatedRunLink
                      ? {
                          key: `run-${relatedRunLink.run.id}`,
                          label: `run ${relatedRunLink.run.id}`,
                          tone: "run" as const,
                          onClick: () => {
                            onOpenRunOutcome(relatedRunLink.run.id, 0);
                          },
                        }
                      : null,
                    relatedRunLink && relatedRunResult
                      ? {
                          key: `outcome-${relatedRunLink.run.id}-${relatedRunLink.resultIndex}`,
                          label: `outcome ${relatedRunLink.resultIndex + 1}`,
                          tone: "outcome" as const,
                          onClick: () => {
                            onOpenRunOutcome(relatedRunLink.run.id, relatedRunLink.resultIndex);
                          },
                        }
                      : null,
                    relatedApprovalId && contextKind !== "approval"
                      ? {
                          key: `approval-${relatedApprovalId}`,
                          label: `approval ${relatedApprovalId}`,
                          tone: "approval" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              toolPermissionRuntimeId: runtimeContext?.id,
                              asyncTaskId: asyncTaskContext?.id,
                              runtimeAgentId,
                              event: eventContext,
                            });
                          },
                        }
                      : null,
                    relatedIssueId && contextKind !== "issue"
                      ? {
                          key: `issue-${relatedIssueId}`,
                          label: `issue ${relatedIssueId}`,
                          tone: "issue" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              toolPermissionRuntimeId: runtimeContext?.id,
                              asyncTaskId: asyncTaskContext?.id,
                              runtimeAgentId,
                              event: eventContext,
                            });
                          },
                        }
                      : null,
                    runtimeAgentId
                      ? {
                          key: `agent-${runtimeAgentId}`,
                          label: `agent ${runtimeAgentId}`,
                          tone: "agent" as const,
                          onClick: onRevealInAgentTimeline,
                        }
                      : null,
                  ].filter(Boolean) as RelationshipStripItem[]}
                />

                {(projectId || storyId || runtimeAgentId || relatedApprovalId || relatedIssueId) && (
                  <div className="flex flex-wrap gap-2">
                    {projectId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        project {projectId}
                      </Badge>
                    )}
                    {storyId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        story {storyId}
                      </Badge>
                    )}
                    {runtimeAgentId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        agent {runtimeAgentId}
                      </Badge>
                    )}
                    {runtimeContext && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d6e9dc] bg-[#eef8f1] px-2.5 py-1 text-[11px] font-medium text-[#2b6e3f]"
                      >
                        use {runtimeContext.tool_use_id || runtimeContext.id}
                      </Badge>
                    )}
                    {asyncTaskContext?.output_artifact_ref && (
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                          asyncTaskContext.output_quarantined
                            ? "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]"
                            : "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]"
                        }`}
                      >
                        {asyncTaskContext.output_quarantined ? "output quarantined" : "output ready"}
                      </Badge>
                    )}
                    {shadowAuditContext?.artifact_ref ? (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        audit artifact ready
                      </Badge>
                    ) : null}
                    {shadowAuditContext?.blocked_artifact_ref ? (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        blocked artifact ready
                      </Badge>
                    ) : null}
                    {asyncTaskContext?.transcript_artifact_ref && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        transcript ready
                      </Badge>
                    )}
                    {relatedApprovalId && contextKind !== "approval" && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        approval {relatedApprovalId}
                      </Badge>
                    )}
                    {relatedIssueId && contextKind !== "issue" && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        issue {relatedIssueId}
                      </Badge>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {approvalContext?.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onApproveApproval(approvalContext);
                        }}
                      >
                        {busyActionKey === `approval-approve:${approvalContext.id}` ? "Approving..." : "Approve"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onRejectApproval(approvalContext);
                        }}
                      >
                        {busyActionKey === `approval-reject:${approvalContext.id}` ? "Rejecting..." : "Reject"}
                      </Button>
                    </>
                  )}
                  {approvalContext?.status === "approved" && (
                    <Button
                      size="sm"
                      className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onApplyApproval(approvalContext);
                      }}
                    >
                      {busyActionKey === `approval-apply:${approvalContext.id}` ? "Applying..." : "Apply"}
                    </Button>
                  )}
                  {issueContext?.status === "open" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onResolveIssue(issueContext);
                      }}
                    >
                      {busyActionKey === `issue-resolve:${issueContext.id}` ? "Resolving..." : "Resolve"}
                    </Button>
                  )}
                  {runtimeContext?.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onDenyToolPermissionRuntime(runtimeContext);
                        }}
                      >
                        {busyActionKey === `tool-permission-deny:${runtimeContext.id}`
                          ? "Denying..."
                          : "Deny"}
                      </Button>
                      <Button
                        size="sm"
                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onAllowToolPermissionRuntime(runtimeContext);
                        }}
                      >
                        {busyActionKey === `tool-permission-allow:${runtimeContext.id}`
                          ? "Allowing..."
                          : "Allow"}
                      </Button>
                    </>
                  )}
                  {asyncTaskContext && onRefreshAsyncTask && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onRefreshAsyncTask(asyncTaskContext);
                      }}
                    >
                      {busyActionKey === `async-task-refresh:${asyncTaskContext.id}`
                        ? "Refreshing..."
                        : "Refresh task"}
                    </Button>
                  )}
                  {asyncTaskContext && onWaitForAsyncTaskSettlement && !asyncTaskContext.terminal && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d6e9dc] bg-[#eef8f1] text-[12px] text-[#2b6e3f] hover:bg-[#e4f3e8]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onWaitForAsyncTaskSettlement(asyncTaskContext);
                      }}
                    >
                      {busyActionKey === `async-task-wait:${asyncTaskContext.id}`
                        ? "Waiting..."
                        : "Wait for settle"}
                    </Button>
                  )}
                  {asyncTaskContext && onCancelAsyncTask && !asyncTaskContext.terminal && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#f0d0c9] bg-[#fff0ed] text-[12px] text-[#93370d] hover:bg-[#ffe7e1]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onCancelAsyncTask(asyncTaskContext);
                      }}
                    >
                      {busyActionKey === `async-task-cancel:${asyncTaskContext.id}`
                        ? "Cancelling..."
                        : "Cancel task"}
                    </Button>
                  )}
                  {shadowAuditContext && onResolveShadowAudit && shadowAuditContext.open ? (
                    <Button
                      size="sm"
                      className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        void Promise.resolve(onResolveShadowAudit(shadowAuditContext)).catch(
                          () => {}
                        );
                      }}
                    >
                      {busyActionKey === `shadow-audit-resolve:${shadowAuditContext.id}`
                        ? "Resolving..."
                        : "Resolve handoff"}
                    </Button>
                  ) : null}
                  {shadowAuditContext ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                      onClick={() => {
                        openSessionContextShadowAuditQueue(shadowAuditContext.id);
                      }}
                    >
                      {sessionContextReviewQueueLabel}
                    </Button>
                  ) : null}
                  {runtimeAgentId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onOpenRuntimeAgent(runtimeAgentId);
                      }}
                    >
                      Open agent
                    </Button>
                  )}
                  {currentSessionLineageQueue && onAdvanceCurrentQueue ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={onAdvanceCurrentQueue}
                    >
                      {currentSessionLineageQueue === "attention" ? "Next attention" : "Next decision"}
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={onRevealSessionRow}
                  >
                    Reveal session row
                  </Button>
                  {runtimeAgentId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={onRevealInAgentTimeline}
                    >
                      Reveal in agent timeline
                    </Button>
                  )}
                  {relatedRunLink && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onOpenRunOutcome(relatedRunLink.run.id, relatedRunLink.resultIndex);
                      }}
                    >
                      Open related outcome
                    </Button>
                  )}
                  {workspaceHref && (
                    <Link
                      href={workspaceHref}
                      className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                    >
                      Open workspace
                    </Link>
                  )}
                </div>

                {relatedOutcome && (
                  <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Related Outcome
                    </p>
                    <p className="mt-2 text-[13px] font-semibold text-[#37352f]">
                      {relatedOutcome.title}
                    </p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">
                      {relatedOutcome.subtitle || "No outcome subtype"}
                    </p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">{relatedOutcome.message}</p>
                  </div>
                )}

                {shadowAuditContext && (
                  <div className="rounded-xl border border-[#f4e0c4] bg-[#fff9ef] p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
                      Shadow Audit Barrier
                    </p>
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      <SessionMetric
                        label="Source"
                        value={shadowAuditSourceLabel(shadowAuditContext)}
                        detail={shadowAuditContext.action || "quarantine"}
                      />
                      <SessionMetric
                        label="Blocked Owner"
                        value={
                          shadowAuditContext.blocked_artifact_owner_id || "No blocked owner linkage"
                        }
                        detail={
                          shadowAuditContext.blocked_artifact_owner_kind || "No blocked owner type"
                        }
                      />
                      <SessionMetric
                        label="Audit Artifact"
                        value={shadowAuditContext.artifact_ref || "No audit artifact ref"}
                        detail={shadowAuditContext.artifact_id || "No audit artifact id"}
                      />
                      <SessionMetric
                        label="Blocked Artifact"
                        value={
                          shadowAuditContext.blocked_artifact_ref || "No blocked artifact ref"
                        }
                        detail={shadowAuditContext.blocked_artifact_id || "No blocked artifact id"}
                      />
                    </div>
                    {shadowAuditContext.findings.length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {shadowAuditContext.findings.map((finding) => (
                          <Badge
                            key={`${shadowAuditContext.id}-${finding}`}
                            variant="outline"
                            className="rounded-full border-[#f4e0c4] bg-white px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                          >
                            {finding}
                          </Badge>
                        ))}
                      </div>
                    ) : null}
                  </div>
                )}
                {activeSessionContextQueueAudit ? (
                  <ShadowAuditReviewSheet
                    audit={activeSessionContextQueueAudit}
                    open={sessionContextQueueOpen}
                    onOpenChange={setSessionContextQueueOpen}
                    hideTrigger
                    busyActionKey={busyActionKey}
                    formatTimestamp={formatTimestamp}
                    onResolveShadowAudit={handleResolveSessionContextQueuedShadowAudit}
                    queueState={{
                      currentIndex: Math.max(activeSessionContextQueueAuditIndex, 0),
                      totalCount: sessionContextQueueAudits.length,
                      onSelectNext: handleSelectNextSessionContextQueuedAudit,
                      onSelectPrevious: handleSelectPreviousSessionContextQueuedAudit,
                    }}
                  />
                ) : null}

                {asyncTaskContext && (
                  <div className="grid gap-3 xl:grid-cols-2">
                    <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Output Artifact
                          </p>
                          <p className="mt-2 text-[12px] text-[#6b6b6b]">
                            {asyncTaskContext.output_artifact_ref
                              ? asyncTaskContext.output_quarantined
                                ? "Durable output exists but is quarantined until shadow-audit review is resolved."
                                : asyncTaskContext.output_preview || "Durable output is ready for inline inspection."
                              : "No durable output artifact is available yet."}
                          </p>
                        </div>
                        {asyncTaskContext.output_artifact_ref ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-lg border-[#d6e9dc] bg-white text-[12px] text-[#2b6e3f] hover:bg-[#eef8f1]"
                            disabled={loadingTaskOutput}
                            onClick={() => {
                              void handleTaskOutputToggle(asyncTaskContext);
                            }}
                          >
                            {loadingTaskOutput
                              ? "Loading..."
                              : showTaskOutput
                                ? "Hide output"
                                : taskOutputArtifact
                                  ? "Show output"
                                  : "Load output"}
                          </Button>
                        ) : null}
                      </div>
                      {asyncTaskContext.output_preview ? (
                        <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                          {asyncTaskContext.output_preview}
                        </pre>
                      ) : null}
                      {taskOutputError ? (
                        <p className="mt-3 text-[12px] text-[#b42318]">{taskOutputError}</p>
                      ) : null}
                      {showTaskOutput && taskOutputArtifact ? (
                        <>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {taskOutputArtifact.quarantined ? (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                              >
                                quarantined
                              </Badge>
                            ) : null}
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                                taskOutputArtifact.quarantined
                                  ? "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]"
                                  : "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]"
                              }`}
                            >
                              {taskOutputArtifact.content_bytes} bytes
                            </Badge>
                            {taskOutputArtifact.truncated ? (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                              >
                                truncated
                              </Badge>
                            ) : null}
                            {taskOutputArtifact.source_path ? (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                {taskOutputArtifact.source_path}
                              </Badge>
                            ) : null}
                          </div>
                          {taskOutputArtifact.content_blocked ? (
                            <div className="mt-3 rounded-lg border border-[#f4e0c4] bg-[#fff6e8] p-3">
                              <p className="text-[12px] font-medium text-[#9a6700]">
                                {taskOutputArtifact.message ||
                                  "Output content is blocked until shadow-audit review is resolved."}
                              </p>
                              {taskOutputQueueAudits.length > 0 ? (
                                <div className="mt-3 space-y-3">
                                  {taskOutputQueueAudits.map((audit) => (
                                    <div
                                      key={`${asyncTaskContext.id}-output-shadow-audit-${audit.id}`}
                                      className="rounded-lg border border-[#f4e0c4] bg-white p-3"
                                    >
                                      <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div>
                                          <div className="flex flex-wrap items-center gap-2">
                                            <p className="font-mono text-[11px] text-[#37352f]">
                                              {audit.id}
                                            </p>
                                            <Badge
                                              variant="outline"
                                              className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${shadowAuditStatusClass(audit.status)}`}
                                            >
                                              {audit.status}
                                            </Badge>
                                          </div>
                                          <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                            {audit.summary ||
                                              "Quarantined output requires explicit operator review."}
                                          </p>
                                          {audit.findings.length > 0 ? (
                                            <div className="mt-2 flex flex-wrap gap-2">
                                              {audit.findings.slice(0, 3).map((finding) => (
                                                <Badge
                                                  key={`${audit.id}-${finding}`}
                                                  variant="outline"
                                                  className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                                >
                                                  {finding}
                                                </Badge>
                                              ))}
                                            </div>
                                          ) : null}
                                        </div>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                                          onClick={() => {
                                            openTaskOutputShadowAuditQueue(audit.id);
                                          }}
                                        >
                                          {taskOutputReviewQueueLabel}
                                        </Button>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              ) : null}
                              {activeTaskOutputQueueAudit ? (
                                <ShadowAuditReviewSheet
                                  audit={activeTaskOutputQueueAudit}
                                  open={taskOutputQueueOpen}
                                  onOpenChange={setTaskOutputQueueOpen}
                                  hideTrigger
                                  busyActionKey={busyActionKey}
                                  formatTimestamp={formatTimestamp}
                                  onResolveShadowAudit={handleResolveTaskOutputQueuedShadowAudit}
                                  queueState={{
                                    currentIndex: Math.max(activeTaskOutputQueueAuditIndex, 0),
                                    totalCount: taskOutputQueueAudits.length,
                                    onSelectNext: handleSelectNextTaskOutputQueuedAudit,
                                    onSelectPrevious: handleSelectPreviousTaskOutputQueuedAudit,
                                  }}
                                />
                              ) : null}
                            </div>
                          ) : (
                            <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                              {taskOutputArtifact.content}
                            </pre>
                          )}
                        </>
                      ) : null}
                    </div>

                    <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Transcript Artifact
                          </p>
                          <p className="mt-2 text-[12px] text-[#6b6b6b]">
                            {asyncTaskContext.transcript_artifact_ref
                              ? `${asyncTaskContext.history.length} recorded lifecycle entries.`
                              : "No durable transcript artifact is available yet."}
                          </p>
                        </div>
                        {asyncTaskContext.transcript_artifact_ref ? (
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-lg border-[#d3e5ef] bg-white text-[12px] text-[#2a6690] hover:bg-[#eef7fb]"
                            disabled={loadingTaskTranscript}
                            onClick={() => {
                              void handleTaskTranscriptToggle(asyncTaskContext);
                            }}
                          >
                            {loadingTaskTranscript
                              ? "Loading..."
                              : showTaskTranscript
                                ? "Hide transcript"
                                : taskTranscriptArtifact
                                  ? "Show transcript"
                                  : "Load transcript"}
                          </Button>
                        ) : null}
                      </div>
                      {asyncTaskContext.history.length ? (
                        <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                          {formatJson(asyncTaskContext.history.slice(-3))}
                        </pre>
                      ) : null}
                      {taskTranscriptError ? (
                        <p className="mt-3 text-[12px] text-[#b42318]">{taskTranscriptError}</p>
                      ) : null}
                      {showTaskTranscript && taskTranscriptArtifact ? (
                        <>
                          <div className="mt-3 flex flex-wrap gap-2">
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                            >
                              updated {formatTimestamp(taskTranscriptArtifact.updated_at)}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {taskTranscriptArtifact.id}
                            </Badge>
                          </div>
                          <pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                            {taskTranscriptArtifact.content}
                          </pre>
                        </>
                      ) : null}
                    </div>
                  </div>
                )}

                <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Payload
                  </p>
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                    {formatJson(payload)}
                  </pre>
                </div>
              </div>
            );
          })()
        )}
      </CardContent>
    </Card>
  );
}
