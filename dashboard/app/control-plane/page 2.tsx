"use client";
import { useCallback, useMemo, useRef, useState } from "react";
import { ControlPlaneLayout } from "@/components/control-plane-layout";
import { ControlPlaneLoadingShell } from "@/components/control-plane-loading-shell";
import {
  type QueueAdvanceFeedback,
  type QueueAdvanceFocusDelta,
} from "@/components/queue-advance-notice";
import {
} from "@/lib/api";
import {
  approvalMatchesSearch,
  asRecord,
  controlPassMatchesSearch,
  describeRunResult,
  eventFamily,
  eventMatchesSearch,
  formatJson,
  formatScopeList,
  formatTimestamp,
  issueMatchesSearch,
  matchesSearch,
  outcomeProjectId,
  outcomeProjectName,
  outcomeRuntimeAgentId,
  outcomeRuntimeAgentIds,
  outcomeStoryId,
  outcomeStoryTitle,
  runMatchesSearch,
  sessionMatchesSearch,
  toNullableNumber,
  toNumber,
  toStringArray,
  toStringValue,
} from "@/lib/control-plane-data";
import {
  emptySnoozedVisibilityRecord,
  emptyVisibilityKeysRecord,
  isPersistedAgentTimelineStateEmpty,
  isPersistedLineageQueueStateEmpty,
  sanitizeOperatorVisibilityState,
  visibleEntriesByOperatorVisibilityState,
} from "@/lib/control-plane-operator-state";
import { buildRuntimeAgentSectionProps } from "@/lib/control-plane-runtime-agent-props";
import { buildSessionDrilldownSectionProps } from "@/lib/control-plane-session-drilldown-props";
import {
  AGENT_PRIORITY_QUEUE_KEYS,
  SESSION_LINEAGE_QUEUE_KEYS,
  type AgentScopedOutcome,
  type AgentTimelineEntry,
  type LineageQueueKind,
  type PendingAgentTimelineTarget,
  type QueueAdvanceTarget,
  type SessionContextKind,
  type SessionLineageEntry,
  type TriageInboxFeedback,
} from "@/lib/control-plane-models";
import {
  agentTimelineEntryKey,
  agentTimelineRowDomId,
  resolveAgentTimelineRunLink,
  resolveRunLinkFromContext,
  resolveSessionEventFromContext,
  sessionContextRowDomId,
  sessionEventKey,
  withSelectedItem,
} from "@/lib/control-plane-linking";
import {
  buildHeaderSectionProps,
  buildMainSectionsProps,
  buildWorkspaceSectionProps,
} from "@/lib/control-plane-section-props";
import {
  agentTimelinePriority,
  countTriagePriorities,
  matchesAgentOutcomeFilter,
  matchesAgentTimelineFilter,
  matchesEventFilter,
  matchesRunFilter,
  matchesSessionLineageFilter,
  nextBestTriageItem,
  nextSessionLineageQueueEntry,
  nextTriageEntryByPriority,
  sessionLineagePriority,
  sessionLineageQueuePosition,
  sessionLineageTraits,
  triageQueuePosition,
} from "@/lib/control-plane-triage";
import {
  type PendingAgentPriorityAutoAdvance,
  type PendingLineageAutoAdvance,
  useControlPlaneActions,
} from "@/lib/use-control-plane-actions";
import { useControlPlaneAgentTimelineSelection } from "@/lib/use-control-plane-agent-timeline-selection";
import { useControlPlaneAgentPriorityQueues } from "@/lib/use-control-plane-agent-priority-queues";
import { useControlPlaneBootstrap } from "@/lib/use-control-plane-bootstrap";
import { useControlPlaneDataLoader } from "@/lib/use-control-plane-data-loader";
import { useControlPlaneLinkedSelection } from "@/lib/use-control-plane-linked-selection";
import { useControlPlaneOperatorPersistence } from "@/lib/use-control-plane-operator-persistence";
import { useControlPlaneQueueAdvance } from "@/lib/use-control-plane-queue-advance";
import { useControlPlaneRevealFlows } from "@/lib/use-control-plane-reveal-flows";
import { useControlPlaneRunSelection } from "@/lib/use-control-plane-run-selection";
import { useControlPlaneSessionLineageQueues } from "@/lib/use-control-plane-session-lineage-queues";
import { useControlPlaneSessionLineageSelection } from "@/lib/use-control-plane-session-lineage-selection";
import { useControlPlaneTriageInbox } from "@/lib/use-control-plane-triage-inbox";
import type {
  AccountHealth,
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
  ExecutionPlaneCountMap,
  ExecutionIssueRecord,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
  OrchestratorSessionControlProfile,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  ProjectSummary,
} from "@/lib/types";

const TRIAGE_INBOX_FEEDBACK_LIMIT = 5;

export default function ControlPlanePage() {
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [controlPasses, setControlPasses] = useState<OrchestratorControlPassRecord[]>([]);
  const [controlSummary, setControlSummary] = useState<OrchestratorControlPassSummary | null>(null);
  const [sessions, setSessions] = useState<OrchestratorSessionRecord[]>([]);
  const [sessionSummary, setSessionSummary] = useState<OrchestratorSessionSummary | null>(null);
  const [controlProfiles, setControlProfiles] = useState<OrchestratorSessionControlProfile[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRunResultIndex, setSelectedRunResultIndex] = useState(0);
  const [selectedPassId, setSelectedPassId] = useState("");
  const [selectedSession, setSelectedSession] = useState<OrchestratorSessionDetail | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<ExecutionRuntimeAgentDetail | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [runFilter, setRunFilter] = useState("all");
  const [eventFilter, setEventFilter] = useState("all");
  const [sessionLineageFilter, setSessionLineageFilter] = useState("all");
  const [agentActivityFilter, setAgentActivityFilter] = useState("all");
  const [agentActivitySearch, setAgentActivitySearch] = useState("");
  const [agentTimelineFilter, setAgentTimelineFilter] = useState("all");
  const [agentTimelineSearch, setAgentTimelineSearch] = useState("");
  const [selectedAgentTimelineKey, setSelectedAgentTimelineKey] = useState("");
  const [pendingAgentTimelineTarget, setPendingAgentTimelineTarget] =
    useState<PendingAgentTimelineTarget | null>(null);
  const [dismissedAgentTimelineKeys, setDismissedAgentTimelineKeys] = useState<string[]>([]);
  const [snoozedAgentTimelineUntil, setSnoozedAgentTimelineUntil] = useState<Record<string, number>>(
    {}
  );
  const [pendingAgentPriorityAutoAdvance, setPendingAgentPriorityAutoAdvance] =
    useState<PendingAgentPriorityAutoAdvance | null>(null);
  const [pendingLineageAutoAdvance, setPendingLineageAutoAdvance] =
    useState<PendingLineageAutoAdvance | null>(null);
  const [dismissedLineageQueueKeys, setDismissedLineageQueueKeys] = useState<
    Record<LineageQueueKind, string[]>
  >(() => emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
  const [snoozedLineageQueueUntil, setSnoozedLineageQueueUntil] = useState<
    Record<LineageQueueKind, Record<string, number>>
  >(() => emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
  const [lineageQueueNow, setLineageQueueNow] = useState(() => Date.now());
  const [pendingSessionRowDomId, setPendingSessionRowDomId] = useState("");
  const [pendingAgentTimelineRowDomId, setPendingAgentTimelineRowDomId] = useState("");
  const [selectedSessionApprovalId, setSelectedSessionApprovalId] = useState("");
  const [selectedSessionIssueId, setSelectedSessionIssueId] = useState("");
  const [selectedSessionEventKey, setSelectedSessionEventKey] = useState("");
  const [selectedSessionContextKind, setSelectedSessionContextKind] =
    useState<SessionContextKind>("");
  const [selectedTriageInboxKey, setSelectedTriageInboxKey] = useState("");
  const [sessionQueueAdvanceFeedback, setSessionQueueAdvanceFeedback] =
    useState<QueueAdvanceFeedback<QueueAdvanceTarget> | null>(null);
  const [agentQueueAdvanceFeedback, setAgentQueueAdvanceFeedback] =
    useState<QueueAdvanceFeedback<QueueAdvanceTarget> | null>(null);
  const [sessionQueueFocusDelta, setSessionQueueFocusDelta] =
    useState<QueueAdvanceFocusDelta | null>(null);
  const [agentQueueFocusDelta, setAgentQueueFocusDelta] =
    useState<QueueAdvanceFocusDelta | null>(null);
  const [triageInboxFeedbackHistory, setTriageInboxFeedbackHistory] = useState<
    TriageInboxFeedback[]
  >([]);
  const [triageInboxFeedbackFilter, setTriageInboxFeedbackFilter] = useState<
    "all" | "success" | "info"
  >("all");
  const [expandedTriageInboxResultGroups, setExpandedTriageInboxResultGroups] = useState<string[]>(
    []
  );
  const [expandedSessionLineageQueues, setExpandedSessionLineageQueues] = useState<
    LineageQueueKind[]
  >([...SESSION_LINEAGE_QUEUE_KEYS]);
  const [expandedAgentPriorityQueues, setExpandedAgentPriorityQueues] = useState<
    Array<(typeof AGENT_PRIORITY_QUEUE_KEYS)[number]>
  >([...AGENT_PRIORITY_QUEUE_KEYS]);
  const [historySearch, setHistorySearch] = useState("");
  const [entitySearch, setEntitySearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [busyActionKey, setBusyActionKey] = useState("");
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const selectedSessionLineageEntryRef = useRef<SessionLineageEntry | null>(null);
  const selectedAgentTimelineEntryRef = useRef<AgentTimelineEntry | null>(null);
  const selectedTriageInboxKeyRef = useRef("");
  const sessionLineageFilterRef = useRef("all");

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

  const focusAgentTimeline = useCallback(
    (
      filter: string,
      options?: {
        entry?: AgentTimelineEntry | null;
        search?: string;
      }
    ) => {
      setAgentTimelineFilter(filter);
      setAgentTimelineSearch(options?.search ?? "");
      setSelectedAgentTimelineKey(options?.entry ? agentTimelineEntryKey(options.entry) : "");
    },
    []
  );
  const {
    refresh,
    recordTriageInboxFeedback,
    applyRecommendation,
    approveApproval,
    rejectApproval,
    applyApproval,
    resolveIssue,
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
  const recentSessions = useMemo(() => filteredSessionHistory.slice(0, 6), [filteredSessionHistory]);
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
  const linkedApprovals = useMemo(
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
  useControlPlaneRunSelection({
    filteredRuns,
    linkedRuns,
    selectedRunId,
    selectedRunResultIndex,
    setSelectedRunId,
    setSelectedRunResultIndex,
  });
  const linkedIssues = useMemo(
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
  const sessionLineageEntries = useMemo(() => {
    const entries: SessionLineageEntry[] = [];
    linkedRuns.forEach((run) => {
      run.results.forEach((result, resultIndex) => {
        const approvalId = toStringValue(asRecord(result.approval)?.id);
        const issueId = toStringValue(asRecord(result.issue)?.id);
        const linkedApproval = approvalId ? approvalById.get(approvalId) ?? null : null;
        const linkedIssue = issueId ? issueById.get(issueId) ?? null : null;
        const runtimeAgentId =
          outcomeRuntimeAgentId(result) ||
          linkedApproval?.runtime_agent_ids[0] ||
          linkedIssue?.runtime_agent_ids[0] ||
          linkedIssue?.runtime_agent_id ||
          "";
        const relatedEventMatch = resolveSessionEventFromContext(selectedSession?.events || [], {
          runId: run.id,
          approvalId,
          issueId,
          runtimeAgentId,
        });
        const details = describeRunResult(result);
        const projectId = outcomeProjectId(result);
        const projectName = outcomeProjectName(result);
        const storyId = outcomeStoryId(result);
        const storyTitle = outcomeStoryTitle(result);
        const timestamp =
          toStringValue(relatedEventMatch?.event?.timestamp) ||
          run.completed_at ||
          run.updated_at ||
          run.created_at;
        entries.push({
          key: `${run.id}:${resultIndex}`,
          runId: run.id,
          resultIndex,
          timestamp,
          status: toStringValue(result.status, run.status || "unknown"),
          title: details.title,
          subtitle: details.subtitle,
          message: details.message,
          approvalId,
          issueId,
          eventKey: relatedEventMatch?.key || "",
          eventName: toStringValue(relatedEventMatch?.event?.event),
          runtimeAgentId,
          projectId,
          projectName,
          storyId,
          storyTitle,
          event: relatedEventMatch?.event || null,
        });
      });
    });
    return entries.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        right.runId.localeCompare(left.runId) ||
        left.resultIndex - right.resultIndex
    );
  }, [approvalById, issueById, linkedRuns, selectedSession]);
  const { selectedSessionLineageEntry } = useControlPlaneSessionLineageSelection({
    selectedSessionId,
    selectedRunId,
    selectedRunResultIndex,
    sessionLineageEntries,
    sessionLineageFilter,
    selectedSessionLineageEntryRef,
    sessionLineageFilterRef,
    setExpandedSessionLineageQueues,
  });
  const filteredSessionLineageEntries = useMemo(
    () =>
      sessionLineageEntries.filter((entry) =>
        matchesSessionLineageFilter(entry, sessionLineageFilter)
      ),
    [sessionLineageEntries, sessionLineageFilter]
  );
  const sessionLineagePriorityCounts = useMemo(
    () => countTriagePriorities(filteredSessionLineageEntries, sessionLineagePriority),
    [filteredSessionLineageEntries]
  );
  const nextBestSessionLineageEntry = useMemo(
    () =>
      nextBestTriageItem(
        filteredSessionLineageEntries,
        selectedSessionLineageEntry,
        (entry) => entry.key,
        sessionLineagePriority
      ),
    [filteredSessionLineageEntries, selectedSessionLineageEntry]
  );
  const selectedSessionLineagePriority = useMemo(
    () =>
      selectedSessionLineageEntry ? sessionLineagePriority(selectedSessionLineageEntry) : null,
    [selectedSessionLineageEntry]
  );
  const visibleSessionLineageEntries = useMemo(
    () =>
      withSelectedItem(
        filteredSessionLineageEntries,
        selectedSessionLineageEntry,
        6,
        (entry) => entry.key
      ),
    [filteredSessionLineageEntries, selectedSessionLineageEntry]
  );
  const sessionLineageStatusCounts = useMemo(
    () =>
      sessionLineageEntries.reduce<ExecutionPlaneCountMap>((acc, entry) => {
        acc[entry.status] = (acc[entry.status] || 0) + 1;
        return acc;
      }, {}),
    [sessionLineageEntries]
  );
  const sessionLineageDecisionCount = useMemo(
    () =>
      sessionLineageEntries.filter((entry) => entry.approvalId || entry.issueId).length,
    [sessionLineageEntries]
  );
  const sessionLineageAttentionCount = useMemo(
    () =>
      sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "attention")).length,
    [sessionLineageEntries]
  );
  const sessionLineageEventCount = useMemo(
    () => sessionLineageEntries.filter((entry) => entry.eventKey).length,
    [sessionLineageEntries]
  );
  const sessionLineageAgentCount = useMemo(
    () => new Set(sessionLineageEntries.map((entry) => entry.runtimeAgentId).filter(Boolean)).size,
    [sessionLineageEntries]
  );
  const sessionLineageAgentLinkedCount = useMemo(
    () => sessionLineageEntries.filter((entry) => entry.runtimeAgentId).length,
    [sessionLineageEntries]
  );
  const sessionLineageFilterCounts = useMemo<Record<string, number>>(
    () => ({
      all: sessionLineageEntries.length,
      attention: sessionLineageAttentionCount,
      decisions: sessionLineageDecisionCount,
      "agent-linked": sessionLineageAgentLinkedCount,
    }),
    [
      sessionLineageAgentLinkedCount,
      sessionLineageAttentionCount,
      sessionLineageDecisionCount,
      sessionLineageEntries.length,
    ]
  );
  const latestAgentLinkedLineageEntry = useMemo(
    () => sessionLineageEntries.find((entry) => matchesSessionLineageFilter(entry, "agent-linked")) ?? null,
    [sessionLineageEntries]
  );
  const attentionSessionLineageSourceEntries = useMemo(
    () => sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "attention")),
    [sessionLineageEntries]
  );
  const decisionSessionLineageSourceEntries = useMemo(
    () => sessionLineageEntries.filter((entry) => matchesSessionLineageFilter(entry, "decisions")),
    [sessionLineageEntries]
  );
  const attentionOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedLineageQueueKeys.attention,
          snoozedUntil: snoozedLineageQueueUntil.attention,
        },
        lineageQueueNow
      ),
    [dismissedLineageQueueKeys.attention, lineageQueueNow, snoozedLineageQueueUntil.attention]
  );
  const decisionOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedLineageQueueKeys.decisions,
          snoozedUntil: snoozedLineageQueueUntil.decisions,
        },
        lineageQueueNow
      ),
    [dismissedLineageQueueKeys.decisions, lineageQueueNow, snoozedLineageQueueUntil.decisions]
  );
  const attentionSessionLineageEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        attentionSessionLineageSourceEntries,
        (entry) => entry.key,
        attentionOperatorVisibilityState,
        lineageQueueNow
      ),
    [
      attentionOperatorVisibilityState,
      attentionSessionLineageSourceEntries,
      lineageQueueNow,
    ]
  );
  const decisionSessionLineageEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        decisionSessionLineageSourceEntries,
        (entry) => entry.key,
        decisionOperatorVisibilityState,
        lineageQueueNow
      ),
    [
      decisionOperatorVisibilityState,
      decisionSessionLineageSourceEntries,
      lineageQueueNow,
    ]
  );
  const attentionSessionLineageQueue = useMemo(
    () => attentionSessionLineageEntries.slice(0, 3),
    [attentionSessionLineageEntries]
  );
  const decisionSessionLineageQueue = useMemo(
    () => decisionSessionLineageEntries.slice(0, 3),
    [decisionSessionLineageEntries]
  );
  const attentionQueuePosition = useMemo(
    () => sessionLineageQueuePosition(attentionSessionLineageEntries, selectedSessionLineageEntry),
    [attentionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const decisionQueuePosition = useMemo(
    () => sessionLineageQueuePosition(decisionSessionLineageEntries, selectedSessionLineageEntry),
    [decisionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const nextAttentionSessionLineageEntry = useMemo(
    () =>
      nextSessionLineageQueueEntry(
        attentionSessionLineageEntries,
        selectedSessionLineageEntry
      ),
    [attentionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const nextDecisionSessionLineageEntry = useMemo(
    () =>
      nextSessionLineageQueueEntry(
        decisionSessionLineageEntries,
        selectedSessionLineageEntry
      ),
    [decisionSessionLineageEntries, selectedSessionLineageEntry]
  );
  const currentSessionLineageQueue = useMemo<LineageQueueKind | "">(() => {
    if (selectedSessionLineageEntry) {
      if (attentionSessionLineageEntries.some((entry) => entry.key === selectedSessionLineageEntry.key)) {
        return "attention";
      }
      if (decisionSessionLineageEntries.some((entry) => entry.key === selectedSessionLineageEntry.key)) {
        return "decisions";
      }
    }
    if (sessionLineageFilter === "attention" && attentionSessionLineageEntries.length) {
      return "attention";
    }
    if (sessionLineageFilter === "decisions" && decisionSessionLineageEntries.length) {
      return "decisions";
    }
    if (attentionSessionLineageEntries.length) return "attention";
    if (decisionSessionLineageEntries.length) return "decisions";
    return "";
  }, [
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    selectedSessionLineageEntry,
    sessionLineageFilter,
  ]);
  const hiddenAttentionQueueCount = useMemo(
    () => Math.max(attentionSessionLineageSourceEntries.length - attentionSessionLineageEntries.length, 0),
    [attentionSessionLineageEntries.length, attentionSessionLineageSourceEntries.length]
  );
  const hiddenDecisionQueueCount = useMemo(
    () => Math.max(decisionSessionLineageSourceEntries.length - decisionSessionLineageEntries.length, 0),
    [decisionSessionLineageEntries.length, decisionSessionLineageSourceEntries.length]
  );
  const persistedLineageQueueState = useMemo(
    () => ({
      dismissed: {
        attention: attentionOperatorVisibilityState.dismissed,
        decisions: decisionOperatorVisibilityState.dismissed,
      },
      snoozedUntil: {
        attention: attentionOperatorVisibilityState.snoozedUntil,
        decisions: decisionOperatorVisibilityState.snoozedUntil,
      },
    }),
    [attentionOperatorVisibilityState, decisionOperatorVisibilityState]
  );
  const persistedDismissedLineageQueueCount = useMemo(
    () =>
      persistedLineageQueueState.dismissed.attention.length +
      persistedLineageQueueState.dismissed.decisions.length,
    [persistedLineageQueueState]
  );
  const persistedSnoozedLineageQueueCount = useMemo(
    () =>
      Object.keys(persistedLineageQueueState.snoozedUntil.attention).length +
      Object.keys(persistedLineageQueueState.snoozedUntil.decisions).length,
    [persistedLineageQueueState]
  );
  const hasPersistedLineageQueuePreferences = useMemo(
    () =>
      !isPersistedLineageQueueStateEmpty(
        persistedLineageQueueState,
        SESSION_LINEAGE_QUEUE_KEYS
      ),
    [persistedLineageQueueState]
  );
  const selectedSessionLineageTraits = useMemo(() => {
    return sessionLineageTraits(selectedSessionLineageEntry);
  }, [selectedSessionLineageEntry]);
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
    selectedSessionEvent,
    selectedSessionEventKey,
    selectedSessionContextKind,
    selectedRun,
    selectedRunResult,
    setSelectedSessionApprovalId,
    setSelectedSessionIssueId,
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
  const agentScopedRuns = useMemo(() => {
    if (!selectedAgentId) return [] as ExecutionAgentActionRunRecord[];
    return linkedRuns.filter((run) => {
      if (run.runtime_agent_ids.includes(selectedAgentId)) return true;
      if (toStringValue(run.selection.runtime_agent_id) === selectedAgentId) return true;
      return run.results.some((result) => {
        const record = asRecord(result);
        return record ? outcomeRuntimeAgentIds(record).includes(selectedAgentId) : false;
      });
    });
  }, [linkedRuns, selectedAgentId]);
  const agentScopedOutcomes = useMemo(() => {
    if (!selectedAgentId) return [] as AgentScopedOutcome[];
    const outcomes: AgentScopedOutcome[] = [];
    agentScopedRuns.forEach((run) => {
      const defaultToRunScope = run.runtime_agent_ids.length === 1 && run.runtime_agent_ids[0] === selectedAgentId;
      run.results.forEach((rawResult, resultIndex) => {
        const result = asRecord(rawResult);
        if (!result) return;
        const runtimeAgentIds = outcomeRuntimeAgentIds(result);
        if (!runtimeAgentIds.includes(selectedAgentId) && !defaultToRunScope) {
          return;
        }
        outcomes.push({
          run,
          result,
          resultIndex,
          timestamp: run.completed_at || run.updated_at || run.created_at,
          runtimeAgentIds,
        });
      });
    });
    return outcomes.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        right.run.created_at.localeCompare(left.run.created_at) ||
        left.resultIndex - right.resultIndex
    );
  }, [agentScopedRuns, selectedAgentId]);
  const filteredAgentScopedRuns = useMemo(
    () =>
      agentScopedRuns.filter(
        (run) =>
          matchesRunFilter(run, agentActivityFilter) &&
          runMatchesSearch(run, agentActivitySearch)
      ),
    [agentActivityFilter, agentActivitySearch, agentScopedRuns]
  );
  const filteredAgentScopedOutcomes = useMemo(
    () =>
      agentScopedOutcomes.filter(
        (outcome) =>
          matchesAgentOutcomeFilter(outcome, agentActivityFilter) &&
          matchesSearch(
            [
              outcome.run.id,
              outcome.run.actor,
              outcome.run.mode,
              outcome.run.reason,
              outcome.runtimeAgentIds,
              outcome.result,
              describeRunResult(outcome.result),
            ],
            agentActivitySearch
          )
      ),
    [agentActivityFilter, agentActivitySearch, agentScopedOutcomes]
  );
  const agentTimelineEntries = useMemo(() => {
    if (!selectedAgent) return [] as AgentTimelineEntry[];
    const entries: AgentTimelineEntry[] = [];

    selectedAgent.approvals.forEach((approval) => {
      entries.push({
        kind: "approval",
        id: approval.id,
        timestamp:
          approval.applied_at ||
          approval.decided_at ||
          approval.updated_at ||
          approval.created_at,
        status: approval.status,
        title: approval.action || approval.id,
        subtitle: approval.project_name || approval.project_id,
        message: approval.reason || "No approval reason provided.",
        approval,
      });
    });

    selectedAgent.issues.forEach((issue) => {
      entries.push({
        kind: "issue",
        id: issue.id,
        timestamp: issue.resolved_at || issue.updated_at || issue.created_at,
        status: issue.status,
        title: issue.title || issue.root_cause || issue.category || issue.id,
        subtitle: issue.category || issue.severity || issue.project_name || issue.project_id,
        message: issue.description || issue.root_cause || "No issue detail provided.",
        issue,
      });
    });

    selectedAgent.events.forEach((event, index) => {
      entries.push({
        kind: "event",
        id: `${toStringValue(event.event, "event")}:${toStringValue(event.timestamp, String(index))}`,
        timestamp: toStringValue(event.timestamp),
        status: toStringValue(event.status, "unknown"),
        title: toStringValue(event.event, "unknown_event"),
        subtitle: eventFamily(toStringValue(event.event)),
        message: toStringValue(event.message, "No event message"),
        event,
      });
    });

    return entries.sort(
      (left, right) =>
        right.timestamp.localeCompare(left.timestamp) ||
        left.kind.localeCompare(right.kind) ||
        left.id.localeCompare(right.id)
    );
  }, [selectedAgent]);
  const agentTimelineOperatorVisibilityState = useMemo(
    () =>
      sanitizeOperatorVisibilityState(
        {
          dismissed: dismissedAgentTimelineKeys,
          snoozedUntil: snoozedAgentTimelineUntil,
        },
        lineageQueueNow
      ),
    [dismissedAgentTimelineKeys, lineageQueueNow, snoozedAgentTimelineUntil]
  );
  const activeAgentTimelineEntries = useMemo(
    () =>
      visibleEntriesByOperatorVisibilityState(
        agentTimelineEntries,
        agentTimelineEntryKey,
        agentTimelineOperatorVisibilityState,
        lineageQueueNow
      ),
    [agentTimelineEntries, agentTimelineOperatorVisibilityState, lineageQueueNow]
  );
  const filteredAgentTimelineEntries = useMemo(
    () =>
      activeAgentTimelineEntries.filter(
        (entry) =>
          matchesAgentTimelineFilter(entry, agentTimelineFilter) &&
          matchesSearch(
            [
              entry.kind,
              entry.id,
              entry.status,
              entry.title,
              entry.subtitle,
              entry.message,
              entry.approval,
              entry.issue,
              entry.event,
            ],
            agentTimelineSearch
          )
    ),
    [activeAgentTimelineEntries, agentTimelineFilter, agentTimelineSearch]
  );
  const agentTimelineFilterCounts = useMemo<Record<string, number>>(
    () => ({
      all: activeAgentTimelineEntries.length,
      approvals: activeAgentTimelineEntries.filter((entry) => entry.kind === "approval").length,
      issues: activeAgentTimelineEntries.filter((entry) => entry.kind === "issue").length,
      events: activeAgentTimelineEntries.filter((entry) => entry.kind === "event").length,
      attention: activeAgentTimelineEntries.filter((entry) =>
        matchesAgentTimelineFilter(entry, "attention")
      ).length,
    }),
    [activeAgentTimelineEntries]
  );
  const { selectedAgentTimelineEntry } = useControlPlaneAgentTimelineSelection({
    selectedAgentId,
    filteredAgentTimelineEntries,
    selectedAgentTimelineKey,
    setSelectedAgentTimelineKey,
    setExpandedAgentPriorityQueues,
    selectedAgentTimelineEntryRef,
  });
  const visibleAgentTimelineEntries = useMemo(
    () =>
      withSelectedItem(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        6,
        agentTimelineEntryKey
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const latestAgentApprovalEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "approval") ?? null,
    [activeAgentTimelineEntries]
  );
  const latestAgentIssueEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "issue") ?? null,
    [activeAgentTimelineEntries]
  );
  const latestAgentEventEntry = useMemo(
    () => activeAgentTimelineEntries.find((entry) => entry.kind === "event") ?? null,
    [activeAgentTimelineEntries]
  );
  const hiddenAgentTimelineEntryCount = useMemo(
    () => Math.max(agentTimelineEntries.length - activeAgentTimelineEntries.length, 0),
    [activeAgentTimelineEntries.length, agentTimelineEntries.length]
  );
  const persistedAgentTimelineState = useMemo(
    () => agentTimelineOperatorVisibilityState,
    [agentTimelineOperatorVisibilityState]
  );
  const persistedDismissedAgentTimelineCount = useMemo(
    () => persistedAgentTimelineState.dismissed.length,
    [persistedAgentTimelineState]
  );
  const persistedSnoozedAgentTimelineCount = useMemo(
    () => Object.keys(persistedAgentTimelineState.snoozedUntil).length,
    [persistedAgentTimelineState]
  );
  const hasPersistedAgentTimelinePreferences = useMemo(
    () => !isPersistedAgentTimelineStateEmpty(persistedAgentTimelineState),
    [persistedAgentTimelineState]
  );
  const selectedAgentTimelineRunLink = useMemo(
    () =>
      selectedAgentTimelineEntry
        ? resolveAgentTimelineRunLink(selectedAgentTimelineEntry, linkedRuns)
        : null,
    [linkedRuns, selectedAgentTimelineEntry]
  );
  const agentTimelinePriorityCounts = useMemo(
    () => countTriagePriorities(filteredAgentTimelineEntries, agentTimelinePriority),
    [filteredAgentTimelineEntries]
  );
  const nextBestAgentTimelineEntry = useMemo(
    () =>
      nextBestTriageItem(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const selectedAgentTimelinePriority = useMemo(
    () => (selectedAgentTimelineEntry ? agentTimelinePriority(selectedAgentTimelineEntry) : null),
    [selectedAgentTimelineEntry]
  );
  const currentAgentPriorityQueue = useMemo<
    (typeof AGENT_PRIORITY_QUEUE_KEYS)[number] | ""
  >(() => {
    if (selectedAgentTimelinePriority === "critical" || selectedAgentTimelinePriority === "high") {
      return selectedAgentTimelinePriority;
    }
    if (filteredAgentTimelineEntries.some((entry) => agentTimelinePriority(entry) === "critical")) {
      return "critical";
    }
    if (filteredAgentTimelineEntries.some((entry) => agentTimelinePriority(entry) === "high")) {
      return "high";
    }
    return "";
  }, [
    filteredAgentTimelineEntries,
    selectedAgentTimelinePriority,
  ]);
  const criticalAgentTimelineEntries = useMemo(
    () =>
      filteredAgentTimelineEntries.filter(
        (entry) => agentTimelinePriority(entry) === "critical"
      ),
    [filteredAgentTimelineEntries]
  );
  const highAgentTimelineEntries = useMemo(
    () =>
      filteredAgentTimelineEntries.filter((entry) => agentTimelinePriority(entry) === "high"),
    [filteredAgentTimelineEntries]
  );
  const criticalAgentTimelineQueue = useMemo(
    () => criticalAgentTimelineEntries.slice(0, 2),
    [criticalAgentTimelineEntries]
  );
  const highAgentTimelineQueue = useMemo(
    () => highAgentTimelineEntries.slice(0, 2),
    [highAgentTimelineEntries]
  );
  const criticalAgentTimelinePosition = useMemo(
    () =>
      triageQueuePosition(
        criticalAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey
      ),
    [criticalAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const highAgentTimelinePosition = useMemo(
    () =>
      triageQueuePosition(
        highAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey
      ),
    [highAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const nextCriticalAgentTimelineEntry = useMemo(
    () =>
      nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        "critical"
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const nextHighAgentTimelineEntry = useMemo(
    () =>
      nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        selectedAgentTimelineEntry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        "high"
      ),
    [filteredAgentTimelineEntries, selectedAgentTimelineEntry]
  );
  const selectedAgentTimelineEntryKeyValue = selectedAgentTimelineEntry
    ? agentTimelineEntryKey(selectedAgentTimelineEntry)
    : "";
  const inspectAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
      const relatedRunLink = resolveAgentTimelineRunLink(entry, linkedRuns);
      setSelectedAgentTimelineKey(agentTimelineEntryKey(entry));
      syncLinkedSelection({
        runId:
          relatedRunLink?.run.id ||
          toStringValue(entry.event?.agent_action_run_id) ||
          toStringValue(entry.event?.run_id),
        resultIndex: relatedRunLink?.resultIndex,
        approvalId:
          entry.approval?.id ||
          entry.issue?.approval_id ||
          toStringValue(entry.event?.approval_id),
        issueId: entry.issue?.id || toStringValue(entry.event?.issue_id),
        runtimeAgentId: selectedAgent?.runtime_agent_id || selectedAgentId,
        event: entry.event || null,
      });
    },
    [linkedRuns, selectedAgent, selectedAgentId, syncLinkedSelection]
  );
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
  const openSessionQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "session-lineage") return;
      focusSessionLineageEntry(target.entry, target.filter);
    },
    [focusSessionLineageEntry]
  );
  const openAgentQueueAdvanceTarget = useCallback(
    (target: QueueAdvanceTarget | null | undefined) => {
      if (!target || target.kind !== "agent-timeline") return;
      restoreAgentTimelineEntryVisibility(agentTimelineEntryKey(target.entry));
      revealAgentTimelineEntry(target.entry);
      inspectAgentTimelineEntry(target.entry);
    },
    [inspectAgentTimelineEntry, restoreAgentTimelineEntryVisibility, revealAgentTimelineEntry]
  );
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
  const selectedControl = selectedSession?.control ?? null;
  const loading = !controlSummary || !sessionSummary;

  if (loading) {
    return <ControlPlaneLoadingShell health={health} visibleProjects={visibleProjects} />;
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
      focusRuntimeAgent,
      runAgentSuggestedCommand,
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
    applyControlPlan,
    applyRecommendation,
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
  });

  const mainSectionsProps = buildMainSectionsProps({
    notice,
    errorMessage,
    workspaceSectionProps,
    sessionDrilldownSectionProps,
  });

  return (
    <ControlPlaneLayout
      health={health}
      visibleProjects={visibleProjects}
      headerSectionProps={headerSectionProps}
      mainSectionsProps={mainSectionsProps}
    />
  );
}
