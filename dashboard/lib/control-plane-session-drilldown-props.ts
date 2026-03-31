import type { ComponentProps } from "react";
import { SessionDrilldownSection } from "@/components/session-drilldown-section";
import type { SessionLineageEntry } from "@/lib/control-plane-models";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  OrchestratorSessionControl,
  OrchestratorSessionControlProfile,
  OrchestratorSessionControlRecommendation,
  OrchestratorSessionDetail,
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
  applyControlPlan: (profile: OrchestratorSessionControlProfile) => Promise<void>;
  applyRecommendation: (recommendation: OrchestratorSessionControlRecommendation) => Promise<void>;
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
  sessionContextRowDomId: (kind: "approval" | "issue" | "event", key: string) => string;
  syncLinkedSelection: (payload: {
    event?: Record<string, unknown> | null;
    runId?: string;
    approvalId?: string;
    issueId?: string;
    runtimeAgentId?: string;
  }) => void;
  selectedPass: SessionDrilldownSectionProps["selectedControlPassCardProps"]["selectedPass"];
  setSelectedSessionId: (sessionId: string) => void;
  selectedSessionApprovalId: string;
  selectedSessionIssueId: string;
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
  onCopySessionLink: () => void;
  canCopyFocusedLink: boolean;
  onCopyFocusedLink: () => void;
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
  applyControlPlan,
  applyRecommendation,
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
  onCopySessionLink,
  canCopyFocusedLink,
  onCopyFocusedLink,
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
          entitySearch,
          onEntitySearchChange: setEntitySearch,
          onClearEntitySearch: () => {
            setEntitySearch("");
          },
          sortedProfiles,
          busyActionKey,
          onCopySessionLink,
          canCopyFocusedLink,
          onCopyFocusedLink,
          onApplyControlPlan: (profile) => {
            void applyControlPlan(profile);
          },
          onApplyRecommendation: (recommendation) => {
            void applyRecommendation(recommendation);
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
      linkedApprovals,
      filteredApprovals,
      visibleSessionApprovals,
      selectedSessionApprovalId,
      linkedIssues,
      filteredIssues,
      visibleSessionIssues,
      selectedSessionIssueId,
      busyActionKey,
      formatTimestamp,
      sessionContextRowDomId,
      onSearchEntity: setEntitySearch,
      onFocusRuntimeAgent: (runtimeAgentId) => {
        focusRuntimeAgent(runtimeAgentId, true);
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
