import type { ComponentProps } from "react";
import { SessionDrilldownSection } from "@/components/session-drilldown-section";
import type { SessionLineageEntry } from "@/lib/control-plane-models";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  ExecutionRuntimeAgentTaskOutputArtifact,
  ExecutionRuntimeAgentTaskRecord,
  ExecutionRuntimeAgentTaskTranscriptArtifact,
  OrchestratorSessionControl,
  OrchestratorSessionControlProfile,
  OrchestratorSessionControlRecommendation,
  OrchestratorSessionDetail,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

type SessionDrilldownSectionProps = ComponentProps<typeof SessionDrilldownSection>;
type EventFilter = "all" | "control" | "actions" | "decisions" | "attention";
type RunFilter = "all" | "execute" | "preview" | "attention";

type BuildSessionDrilldownSectionPropsArgs = {
  selectedSessionId: string;
  sessionLoading: boolean;
  selectedSession: OrchestratorSessionDetail | null;
  selectedControl: OrchestratorSessionControl | null;
  linkedAgentIds: string[];
  selectedAgentId: string;
  focusRuntimeAgent: (runtimeAgentId: string, syncSearch?: boolean) => void;
  filteredRuns: ExecutionAgentActionRunRecord[];
  linkedRuns: ExecutionAgentActionRunRecord[];
  filteredEvents: Record<string, unknown>[];
  filteredApprovals: ExecutionApprovalRecord[];
  linkedApprovals: ExecutionApprovalRecord[];
  visibleSessionApprovals: ExecutionApprovalRecord[];
  filteredIssues: ExecutionIssueRecord[];
  linkedIssues: ExecutionIssueRecord[];
  visibleSessionIssues: ExecutionIssueRecord[];
  entitySearch: string;
  setEntitySearch: (value: string) => void;
  sortedProfiles: OrchestratorSessionControlProfile[];
  busyActionKey: string;
  latestPreviewRun: ExecutionAgentActionRunRecord | null;
  latestPreviewAppliedRun: ExecutionAgentActionRunRecord | null;
  applyControlPlan: (profile: OrchestratorSessionControlProfile) => Promise<void>;
  applyRecommendation: (recommendation: OrchestratorSessionControlRecommendation) => Promise<void>;
  applyPreviewRun: (run: ExecutionAgentActionRunRecord) => Promise<void>;
  runFilter: RunFilter;
  setRunFilter: (value: RunFilter) => void;
  matchesRunFilter: (run: ExecutionAgentActionRunRecord, filter: Exclude<RunFilter, "all">) => boolean;
  selectedRunId: string;
  setSelectedRunId: (runId: string) => void;
  setSelectedRunResultIndex: (resultIndex: number) => void;
  toNumber: (value: unknown, fallback?: number) => number;
  eventFilter: EventFilter;
  setEventFilter: (value: EventFilter) => void;
  matchesEventFilter: (event: Record<string, unknown>, filter: Exclude<EventFilter, "all">) => boolean;
  visibleSessionEvents: Record<string, unknown>[];
  selectedSessionEventKey: string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toStringArray: (value: unknown) => string[];
  toNullableNumber: (value: unknown) => number | null;
  formatTimestamp: (value?: string | null) => string;
  eventFamily: (eventName: string) => string;
  sessionEventKey: (event: Record<string, unknown>, fallback?: string) => string;
  sessionContextRowDomId: (
    kind: "approval" | "issue" | "event" | "tool_permission_runtime" | "async_task" | "shadow_audit",
    key: string
  ) => string;
  syncLinkedSelection: (payload: {
    event?: Record<string, unknown> | null;
    runId?: string;
    approvalId?: string;
    issueId?: string;
    toolPermissionRuntimeId?: string;
    asyncTaskId?: string;
    shadowAuditId?: string;
    runtimeAgentId?: string;
  }) => void;
  selectedPass: SessionDrilldownSectionProps["selectedControlPassCardProps"]["selectedPass"];
  setSelectedSessionId: (sessionId: string) => void;
  selectedSessionApprovalId: string;
  selectedSessionIssueId: string;
  selectedSessionToolPermissionRuntimeId: string;
  selectedSessionAsyncTaskId: string;
  selectedSessionShadowAuditId: string;
  revealSelectedSessionContextRow: () => void;
  revealSelectedSessionContextInAgentTimeline: () => void;
  selectedSessionContext: SessionDrilldownSectionProps["selectedSessionContextCardProps"]["selectedSessionContext"];
  formatJson: (value: unknown) => string;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  describeRunResult: (result: Record<string, unknown>) => {
    title: string;
    subtitle: string;
    message: string;
  };
  resolveRunLinkFromContext: SessionDrilldownSectionProps["selectedSessionContextCardProps"]["resolveRunLinkFromContext"];
  currentSessionLineageQueue: "attention" | "decisions" | "";
  selectedSessionLineageEntry: SessionLineageEntry | null;
  advanceSessionLineageQueueFromEntry: (
    queue: "attention" | "decisions",
    entry: SessionLineageEntry
  ) => void;
  approveApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  rejectApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  applyApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  resolveIssue: (issue: ExecutionIssueRecord) => Promise<void>;
  resolveToolPermissionRuntime: (
    runtime: ToolPermissionRuntimeRecord,
    outcome: "allow" | "deny"
  ) => Promise<void>;
  onCopySessionLink: () => void;
  canCopyFocusedLink: boolean;
  onCopyFocusedLink: () => void;
  onCopySessionContextLink: () => void;
  loadAsyncTaskOutputArtifact: (
    task: ExecutionRuntimeAgentTaskRecord
  ) => Promise<ExecutionRuntimeAgentTaskOutputArtifact>;
  loadAsyncTaskTranscriptArtifact: (
    task: ExecutionRuntimeAgentTaskRecord
  ) => Promise<ExecutionRuntimeAgentTaskTranscriptArtifact>;
  refreshAsyncTask: (task: ExecutionRuntimeAgentTaskRecord) => Promise<void>;
  waitForAsyncTaskSettlement: (task: ExecutionRuntimeAgentTaskRecord) => Promise<void>;
  cancelAsyncTask: (task: ExecutionRuntimeAgentTaskRecord) => Promise<void>;
  resolveShadowAudit: NonNullable<
    SessionDrilldownSectionProps["linkedDecisionsCardProps"]["onResolveShadowAudit"]
  >;
  inspectShadowAudit: NonNullable<
    SessionDrilldownSectionProps["linkedDecisionsCardProps"]["onInspectShadowAudit"]
  >;
};

export function buildSessionDrilldownSectionProps({
  selectedSessionId,
  sessionLoading,
  selectedSession,
  selectedControl,
  linkedAgentIds,
  selectedAgentId,
  focusRuntimeAgent,
  filteredRuns,
  linkedRuns,
  filteredEvents,
  filteredApprovals,
  linkedApprovals,
  visibleSessionApprovals,
  filteredIssues,
  linkedIssues,
  visibleSessionIssues,
  entitySearch,
  setEntitySearch,
  sortedProfiles,
  busyActionKey,
  latestPreviewRun,
  latestPreviewAppliedRun,
  applyControlPlan,
  applyRecommendation,
  applyPreviewRun,
  runFilter,
  setRunFilter,
  matchesRunFilter,
  selectedRunId,
  setSelectedRunId,
  setSelectedRunResultIndex,
  toNumber,
  eventFilter,
  setEventFilter,
  matchesEventFilter,
  visibleSessionEvents,
  selectedSessionEventKey,
  toStringValue,
  toStringArray,
  toNullableNumber,
  formatTimestamp,
  eventFamily,
  sessionEventKey,
  sessionContextRowDomId,
  syncLinkedSelection,
  selectedPass,
  setSelectedSessionId,
  selectedSessionApprovalId,
  selectedSessionIssueId,
  selectedSessionToolPermissionRuntimeId,
  selectedSessionAsyncTaskId,
  selectedSessionShadowAuditId,
  revealSelectedSessionContextRow,
  revealSelectedSessionContextInAgentTimeline,
  selectedSessionContext,
  formatJson,
  asRecord,
  describeRunResult,
  resolveRunLinkFromContext,
  currentSessionLineageQueue,
  selectedSessionLineageEntry,
  advanceSessionLineageQueueFromEntry,
  approveApproval,
  rejectApproval,
  applyApproval,
  resolveIssue,
  resolveToolPermissionRuntime,
  onCopySessionLink,
  canCopyFocusedLink,
  onCopyFocusedLink,
  onCopySessionContextLink,
  loadAsyncTaskOutputArtifact,
  loadAsyncTaskTranscriptArtifact,
  refreshAsyncTask,
  waitForAsyncTaskSettlement,
  cancelAsyncTask,
  resolveShadowAudit,
  inspectShadowAudit,
}: BuildSessionDrilldownSectionPropsArgs): SessionDrilldownSectionProps {
  return {
    selectedSessionId,
    sessionLoading,
    selectedSession,
    controlSectionProps: selectedSession
      ? {
          selectedSession,
          selectedControl,
          linkedAgentIds,
          selectedAgentId,
          onFocusRuntimeAgent: (runtimeAgentId) => {
            focusRuntimeAgent(runtimeAgentId, true);
          },
          filteredRunsCount: filteredRuns.length,
          linkedRunsCount: linkedRuns.length,
          filteredEventsCount: filteredEvents.length,
          filteredApprovalsCount: filteredApprovals.length,
          linkedApprovalsCount: linkedApprovals.length,
          filteredIssuesCount: filteredIssues.length,
          linkedIssuesCount: linkedIssues.length,
          linkedApprovals,
          linkedIssues,
          entitySearch,
          onEntitySearchChange: setEntitySearch,
          onClearEntitySearch: () => {
            setEntitySearch("");
          },
          sortedProfiles,
          busyActionKey,
          selectedRunId,
          selectedSessionApprovalId,
          selectedSessionIssueId,
          onCopySessionLink,
          canCopyFocusedLink,
          onCopyFocusedLink,
          latestPreviewRun,
          latestPreviewAppliedRun,
          onInspectRun: setSelectedRunId,
          onInspectApproval: (approval) => {
            syncLinkedSelection({
              approvalId: approval.id,
              issueId: approval.issue_id,
              runtimeAgentId: approval.runtime_agent_ids[0],
            });
          },
          onInspectIssue: (issue) => {
            syncLinkedSelection({
              issueId: issue.id,
              approvalId: issue.approval_id,
              runtimeAgentId: issue.runtime_agent_ids[0] || issue.runtime_agent_id,
            });
          },
          onApplyPreviewRun: (run) => {
            void applyPreviewRun(run);
          },
          onApplyControlPlan: (profile) => {
            void applyControlPlan(profile);
          },
          onApplyRecommendation: (recommendation) => {
            void applyRecommendation(recommendation);
          },
          onInspectShadowAudit: (audit) => {
            inspectShadowAudit(audit);
          },
          onResolveShadowAudit: (audit) => {
            return resolveShadowAudit(audit);
          },
        }
      : null,
    activitySectionProps: selectedSession
      ? {
          selectedSession,
          selectedControl,
          linkedRuns,
          runFilter,
          onRunFilterChange: setRunFilter,
          getRunFilterCount: (filter) => linkedRuns.filter((run) => matchesRunFilter(run, filter)).length,
          filteredRuns,
          selectedRunId,
          onSelectRun: setSelectedRunId,
          onFocusRuntimeAgent: (runtimeAgentId) => {
            focusRuntimeAgent(runtimeAgentId, true);
          },
          toNumber,
          eventFilter,
          onEventFilterChange: setEventFilter,
          getEventFilterCount: (filter) =>
            (selectedSession.events || []).filter((event) => matchesEventFilter(event, filter)).length,
          filteredEvents,
          visibleSessionEvents,
          selectedSessionEventKey,
          toStringValue,
          toStringArray,
          toNullableNumber,
          formatTimestamp,
          eventFamily,
          sessionEventKey,
          sessionContextRowDomId,
          onSyncLinkedSelection: syncLinkedSelection,
          onSearchEntity: setEntitySearch,
        }
      : null,
    selectedControlPassCardProps: {
      selectedPass,
      toStringValue,
      toNumber,
      onOpenSession: setSelectedSessionId,
    },
    linkedDecisionsCardProps: {
      selectedSession,
      linkedRuns,
      linkedApprovals,
      filteredApprovals,
      visibleSessionApprovals,
      selectedSessionApprovalId,
      linkedIssues,
      filteredIssues,
      visibleSessionIssues,
      selectedSessionIssueId,
      selectedSessionToolPermissionRuntimeId,
      selectedSessionAsyncTaskId,
      selectedSessionShadowAuditId,
      busyActionKey,
      formatTimestamp,
      sessionContextRowDomId,
      onSearchEntity: setEntitySearch,
      onFocusRuntimeAgent: (runtimeAgentId) => {
        focusRuntimeAgent(runtimeAgentId, true);
      },
      onInspectRun: (runId) => {
        setSelectedRunId(runId);
        setSelectedRunResultIndex(0);
      },
      onInspectApproval: (approval) => {
        syncLinkedSelection({
          approvalId: approval.id,
          issueId: approval.issue_id,
          runtimeAgentId: approval.runtime_agent_ids[0],
        });
      },
      onInspectIssue: (issue) => {
        syncLinkedSelection({
          issueId: issue.id,
          approvalId: issue.approval_id,
          runtimeAgentId: issue.runtime_agent_ids[0] || issue.runtime_agent_id,
        });
      },
      onInspectToolPermissionRuntime: (runtime) => {
        syncLinkedSelection({
          toolPermissionRuntimeId: runtime.id,
          runtimeAgentId: runtime.runtime_agent_ids[0],
        });
      },
      onInspectAsyncTask: (task) => {
        syncLinkedSelection({
          asyncTaskId: task.id,
          runId: task.agent_action_run_id,
          approvalId: task.approval_id,
          issueId: task.issue_id,
          runtimeAgentId: task.runtime_agent_ids[0] || task.runtime_agent_id,
        });
      },
      onInspectShadowAudit: (audit) => {
        const linkedTask =
          (selectedSession?.async_tasks || []).find(
            (task) => task.id === audit.source_id || task.id === audit.blocked_artifact_owner_id
          ) || null;
        syncLinkedSelection({
          shadowAuditId: audit.id,
          asyncTaskId: linkedTask?.id,
          runId: linkedTask?.agent_action_run_id,
          approvalId: linkedTask?.approval_id,
          issueId: linkedTask?.issue_id,
          runtimeAgentId:
            audit.runtime_agent_ids[0] ||
            linkedTask?.runtime_agent_ids[0] ||
            linkedTask?.runtime_agent_id,
        });
      },
      onRefreshAsyncTask: (task) => {
        void refreshAsyncTask(task);
      },
      onWaitForAsyncTaskSettlement: (task) => {
        void waitForAsyncTaskSettlement(task);
      },
      onCancelAsyncTask: (task) => {
        void cancelAsyncTask(task);
      },
      onResolveShadowAudit: (audit) => {
        return resolveShadowAudit(audit);
      },
      onApproveApproval: (approval) => {
        void approveApproval(approval);
      },
      onRejectApproval: (approval) => {
        void rejectApproval(approval);
      },
      onApplyApproval: (approval) => {
        void applyApproval(approval);
      },
      onResolveIssue: (issue) => {
        void resolveIssue(issue);
      },
      onAllowToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "allow");
      },
      onDenyToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "deny");
      },
    },
    selectedSessionContextCardProps: {
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
      onRevealSessionRow: revealSelectedSessionContextRow,
      onRevealInAgentTimeline: revealSelectedSessionContextInAgentTimeline,
      onCopyLink: onCopySessionContextLink,
      onOpenRuntimeAgent: (runtimeAgentId) => {
        focusRuntimeAgent(runtimeAgentId, true);
      },
      onSyncLinkedSelection: syncLinkedSelection,
      onOpenRunOutcome: (runId, resultIndex) => {
        setSelectedRunId(runId);
        setSelectedRunResultIndex(resultIndex);
      },
      onApproveApproval: (approval) => {
        void approveApproval(approval);
      },
      onRejectApproval: (approval) => {
        void rejectApproval(approval);
      },
      onApplyApproval: (approval) => {
        void applyApproval(approval);
      },
      onResolveIssue: (issue) => {
        void resolveIssue(issue);
      },
      onAllowToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "allow");
      },
      onDenyToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "deny");
      },
      onResolveShadowAudit: (audit) => {
        return resolveShadowAudit(audit);
      },
      onLoadAsyncTaskOutputArtifact: (task) => loadAsyncTaskOutputArtifact(task),
      onLoadAsyncTaskTranscriptArtifact: (task) => loadAsyncTaskTranscriptArtifact(task),
      onRefreshAsyncTask: (task) => {
        void refreshAsyncTask(task);
      },
      onWaitForAsyncTaskSettlement: (task) => {
        void waitForAsyncTaskSettlement(task);
      },
      onCancelAsyncTask: (task) => {
        void cancelAsyncTask(task);
      },
      onAdvanceCurrentQueue:
        currentSessionLineageQueue && selectedSessionLineageEntry
          ? () => {
              advanceSessionLineageQueueFromEntry(
                currentSessionLineageQueue,
                selectedSessionLineageEntry
              );
            }
          : null,
    },
  };
}
