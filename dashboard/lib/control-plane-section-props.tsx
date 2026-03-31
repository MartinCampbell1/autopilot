import type { ComponentProps } from "react";
import { ControlPlaneHeaderSections } from "@/components/control-plane-header-sections";
import { ControlPlaneMainSections } from "@/components/control-plane-main-sections";
import { ControlPlaneWorkspaceSection } from "@/components/control-plane-workspace-section";
import { SelectedOutcomeInspector } from "@/components/selected-outcome-inspector";
import type {
  LineageQueueKind,
  SessionLineageEntry,
  TriageInboxFeedbackGroup,
  TriageInboxItem,
} from "@/lib/control-plane-models";
import type { OrchestratorControlPassRecord } from "@/lib/types";

type WorkspaceSectionProps = ComponentProps<typeof ControlPlaneWorkspaceSection>;
type HeaderSectionProps = ComponentProps<typeof ControlPlaneHeaderSections>;
type MainSectionsProps = ComponentProps<typeof ControlPlaneMainSections>;
type SelectedOutcomeInspectorProps = ComponentProps<typeof SelectedOutcomeInspector>;

type BuildWorkspaceSectionPropsArgs = {
  hasSelectedSession: boolean;
  recentControlPasses: WorkspaceSectionProps["recentControlPasses"];
  totalControlPassCount: number;
  selectedPassId: string;
  formatTimestamp: WorkspaceSectionProps["formatTimestamp"];
  toStringValue: WorkspaceSectionProps["toStringValue"];
  toNumber: WorkspaceSectionProps["toNumber"];
  setSelectedPassId: (value: string) => void;
  setSelectedSessionId: (value: string) => void;
  selectedRun: WorkspaceSectionProps["selectedActionRunCardProps"]["selectedRun"];
  selectedRunResult: Record<string, unknown> | null;
  selectedRunResultIndex: number;
  setSelectedRunResultIndex: (index: number) => void;
  formatScopeList: WorkspaceSectionProps["selectedActionRunCardProps"]["formatScopeList"];
  describeRunResult: WorkspaceSectionProps["selectedActionRunCardProps"]["describeRunResult"];
  toStringArray: WorkspaceSectionProps["selectedActionRunCardProps"]["toStringArray"];
  asRecord: WorkspaceSectionProps["selectedActionRunCardProps"]["asRecord"];
  selectedSessionEvents: SelectedOutcomeInspectorProps["selectedSessionEvents"];
  formatJson: SelectedOutcomeInspectorProps["formatJson"];
  sessionEventKey: SelectedOutcomeInspectorProps["sessionEventKey"];
  resolveSessionEventFromContext: SelectedOutcomeInspectorProps["resolveSessionEventFromContext"];
  outcomeProjectId: SelectedOutcomeInspectorProps["outcomeProjectId"];
  outcomeProjectName: SelectedOutcomeInspectorProps["outcomeProjectName"];
  outcomeStoryId: SelectedOutcomeInspectorProps["outcomeStoryId"];
  outcomeStoryTitle: SelectedOutcomeInspectorProps["outcomeStoryTitle"];
  outcomeRuntimeAgentId: SelectedOutcomeInspectorProps["outcomeRuntimeAgentId"];
  onOpenSelectedRunResultInTimeline: () => void;
  focusRuntimeAgent: (runtimeAgentId: string, syncSearch?: boolean) => void;
  setEntitySearch: (value: string) => void;
  setSelectedRunId: (runId: string) => void;
  syncLinkedSelection: SelectedOutcomeInspectorProps["onSyncLinkedSelection"];
  sessionLineageEntries: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineageEntries"];
  linkedRunsCount: number;
  linkedApprovalsCount: number;
  linkedIssuesCount: number;
  linkedAgentCount: number;
  sessionLineageDecisionCount: number;
  sessionLineageEventCount: number;
  sessionLineageAgentCount: number;
  sessionLineageStatusCounts: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineageStatusCounts"];
  filteredSessionLineageEntriesCount: number;
  sessionLineageFilter: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineageFilter"];
  setSessionLineageFilter: (value: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineageFilter"]) => void;
  sessionLineageAttentionCount: number;
  sessionLineageAgentLinkedCount: number;
  persistedDismissedLineageQueueCount: number;
  persistedSnoozedLineageQueueCount: number;
  sessionLineagePriorityCounts: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineagePriorityCounts"];
  hasPersistedLineageQueuePreferences: boolean;
  exportSessionLineageQueuePreferences: () => void | Promise<void>;
  resetSessionLineageQueuePreferences: () => void;
  selectedSessionLineageEntry: SessionLineageEntry | null;
  selectedSessionLineagePriority: WorkspaceSectionProps["sessionLineageSectionProps"]["selectedSessionLineagePriority"];
  selectedSessionLineageTraits: WorkspaceSectionProps["sessionLineageSectionProps"]["selectedSessionLineageTraits"];
  nextBestSessionLineageEntry: WorkspaceSectionProps["sessionLineageSectionProps"]["nextBestSessionLineageEntry"];
  attentionSessionLineageEntries: WorkspaceSectionProps["sessionLineageSectionProps"]["attentionSessionLineageEntries"];
  decisionSessionLineageEntries: WorkspaceSectionProps["sessionLineageSectionProps"]["decisionSessionLineageEntries"];
  latestAgentLinkedLineageEntry: WorkspaceSectionProps["sessionLineageSectionProps"]["latestAgentLinkedLineageEntry"];
  inspectSessionLineageEntry: (entry: SessionLineageEntry) => void;
  advanceSessionLineageQueue: (filter: "attention" | "decisions") => void;
  focusSessionLineageEntry: (entry: SessionLineageEntry, filter: string) => void;
  expandedSessionLineageQueues: WorkspaceSectionProps["sessionLineageSectionProps"]["expandedSessionLineageQueues"];
  currentSessionLineageQueue: WorkspaceSectionProps["sessionLineageSectionProps"]["currentSessionLineageQueue"];
  expandAllSessionLineageQueues: () => void;
  collapseAllSessionLineageQueues: () => void;
  openCurrentSessionLineageQueue: () => void;
  sessionQueueAdvanceFeedback: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionQueueAdvanceFeedback"];
  sessionQueueAdvanceFocusSummary: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionQueueAdvanceFocusSummary"];
  sessionQueueFocusDelta: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionQueueFocusDelta"];
  sessionQueueAdvanceNoticeActions: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionQueueAdvanceNoticeActions"];
  attentionQueuePosition: number;
  hiddenAttentionQueueCount: number;
  attentionSessionLineageQueue: WorkspaceSectionProps["sessionLineageSectionProps"]["attentionSessionLineageQueue"];
  toggleSessionLineageQueueExpansion: (queue: LineageQueueKind) => void;
  restoreSessionLineageQueue: (queue: LineageQueueKind) => void;
  sessionLineagePriority: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineagePriority"];
  sessionLineageTraits: WorkspaceSectionProps["sessionLineageSectionProps"]["sessionLineageTraits"];
  snoozeSessionLineageQueueEntry: (queue: LineageQueueKind, entry: SessionLineageEntry, minutes?: number) => void;
  advanceSessionLineageQueueFromEntry: (queue: LineageQueueKind, entry: SessionLineageEntry | null) => void;
  dismissSessionLineageQueueEntry: (queue: LineageQueueKind, entry: SessionLineageEntry) => void;
  findSessionLineageEntryInSession: (entry: SessionLineageEntry) => void;
  revealSessionLineageEntryInTimeline: (entry: SessionLineageEntry) => void;
  decisionQueuePosition: number;
  hiddenDecisionQueueCount: number;
  decisionSessionLineageQueue: WorkspaceSectionProps["sessionLineageSectionProps"]["decisionSessionLineageQueue"];
  visibleSessionLineageEntries: WorkspaceSectionProps["sessionLineageSectionProps"]["visibleSessionLineageEntries"];
  triageInboxItemCount: number;
  triageInboxItems: TriageInboxItem[];
  selectedTriageInboxItem: WorkspaceSectionProps["triageInboxSectionProps"]["selectedTriageInboxItem"];
  syncedTriageInboxItem: WorkspaceSectionProps["triageInboxSectionProps"]["syncedTriageInboxItem"];
  inspectTriageInboxItem: WorkspaceSectionProps["triageInboxSectionProps"]["onInspectTriageInboxItem"];
  inspectAndAdvanceTriageInboxItem: WorkspaceSectionProps["triageInboxSectionProps"]["onInspectAndAdvanceTriageInboxItem"];
  advanceTriageInboxCursor: WorkspaceSectionProps["triageInboxSectionProps"]["onAdvanceTriageInboxCursor"];
  syncTriageInboxCursorToSelection: WorkspaceSectionProps["triageInboxSectionProps"]["onSyncTriageInboxCursorToSelection"];
  triageInboxFeedbackHistoryCount: number;
  triageInboxFeedbackFilter: WorkspaceSectionProps["triageInboxSectionProps"]["triageInboxFeedbackFilter"];
  setTriageInboxFeedbackFilter: (value: WorkspaceSectionProps["triageInboxSectionProps"]["triageInboxFeedbackFilter"]) => void;
  triageInboxFeedbackCounts: WorkspaceSectionProps["triageInboxSectionProps"]["triageInboxFeedbackCounts"];
  triageInboxFeedback: WorkspaceSectionProps["triageInboxSectionProps"]["triageInboxFeedback"];
  groupedRecentTriageInboxFeedback: TriageInboxFeedbackGroup[];
  recentTriageInboxFeedbackCount: number;
  expandedTriageInboxResultGroups: string[];
  currentTriageInboxFeedbackGroup: TriageInboxFeedbackGroup | null;
  expandAllTriageInboxResultGroups: () => void;
  collapseAllTriageInboxResultGroups: () => void;
  openCurrentTriageInboxResultGroup: () => void;
  toggleTriageInboxResultGroup: (groupKey: string) => void;
  openTriageInboxHistoryGroup: (groupKey: string) => void;
  snoozeTriageInboxItem: (item: TriageInboxItem) => void;
  dismissTriageInboxItem: (item: TriageInboxItem) => void;
  runtimeAgentSectionProps: WorkspaceSectionProps["runtimeAgentSectionProps"];
  controlSummary: WorkspaceSectionProps["controlPlaneOverviewSectionsProps"]["controlSummary"];
  recentSessions: WorkspaceSectionProps["controlPlaneOverviewSectionsProps"]["recentSessions"];
  totalSessionCount: number;
  selectedSessionId: string;
  sessionSummary: WorkspaceSectionProps["controlPlaneOverviewSectionsProps"]["sessionSummary"];
};

type BuildHeaderSectionPropsArgs = {
  latestControlPassAt?: string | null;
  latestSessionAt?: string | null;
  selectedSessionId: string;
  selectedControlState?: string | null;
  refreshing: boolean;
  refresh: () => Promise<void>;
  formatTimestamp: HeaderSectionProps["formatTimestamp"];
  controlSummary: HeaderSectionProps["controlSummary"];
  sessionSummary: HeaderSectionProps["sessionSummary"];
  historySearch: string;
  setHistorySearch: (value: string) => void;
  filteredSessionHistoryCount: number;
  totalSessionCount: number;
  filteredControlPassHistoryCount: number;
  totalControlPassCount: number;
  onCopyCurrentLink: () => void;
};

export function buildWorkspaceSectionProps({
  hasSelectedSession,
  recentControlPasses,
  totalControlPassCount,
  selectedPassId,
  formatTimestamp,
  toStringValue,
  toNumber,
  setSelectedPassId,
  setSelectedSessionId,
  selectedRun,
  selectedRunResult,
  selectedRunResultIndex,
  setSelectedRunResultIndex,
  formatScopeList,
  describeRunResult,
  toStringArray,
  asRecord,
  selectedSessionEvents,
  formatJson,
  sessionEventKey,
  resolveSessionEventFromContext,
  outcomeProjectId,
  outcomeProjectName,
  outcomeStoryId,
  outcomeStoryTitle,
  outcomeRuntimeAgentId,
  onOpenSelectedRunResultInTimeline,
  focusRuntimeAgent,
  setEntitySearch,
  setSelectedRunId,
  syncLinkedSelection,
  sessionLineageEntries,
  linkedRunsCount,
  linkedApprovalsCount,
  linkedIssuesCount,
  linkedAgentCount,
  sessionLineageDecisionCount,
  sessionLineageEventCount,
  sessionLineageAgentCount,
  sessionLineageStatusCounts,
  filteredSessionLineageEntriesCount,
  sessionLineageFilter,
  setSessionLineageFilter,
  sessionLineageAttentionCount,
  sessionLineageAgentLinkedCount,
  persistedDismissedLineageQueueCount,
  persistedSnoozedLineageQueueCount,
  sessionLineagePriorityCounts,
  hasPersistedLineageQueuePreferences,
  exportSessionLineageQueuePreferences,
  resetSessionLineageQueuePreferences,
  selectedSessionLineageEntry,
  selectedSessionLineagePriority,
  selectedSessionLineageTraits,
  nextBestSessionLineageEntry,
  attentionSessionLineageEntries,
  decisionSessionLineageEntries,
  latestAgentLinkedLineageEntry,
  inspectSessionLineageEntry,
  advanceSessionLineageQueue,
  focusSessionLineageEntry,
  expandedSessionLineageQueues,
  currentSessionLineageQueue,
  expandAllSessionLineageQueues,
  collapseAllSessionLineageQueues,
  openCurrentSessionLineageQueue,
  sessionQueueAdvanceFeedback,
  sessionQueueAdvanceFocusSummary,
  sessionQueueFocusDelta,
  sessionQueueAdvanceNoticeActions,
  attentionQueuePosition,
  hiddenAttentionQueueCount,
  attentionSessionLineageQueue,
  toggleSessionLineageQueueExpansion,
  restoreSessionLineageQueue,
  sessionLineagePriority,
  sessionLineageTraits,
  snoozeSessionLineageQueueEntry,
  advanceSessionLineageQueueFromEntry,
  dismissSessionLineageQueueEntry,
  findSessionLineageEntryInSession,
  revealSessionLineageEntryInTimeline,
  decisionQueuePosition,
  hiddenDecisionQueueCount,
  decisionSessionLineageQueue,
  visibleSessionLineageEntries,
  triageInboxItemCount,
  triageInboxItems,
  selectedTriageInboxItem,
  syncedTriageInboxItem,
  inspectTriageInboxItem,
  inspectAndAdvanceTriageInboxItem,
  advanceTriageInboxCursor,
  syncTriageInboxCursorToSelection,
  triageInboxFeedbackHistoryCount,
  triageInboxFeedbackFilter,
  setTriageInboxFeedbackFilter,
  triageInboxFeedbackCounts,
  triageInboxFeedback,
  groupedRecentTriageInboxFeedback,
  recentTriageInboxFeedbackCount,
  expandedTriageInboxResultGroups,
  currentTriageInboxFeedbackGroup,
  expandAllTriageInboxResultGroups,
  collapseAllTriageInboxResultGroups,
  openCurrentTriageInboxResultGroup,
  toggleTriageInboxResultGroup,
  openTriageInboxHistoryGroup,
  snoozeTriageInboxItem,
  dismissTriageInboxItem,
  runtimeAgentSectionProps,
  controlSummary,
  recentSessions,
  totalSessionCount,
  selectedSessionId,
  sessionSummary,
}: BuildWorkspaceSectionPropsArgs): WorkspaceSectionProps {
  return {
    recentControlPasses,
    totalControlPassCount,
    selectedPassId,
    formatTimestamp,
    toStringValue,
    toNumber,
    onInspectControlPass: (controlPass: OrchestratorControlPassRecord) => {
      setSelectedPassId(controlPass.id);
      if (controlPass.orchestrator_session_id) {
        setSelectedSessionId(controlPass.orchestrator_session_id);
      }
    },
    selectedActionRunCardProps: {
      selectedRun,
      selectedRunResultIndex,
      onSelectResult: setSelectedRunResultIndex,
      formatTimestamp,
      formatScopeList,
      describeRunResult,
      toNumber,
      toStringArray,
      toStringValue,
      asRecord,
      children:
        selectedRun && selectedRunResult ? (
          <SelectedOutcomeInspector
            selectedRun={selectedRun}
            selectedRunResult={selectedRunResult}
            selectedRunResultIndex={selectedRunResultIndex}
            selectedSessionEvents={selectedSessionEvents}
            formatJson={formatJson}
            asRecord={asRecord}
            toStringValue={toStringValue}
            sessionEventKey={sessionEventKey}
            resolveSessionEventFromContext={resolveSessionEventFromContext}
            outcomeProjectId={outcomeProjectId}
            outcomeProjectName={outcomeProjectName}
            outcomeStoryId={outcomeStoryId}
            outcomeStoryTitle={outcomeStoryTitle}
            outcomeRuntimeAgentId={outcomeRuntimeAgentId}
            onOpenInAgentTimeline={onOpenSelectedRunResultInTimeline}
            onFocusRuntimeAgent={(runtimeAgentId) => {
              focusRuntimeAgent(runtimeAgentId, true);
            }}
            onFindApproval={(approvalId) => {
              setEntitySearch(approvalId);
            }}
            onFindIssue={(issueId) => {
              setEntitySearch(issueId);
            }}
            onSelectRunOutcome={(runId, resultIndex) => {
              setSelectedRunId(runId);
              setSelectedRunResultIndex(resultIndex);
            }}
            onSyncLinkedSelection={syncLinkedSelection}
          />
        ) : null,
    },
    sessionLineageSectionProps: {
      hasSelectedSession,
      sessionEventTotalCount: selectedSessionEvents.length,
      sessionLineageEntries,
      linkedRunCount: linkedRunsCount,
      linkedApprovalCount: linkedApprovalsCount,
      linkedIssueCount: linkedIssuesCount,
      linkedAgentCount,
      sessionLineageDecisionCount,
      sessionLineageEventCount,
      sessionLineageAgentCount,
      sessionLineageStatusCounts,
      filteredSessionLineageEntriesCount,
      sessionLineageFilter,
      onSessionLineageFilterChange: setSessionLineageFilter,
      sessionLineageAttentionCount,
      sessionLineageAgentLinkedCount,
      persistedDismissedLineageQueueCount,
      persistedSnoozedLineageQueueCount,
      sessionLineagePriorityCounts,
      hasPersistedLineageQueuePreferences,
      onExportSessionLineageQueuePreferences: exportSessionLineageQueuePreferences,
      onResetSessionLineageQueuePreferences: resetSessionLineageQueuePreferences,
      selectedSessionLineageEntry,
      selectedSessionLineagePriority,
      selectedSessionLineageTraits,
      formatTimestamp,
      nextBestSessionLineageEntry,
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      latestAgentLinkedLineageEntry,
      onInspectSessionLineageEntry: inspectSessionLineageEntry,
      onAdvanceSessionLineageQueue: advanceSessionLineageQueue,
      onFocusSessionLineageEntry: focusSessionLineageEntry,
      expandedSessionLineageQueues,
      currentSessionLineageQueue,
      onExpandAllSessionLineageQueues: expandAllSessionLineageQueues,
      onCollapseAllSessionLineageQueues: collapseAllSessionLineageQueues,
      onOpenCurrentSessionLineageQueue: openCurrentSessionLineageQueue,
      sessionQueueAdvanceFeedback,
      sessionQueueAdvanceFocusSummary,
      sessionQueueFocusDelta,
      sessionQueueAdvanceNoticeActions,
      attentionQueuePosition,
      hiddenAttentionQueueCount,
      attentionSessionLineageQueue,
      onToggleSessionLineageQueueExpansion: toggleSessionLineageQueueExpansion,
      onRestoreSessionLineageQueue: restoreSessionLineageQueue,
      sessionLineagePriority,
      sessionLineageTraits,
      onSnoozeSessionLineageQueueEntry: snoozeSessionLineageQueueEntry,
      onAdvanceSessionLineageQueueFromEntry: advanceSessionLineageQueueFromEntry,
      onDismissSessionLineageQueueEntry: dismissSessionLineageQueueEntry,
      onFindSessionLineageEntryInSession: findSessionLineageEntryInSession,
      onRevealSessionLineageEntryInTimeline: revealSessionLineageEntryInTimeline,
      decisionQueuePosition,
      hiddenDecisionQueueCount,
      decisionSessionLineageQueue,
      visibleSessionLineageEntries,
      onSelectRunOutcome: (runId, resultIndex) => {
        setSelectedRunId(runId);
        setSelectedRunResultIndex(resultIndex);
      },
    },
    triageInboxSectionProps: {
      triageInboxItemCount,
      triageInboxItems,
      selectedTriageInboxItem,
      syncedTriageInboxItem,
      formatTimestamp,
      onInspectTriageInboxItem: inspectTriageInboxItem,
      onInspectAndAdvanceTriageInboxItem: inspectAndAdvanceTriageInboxItem,
      onAdvanceTriageInboxCursor: advanceTriageInboxCursor,
      onSyncTriageInboxCursorToSelection: syncTriageInboxCursorToSelection,
      triageInboxFeedbackHistoryCount,
      triageInboxFeedbackFilter,
      onTriageInboxFeedbackFilterChange: setTriageInboxFeedbackFilter,
      triageInboxFeedbackCounts,
      triageInboxFeedback,
      groupedRecentTriageInboxFeedback,
      recentTriageInboxFeedbackCount,
      expandedTriageInboxResultGroups,
      currentTriageInboxFeedbackGroup,
      onExpandAllTriageInboxResultGroups: expandAllTriageInboxResultGroups,
      onCollapseAllTriageInboxResultGroups: collapseAllTriageInboxResultGroups,
      onOpenCurrentTriageInboxResultGroup: openCurrentTriageInboxResultGroup,
      onToggleTriageInboxResultGroup: toggleTriageInboxResultGroup,
      onOpenTriageInboxHistoryGroup: openTriageInboxHistoryGroup,
      onSnoozeTriageInboxItem: snoozeTriageInboxItem,
      onDismissTriageInboxItem: dismissTriageInboxItem,
    },
    runtimeAgentSectionProps,
    controlPlaneOverviewSectionsProps: {
      controlSummary,
      recentSessions,
      totalSessionCount,
      selectedSessionId,
      onSelectSession: setSelectedSessionId,
      sessionSummary,
    },
  };
}

export function buildHeaderSectionProps({
  latestControlPassAt,
  latestSessionAt,
  selectedSessionId,
  selectedControlState,
  refreshing,
  refresh,
  formatTimestamp,
  controlSummary,
  sessionSummary,
  historySearch,
  setHistorySearch,
  filteredSessionHistoryCount,
  totalSessionCount,
  filteredControlPassHistoryCount,
  totalControlPassCount,
  onCopyCurrentLink,
}: BuildHeaderSectionPropsArgs): HeaderSectionProps {
  return {
    latestControlPassAt,
    latestSessionAt,
    selectedSessionId,
    selectedControlState,
    refreshing,
    onRefresh: () => {
      void refresh();
    },
    formatTimestamp,
    controlSummary,
    sessionSummary,
    historySearch,
    onHistorySearchChange: setHistorySearch,
    onClearHistorySearch: () => {
      setHistorySearch("");
    },
    filteredSessionHistoryCount,
    totalSessionCount,
    filteredControlPassHistoryCount,
    totalControlPassCount,
    onCopyCurrentLink,
  };
}

export function buildMainSectionsProps({
  notice,
  errorMessage,
  workspaceSectionProps,
  sessionDrilldownSectionProps,
}: MainSectionsProps): MainSectionsProps {
  return {
    notice,
    errorMessage,
    workspaceSectionProps,
    sessionDrilldownSectionProps,
  };
}
