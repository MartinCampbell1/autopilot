import type { ComponentProps } from "react";
import { RuntimeAgentActivitySection } from "@/components/runtime-agent-activity-section";
import { RuntimeAgentSection } from "@/components/runtime-agent-section";
import { RuntimeAgentTimelineSection } from "@/components/runtime-agent-timeline-section";
import type {
  AgentScopedOutcome,
  AgentTimelineEntry,
  LinkedSelectionContext,
} from "@/lib/control-plane-models";
import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
} from "@/lib/types";

type RuntimeAgentSectionProps = ComponentProps<typeof RuntimeAgentSection>;
type RuntimeAgentActivitySectionProps = ComponentProps<typeof RuntimeAgentActivitySection>;
type RuntimeAgentTimelineSectionProps = ComponentProps<typeof RuntimeAgentTimelineSection>;

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type FocusAgentTimeline = (
  filter: string,
  options?: {
    entry?: AgentTimelineEntry | null;
    search?: string;
  }
) => void;

type EventFilter = "all" | "control" | "actions" | "decisions" | "attention";

type BuildRuntimeAgentSectionPropsArgs = {
  selectedAgentId: RuntimeAgentSectionProps["selectedAgentId"];
  agentLoading: RuntimeAgentSectionProps["agentLoading"];
  selectedAgent: RuntimeAgentSectionProps["selectedAgent"];
  busyActionKey: RuntimeAgentSectionProps["busyActionKey"];
  formatTimestamp: RuntimeAgentSectionProps["formatTimestamp"];
  toNumber: RuntimeAgentSectionProps["toNumber"];
  toStringValue: RuntimeAgentSectionProps["toStringValue"];
  formatJson: RuntimeAgentTimelineSectionProps["formatJson"];
  toNullableNumber: RuntimeAgentTimelineSectionProps["toNullableNumber"];
  asRecord: RuntimeAgentTimelineSectionProps["asRecord"];
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  outcomeProjectId: RuntimeAgentActivitySectionProps["outcomeProjectId"];
  outcomeStoryId: RuntimeAgentActivitySectionProps["outcomeStoryId"];
  selectedRunId: string;
  setSelectedRunId: (runId: string) => void;
  selectedRunResultIndex: number;
  setSelectedRunResultIndex: (resultIndex: number) => void;
  onCopyAgentLink: () => void;
  focusRuntimeAgent: (runtimeAgentId: string, syncSearch?: boolean) => void;
  runAgentSuggestedCommand: (
    command: Record<string, unknown>,
    mode: "execute_now" | "request_approval"
  ) => Promise<void>;
  inspectAsyncFollowThrough: () => void;
  onAllowToolPermissionRuntime: RuntimeAgentSectionProps["onAllowToolPermissionRuntime"];
  onDenyToolPermissionRuntime: RuntimeAgentSectionProps["onDenyToolPermissionRuntime"];
  agentScopedRuns: ExecutionAgentActionRunRecord[];
  agentActivitySearch: string;
  setAgentActivitySearch: (value: string) => void;
  agentActivityFilter: string;
  setAgentActivityFilter: (value: string) => void;
  filteredAgentScopedRuns: ExecutionAgentActionRunRecord[];
  agentScopedOutcomes: AgentScopedOutcome[];
  filteredAgentScopedOutcomes: AgentScopedOutcome[];
  setEntitySearch: (value: string) => void;
  activeAgentTimelineEntries: AgentTimelineEntry[];
  hiddenAgentTimelineEntryCount: number;
  agentTimelineSearch: string;
  setAgentTimelineSearch: (value: string) => void;
  agentTimelineFilter: RuntimeAgentTimelineSectionProps["agentTimelineFilter"];
  setAgentTimelineFilter: (value: RuntimeAgentTimelineSectionProps["agentTimelineFilter"]) => void;
  persistedDismissedAgentTimelineCount: number;
  persistedSnoozedAgentTimelineCount: number;
  agentTimelinePriorityCounts: RuntimeAgentTimelineSectionProps["agentTimelinePriorityCounts"];
  nextBestAgentTimelineEntry: RuntimeAgentTimelineSectionProps["nextBestAgentTimelineEntry"];
  hasPersistedAgentTimelinePreferences: boolean;
  inspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  restoreAgentTimelineHidden: () => void;
  exportAgentTimelinePreferences: () => void | Promise<void>;
  resetAgentTimelinePreferences: () => void;
  agentQueueAdvanceFeedback: RuntimeAgentTimelineSectionProps["agentQueueAdvanceFeedback"];
  agentQueueAdvanceFocusSummary: RuntimeAgentTimelineSectionProps["agentQueueAdvanceFocusSummary"];
  agentQueueFocusDelta: RuntimeAgentTimelineSectionProps["agentQueueFocusDelta"];
  agentQueueAdvanceNoticeActions: RuntimeAgentTimelineSectionProps["agentQueueAdvanceNoticeActions"];
  nextCriticalAgentTimelineEntry: RuntimeAgentTimelineSectionProps["nextCriticalAgentTimelineEntry"];
  nextHighAgentTimelineEntry: RuntimeAgentTimelineSectionProps["nextHighAgentTimelineEntry"];
  expandedAgentPriorityQueues: RuntimeAgentTimelineSectionProps["expandedAgentPriorityQueues"];
  currentAgentPriorityQueue: RuntimeAgentTimelineSectionProps["currentAgentPriorityQueue"];
  expandAllAgentPriorityQueues: () => void;
  collapseAllAgentPriorityQueues: () => void;
  openCurrentAgentPriorityQueue: () => void;
  criticalAgentTimelineQueue: RuntimeAgentTimelineSectionProps["criticalAgentTimelineQueue"];
  criticalAgentTimelineTotal: number;
  criticalAgentTimelinePosition: number;
  highAgentTimelineQueue: RuntimeAgentTimelineSectionProps["highAgentTimelineQueue"];
  highAgentTimelineTotal: number;
  highAgentTimelinePosition: number;
  toggleAgentPriorityQueueExpansion: RuntimeAgentTimelineSectionProps["onToggleAgentPriorityQueueExpansion"];
  filteredAgentTimelineEntriesCount: number;
  visibleAgentTimelineEntries: RuntimeAgentTimelineSectionProps["visibleAgentTimelineEntries"];
  selectedAgentTimelineEntry: RuntimeAgentTimelineSectionProps["selectedAgentTimelineEntry"];
  selectedAgentTimelineRunLink: RuntimeAgentTimelineSectionProps["selectedAgentTimelineRunLink"];
  selectedAgentTimelinePriority: RuntimeAgentTimelineSectionProps["selectedAgentTimelinePriority"];
  latestAgentIssueEntry: RuntimeAgentTimelineSectionProps["latestAgentIssueEntry"];
  latestAgentApprovalEntry: RuntimeAgentTimelineSectionProps["latestAgentApprovalEntry"];
  latestAgentEventEntry: RuntimeAgentTimelineSectionProps["latestAgentEventEntry"];
  syncLinkedSelection: (payload: LinkedSelectionContext) => void;
  approveApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  rejectApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  applyApproval: (approval: ExecutionApprovalRecord) => Promise<void>;
  resolveIssue: (issue: ExecutionIssueRecord) => Promise<void>;
  advanceCurrentAgentPriorityQueue: (entry: AgentTimelineEntry) => void;
  focusAgentTimeline: FocusAgentTimeline;
  setEventFilter: (value: EventFilter) => void;
  snoozeAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  dismissAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  advanceAgentPriorityQueueFromEntry: RuntimeAgentTimelineSectionProps["onAdvanceAgentPriorityQueueFromEntry"];
  findAgentTimelineEntryInSession: (entry: AgentTimelineEntry) => void;
  revealAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  agentTimelineEntryKey: RuntimeAgentTimelineSectionProps["agentTimelineEntryKey"];
  agentTimelinePriority: RuntimeAgentTimelineSectionProps["agentTimelinePriority"];
  agentTimelineRowDomId: RuntimeAgentTimelineSectionProps["agentTimelineRowDomId"];
};

export function buildRuntimeAgentSectionProps({
  selectedAgentId,
  agentLoading,
  selectedAgent,
  busyActionKey,
  formatTimestamp,
  toNumber,
  toStringValue,
  formatJson,
  toNullableNumber,
  asRecord,
  describeRunResult,
  outcomeProjectId,
  outcomeStoryId,
  selectedRunId,
  setSelectedRunId,
  selectedRunResultIndex,
  setSelectedRunResultIndex,
  onCopyAgentLink,
  focusRuntimeAgent,
  runAgentSuggestedCommand,
  inspectAsyncFollowThrough,
  onAllowToolPermissionRuntime,
  onDenyToolPermissionRuntime,
  agentScopedRuns,
  agentActivitySearch,
  setAgentActivitySearch,
  agentActivityFilter,
  setAgentActivityFilter,
  filteredAgentScopedRuns,
  agentScopedOutcomes,
  filteredAgentScopedOutcomes,
  setEntitySearch,
  activeAgentTimelineEntries,
  hiddenAgentTimelineEntryCount,
  agentTimelineSearch,
  setAgentTimelineSearch,
  agentTimelineFilter,
  setAgentTimelineFilter,
  persistedDismissedAgentTimelineCount,
  persistedSnoozedAgentTimelineCount,
  agentTimelinePriorityCounts,
  nextBestAgentTimelineEntry,
  hasPersistedAgentTimelinePreferences,
  inspectAgentTimelineEntry,
  restoreAgentTimelineHidden,
  exportAgentTimelinePreferences,
  resetAgentTimelinePreferences,
  agentQueueAdvanceFeedback,
  agentQueueAdvanceFocusSummary,
  agentQueueFocusDelta,
  agentQueueAdvanceNoticeActions,
  nextCriticalAgentTimelineEntry,
  nextHighAgentTimelineEntry,
  expandedAgentPriorityQueues,
  currentAgentPriorityQueue,
  expandAllAgentPriorityQueues,
  collapseAllAgentPriorityQueues,
  openCurrentAgentPriorityQueue,
  criticalAgentTimelineQueue,
  criticalAgentTimelineTotal,
  criticalAgentTimelinePosition,
  highAgentTimelineQueue,
  highAgentTimelineTotal,
  highAgentTimelinePosition,
  toggleAgentPriorityQueueExpansion,
  filteredAgentTimelineEntriesCount,
  visibleAgentTimelineEntries,
  selectedAgentTimelineEntry,
  selectedAgentTimelineRunLink,
  selectedAgentTimelinePriority,
  latestAgentIssueEntry,
  latestAgentApprovalEntry,
  latestAgentEventEntry,
  syncLinkedSelection,
  approveApproval,
  rejectApproval,
  applyApproval,
  resolveIssue,
  advanceCurrentAgentPriorityQueue,
  focusAgentTimeline,
  setEventFilter,
  snoozeAgentTimelineEntry,
  dismissAgentTimelineEntry,
  advanceAgentPriorityQueueFromEntry,
  findAgentTimelineEntryInSession,
  revealAgentTimelineEntry,
  agentTimelineEntryKey,
  agentTimelinePriority,
  agentTimelineRowDomId,
}: BuildRuntimeAgentSectionPropsArgs): RuntimeAgentSectionProps {
  const activitySectionProps: RuntimeAgentSectionProps["activitySectionProps"] = selectedAgent
    ? {
        selectedAgent,
        agentScopedRuns,
        agentActivitySearch,
        onAgentActivitySearchChange: setAgentActivitySearch,
        agentActivityFilter,
        onAgentActivityFilterChange: setAgentActivityFilter,
        filteredAgentScopedRuns,
        selectedRunId,
        selectedRunResultIndex,
        onSelectRun: (runId, resultIndex) => {
          setSelectedRunId(runId);
          setSelectedRunResultIndex(resultIndex);
        },
        formatTimestamp,
        toNumber,
        describeRunResult,
        agentScopedOutcomes,
        filteredAgentScopedOutcomes,
        outcomeProjectId,
        outcomeStoryId,
        toStringValue,
        asRecord,
        onFindOutcomeInSession: (runId, resultIndex) => {
          setEntitySearch(runId);
          setSelectedRunId(runId);
          setSelectedRunResultIndex(resultIndex);
        },
      }
    : null;

  const timelineSectionProps: RuntimeAgentSectionProps["timelineSectionProps"] = selectedAgent
    ? {
        selectedAgent,
        activeAgentTimelineEntries,
        hiddenAgentTimelineEntryCount,
        agentTimelineSearch,
        onAgentTimelineSearchChange: setAgentTimelineSearch,
        agentTimelineFilter,
        onAgentTimelineFilterChange: setAgentTimelineFilter,
        persistedDismissedAgentTimelineCount,
        persistedSnoozedAgentTimelineCount,
        agentTimelinePriorityCounts,
        nextBestAgentTimelineEntry,
        hasPersistedAgentTimelinePreferences,
        onInspectAgentTimelineEntry: inspectAgentTimelineEntry,
        onRestoreAgentTimelineHidden: restoreAgentTimelineHidden,
        onExportAgentTimelinePreferences: exportAgentTimelinePreferences,
        onResetAgentTimelinePreferences: resetAgentTimelinePreferences,
        agentQueueAdvanceFeedback,
        agentQueueAdvanceFocusSummary,
        agentQueueFocusDelta,
        agentQueueAdvanceNoticeActions,
        nextCriticalAgentTimelineEntry,
        nextHighAgentTimelineEntry,
        expandedAgentPriorityQueues,
        currentAgentPriorityQueue,
        onExpandAllAgentPriorityQueues: expandAllAgentPriorityQueues,
        onCollapseAllAgentPriorityQueues: collapseAllAgentPriorityQueues,
        onOpenCurrentAgentPriorityQueue: openCurrentAgentPriorityQueue,
        criticalAgentTimelineQueue,
        criticalAgentTimelineTotal,
        criticalAgentTimelinePosition,
        highAgentTimelineQueue,
        highAgentTimelineTotal,
        highAgentTimelinePosition,
        onToggleAgentPriorityQueueExpansion: toggleAgentPriorityQueueExpansion,
        filteredAgentTimelineEntriesCount,
        visibleAgentTimelineEntries,
        selectedAgentTimelineEntry,
        selectedAgentTimelineRunLink,
        selectedAgentTimelinePriority,
        latestAgentIssueEntry,
        latestAgentApprovalEntry,
        latestAgentEventEntry,
        busyActionKey,
        formatTimestamp,
        formatJson,
        toStringValue,
        toNullableNumber,
        asRecord,
        describeRunResult,
        onSelectTimelineEntry: inspectAgentTimelineEntry,
        onSyncLinkedSelection: syncLinkedSelection,
        onFocusRuntimeAgent: (runtimeAgentId) => {
          focusRuntimeAgent(runtimeAgentId, true);
        },
        onSelectRun: (runId, resultIndex) => {
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
        onAdvanceCurrentPriorityQueue: advanceCurrentAgentPriorityQueue,
        onSearchEntity: setEntitySearch,
        onFocusAgentTimeline: (filter, entry) => {
          focusAgentTimeline(filter, entry ? { entry } : undefined);
        },
        onFilterSessionByToken: (value) => {
          setEventFilter("all");
          setEntitySearch(value);
        },
        onSnoozeAgentTimelineEntry: snoozeAgentTimelineEntry,
        onDismissAgentTimelineEntry: dismissAgentTimelineEntry,
        onAdvanceAgentPriorityQueueFromEntry: advanceAgentPriorityQueueFromEntry,
        onFindAgentTimelineEntryInSession: findAgentTimelineEntryInSession,
        onRevealAgentTimelineEntry: revealAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        agentTimelineRowDomId,
      }
    : null;

  const pendingAsyncRuns = agentScopedRuns
    .filter((run) => run.completion_state === "pending_async")
    .sort(
      (left, right) =>
        (right.updated_at || right.created_at).localeCompare(left.updated_at || left.created_at) ||
        right.id.localeCompare(left.id)
    );

  return {
    selectedAgentId,
    agentLoading,
    selectedAgent,
    busyActionKey,
    formatTimestamp,
    toNumber,
    toStringValue,
    pendingAsyncRuns,
    onCopyLink: onCopyAgentLink,
    onFocusRuntimeAgent: (runtimeAgentId) => {
      focusRuntimeAgent(runtimeAgentId, true);
    },
    onAllowToolPermissionRuntime,
    onDenyToolPermissionRuntime,
    onRunSuggestedCommand: (command, mode) => {
      void runAgentSuggestedCommand(command, mode);
    },
    onInspectAsyncFollowThrough: inspectAsyncFollowThrough,
    activitySectionProps,
    timelineSectionProps,
  };
}
