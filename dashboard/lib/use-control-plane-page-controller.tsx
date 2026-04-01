"use client";
import { useCallback, useMemo } from "react";
import {
  asRecord,
  describeRunResult,
  eventFamily,
  formatJson,
  formatScopeList,
  formatTimestamp,
  outcomeProjectId,
  outcomeProjectName,
  outcomeRuntimeAgentId,
  outcomeStoryId,
  outcomeStoryTitle,
  toNullableNumber,
  toNumber,
  toStringArray,
  toStringValue,
} from "@/lib/control-plane-data";
import { buildRuntimeAgentSectionProps } from "@/lib/control-plane-runtime-agent-props";
import { buildSessionDrilldownSectionProps } from "@/lib/control-plane-session-drilldown-props";
import {
  agentTimelineEntryKey,
  agentTimelineRowDomId,
  resolveRunLinkFromContext,
  resolveSessionEventFromContext,
  sessionContextRowDomId,
  sessionEventKey,
} from "@/lib/control-plane-linking";
import {
  buildHeaderSectionProps,
  buildMainSectionsProps,
  buildWorkspaceSectionProps,
} from "@/lib/control-plane-section-props";
import {
  agentTimelinePriority,
  matchesEventFilter,
  matchesRunFilter,
  sessionLineagePriority,
  sessionLineageTraits,
} from "@/lib/control-plane-triage";
import {
  useControlPlaneActions,
} from "@/lib/use-control-plane-actions";
import { useControlPlaneAgentNavigation } from "@/lib/use-control-plane-agent-navigation";
import { useControlPlaneAgentPriorityQueues } from "@/lib/use-control-plane-agent-priority-queues";
import { useControlPlaneBootstrap } from "@/lib/use-control-plane-bootstrap";
import { useControlPlaneDataLoader } from "@/lib/use-control-plane-data-loader";
import { useControlPlaneLinkedSelection } from "@/lib/use-control-plane-linked-selection";
import { useControlPlaneOperatorPersistence } from "@/lib/use-control-plane-operator-persistence";
import { useControlPlaneQueueAdvance } from "@/lib/use-control-plane-queue-advance";
import { useControlPlaneQueueTargetNavigation } from "@/lib/use-control-plane-queue-target-navigation";
import { useControlPlaneRevealFlows } from "@/lib/use-control-plane-reveal-flows";
import { useControlPlaneRunSelection } from "@/lib/use-control-plane-run-selection";
import { useControlPlaneRuntimeAgentModel } from "@/lib/use-control-plane-runtime-agent-model";
import { useControlPlaneSessionLineageModel } from "@/lib/use-control-plane-session-lineage-model";
import { useControlPlaneSessionOverviewModel } from "@/lib/use-control-plane-session-overview-model";
import { useControlPlaneSessionLineageQueues } from "@/lib/use-control-plane-session-lineage-queues";
import { useControlPlaneTriageInbox } from "@/lib/use-control-plane-triage-inbox";
import {
  type ControlPlaneViewSelection,
  useControlPlaneViewState,
} from "@/lib/use-control-plane-view-state";

type BuildControlPlaneUrl = (selection: ControlPlaneViewSelection) => string;

export function useControlPlanePageController(
  initialSelection?: ControlPlaneViewSelection,
  buildControlPlaneUrl?: BuildControlPlaneUrl
) {
  const TRIAGE_INBOX_FEEDBACK_LIMIT = 5;
  const {
    health,
    setHealth,
    projects,
    setProjects,
    controlPasses,
    setControlPasses,
    controlSummary,
    setControlSummary,
    sessions,
    setSessions,
    sessionSummary,
    setSessionSummary,
    controlProfiles,
    setControlProfiles,
    selectedSessionId,
    setSelectedSessionId,
    selectedAgentId,
    setSelectedAgentId,
    selectedRunId,
    setSelectedRunId,
    selectedRunResultIndex,
    setSelectedRunResultIndex,
    selectedPassId,
    setSelectedPassId,
    selectedSession,
    setSelectedSession,
    selectedAgent,
    setSelectedAgent,
    agentLoading,
    setAgentLoading,
    runFilter,
    setRunFilter,
    eventFilter,
    setEventFilter,
    sessionLineageFilter,
    setSessionLineageFilter,
    agentActivityFilter,
    setAgentActivityFilter,
    agentActivitySearch,
    setAgentActivitySearch,
    agentTimelineFilter,
    setAgentTimelineFilter,
    agentTimelineSearch,
    setAgentTimelineSearch,
    selectedAgentTimelineKey,
    setSelectedAgentTimelineKey,
    pendingAgentTimelineTarget,
    setPendingAgentTimelineTarget,
    dismissedAgentTimelineKeys,
    setDismissedAgentTimelineKeys,
    snoozedAgentTimelineUntil,
    setSnoozedAgentTimelineUntil,
    pendingAgentPriorityAutoAdvance,
    setPendingAgentPriorityAutoAdvance,
    pendingLineageAutoAdvance,
    setPendingLineageAutoAdvance,
    dismissedLineageQueueKeys,
    setDismissedLineageQueueKeys,
    snoozedLineageQueueUntil,
    setSnoozedLineageQueueUntil,
    lineageQueueNow,
    setLineageQueueNow,
    pendingSessionRowDomId,
    setPendingSessionRowDomId,
    pendingAgentTimelineRowDomId,
    setPendingAgentTimelineRowDomId,
    selectedSessionApprovalId,
    setSelectedSessionApprovalId,
    selectedSessionIssueId,
    setSelectedSessionIssueId,
    selectedSessionToolPermissionRuntimeId,
    setSelectedSessionToolPermissionRuntimeId,
    selectedSessionEventKey,
    setSelectedSessionEventKey,
    selectedSessionContextKind,
    setSelectedSessionContextKind,
    selectedTriageInboxKey,
    setSelectedTriageInboxKey,
    sessionQueueAdvanceFeedback,
    setSessionQueueAdvanceFeedback,
    agentQueueAdvanceFeedback,
    setAgentQueueAdvanceFeedback,
    sessionQueueFocusDelta,
    setSessionQueueFocusDelta,
    agentQueueFocusDelta,
    setAgentQueueFocusDelta,
    triageInboxFeedbackHistory,
    setTriageInboxFeedbackHistory,
    triageInboxFeedbackFilter,
    setTriageInboxFeedbackFilter,
    expandedTriageInboxResultGroups,
    setExpandedTriageInboxResultGroups,
    expandedSessionLineageQueues,
    setExpandedSessionLineageQueues,
    expandedAgentPriorityQueues,
    setExpandedAgentPriorityQueues,
    historySearch,
    setHistorySearch,
    entitySearch,
    setEntitySearch,
    refreshing,
    setRefreshing,
    sessionLoading,
    setSessionLoading,
    busyActionKey,
    setBusyActionKey,
    notice,
    setNotice,
    errorMessage,
    setErrorMessage,
    selectedSessionLineageEntryRef,
    selectedAgentTimelineEntryRef,
    selectedTriageInboxKeyRef,
    sessionLineageFilterRef,
  } = useControlPlaneViewState(initialSelection);

  const { loadOverview, loadSessionDetail, loadAgentDetail } = useControlPlaneDataLoader({
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
  });

  const {
    refresh,
    recordTriageInboxFeedback,
    applyRecommendation,
    approveApproval,
    rejectApproval,
    applyApproval,
    resolveIssue,
    resolveToolPermissionRuntime,
    applyPreviewRun,
    runAgentSuggestedCommand,
    applyControlPlan,
  } = useControlPlaneActions({
    selectedSessionId,
    selectedAgentId,
    selectedAgent,
    setRefreshing,
    setBusyActionKey,
    setNotice,
    setErrorMessage,
    setSelectedRunId,
    setSelectedRunResultIndex,
    setSelectedPassId,
    setSelectedAgent,
    setEntitySearch,
    setPendingLineageAutoAdvance,
    setPendingAgentPriorityAutoAdvance,
    setTriageInboxFeedbackHistory,
    selectedSessionLineageEntryRef,
    selectedAgentTimelineEntryRef,
    selectedTriageInboxKeyRef,
    sessionLineageFilterRef,
    loadOverview,
    loadSessionDetail,
    loadAgentDetail,
    toStringValue,
    triageInboxFeedbackLimit: TRIAGE_INBOX_FEEDBACK_LIMIT,
  });

  const copyControlPlaneLink = useCallback(
    async (selection: ControlPlaneViewSelection, successMessage: string) => {
      const url = buildControlPlaneUrl?.(selection);
      if (!url) {
        setErrorMessage("Unable to build control plane link.");
        return;
      }

      try {
        if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(url);
          setNotice(successMessage);
          setErrorMessage("");
          return;
        }
        setErrorMessage("Clipboard is unavailable in this environment.");
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : "Failed to copy control plane link.");
      }
    },
    [buildControlPlaneUrl, setErrorMessage, setNotice]
  );

  useControlPlaneOperatorPersistence({
    selectedSessionId,
    selectedAgentId,
    dismissedLineageQueueKeys,
    setDismissedLineageQueueKeys,
    snoozedLineageQueueUntil,
    setSnoozedLineageQueueUntil,
    lineageQueueNow,
    setLineageQueueNow,
    sessionQueueFocusDelta,
    setSessionQueueFocusDelta,
    dismissedAgentTimelineKeys,
    setDismissedAgentTimelineKeys,
    snoozedAgentTimelineUntil,
    setSnoozedAgentTimelineUntil,
    agentQueueFocusDelta,
    setAgentQueueFocusDelta,
  });

  const { focusRuntimeAgent } = useControlPlaneBootstrap({
    sessions,
    controlPasses,
    selectedSessionId,
    selectedAgentId,
    selectedRunId,
    selectedRunResultIndex,
    selectedSession,
    loadSessionDetail,
    loadAgentDetail,
    setSelectedSessionId,
    setSelectedAgentId,
    setSelectedRunId,
    setSelectedRunResultIndex,
    setSelectedPassId,
    setSelectedAgent,
    setSelectedSession,
    setSelectedSessionApprovalId,
    setSelectedSessionIssueId,
    setSelectedSessionToolPermissionRuntimeId,
    setSelectedSessionEventKey,
    setSelectedSessionContextKind,
    setEntitySearch,
    setSessionQueueAdvanceFeedback,
    setSessionQueueFocusDelta,
    setPendingLineageAutoAdvance,
    setLineageQueueNow,
    setSessionLoading,
    setAgentLoading,
    setErrorMessage,
    setAgentActivityFilter,
    setAgentActivitySearch,
    setAgentTimelineFilter,
    setAgentTimelineSearch,
    setSelectedAgentTimelineKey,
    setAgentQueueAdvanceFeedback,
    setAgentQueueFocusDelta,
    setPendingAgentPriorityAutoAdvance,
  });

  const {
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
  } = useControlPlaneSessionOverviewModel({
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
  });
  useControlPlaneRunSelection({
    filteredRuns,
    linkedRuns,
    selectedRunId,
    selectedRunResultIndex,
    preserveEmptyRunSelection: Boolean(
      selectedSessionApprovalId ||
        selectedSessionIssueId ||
        selectedSessionToolPermissionRuntimeId ||
        selectedSessionEventKey
    ),
    setSelectedRunId,
    setSelectedRunResultIndex,
  });
  const selectedSessionToolPermissionRuntime = useMemo(
    () =>
      (selectedSession?.tool_permission_runtimes || []).find(
        (runtime) => runtime.id === selectedSessionToolPermissionRuntimeId
      ) ?? null,
    [selectedSession, selectedSessionToolPermissionRuntimeId]
  );
  const latestSessionPreviewRun = useMemo(() => {
    const previewRuns = linkedRuns.filter(
      (run) =>
        run.dry_run &&
        run.run_kind === "batch" &&
        toStringArray(run.selection?.selected_action_keys).length > 0
    );
    if (!previewRuns.length) return null;
    const executionRuns = linkedRuns.filter((run) => !run.dry_run);
    return (
      previewRuns.find((previewRun) => {
        const previewKey = toStringValue(previewRun.preview_id, previewRun.id);
        return !executionRuns.some(
          (run) => toStringValue(run.preview_id) === previewKey
        );
      }) ?? previewRuns[0]
    );
  }, [linkedRuns]);
  const latestSessionPreviewAppliedRun = useMemo(() => {
    if (!latestSessionPreviewRun) return null;
    const previewKey = toStringValue(latestSessionPreviewRun.preview_id, latestSessionPreviewRun.id);
    return (
      linkedRuns.find(
        (run) => !run.dry_run && toStringValue(run.preview_id) === previewKey
      ) ?? null
    );
  }, [latestSessionPreviewRun, linkedRuns]);
  const {
    sessionLineageEntries,
    selectedSessionLineageEntry,
    filteredSessionLineageEntries,
    sessionLineagePriorityCounts,
    nextBestSessionLineageEntry,
    selectedSessionLineagePriority,
    visibleSessionLineageEntries,
    sessionLineageStatusCounts,
    sessionLineageDecisionCount,
    sessionLineageAttentionCount,
    sessionLineageEventCount,
    sessionLineageAgentCount,
    sessionLineageAgentLinkedCount,
    sessionLineageFilterCounts,
    latestAgentLinkedLineageEntry,
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    attentionSessionLineageQueue,
    decisionSessionLineageQueue,
    attentionQueuePosition,
    decisionQueuePosition,
    nextAttentionSessionLineageEntry,
    nextDecisionSessionLineageEntry,
    currentSessionLineageQueue,
    hiddenAttentionQueueCount,
    hiddenDecisionQueueCount,
    persistedLineageQueueState,
    persistedDismissedLineageQueueCount,
    persistedSnoozedLineageQueueCount,
    hasPersistedLineageQueuePreferences,
    selectedSessionLineageTraits,
  } = useControlPlaneSessionLineageModel({
    approvalById,
    issueById,
    linkedRuns,
    selectedSession,
    selectedSessionId,
    selectedRunId,
    selectedRunResultIndex,
    sessionLineageFilter,
    dismissedLineageQueueKeys,
    snoozedLineageQueueUntil,
    lineageQueueNow,
    selectedSessionLineageEntryRef,
    sessionLineageFilterRef,
    setExpandedSessionLineageQueues,
  });
  const {
    syncLinkedSelection,
    inspectSessionLineageEntry,
    focusSessionLineageEntry,
    openSelectedRunResultInTimeline,
    selectedSessionContext,
    revealSelectedSessionContextRow,
    revealSelectedSessionContextInAgentTimeline,
  } = useControlPlaneLinkedSelection({
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
  });

  const currentSelection = useMemo<ControlPlaneViewSelection>(
    () => ({
      sessionId: selectedSessionId || null,
      agentId: selectedAgentId || null,
      runId: selectedRunId || null,
      resultIndex: selectedRunId ? selectedRunResultIndex : null,
      passId: selectedPassId || null,
      sessionContextKind: selectedSessionContextKind || null,
      approvalId: selectedSessionApprovalId || null,
      issueId: selectedSessionIssueId || null,
      toolPermissionRuntimeId: selectedSessionToolPermissionRuntimeId || null,
      eventKey: selectedSessionEventKey || null,
    }),
    [
      selectedAgentId,
      selectedPassId,
      selectedRunId,
      selectedRunResultIndex,
      selectedSessionApprovalId,
      selectedSessionContextKind,
      selectedSessionEventKey,
      selectedSessionId,
      selectedSessionIssueId,
      selectedSessionToolPermissionRuntimeId,
    ]
  );

  const selectedRunLinkSelection = useMemo<ControlPlaneViewSelection | null>(() => {
    if (!selectedRun) return null;

    const resultRecord =
      asRecord(selectedRun.results[selectedRunResultIndex]) || asRecord(selectedRunResult);
    const approval = asRecord(resultRecord?.approval);
    const issue = asRecord(resultRecord?.issue);
    const approvalId = toStringValue(approval?.id);
    const issueId = toStringValue(issue?.id);
    const runtimeAgentId =
      outcomeRuntimeAgentId(resultRecord || {}) || selectedRun.runtime_agent_ids[0] || selectedAgentId;
    const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
      runId: selectedRun.id,
      resultIndex: selectedRunResultIndex,
      approvalId,
      issueId,
      runtimeAgentId,
    });
    const sessionContextKind = issueId
      ? "issue"
      : approvalId
        ? "approval"
        : matchedEvent
          ? "event"
          : null;

    return {
      sessionId: selectedSessionId || null,
      agentId: runtimeAgentId || null,
      runId: selectedRun.id,
      resultIndex: selectedRunResultIndex,
      passId: null,
      sessionContextKind,
      approvalId: approvalId || null,
      issueId: issueId || null,
      toolPermissionRuntimeId: null,
      eventKey: matchedEvent?.key || null,
    };
  }, [
    selectedAgentId,
    selectedRun,
    selectedRunResult,
    selectedRunResultIndex,
    selectedSession,
    selectedSessionId,
  ]);

  const selectedSessionContextLinkSelection = useMemo<ControlPlaneViewSelection | null>(() => {
    if (!selectedSessionContext) return null;

    const eventContext = selectedSessionContext.kind === "event" ? selectedSessionContext.event : null;
    const runtimeContext =
      selectedSessionContext.kind === "tool_permission_runtime"
        ? selectedSessionContext.runtime
        : null;
    const approvalId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.id
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.approval_id
          : runtimeContext?.approval_id || toStringValue(eventContext?.approval_id);
    const issueId =
      selectedSessionContext.kind === "issue"
        ? selectedSessionContext.issue.id
        : selectedSessionContext.kind === "approval"
          ? selectedSessionContext.approval.issue_id
          : runtimeContext?.issue_id || toStringValue(eventContext?.issue_id);
    const runtimeAgentId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.runtime_agent_ids[0]
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.runtime_agent_ids[0] ||
            selectedSessionContext.issue.runtime_agent_id
          : selectedSessionContext.kind === "tool_permission_runtime"
            ? runtimeContext?.runtime_agent_ids[0] || ""
          : toStringValue(eventContext?.runtime_agent_id) ||
            toStringArray(eventContext?.runtime_agent_ids)[0];
    const directRunId =
      selectedSessionContext.kind === "event"
        ? toStringValue(eventContext?.agent_action_run_id) || toStringValue(eventContext?.run_id)
        : "";
    const relatedRunLink = resolveRunLinkFromContext(linkedRuns, {
      runId: directRunId,
      approvalId,
      issueId,
      runtimeAgentId,
      event: eventContext,
    });

    return {
      sessionId: selectedSessionId || null,
      agentId: runtimeAgentId || null,
      runId: relatedRunLink?.run.id || directRunId || null,
      resultIndex: relatedRunLink ? relatedRunLink.resultIndex : null,
      passId: null,
      sessionContextKind: selectedSessionContext.kind,
      approvalId:
        selectedSessionContext.kind === "tool_permission_runtime" ? null : approvalId || null,
      issueId:
        selectedSessionContext.kind === "tool_permission_runtime" ? null : issueId || null,
      toolPermissionRuntimeId: runtimeContext?.id || null,
      eventKey:
        selectedSessionContext.kind === "event"
          ? selectedSessionEventKey || sessionEventKey(selectedSessionContext.event)
          : null,
    };
  }, [
    linkedRuns,
    selectedSessionContext,
    selectedSessionEventKey,
    selectedSessionId,
  ]);

  const selectedRuntimeAgentLinkSelection = useMemo<ControlPlaneViewSelection | null>(() => {
    const runtimeAgentId = selectedAgent?.runtime_agent_id || selectedAgentId;
    if (!runtimeAgentId) return null;
    return {
      sessionId: selectedSessionId || null,
      agentId: runtimeAgentId,
      runId: null,
      resultIndex: null,
      passId: null,
      sessionContextKind: null,
      approvalId: null,
      issueId: null,
      toolPermissionRuntimeId: null,
      eventKey: null,
    };
  }, [selectedAgent, selectedAgentId, selectedSessionId]);

  const copySelectionLink = useCallback(
    (
      selection: ControlPlaneViewSelection | null,
      successMessage: string,
      missingSelectionMessage: string
    ) => {
      if (!selection) {
        setErrorMessage(missingSelectionMessage);
        return;
      }
      void copyControlPlaneLink(selection, successMessage);
    },
    [copyControlPlaneLink, setErrorMessage]
  );
  const {
    advanceSessionLineageQueue,
    advanceSessionLineageQueueFromEntry,
    dismissSessionLineageQueueEntry,
    snoozeSessionLineageQueueEntry,
    restoreSessionLineageQueue,
    resetSessionLineageQueuePreferences,
    toggleSessionLineageQueueExpansion,
    expandAllSessionLineageQueues,
    collapseAllSessionLineageQueues,
    openCurrentSessionLineageQueue,
    exportSessionLineageQueuePreferences,
  } = useControlPlaneSessionLineageQueues({
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    selectedSessionLineageEntry,
    sessionLineageFilter,
    currentSessionLineageQueue,
    selectedSessionId,
    persistedLineageQueueState,
    pendingLineageAutoAdvance,
    setDismissedLineageQueueKeys,
    setSnoozedLineageQueueUntil,
    setLineageQueueNow,
    setNotice,
    setErrorMessage,
    setExpandedSessionLineageQueues,
    setSessionQueueAdvanceFeedback,
    setPendingLineageAutoAdvance,
    setSessionLineageFilter,
    focusSessionLineageEntry,
  });
  const {
    agentScopedRuns,
    agentScopedOutcomes,
    filteredAgentScopedRuns,
    filteredAgentScopedOutcomes,
    agentTimelineEntries,
    activeAgentTimelineEntries,
    filteredAgentTimelineEntries,
    agentTimelineFilterCounts,
    selectedAgentTimelineEntry,
    visibleAgentTimelineEntries,
    latestAgentApprovalEntry,
    latestAgentIssueEntry,
    latestAgentEventEntry,
    hiddenAgentTimelineEntryCount,
    persistedDismissedAgentTimelineCount,
    persistedSnoozedAgentTimelineCount,
    hasPersistedAgentTimelinePreferences,
    selectedAgentTimelineRunLink,
    agentTimelinePriorityCounts,
    nextBestAgentTimelineEntry,
    selectedAgentTimelinePriority,
    currentAgentPriorityQueue,
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    criticalAgentTimelineQueue,
    highAgentTimelineQueue,
    criticalAgentTimelinePosition,
    highAgentTimelinePosition,
    nextCriticalAgentTimelineEntry,
    nextHighAgentTimelineEntry,
    selectedAgentTimelineEntryKeyValue,
  } = useControlPlaneRuntimeAgentModel({
    selectedAgentId,
    selectedAgent,
    linkedRuns,
    agentActivityFilter,
    agentActivitySearch,
    agentTimelineFilter,
    agentTimelineSearch,
    dismissedAgentTimelineKeys,
    snoozedAgentTimelineUntil,
    lineageQueueNow,
    selectedAgentTimelineKey,
    setSelectedAgentTimelineKey,
    setExpandedAgentPriorityQueues,
    selectedAgentTimelineEntryRef,
  });
  const {
    focusAgentTimeline,
    inspectAgentTimelineEntry,
  } = useControlPlaneAgentNavigation({
    linkedRuns,
    selectedAgent,
    selectedAgentId,
    syncLinkedSelection,
    setAgentTimelineFilter,
    setAgentTimelineSearch,
    setSelectedAgentTimelineKey,
  });
  const {
    toggleAgentPriorityQueueExpansion,
    expandAllAgentPriorityQueues,
    collapseAllAgentPriorityQueues,
    openCurrentAgentPriorityQueue,
    dismissAgentTimelineEntry,
    snoozeAgentTimelineEntry,
    restoreAgentTimelineHidden,
    resetAgentTimelinePreferences,
    exportAgentTimelinePreferences,
    advanceAgentPriorityQueueFromEntry,
  } = useControlPlaneAgentPriorityQueues({
    selectedAgentId,
    selectedAgentTimelineEntryRef,
    filteredAgentTimelineEntries,
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    currentAgentPriorityQueue,
    dismissedAgentTimelineKeys,
    snoozedAgentTimelineUntil,
    lineageQueueNow,
    pendingAgentPriorityAutoAdvance,
    setDismissedAgentTimelineKeys,
    setSnoozedAgentTimelineUntil,
    setLineageQueueNow,
    setNotice,
    setErrorMessage,
    setExpandedAgentPriorityQueues,
    setPendingAgentPriorityAutoAdvance,
    setAgentQueueAdvanceFeedback,
    inspectAgentTimelineEntry,
  });
  const {
    restoreAgentTimelineEntryVisibility,
    revealAgentTimelineEntry,
    findSessionLineageEntryInSession,
    revealSessionLineageEntryInTimeline,
    findAgentTimelineEntryInSession,
  } = useControlPlaneRevealFlows({
    selectedAgentId,
    selectedAgent,
    linkedRuns,
    syncLinkedSelection,
    agentTimelineEntries,
    visibleAgentTimelineEntries,
    pendingAgentTimelineTarget,
    setPendingAgentTimelineTarget,
    pendingSessionRowDomId,
    setPendingSessionRowDomId,
    pendingAgentTimelineRowDomId,
    setPendingAgentTimelineRowDomId,
    setDismissedAgentTimelineKeys,
    setSnoozedAgentTimelineUntil,
    setLineageQueueNow,
    setAgentTimelineFilter,
    setAgentTimelineSearch,
    setSelectedAgentTimelineKey,
    setEntitySearch,
    setSelectedRunId,
    setSelectedRunResultIndex,
    setNotice,
  });
  const { openSessionQueueAdvanceTarget, openAgentQueueAdvanceTarget } =
    useControlPlaneQueueTargetNavigation({
      focusSessionLineageEntry,
      restoreAgentTimelineEntryVisibility,
      revealAgentTimelineEntry,
      inspectAgentTimelineEntry,
    });
  const {
    sessionQueueAdvanceFocusSummary,
    agentQueueAdvanceFocusSummary,
    sessionQueueAdvanceNoticeActions,
    agentQueueAdvanceNoticeActions,
  } = useControlPlaneQueueAdvance({
    sessionLineageFilter,
    sessionLineageEntriesCount: sessionLineageEntries.length,
    filteredSessionLineageEntriesCount: filteredSessionLineageEntries.length,
    sessionLineageFilterCounts,
    focusSessionLineageEntry,
    setSessionLineageFilter,
    sessionQueueAdvanceFeedback,
    setSessionQueueFocusDelta,
    currentSessionLineageQueue,
    openCurrentSessionLineageQueue,
    openSessionQueueAdvanceTarget,
    agentTimelineFilter,
    activeAgentTimelineEntriesCount: activeAgentTimelineEntries.length,
    filteredAgentTimelineEntriesCount: filteredAgentTimelineEntries.length,
    agentTimelineFilterCounts,
    focusAgentTimeline,
    inspectAgentTimelineEntry,
    agentQueueAdvanceFeedback,
    setAgentQueueFocusDelta,
    currentAgentPriorityQueue,
    openCurrentAgentPriorityQueue,
    openAgentQueueAdvanceTarget,
  });
  const {
    triageInboxItems,
    triageInboxItemCount,
    selectedTriageInboxItem,
    triageInboxFeedbackCounts,
    triageInboxFeedback,
    recentTriageInboxFeedback,
    groupedRecentTriageInboxFeedback,
    currentTriageInboxFeedbackGroup,
    syncedTriageInboxItem,
    advanceTriageInboxCursor,
    inspectTriageInboxItem,
    openTriageInboxHistoryGroup,
    inspectAndAdvanceTriageInboxItem,
    snoozeTriageInboxItem,
    dismissTriageInboxItem,
    syncTriageInboxCursorToSelection,
    toggleTriageInboxResultGroup,
    expandAllTriageInboxResultGroups,
    collapseAllTriageInboxResultGroups,
    openCurrentTriageInboxResultGroup,
  } = useControlPlaneTriageInbox({
    nextAttentionSessionLineageEntry,
    attentionSessionLineageEntries,
    selectedSessionLineageEntry,
    focusSessionLineageEntry,
    snoozeSessionLineageQueueEntry,
    dismissSessionLineageQueueEntry,
    nextDecisionSessionLineageEntry,
    decisionSessionLineageEntries,
    nextCriticalAgentTimelineEntry,
    criticalAgentTimelineEntries,
    selectedAgentTimelineEntryKeyValue,
    inspectAgentTimelineEntry,
    snoozeAgentTimelineEntry,
    dismissAgentTimelineEntry,
    nextHighAgentTimelineEntry,
    highAgentTimelineEntries,
    selectedTriageInboxKey,
    setSelectedTriageInboxKey,
    triageInboxFeedbackHistory,
    setTriageInboxFeedbackHistory,
    triageInboxFeedbackFilter,
    setTriageInboxFeedbackFilter,
    setExpandedTriageInboxResultGroups,
    selectedTriageInboxKeyRef,
    selectedAgentId,
    selectedSessionId,
    recordTriageInboxFeedback,
    triageInboxFeedbackLimit: TRIAGE_INBOX_FEEDBACK_LIMIT,
  });
  const loading = !controlSummary || !sessionSummary;

  if (loading) {
    return {
      loading,
      health,
      visibleProjects,
      selectedSessionId,
      selectedAgentId,
      selectedRunId,
      selectedPassId,
      headerSectionProps: null,
      mainSectionsProps: null,
    };
  }

  const workspaceSectionProps = buildWorkspaceSectionProps({
    hasSelectedSession: Boolean(selectedSession),
    recentControlPasses,
    totalControlPassCount: controlPasses.length,
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
    onCopySelectedRunLink: () => {
      copySelectionLink(
        selectedRunLinkSelection,
        "Copied selected run link.",
        "No action run is selected."
      );
    },
    busyActionKey,
    onApplySelectedPreviewRun: (run) => {
      void applyPreviewRun(run);
    },
    formatScopeList,
    describeRunResult,
    toStringArray,
    asRecord,
    selectedSessionEvents: selectedSession?.events || [],
    formatJson,
    sessionEventKey,
    resolveSessionEventFromContext,
    outcomeProjectId,
    outcomeProjectName,
    outcomeStoryId,
    outcomeStoryTitle,
    outcomeRuntimeAgentId,
    onOpenSelectedRunResultInTimeline: openSelectedRunResultInTimeline,
    focusRuntimeAgent,
    setEntitySearch,
    setSelectedRunId,
    syncLinkedSelection,
    sessionLineageEntries,
    linkedRunsCount: linkedRuns.length,
    linkedApprovalsCount: linkedApprovals.length,
    linkedIssuesCount: linkedIssues.length,
    linkedAgentCount: linkedAgentIds.length,
    sessionLineageDecisionCount,
    sessionLineageEventCount,
    sessionLineageAgentCount,
    sessionLineageStatusCounts,
    filteredSessionLineageEntriesCount: filteredSessionLineageEntries.length,
    sessionLineageFilter: sessionLineageFilter as
      | "all"
      | "attention"
      | "decisions"
      | "agent-linked",
    setSessionLineageFilter: (value) => {
      setSessionLineageFilter(value);
    },
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
    triageInboxFeedbackHistoryCount: triageInboxFeedbackHistory.length,
    triageInboxFeedbackFilter,
    setTriageInboxFeedbackFilter,
    triageInboxFeedbackCounts,
    triageInboxFeedback,
    groupedRecentTriageInboxFeedback,
    recentTriageInboxFeedbackCount: recentTriageInboxFeedback.length,
    expandedTriageInboxResultGroups,
    currentTriageInboxFeedbackGroup,
    expandAllTriageInboxResultGroups,
    collapseAllTriageInboxResultGroups,
    openCurrentTriageInboxResultGroup,
    toggleTriageInboxResultGroup,
    openTriageInboxHistoryGroup,
    snoozeTriageInboxItem,
    dismissTriageInboxItem,
    runtimeAgentSectionProps: buildRuntimeAgentSectionProps({
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
      onCopyAgentLink: () => {
        copySelectionLink(
          selectedRuntimeAgentLinkSelection,
          "Copied runtime agent link.",
          "No runtime agent is selected."
        );
      },
      focusRuntimeAgent,
      runAgentSuggestedCommand,
      onAllowToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "allow");
      },
      onDenyToolPermissionRuntime: (runtime) => {
        void resolveToolPermissionRuntime(runtime, "deny");
      },
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
      agentTimelineFilter: agentTimelineFilter as
        | "all"
        | "approvals"
        | "issues"
        | "events"
        | "attention",
      setAgentTimelineFilter: (value) => {
        setAgentTimelineFilter(value);
      },
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
      criticalAgentTimelineTotal: criticalAgentTimelineEntries.length,
      criticalAgentTimelinePosition,
      highAgentTimelineQueue,
      highAgentTimelineTotal: highAgentTimelineEntries.length,
      highAgentTimelinePosition,
      toggleAgentPriorityQueueExpansion,
      filteredAgentTimelineEntriesCount: filteredAgentTimelineEntries.length,
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
      advanceCurrentAgentPriorityQueue: (entry) => {
        if (currentAgentPriorityQueue) {
          advanceAgentPriorityQueueFromEntry(currentAgentPriorityQueue, entry);
        }
      },
      focusAgentTimeline,
      setEventFilter: (value) => {
        setEventFilter(value);
      },
      snoozeAgentTimelineEntry,
      dismissAgentTimelineEntry,
      advanceAgentPriorityQueueFromEntry,
      findAgentTimelineEntryInSession,
      revealAgentTimelineEntry,
      agentTimelineEntryKey,
      agentTimelinePriority,
      agentTimelineRowDomId,
    }),
    controlSummary,
    recentSessions,
    totalSessionCount: sessions.length,
    selectedSessionId,
    sessionSummary,
  });

  const sessionDrilldownSectionProps = buildSessionDrilldownSectionProps({
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
    latestPreviewRun: latestSessionPreviewRun,
    latestPreviewAppliedRun: latestSessionPreviewAppliedRun,
    applyControlPlan,
    applyRecommendation,
    applyPreviewRun,
    runFilter: runFilter as "all" | "execute" | "preview" | "attention",
    setRunFilter,
    matchesRunFilter,
    selectedRunId,
    setSelectedRunId,
    setSelectedRunResultIndex,
    toNumber,
    eventFilter: eventFilter as "all" | "control" | "actions" | "decisions" | "attention",
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
    onCopySessionLink: () => {
      void copyControlPlaneLink(
        {
          sessionId: selectedSessionId || null,
        },
        "Copied session link."
      );
    },
    canCopyFocusedLink: Boolean(
      selectedAgentId || selectedRunId || selectedPassId || selectedSessionContext
    ),
    onCopyFocusedLink: () => {
      copySelectionLink(
        currentSelection,
        "Copied focused control link.",
        "No focused control selection is available."
      );
    },
    onCopySessionContextLink: () => {
      copySelectionLink(
        selectedSessionContextLinkSelection,
        "Copied selected session context link.",
        "No session context is selected."
      );
    },
  });

  const headerSectionProps = buildHeaderSectionProps({
    latestControlPassAt: controlSummary.latest_control_pass_at,
    latestSessionAt: sessionSummary.latest_session_at,
    selectedSessionId,
    selectedControlState: selectedControl?.state || null,
    refreshing,
    refresh,
    formatTimestamp,
    controlSummary,
    sessionSummary,
    historySearch,
    setHistorySearch,
    filteredSessionHistoryCount: filteredSessionHistory.length,
    totalSessionCount: sessions.length,
    filteredControlPassHistoryCount: filteredControlPassHistory.length,
    totalControlPassCount: controlPasses.length,
    onCopyCurrentLink: () => {
      copySelectionLink(
        currentSelection,
        "Copied current control plane link.",
        "Unable to determine the current control plane selection."
      );
    },
  });

  const mainSectionsProps = buildMainSectionsProps({
    notice,
    errorMessage,
    workspaceSectionProps,
    sessionDrilldownSectionProps,
  });

  return {
    loading,
    health,
    visibleProjects,
    selectedSessionId,
    selectedAgentId,
    selectedRunId,
    selectedRunResultIndex,
    selectedPassId,
    selectedSessionApprovalId,
    selectedSessionIssueId,
    selectedSessionToolPermissionRuntimeId,
    selectedSessionEventKey,
    selectedSessionContextKind,
    headerSectionProps,
    mainSectionsProps,
  };
}
