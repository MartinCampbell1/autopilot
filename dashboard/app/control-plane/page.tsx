"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ControlPlaneLayout } from "@/components/control-plane-layout";
import { ControlPlaneLoadingShell } from "@/components/control-plane-loading-shell";
import {
  type QueueAdvanceFeedback,
  type QueueAdvanceFocusDelta,
  type QueueAdvanceFocusSummary,
  type QueueAdvanceSignal,
} from "@/components/queue-advance-notice";
import { SelectedOutcomeInspector } from "@/components/selected-outcome-inspector";
import {
  applyExecutionPlaneOrchestratorSessionControlPlan,
  applyExecutionPlaneOrchestratorSessionRecommendation,
  applyExecutionPlaneApproval,
  approveExecutionPlaneApproval,
  executeExecutionPlaneAgentAction,
  fetchAccountsHealth,
  fetchExecutionPlaneAgentDetail,
  fetchExecutionPlaneControlPassSummary,
  fetchExecutionPlaneControlPasses,
  fetchExecutionPlaneOrchestratorSession,
  fetchExecutionPlaneOrchestratorSessionControlProfiles,
  fetchExecutionPlaneOrchestratorSessions,
  fetchExecutionPlaneOrchestratorSessionSummary,
  fetchProjects,
  rejectExecutionPlaneApproval,
  resolveExecutionPlaneIssue,
} from "@/lib/api";
import {
  approvalMatchesSearch,
  asRecord,
  controlPassMatchesSearch,
  describeRunResult,
  eventFamily,
  eventMatchesSearch,
  extractLatestRunIdFromAppliedSteps,
  extractRunId,
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
  buildQueueAdvanceFocusDelta,
  buildScopedStorageKey,
  emptySnoozedVisibilityRecord,
  emptyVisibilityKeysRecord,
  isPersistedAgentTimelineStateEmpty,
  isPersistedLineageQueueStateEmpty,
  persistQueueAdvanceFocusDelta,
  readPersistedQueueAdvanceFocusDelta,
  sanitizeOperatorVisibilityState,
  sanitizePersistedAgentTimelineState,
  sanitizePersistedLineageQueueState,
  type PersistedAgentTimelineState,
  type PersistedLineageQueueState,
  visibleEntriesByOperatorVisibilityState,
} from "@/lib/control-plane-operator-state";
import { buildRuntimeAgentSectionProps } from "@/lib/control-plane-runtime-agent-props";
import { buildSessionDrilldownSectionProps } from "@/lib/control-plane-session-drilldown-props";
import {
  AGENT_PRIORITY_QUEUE_KEYS,
  SESSION_LINEAGE_QUEUE_KEYS,
  type AgentScopedOutcome,
  type AgentTimelineEntry,
  type LinkedSelectionContext,
  type LineageQueueKind,
  type PendingAgentTimelineTarget,
  type QueueAdvanceTarget,
  type SessionContextKind,
  type SessionLineageEntry,
  type TriageInboxFeedback,
  type TriageInboxFeedbackGroup,
  type TriageInboxItem,
} from "@/lib/control-plane-models";
import {
  agentQueueAdvanceTarget,
  agentTimelineEntryKey,
  agentTimelineRowDomId,
  resolveAgentTimelineEntryFromTarget,
  resolveAgentTimelineRunLink,
  resolveRunLinkFromContext,
  resolveSessionEventFromContext,
  sessionContextRowDomId,
  sessionEventKey,
  sessionQueueAdvanceTarget,
  withSelectedItem,
} from "@/lib/control-plane-linking";
import {
  agentTimelineEntryStatusClass,
  agentTimelineFilterClass,
  agentTimelineFilterLabel,
  agentTimelinePriority,
  buildQueueAdvanceFeedback,
  buildQueueAdvanceFocusSummary,
  buildQueueAdvanceNoticeActionProps,
  countTriagePriorities,
  describeAgentQueueAdvanceReason,
  describeSessionQueueAdvanceReason,
  matchesAgentOutcomeFilter,
  matchesAgentTimelineFilter,
  matchesEventFilter,
  matchesRunFilter,
  matchesSessionLineageFilter,
  nextBestTriageItem,
  nextSessionLineageQueueEntry,
  nextTriageEntryByPriority,
  sessionLineageFilterClass,
  sessionLineageFilterLabel,
  sessionLineagePriority,
  sessionLineageQueuePosition,
  sessionLineageTraits,
  triageQueuePosition,
} from "@/lib/control-plane-triage";
import { passStatusClass } from "@/lib/control-plane-ui";
import { useSSE } from "@/lib/sse";
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
  OrchestratorSessionControlRecommendation,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  ProjectSummary,
} from "@/lib/types";

const DEFAULT_CONTROL_ACTOR = "dashboard-control-plane";
const LINEAGE_QUEUE_STORAGE_PREFIX = "control-plane:lineage-queue:";
const AGENT_TIMELINE_STORAGE_PREFIX = "control-plane:agent-timeline:";
const SESSION_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:session-queue-focus:";
const AGENT_QUEUE_FOCUS_STORAGE_PREFIX = "control-plane:agent-queue-focus:";
const TRIAGE_INBOX_FEEDBACK_LIMIT = 5;

function scrollToDomId(id: string): boolean {
  if (!id || typeof document === "undefined") return false;
  const node = document.getElementById(id);
  if (!node) return false;
  node.scrollIntoView({ behavior: "smooth", block: "center" });
  return true;
}

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
  const [pendingAgentPriorityAutoAdvance, setPendingAgentPriorityAutoAdvance] = useState<{
    priority: "critical" | "high";
    previousKey: string;
    previousEntry: AgentTimelineEntry | null;
  } | null>(null);
  const [pendingLineageAutoAdvance, setPendingLineageAutoAdvance] = useState<{
    filter: "attention" | "decisions";
    previousKey: string;
    previousEntry: SessionLineageEntry | null;
    previousFilter: string;
  } | null>(null);
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
  const [hydratedAgentTimelineStorageKey, setHydratedAgentTimelineStorageKey] = useState("");
  const [hydratedLineageQueueSessionId, setHydratedLineageQueueSessionId] = useState("");
  const [hydratedSessionQueueFocusStorageKey, setHydratedSessionQueueFocusStorageKey] =
    useState("");
  const [hydratedAgentQueueFocusStorageKey, setHydratedAgentQueueFocusStorageKey] =
    useState("");
  const selectedSessionLineageEntryRef = useRef<SessionLineageEntry | null>(null);
  const selectedAgentTimelineEntryRef = useRef<AgentTimelineEntry | null>(null);
  const selectedTriageInboxKeyRef = useRef("");
  const sessionLineageFilterRef = useRef("all");

  const loadOverview = useCallback(async () => {
    try {
      const [
        healthData,
        projectData,
        controlPassData,
        controlPassSummaryData,
        sessionData,
        sessionSummaryData,
        profileData,
      ] = await Promise.all([
        fetchAccountsHealth(),
        fetchProjects(false),
        fetchExecutionPlaneControlPasses(),
        fetchExecutionPlaneControlPassSummary(),
        fetchExecutionPlaneOrchestratorSessions(),
        fetchExecutionPlaneOrchestratorSessionSummary(),
        fetchExecutionPlaneOrchestratorSessionControlProfiles(),
      ]);
      setHealth(healthData);
      setProjects((projectData.projects || []) as ProjectSummary[]);
      setControlPasses((controlPassData.control_passes || []) as OrchestratorControlPassRecord[]);
      setControlSummary(controlPassSummaryData);
      setSessions((sessionData.sessions || []) as OrchestratorSessionRecord[]);
      setSessionSummary(sessionSummaryData);
      setControlProfiles((profileData.profiles || []) as OrchestratorSessionControlProfile[]);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load control plane.");
    }
  }, []);

  const loadSessionDetail = useCallback(async (sessionId: string) => {
    const detail = await fetchExecutionPlaneOrchestratorSession(sessionId, { eventLimit: 12 });
    setSelectedSession(detail);
    setSelectedRunId((current) => {
      if (current && detail.runs.some((run) => run.id === current)) {
        return current;
      }
      return detail.runs[0]?.id ?? "";
    });
    setSelectedPassId((current) => {
      if (current && detail.control_passes.some((controlPass) => controlPass.id === current)) {
        return current;
      }
      return detail.control_passes[0]?.id ?? current;
    });
    return detail;
  }, []);

  const loadAgentDetail = useCallback(async (runtimeAgentId: string) => {
    return fetchExecutionPlaneAgentDetail(runtimeAgentId, { eventLimit: 12 });
  }, []);

  useEffect(() => {
    void loadOverview();
    const interval = setInterval(() => {
      void loadOverview();
    }, 15000);
    return () => clearInterval(interval);
  }, [loadOverview]);

  useSSE(
    useCallback(() => {
      void loadOverview();
      if (selectedSessionId) {
        void loadSessionDetail(selectedSessionId).catch(() => {
          // Keep current detail state on transient SSE fetch failures.
        });
      }
    }, [loadOverview, loadSessionDetail, selectedSessionId])
  );

  useEffect(() => {
    if (sessions.length === 0) {
      setSelectedSessionId("");
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSession(null);
      return;
    }
    setSelectedSessionId((current) =>
      sessions.some((session) => session.id === current) ? current : sessions[0].id
    );
  }, [sessions]);
  useEffect(() => {
    const interval = setInterval(() => {
      setLineageQueueNow(Date.now());
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (controlPasses.length === 0) {
      setSelectedPassId("");
      return;
    }
    setSelectedPassId((current) =>
      controlPasses.some((controlPass) => controlPass.id === current)
        ? current
        : controlPasses[0].id
    );
  }, [controlPasses]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSelectedAgentId("");
      setSelectedRunId("");
      setSelectedAgent(null);
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionEventKey("");
      setSelectedSessionContextKind("");
      setEntitySearch("");
      setSelectedSession(null);
      return;
    }

    let cancelled = false;
    setSessionLoading(true);
    fetchExecutionPlaneOrchestratorSession(selectedSessionId, { eventLimit: 12 })
      .then((detail) => {
        if (cancelled) return;
        setSelectedSession(detail);
        setSelectedRunId((current) => {
          if (current && detail.runs.some((run) => run.id === current)) {
            return current;
          }
          return detail.runs[0]?.id ?? "";
        });
        setSelectedPassId((current) => {
          if (current && detail.control_passes.some((controlPass) => controlPass.id === current)) {
            return current;
          }
          return detail.control_passes[0]?.id ?? current;
        });
        setErrorMessage("");
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedSession(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load orchestrator session detail."
        );
      })
      .finally(() => {
        if (!cancelled) setSessionLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  useEffect(() => {
    setEntitySearch("");
    setSelectedSessionApprovalId("");
    setSelectedSessionIssueId("");
    setSelectedSessionEventKey("");
    setSelectedSessionContextKind("");
    setSessionQueueAdvanceFeedback(null);
    setSessionQueueFocusDelta(null);
    setPendingLineageAutoAdvance(null);
    setLineageQueueNow(Date.now());
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) {
      setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setHydratedLineageQueueSessionId("");
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    setHydratedLineageQueueSessionId("");

    if (typeof window === "undefined") {
      setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
      setHydratedLineageQueueSessionId(selectedSessionId);
      return;
    }

    const storageKey = buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedLineageQueueState<LineageQueueKind> | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedLineageQueueState<LineageQueueKind>;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedLineageQueueState(
      parsed,
      now,
      SESSION_LINEAGE_QUEUE_KEYS
    );
    setDismissedLineageQueueKeys(sanitized.dismissed);
    setSnoozedLineageQueueUntil(sanitized.snoozedUntil);
    setHydratedLineageQueueSessionId(selectedSessionId);

    if (isPersistedLineageQueueStateEmpty(sanitized, SESSION_LINEAGE_QUEUE_KEYS)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId || hydratedLineageQueueSessionId !== selectedSessionId) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedLineageQueueState(
      {
        dismissed: dismissedLineageQueueKeys,
        snoozedUntil: snoozedLineageQueueUntil,
      },
      lineageQueueNow,
      SESSION_LINEAGE_QUEUE_KEYS
    );
    const storageKey = buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId);

    if (isPersistedLineageQueueStateEmpty(sanitized, SESSION_LINEAGE_QUEUE_KEYS)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedLineageQueueKeys,
    hydratedLineageQueueSessionId,
    lineageQueueNow,
    selectedSessionId,
    snoozedLineageQueueUntil,
  ]);

  useEffect(() => {
    if (!selectedSessionId) {
      setSessionQueueFocusDelta(null);
      setHydratedSessionQueueFocusStorageKey("");
      return;
    }

    const storageKey = buildScopedStorageKey(
      SESSION_QUEUE_FOCUS_STORAGE_PREFIX,
      selectedSessionId
    );
    setHydratedSessionQueueFocusStorageKey("");

    if (typeof window === "undefined") {
      setHydratedSessionQueueFocusStorageKey(storageKey);
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setSessionQueueFocusDelta(sanitized);
    setHydratedSessionQueueFocusStorageKey(storageKey);
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!selectedSessionId) return;
    const storageKey = buildScopedStorageKey(
      SESSION_QUEUE_FOCUS_STORAGE_PREFIX,
      selectedSessionId
    );
    if (hydratedSessionQueueFocusStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, sessionQueueFocusDelta);
  }, [
    hydratedSessionQueueFocusStorageKey,
    selectedSessionId,
    sessionQueueFocusDelta,
  ]);

  useEffect(() => {
    if (!selectedSession) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }

    const sessionRuns = (selectedSession.runs || []) as ExecutionAgentActionRunRecord[];
    const currentRun = sessionRuns.find((run) => run.id === selectedRunId) ?? sessionRuns[0] ?? null;
    const currentRunResult =
      currentRun?.results[selectedRunResultIndex] ??
      currentRun?.results[0] ??
      null;
    const sessionApprovals = selectedSession.approvals || [];
    const sessionIssues = selectedSession.issues || [];
    const candidateIds = [
      currentRunResult && typeof currentRunResult === "object"
        ? outcomeRuntimeAgentId(currentRunResult as Record<string, unknown>)
        : "",
      ...selectedSession.linked_runtime_agent_ids,
      ...sessionRuns.flatMap((run) => run.runtime_agent_ids || []),
      ...sessionApprovals.flatMap((approval) => approval.runtime_agent_ids || []),
      ...sessionIssues.flatMap((issue) =>
        issue.runtime_agent_ids.length > 0
          ? issue.runtime_agent_ids
          : issue.runtime_agent_id
            ? [issue.runtime_agent_id]
            : []
      ),
    ].filter(Boolean);
    const uniqueIds = [...new Set(candidateIds)];
    if (!uniqueIds.length) {
      setSelectedAgentId("");
      setSelectedAgent(null);
      return;
    }
    setSelectedAgentId((current) => (current && uniqueIds.includes(current) ? current : uniqueIds[0]));
  }, [selectedRunId, selectedRunResultIndex, selectedSession]);

  useEffect(() => {
    if (!selectedAgentId) {
      setSelectedAgent(null);
      return;
    }
    let cancelled = false;
    setAgentLoading(true);
    loadAgentDetail(selectedAgentId)
      .then((detail) => {
        if (cancelled) return;
        setSelectedAgent(detail);
      })
      .catch((error) => {
        if (cancelled) return;
        setSelectedAgent(null);
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load runtime agent detail."
        );
      })
      .finally(() => {
        if (!cancelled) setAgentLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [loadAgentDetail, selectedAgentId]);

  useEffect(() => {
    setSelectedRunResultIndex(0);
  }, [selectedRunId]);

  useEffect(() => {
    setAgentActivityFilter("all");
    setAgentActivitySearch("");
    setAgentTimelineFilter("all");
    setAgentTimelineSearch("");
    setSelectedAgentTimelineKey("");
    setAgentQueueAdvanceFeedback(null);
    setAgentQueueFocusDelta(null);
    setPendingAgentPriorityAutoAdvance(null);
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      setHydratedAgentTimelineStorageKey("");
      return;
    }

    const now = Date.now();
    setLineageQueueNow(now);
    setHydratedAgentTimelineStorageKey("");

    if (typeof window === "undefined") {
      setDismissedAgentTimelineKeys([]);
      setSnoozedAgentTimelineUntil({});
      setHydratedAgentTimelineStorageKey(
        buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId)
      );
      return;
    }

    const storageKey = buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId);
    const raw = window.localStorage.getItem(storageKey);
    let parsed: PersistedAgentTimelineState | null = null;
    if (raw) {
      try {
        parsed = JSON.parse(raw) as PersistedAgentTimelineState;
      } catch {
        parsed = null;
      }
    }

    const sanitized = sanitizePersistedAgentTimelineState(parsed, now);
    setDismissedAgentTimelineKeys(sanitized.dismissed);
    setSnoozedAgentTimelineUntil(sanitized.snoozedUntil);
    setHydratedAgentTimelineStorageKey(storageKey);

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId);
    if (hydratedAgentTimelineStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;

    const sanitized = sanitizePersistedAgentTimelineState(
      {
        dismissed: dismissedAgentTimelineKeys,
        snoozedUntil: snoozedAgentTimelineUntil,
      },
      lineageQueueNow
    );

    if (isPersistedAgentTimelineStateEmpty(sanitized)) {
      window.localStorage.removeItem(storageKey);
      return;
    }
    window.localStorage.setItem(storageKey, JSON.stringify(sanitized));
  }, [
    dismissedAgentTimelineKeys,
    hydratedAgentTimelineStorageKey,
    lineageQueueNow,
    selectedAgentId,
    snoozedAgentTimelineUntil,
  ]);

  useEffect(() => {
    if (!selectedAgentId) {
      setAgentQueueFocusDelta(null);
      setHydratedAgentQueueFocusStorageKey("");
      return;
    }

    const storageKey = buildScopedStorageKey(AGENT_QUEUE_FOCUS_STORAGE_PREFIX, selectedAgentId);
    setHydratedAgentQueueFocusStorageKey("");

    if (typeof window === "undefined") {
      setHydratedAgentQueueFocusStorageKey(storageKey);
      return;
    }
    const sanitized = readPersistedQueueAdvanceFocusDelta(storageKey);
    setAgentQueueFocusDelta(sanitized);
    setHydratedAgentQueueFocusStorageKey(storageKey);
    persistQueueAdvanceFocusDelta(storageKey, sanitized);
  }, [selectedAgentId]);

  useEffect(() => {
    if (!selectedAgentId) return;
    const storageKey = buildScopedStorageKey(AGENT_QUEUE_FOCUS_STORAGE_PREFIX, selectedAgentId);
    if (hydratedAgentQueueFocusStorageKey !== storageKey) {
      return;
    }
    if (typeof window === "undefined") return;
    persistQueueAdvanceFocusDelta(storageKey, agentQueueFocusDelta);
  }, [
    agentQueueFocusDelta,
    hydratedAgentQueueFocusStorageKey,
    selectedAgentId,
  ]);

  useEffect(() => {
    const visibleRuns = ((selectedSession?.runs || []) as ExecutionAgentActionRunRecord[]).filter(
      (run) => matchesRunFilter(run, runFilter) && runMatchesSearch(run, entitySearch)
    );
    if (!visibleRuns.length) {
      return;
    }
    if (!selectedRunId || !visibleRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(visibleRuns[0].id);
    }
  }, [entitySearch, runFilter, selectedRunId, selectedSession]);

  useEffect(() => {
    const currentRuns = (selectedSession?.runs || []) as ExecutionAgentActionRunRecord[];
    const currentRun = currentRuns.find((run) => run.id === selectedRunId) ?? null;
    if (!currentRun) {
      setSelectedRunResultIndex(0);
      return;
    }
    if (selectedRunResultIndex >= currentRun.results.length) {
      setSelectedRunResultIndex(0);
    }
  }, [selectedRunId, selectedRunResultIndex, selectedSession]);

  const refresh = async () => {
    setRefreshing(true);
    try {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
    } finally {
      setRefreshing(false);
    }
  };

  const refreshAfterMutation = useCallback(
    async (sessionId: string) => {
      await loadOverview();
      await loadSessionDetail(sessionId);
    },
    [loadOverview, loadSessionDetail]
  );

  const focusRuntimeAgent = useCallback((runtimeAgentId: string, syncSearch = false) => {
    if (!runtimeAgentId) return;
    setSelectedAgentId(runtimeAgentId);
    if (syncSearch) {
      setEntitySearch(runtimeAgentId);
    }
  }, []);

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

  const refreshAfterAgentMutation = useCallback(
    async (runtimeAgentId: string) => {
      await loadOverview();
      if (selectedSessionId) {
        await loadSessionDetail(selectedSessionId);
      }
      await loadAgentDetail(runtimeAgentId).then((detail) => {
        setSelectedAgent(detail);
      });
    },
    [loadAgentDetail, loadOverview, loadSessionDetail, selectedSessionId]
  );
  const recordTriageInboxFeedback = useCallback(
    (
      itemKey: string,
      itemLabel: string,
      message: string,
      tone: "info" | "success" = "success"
    ) => {
      if (!itemKey || !itemLabel || !message) return;
      const feedback: TriageInboxFeedback = {
        itemKey,
        itemLabel,
        message,
        tone,
        timestamp: new Date().toISOString(),
      };
      setTriageInboxFeedbackHistory((current) => {
        const deduped = current.filter(
          (entry) =>
            !(
              entry.itemKey === feedback.itemKey &&
              entry.itemLabel === feedback.itemLabel &&
              entry.message === feedback.message &&
              entry.tone === feedback.tone
            )
        );
        return [feedback, ...deduped].slice(0, TRIAGE_INBOX_FEEDBACK_LIMIT);
      });
    },
    []
  );

  const runDecisionAction = useCallback(
    async (
      actionKey: string,
      task: () => Promise<string>,
      options?: { autoAdvanceQueue?: boolean }
    ) => {
      if (!selectedSessionId) return;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");
      const currentTriageInboxKey = selectedTriageInboxKeyRef.current;
      const currentLineageEntry = selectedSessionLineageEntryRef.current;
      const currentLineageFilter = sessionLineageFilterRef.current;
      const currentAgentEntry = selectedAgentTimelineEntryRef.current;
      let autoAdvanceFilter: "attention" | "decisions" | "" = "";
      let autoAdvanceAgentPriority: "critical" | "high" | "" = "";
      if (options?.autoAdvanceQueue && currentLineageEntry) {
        if (currentLineageFilter === "attention" || currentLineageFilter === "decisions") {
          autoAdvanceFilter = currentLineageFilter;
        } else if (matchesSessionLineageFilter(currentLineageEntry, "attention")) {
          autoAdvanceFilter = "attention";
        } else if (matchesSessionLineageFilter(currentLineageEntry, "decisions")) {
          autoAdvanceFilter = "decisions";
        }
      }
      if (options?.autoAdvanceQueue && currentAgentEntry) {
        const priority = agentTimelinePriority(currentAgentEntry);
        if (priority === "critical" || priority === "high") {
          autoAdvanceAgentPriority = priority;
        }
      }
      try {
        const message = await task();
        setNotice(message);
        if (currentTriageInboxKey) {
          const itemLabel =
            currentTriageInboxKey === "session-attention"
              ? "Session Attention"
              : currentTriageInboxKey === "session-decisions"
                ? "Session Decision"
                : currentTriageInboxKey === "agent-critical"
                  ? "Agent Critical"
                  : currentTriageInboxKey === "agent-high"
                    ? "Agent High"
                    : "";
          recordTriageInboxFeedback(currentTriageInboxKey, itemLabel, message, "success");
        }
        if (autoAdvanceFilter && currentLineageEntry) {
          setPendingLineageAutoAdvance({
            filter: autoAdvanceFilter,
            previousKey: currentLineageEntry.key,
            previousEntry: currentLineageEntry,
            previousFilter: currentLineageFilter || autoAdvanceFilter,
          });
        }
        if (autoAdvanceAgentPriority && currentAgentEntry) {
          setPendingAgentPriorityAutoAdvance({
            priority: autoAdvanceAgentPriority,
            previousKey: agentTimelineEntryKey(currentAgentEntry),
            previousEntry: currentAgentEntry,
          });
        }
        await refreshAfterMutation(selectedSessionId);
        if (selectedAgentId) {
          const detail = await loadAgentDetail(selectedAgentId);
          setSelectedAgent(detail);
        }
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply linked decision action."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [
      loadAgentDetail,
      recordTriageInboxFeedback,
      refreshAfterMutation,
      selectedAgentId,
      selectedSessionId,
    ]
  );

  const applyRecommendation = async (recommendation: OrchestratorSessionControlRecommendation) => {
    if (!selectedSessionId) return;
    const actionKey = `recommendation:${recommendation.kind}`;
    setBusyActionKey(actionKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await applyExecutionPlaneOrchestratorSessionRecommendation(selectedSessionId, {
        recommendationKind: recommendation.kind,
        actor: DEFAULT_CONTROL_ACTOR,
        reason: `Dashboard applied session recommendation ${recommendation.kind}`,
      });
      const runId = extractRunId(payload.result);
      if (runId) setSelectedRunId(runId);
      setNotice(
        `${payload.recommendation.title || recommendation.kind} finished with status ${payload.status}.`
      );
      await refreshAfterMutation(selectedSessionId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to apply session recommendation."
      );
    } finally {
      setBusyActionKey("");
    }
  };

  const approveApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-approve:${approval.id}`,
      async () => {
        const payload = await approveExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard approved ${approval.action} for session ${selectedSessionId}`,
        });
        return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const rejectApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-reject:${approval.id}`,
      async () => {
        const payload = await rejectExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard rejected ${approval.action} for session ${selectedSessionId}`,
        });
        return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const applyApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(
      `approval-apply:${approval.id}`,
      async () => {
        const payload = await applyExecutionPlaneApproval(approval.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard applied ${approval.action} for session ${selectedSessionId}`,
        });
        return toStringValue(
          payload.command_result.message,
          `Approval ${payload.approval.id} applied successfully.`
        );
      },
      { autoAdvanceQueue: true }
    );
  };

  const resolveIssue = async (issue: ExecutionIssueRecord) => {
    await runDecisionAction(
      `issue-resolve:${issue.id}`,
      async () => {
        const payload = await resolveExecutionPlaneIssue(issue.id, {
          actor: DEFAULT_CONTROL_ACTOR,
          note: `Dashboard resolved issue ${issue.id} for session ${selectedSessionId}`,
        });
        return `Issue ${payload.issue.id} marked ${payload.issue.status}.`;
      },
      { autoAdvanceQueue: true }
    );
  };

  const runAgentSuggestedCommand = async (
    command: Record<string, unknown>,
    mode: "execute_now" | "request_approval"
  ) => {
    if (!selectedAgent) return;
    const commandName = toStringValue(command.command);
    if (!commandName) return;
    const actionKey = `${selectedAgent.runtime_agent_id}:command:${commandName}`;
    const busyKey = `agent-command:${selectedAgent.runtime_agent_id}:${commandName}:${mode}`;
    setBusyActionKey(busyKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await executeExecutionPlaneAgentAction({
        actionKey,
        orchestratorSessionId: selectedSessionId,
        actor: DEFAULT_CONTROL_ACTOR,
        mode,
        reason: `Dashboard ${mode === "execute_now" ? "executed" : "requested approval for"} agent command ${commandName}`,
      });
      const runId = extractRunId(payload);
      if (runId) setSelectedRunId(runId);
      if (payload.approval?.id) {
        setEntitySearch(payload.approval.id);
      }
      setNotice(
        payload.message ||
          toStringValue(payload.command_result?.message) ||
          `Agent command ${commandName} finished with status ${payload.status}.`
      );
      await refreshAfterAgentMutation(selectedAgent.runtime_agent_id);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to execute runtime agent command."
      );
    } finally {
      setBusyActionKey("");
    }
  };

  const applyControlPlan = async (profile: OrchestratorSessionControlProfile) => {
    if (!selectedSessionId) return;
    const actionKey = `profile:${profile.name}`;
    setBusyActionKey(actionKey);
    setNotice("");
    setErrorMessage("");

    try {
      const payload = await applyExecutionPlaneOrchestratorSessionControlPlan(selectedSessionId, {
        profile: profile.name,
        actor: DEFAULT_CONTROL_ACTOR,
        reason: `Dashboard executed ${profile.name} control pass`,
      });
      const runId = extractLatestRunIdFromAppliedSteps(payload.applied);
      if (runId) setSelectedRunId(runId);
      setNotice(
        `Control profile ${payload.profile.name} recorded pass ${payload.control_pass.id} with status ${payload.status}.`
      );
      setSelectedPassId(payload.control_pass.id);
      await refreshAfterMutation(selectedSessionId);
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to apply session control profile."
      );
    } finally {
      setBusyActionKey("");
    }
  };

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
  const selectedSessionLineageEntry = useMemo(() => {
    if (selectedRunId) {
      return (
        sessionLineageEntries.find(
          (entry) => entry.runId === selectedRunId && entry.resultIndex === selectedRunResultIndex
        ) ?? null
      );
    }
    return sessionLineageEntries[0] ?? null;
  }, [selectedRunId, selectedRunResultIndex, sessionLineageEntries]);
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
  useEffect(() => {
    selectedSessionLineageEntryRef.current = selectedSessionLineageEntry;
  }, [selectedSessionLineageEntry]);
  useEffect(() => {
    sessionLineageFilterRef.current = sessionLineageFilter;
  }, [sessionLineageFilter]);
  const syncLinkedSelection = useCallback(
    (context: LinkedSelectionContext) => {
      const approvalId = toStringValue(context.approvalId);
      const issueId = toStringValue(context.issueId);
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

      setSelectedSessionApprovalId(approvalId);
      setSelectedSessionIssueId(issueId);
      setSelectedSessionEventKey(matchedEvent?.key || "");
      setSelectedSessionContextKind(
        context.event ? "event" : issueId ? "issue" : approvalId ? "approval" : matchedEvent ? "event" : ""
      );

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
    [linkedRuns, selectedSession]
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
    [inspectSessionLineageEntry]
  );
  const advanceSessionLineageQueue = useCallback(
    (filter: "attention" | "decisions") => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const previousEntry = selectedSessionLineageEntry;
      const nextEntry = nextSessionLineageQueueEntry(entries, selectedSessionLineageEntry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
        nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
        previousTarget: previousEntry
          ? sessionQueueAdvanceTarget(sessionLineageFilter, previousEntry)
          : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, filter);
    },
    [
      attentionSessionLineageEntries,
      decisionSessionLineageEntries,
      focusSessionLineageEntry,
      sessionLineageFilter,
      selectedSessionLineageEntry,
    ]
  );
  const advanceSessionLineageQueueFromEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry | null) => {
      const entries =
        filter === "attention" ? attentionSessionLineageEntries : decisionSessionLineageEntries;
      const nextEntry = nextSessionLineageQueueEntry(entries, entry);
      if (!nextEntry) return;
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${filter === "attention" ? "Attention" : "Decision"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${filter} item.`,
        nextTarget: sessionQueueAdvanceTarget(filter, nextEntry),
        previousTarget: entry ? sessionQueueAdvanceTarget(filter, entry) : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, filter);
    },
    [attentionSessionLineageEntries, decisionSessionLineageEntries, focusSessionLineageEntry]
  );
  const dismissSessionLineageQueueEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry) => {
      setDismissedLineageQueueKeys((current) => ({
        ...current,
        [filter]: current[filter].includes(entry.key)
          ? current[filter]
          : [...current[filter], entry.key],
      }));
      setLineageQueueNow(Date.now());
      if (selectedSessionLineageEntry?.key === entry.key) {
        setPendingLineageAutoAdvance({
          filter,
          previousKey: entry.key,
          previousEntry: entry,
          previousFilter: filter,
        });
      }
    },
    [selectedSessionLineageEntry]
  );
  const snoozeSessionLineageQueueEntry = useCallback(
    (filter: LineageQueueKind, entry: SessionLineageEntry, minutes = 15) => {
      const snoozedUntil = Date.now() + minutes * 60 * 1000;
      setSnoozedLineageQueueUntil((current) => ({
        ...current,
        [filter]: {
          ...current[filter],
          [entry.key]: snoozedUntil,
        },
      }));
      setLineageQueueNow(Date.now());
      if (selectedSessionLineageEntry?.key === entry.key) {
        setPendingLineageAutoAdvance({
          filter,
          previousKey: entry.key,
          previousEntry: entry,
          previousFilter: filter,
        });
      }
    },
    [selectedSessionLineageEntry]
  );
  const restoreSessionLineageQueue = useCallback((filter: LineageQueueKind) => {
    setDismissedLineageQueueKeys((current) => ({
      ...current,
      [filter]: [],
    }));
    setSnoozedLineageQueueUntil((current) => ({
      ...current,
      [filter]: {},
    }));
    setLineageQueueNow(Date.now());
  }, []);
  const resetSessionLineageQueuePreferences = useCallback(() => {
    setDismissedLineageQueueKeys(emptyVisibilityKeysRecord(SESSION_LINEAGE_QUEUE_KEYS));
    setSnoozedLineageQueueUntil(emptySnoozedVisibilityRecord(SESSION_LINEAGE_QUEUE_KEYS));
    setLineageQueueNow(Date.now());
    setNotice("Session lineage queue state reset.");
    setErrorMessage("");
    if (selectedSessionId && typeof window !== "undefined") {
      window.localStorage.removeItem(
        buildScopedStorageKey(LINEAGE_QUEUE_STORAGE_PREFIX, selectedSessionId)
      );
    }
  }, [selectedSessionId]);
  const toggleSessionLineageQueueExpansion = useCallback((filter: LineageQueueKind) => {
    setExpandedSessionLineageQueues((current) =>
      current.includes(filter)
        ? current.filter((key) => key !== filter)
        : [...current, filter]
    );
  }, []);
  const expandAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, []);
  const collapseAllSessionLineageQueues = useCallback(() => {
    setExpandedSessionLineageQueues([]);
  }, []);
  const openCurrentSessionLineageQueue = useCallback(() => {
    if (!currentSessionLineageQueue) return;
    setExpandedSessionLineageQueues((current) =>
      current.includes(currentSessionLineageQueue)
        ? current
        : [...current, currentSessionLineageQueue]
    );
  }, [currentSessionLineageQueue]);
  const exportSessionLineageQueuePreferences = useCallback(async () => {
    if (!selectedSessionId) return;
    const payload = {
      sessionId: selectedSessionId,
      exportedAt: new Date().toISOString(),
      queueState: persistedLineageQueueState,
    };
    const serialized = JSON.stringify(payload, null, 2);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(serialized);
        setNotice("Copied session lineage queue state.");
        setErrorMessage("");
        return;
      }
      setErrorMessage("Clipboard is unavailable in this environment.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to copy session lineage queue state."
      );
    }
  }, [persistedLineageQueueState, selectedSessionId]);
  const dismissAgentTimelineEntry = useCallback((entry: AgentTimelineEntry) => {
    const entryKey = agentTimelineEntryKey(entry);
    setDismissedAgentTimelineKeys((current) =>
      current.includes(entryKey) ? current : [...current, entryKey]
    );
    setLineageQueueNow(Date.now());
    const currentEntry = selectedAgentTimelineEntryRef.current;
    if (currentEntry && agentTimelineEntryKey(currentEntry) === entryKey) {
      const priority = agentTimelinePriority(entry);
      if (priority === "critical" || priority === "high") {
        setPendingAgentPriorityAutoAdvance({
          priority,
          previousKey: entryKey,
          previousEntry: entry,
        });
      }
    }
  }, []);
  const snoozeAgentTimelineEntry = useCallback((entry: AgentTimelineEntry, minutes = 15) => {
    const entryKey = agentTimelineEntryKey(entry);
    const snoozedUntil = Date.now() + minutes * 60 * 1000;
    setSnoozedAgentTimelineUntil((current) => ({
      ...current,
      [entryKey]: snoozedUntil,
    }));
    setLineageQueueNow(Date.now());
    const currentEntry = selectedAgentTimelineEntryRef.current;
    if (currentEntry && agentTimelineEntryKey(currentEntry) === entryKey) {
      const priority = agentTimelinePriority(entry);
      if (priority === "critical" || priority === "high") {
        setPendingAgentPriorityAutoAdvance({
          priority,
          previousKey: entryKey,
          previousEntry: entry,
        });
      }
    }
  }, []);
  const restoreAgentTimelineHidden = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
  }, []);
  const resetAgentTimelinePreferences = useCallback(() => {
    setDismissedAgentTimelineKeys([]);
    setSnoozedAgentTimelineUntil({});
    setLineageQueueNow(Date.now());
    setNotice("Agent timeline state reset.");
    setErrorMessage("");
    if (selectedAgentId && typeof window !== "undefined") {
      window.localStorage.removeItem(
        buildScopedStorageKey(AGENT_TIMELINE_STORAGE_PREFIX, selectedAgentId)
      );
    }
  }, [selectedAgentId]);
  const exportAgentTimelinePreferences = useCallback(async () => {
    if (!selectedAgentId) return;
    const timelineState = sanitizePersistedAgentTimelineState(
      {
        dismissed: dismissedAgentTimelineKeys,
        snoozedUntil: snoozedAgentTimelineUntil,
      },
      lineageQueueNow
    );
    const payload = {
      runtimeAgentId: selectedAgentId,
      exportedAt: new Date().toISOString(),
      timelineState,
    };
    const serialized = JSON.stringify(payload, null, 2);
    try {
      if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(serialized);
        setNotice("Copied agent timeline state.");
        setErrorMessage("");
        return;
      }
      setErrorMessage("Clipboard is unavailable in this environment.");
    } catch (error) {
      setErrorMessage(
        error instanceof Error ? error.message : "Failed to copy agent timeline state."
      );
    }
  }, [dismissedAgentTimelineKeys, lineageQueueNow, selectedAgentId, snoozedAgentTimelineUntil]);
  useEffect(() => {
    if (!pendingLineageAutoAdvance) return;
    const entries =
      pendingLineageAutoAdvance.filter === "attention"
        ? attentionSessionLineageEntries
        : decisionSessionLineageEntries;
    const currentIndex = entries.findIndex(
      (entry) => entry.key === pendingLineageAutoAdvance.previousKey
    );
    const nextEntry =
      currentIndex === -1 ? (entries[0] ?? null) : (entries[currentIndex + 1] ?? entries[0] ?? null);
    setPendingLineageAutoAdvance(null);
    if (nextEntry) {
      const nextReason = describeSessionQueueAdvanceReason(nextEntry);
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingLineageAutoAdvance.filter === "attention" ? "Attention" : "Decision"} queue auto-advanced`,
        detail: `Moved to "${nextEntry.title}" after the previous queue action completed.`,
        nextTarget: sessionQueueAdvanceTarget(pendingLineageAutoAdvance.filter, nextEntry),
        previousTarget: pendingLineageAutoAdvance.previousEntry
          ? sessionQueueAdvanceTarget(
              pendingLineageAutoAdvance.previousFilter,
              pendingLineageAutoAdvance.previousEntry
            )
          : null,
        reasonDetails: nextReason,
      }));
      focusSessionLineageEntry(nextEntry, pendingLineageAutoAdvance.filter);
    } else {
      setSessionQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingLineageAutoAdvance.filter === "attention" ? "Attention" : "Decision"} queue cleared`,
        detail: `No remaining ${pendingLineageAutoAdvance.filter} items were available after the previous queue action.`,
        previousTarget: pendingLineageAutoAdvance.previousEntry
          ? sessionQueueAdvanceTarget(
              pendingLineageAutoAdvance.previousFilter,
              pendingLineageAutoAdvance.previousEntry
            )
          : null,
      }));
      setSessionLineageFilter(pendingLineageAutoAdvance.filter);
    }
  }, [
    attentionSessionLineageEntries,
    decisionSessionLineageEntries,
    focusSessionLineageEntry,
    pendingLineageAutoAdvance,
  ]);
  useEffect(() => {
    if (!selectedRun || !selectedRunResult) {
      setSelectedSessionApprovalId("");
      setSelectedSessionIssueId("");
      setSelectedSessionEventKey("");
      return;
    }
    const approvalId = toStringValue(asRecord(selectedRunResult.approval)?.id);
    const issueId = toStringValue(asRecord(selectedRunResult.issue)?.id);
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
    const matchedEvent = resolveSessionEventFromContext(selectedSession?.events || [], {
      runId: selectedRun.id,
      approvalId,
      issueId,
      runtimeAgentId,
    });

    setSelectedSessionApprovalId(approvalId);
    setSelectedSessionIssueId(issueId);
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
  }, [selectedRun, selectedRunResult, selectedSession]);
  const openSelectedRunResultInTimeline = useCallback(() => {
    if (!selectedRun || !selectedRunResult) return;
    const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
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
      approvalId: toStringValue(asRecord(selectedRunResult.approval)?.id),
      issueId: toStringValue(asRecord(selectedRunResult.issue)?.id),
    });
  }, [selectedRun, selectedRunResult]);
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
  const sessionQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!sessionQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: sessionLineageFilter,
      total: sessionLineageEntries.length,
      visible: filteredSessionLineageEntries.length,
      labelForFilter: sessionLineageFilterLabel,
      classForFilter: sessionLineageFilterClass,
      noun: "lineage chains",
      scopeLabel: "session",
    });
  }, [
    filteredSessionLineageEntries.length,
    sessionLineageEntries.length,
    sessionLineageFilter,
    sessionQueueAdvanceFeedback,
  ]);
  const agentQueueAdvanceFocusSummary = useMemo<QueueAdvanceFocusSummary | null>(() => {
    if (!agentQueueAdvanceFeedback) return null;
    return buildQueueAdvanceFocusSummary({
      activeFilter: agentTimelineFilter,
      total: activeAgentTimelineEntries.length,
      visible: filteredAgentTimelineEntries.length,
      labelForFilter: agentTimelineFilterLabel,
      classForFilter: agentTimelineFilterClass,
      noun: "active timeline items",
      scopeLabel: "agent",
    });
  }, [
    activeAgentTimelineEntries.length,
    agentQueueAdvanceFeedback,
    agentTimelineFilter,
    filteredAgentTimelineEntries.length,
  ]);
  useEffect(() => {
    if (!filteredAgentTimelineEntries.length) {
      setSelectedAgentTimelineKey("");
      return;
    }
    setSelectedAgentTimelineKey((current) =>
      current && filteredAgentTimelineEntries.some((entry) => agentTimelineEntryKey(entry) === current)
        ? current
        : agentTimelineEntryKey(filteredAgentTimelineEntries[0])
    );
  }, [filteredAgentTimelineEntries]);
  const selectedAgentTimelineEntry = useMemo(
    () =>
      filteredAgentTimelineEntries.find(
        (entry) => agentTimelineEntryKey(entry) === selectedAgentTimelineKey
      ) ?? filteredAgentTimelineEntries[0] ?? null,
    [filteredAgentTimelineEntries, selectedAgentTimelineKey]
  );
  useEffect(() => {
    selectedAgentTimelineEntryRef.current = selectedAgentTimelineEntry;
  }, [selectedAgentTimelineEntry]);
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
  const toggleAgentPriorityQueueExpansion = useCallback(
    (priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number]) => {
      setExpandedAgentPriorityQueues((current) =>
        current.includes(priority)
          ? current.filter((key) => key !== priority)
          : [...current, priority]
      );
    },
    []
  );
  const expandAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, []);
  const collapseAllAgentPriorityQueues = useCallback(() => {
    setExpandedAgentPriorityQueues([]);
  }, []);
  const openCurrentAgentPriorityQueue = useCallback(() => {
    if (!currentAgentPriorityQueue) return;
    setExpandedAgentPriorityQueues((current) =>
      current.includes(currentAgentPriorityQueue)
        ? current
        : [...current, currentAgentPriorityQueue]
    );
  }, [currentAgentPriorityQueue]);
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
  const advanceAgentPriorityQueueFromEntry = useCallback(
    (
      priority: (typeof AGENT_PRIORITY_QUEUE_KEYS)[number],
      entry: AgentTimelineEntry | null
    ) => {
      const nextEntry = nextTriageEntryByPriority(
        filteredAgentTimelineEntries,
        entry,
        agentTimelineEntryKey,
        agentTimelinePriority,
        priority
      );
      if (!nextEntry) return;
      const nextReason = describeAgentQueueAdvanceReason(nextEntry);
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${priority === "critical" ? "Critical" : "High"} queue advanced`,
        detail: `Selected "${nextEntry.title}" as the next ${priority} item.`,
        nextTarget: agentQueueAdvanceTarget(priority, nextEntry),
        previousTarget: entry ? agentQueueAdvanceTarget(priority, entry) : null,
        reasonDetails: nextReason,
      }));
      inspectAgentTimelineEntry(nextEntry);
    },
    [filteredAgentTimelineEntries, inspectAgentTimelineEntry]
  );
  const restoreAgentTimelineEntryVisibility = useCallback((entryKey: string) => {
    if (!entryKey) return;
    setDismissedAgentTimelineKeys((current) => current.filter((key) => key !== entryKey));
    setSnoozedAgentTimelineUntil((current) => {
      if (!(entryKey in current)) return current;
      const next = { ...current };
      delete next[entryKey];
      return next;
    });
    setLineageQueueNow(Date.now());
  }, []);
  const revealAgentTimelineEntry = useCallback(
    (entry: AgentTimelineEntry) => {
      const entryKey = agentTimelineEntryKey(entry);
      setAgentTimelineFilter("all");
      setAgentTimelineSearch("");
      setSelectedAgentTimelineKey(entryKey);
      if (selectedAgentId) {
        setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, entryKey));
      }
    },
    [selectedAgentId]
  );
  const findSessionLineageEntryInSession = useCallback((entry: SessionLineageEntry) => {
    setEntitySearch(entry.runId || entry.issueId || entry.approvalId || entry.title);
    if (entry.runId) {
      setSelectedRunId(entry.runId);
      setSelectedRunResultIndex(entry.resultIndex);
    }
  }, []);
  const revealSessionLineageEntryInTimeline = useCallback(
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
  const findAgentTimelineEntryInSession = useCallback(
    (entry: AgentTimelineEntry) => {
      const relatedRunLink = resolveAgentTimelineRunLink(entry, linkedRuns);
      const approvalId =
        entry.approval?.id ||
        entry.issue?.approval_id ||
        toStringValue(entry.event?.approval_id);
      const issueId = entry.issue?.id || toStringValue(entry.event?.issue_id);
      const eventToken =
        toStringValue(entry.event?.event) ||
        toStringValue(entry.event?.message) ||
        entry.id;

      if (relatedRunLink) {
        setEntitySearch(relatedRunLink.run.id || approvalId || issueId || eventToken);
        setSelectedRunId(relatedRunLink.run.id);
        setSelectedRunResultIndex(relatedRunLink.resultIndex);
        return;
      }

      setEntitySearch(approvalId || issueId || eventToken);
    },
    [linkedRuns]
  );
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
  const applySessionQueueFocus = useCallback(
    (nextFilter: string, entry?: SessionLineageEntry | null) => {
      setSessionQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          sessionLineageFilterLabel(sessionLineageFilter),
          sessionLineageFilterLabel(nextFilter),
          sessionLineageFilterCounts[sessionLineageFilter] ?? sessionLineageEntries.length,
          sessionLineageFilterCounts[nextFilter] ?? sessionLineageEntries.length
        )
      );
      if (entry) {
        focusSessionLineageEntry(entry, nextFilter);
        return;
      }
      setSessionLineageFilter(nextFilter);
    },
    [
      focusSessionLineageEntry,
      sessionLineageEntries.length,
      sessionLineageFilter,
      sessionLineageFilterCounts,
    ]
  );
  const applyAgentQueueFocus = useCallback(
    (nextFilter: string, entry?: AgentTimelineEntry | null) => {
      setAgentQueueFocusDelta(
        buildQueueAdvanceFocusDelta(
          agentTimelineFilterLabel(agentTimelineFilter),
          agentTimelineFilterLabel(nextFilter),
          agentTimelineFilterCounts[agentTimelineFilter] ?? activeAgentTimelineEntries.length,
          agentTimelineFilterCounts[nextFilter] ?? activeAgentTimelineEntries.length
        )
      );
      focusAgentTimeline(nextFilter, entry ? { entry } : undefined);
      if (entry) {
        inspectAgentTimelineEntry(entry);
      }
    },
    [
      activeAgentTimelineEntries.length,
      agentTimelineFilter,
      agentTimelineFilterCounts,
      focusAgentTimeline,
      inspectAgentTimelineEntry,
    ]
  );
  const focusSessionQueueAdvanceSignal = useCallback(
    (signal: QueueAdvanceSignal) => {
      const target = sessionQueueAdvanceFeedback?.nextTarget;
      if (!target || target.kind !== "session-lineage") return;
      applySessionQueueFocus(signal.focusFilter || target.filter, target.entry);
    },
    [applySessionQueueFocus, sessionQueueAdvanceFeedback]
  );
  const focusAgentQueueAdvanceSignal = useCallback(
    (signal: QueueAdvanceSignal) => {
      const target = agentQueueAdvanceFeedback?.nextTarget;
      if (!target || target.kind !== "agent-timeline") return;
      applyAgentQueueFocus(signal.focusFilter || "all", target.entry);
    },
    [agentQueueAdvanceFeedback, applyAgentQueueFocus]
  );
  const sessionQueueAdvanceNoticeActions = useMemo(
    () =>
      buildQueueAdvanceNoticeActionProps({
        feedback: sessionQueueAdvanceFeedback,
        onOpenTarget: openSessionQueueAdvanceTarget,
        onSignalClick: focusSessionQueueAdvanceSignal,
        onResetFocus: () => {
          applySessionQueueFocus(
            "all",
            sessionQueueAdvanceFeedback?.nextTarget?.kind === "session-lineage"
              ? sessionQueueAdvanceFeedback.nextTarget.entry
              : null
          );
        },
        onOpenMatchingQueue: currentSessionLineageQueue
          ? () => {
              openCurrentSessionLineageQueue();
            }
          : undefined,
      }),
    [
      applySessionQueueFocus,
      currentSessionLineageQueue,
      focusSessionQueueAdvanceSignal,
      openCurrentSessionLineageQueue,
      openSessionQueueAdvanceTarget,
      sessionQueueAdvanceFeedback,
    ]
  );
  const agentQueueAdvanceNoticeActions = useMemo(
    () =>
      buildQueueAdvanceNoticeActionProps({
        feedback: agentQueueAdvanceFeedback,
        onOpenTarget: openAgentQueueAdvanceTarget,
        onSignalClick: focusAgentQueueAdvanceSignal,
        onResetFocus: () => {
          applyAgentQueueFocus(
            "all",
            agentQueueAdvanceFeedback?.nextTarget?.kind === "agent-timeline"
              ? agentQueueAdvanceFeedback.nextTarget.entry
              : undefined
          );
        },
        onOpenMatchingQueue: currentAgentPriorityQueue
          ? () => {
              openCurrentAgentPriorityQueue();
            }
          : undefined,
      }),
    [
      agentQueueAdvanceFeedback,
      applyAgentQueueFocus,
      currentAgentPriorityQueue,
      focusAgentQueueAdvanceSignal,
      openAgentQueueAdvanceTarget,
      openCurrentAgentPriorityQueue,
    ]
  );
  const triageInboxItems = useMemo(
    () =>
      [
        nextAttentionSessionLineageEntry
          ? {
              key: "session-attention",
              label: "Session Attention",
              queueDetail: `${attentionSessionLineageEntries.length} queued`,
              title: nextAttentionSessionLineageEntry.title,
              subtitle: `run ${nextAttentionSessionLineageEntry.runId} · outcome ${nextAttentionSessionLineageEntry.resultIndex + 1}`,
              timestamp: nextAttentionSessionLineageEntry.timestamp,
              status: nextAttentionSessionLineageEntry.status,
              statusClassName: passStatusClass(nextAttentionSessionLineageEntry.status),
              priority: sessionLineagePriority(nextAttentionSessionLineageEntry),
              syncedWithSelection:
                selectedSessionLineageEntry?.key === nextAttentionSessionLineageEntry.key,
              onInspect: () => {
                focusSessionLineageEntry(nextAttentionSessionLineageEntry, "attention");
              },
              onSnooze: () => {
                snoozeSessionLineageQueueEntry("attention", nextAttentionSessionLineageEntry);
              },
              onDismiss: () => {
                dismissSessionLineageQueueEntry("attention", nextAttentionSessionLineageEntry);
              },
            }
          : null,
        nextDecisionSessionLineageEntry
          ? {
              key: "session-decisions",
              label: "Session Decision",
              queueDetail: `${decisionSessionLineageEntries.length} queued`,
              title: nextDecisionSessionLineageEntry.title,
              subtitle: `run ${nextDecisionSessionLineageEntry.runId} · outcome ${nextDecisionSessionLineageEntry.resultIndex + 1}`,
              timestamp: nextDecisionSessionLineageEntry.timestamp,
              status: nextDecisionSessionLineageEntry.status,
              statusClassName: passStatusClass(nextDecisionSessionLineageEntry.status),
              priority: sessionLineagePriority(nextDecisionSessionLineageEntry),
              syncedWithSelection:
                selectedSessionLineageEntry?.key === nextDecisionSessionLineageEntry.key,
              onInspect: () => {
                focusSessionLineageEntry(nextDecisionSessionLineageEntry, "decisions");
              },
              onSnooze: () => {
                snoozeSessionLineageQueueEntry("decisions", nextDecisionSessionLineageEntry);
              },
              onDismiss: () => {
                dismissSessionLineageQueueEntry("decisions", nextDecisionSessionLineageEntry);
              },
            }
          : null,
        nextCriticalAgentTimelineEntry
          ? {
              key: "agent-critical",
              label: "Agent Critical",
              queueDetail: `${criticalAgentTimelineEntries.length} queued`,
              title: nextCriticalAgentTimelineEntry.title,
              subtitle: `${nextCriticalAgentTimelineEntry.kind} · ${nextCriticalAgentTimelineEntry.subtitle || "No scope metadata"}`,
              timestamp: nextCriticalAgentTimelineEntry.timestamp,
              status: nextCriticalAgentTimelineEntry.status,
              statusClassName: agentTimelineEntryStatusClass(nextCriticalAgentTimelineEntry),
              priority: agentTimelinePriority(nextCriticalAgentTimelineEntry),
              syncedWithSelection:
                selectedAgentTimelineEntryKeyValue ===
                agentTimelineEntryKey(nextCriticalAgentTimelineEntry),
              onInspect: () => {
                inspectAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
              onSnooze: () => {
                snoozeAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
              onDismiss: () => {
                dismissAgentTimelineEntry(nextCriticalAgentTimelineEntry);
              },
            }
          : null,
        nextHighAgentTimelineEntry
          ? {
              key: "agent-high",
              label: "Agent High",
              queueDetail: `${highAgentTimelineEntries.length} queued`,
              title: nextHighAgentTimelineEntry.title,
              subtitle: `${nextHighAgentTimelineEntry.kind} · ${nextHighAgentTimelineEntry.subtitle || "No scope metadata"}`,
              timestamp: nextHighAgentTimelineEntry.timestamp,
              status: nextHighAgentTimelineEntry.status,
              statusClassName: agentTimelineEntryStatusClass(nextHighAgentTimelineEntry),
              priority: agentTimelinePriority(nextHighAgentTimelineEntry),
              syncedWithSelection:
                selectedAgentTimelineEntryKeyValue ===
                agentTimelineEntryKey(nextHighAgentTimelineEntry),
              onInspect: () => {
                inspectAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
              onSnooze: () => {
                snoozeAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
              onDismiss: () => {
                dismissAgentTimelineEntry(nextHighAgentTimelineEntry);
              },
            }
          : null,
      ].filter(Boolean) as TriageInboxItem[],
    [
      attentionSessionLineageEntries.length,
      criticalAgentTimelineEntries.length,
      decisionSessionLineageEntries.length,
      dismissAgentTimelineEntry,
      dismissSessionLineageQueueEntry,
      focusSessionLineageEntry,
      highAgentTimelineEntries.length,
      inspectAgentTimelineEntry,
      nextAttentionSessionLineageEntry,
      nextCriticalAgentTimelineEntry,
      nextDecisionSessionLineageEntry,
      nextHighAgentTimelineEntry,
      selectedAgentTimelineEntryKeyValue,
      selectedSessionLineageEntry,
      snoozeAgentTimelineEntry,
      snoozeSessionLineageQueueEntry,
    ]
  );
  const triageInboxItemCount = triageInboxItems.length;
  const selectedTriageInboxItem = useMemo(
    () =>
      triageInboxItems.find((item) => item.key === selectedTriageInboxKey) ??
      triageInboxItems[0] ??
      null,
    [triageInboxItems, selectedTriageInboxKey]
  );
  const triageInboxFeedbackCounts = useMemo(
    () => ({
      all: triageInboxFeedbackHistory.length,
      success: triageInboxFeedbackHistory.filter((feedback) => feedback.tone === "success").length,
      info: triageInboxFeedbackHistory.filter((feedback) => feedback.tone === "info").length,
    }),
    [triageInboxFeedbackHistory]
  );
  const visibleTriageInboxFeedbackHistory = useMemo(
    () =>
      triageInboxFeedbackFilter === "all"
        ? triageInboxFeedbackHistory
        : triageInboxFeedbackHistory.filter(
            (feedback) => feedback.tone === triageInboxFeedbackFilter
          ),
    [triageInboxFeedbackFilter, triageInboxFeedbackHistory]
  );
  const triageInboxFeedback = useMemo(
    () => visibleTriageInboxFeedbackHistory[0] ?? null,
    [visibleTriageInboxFeedbackHistory]
  );
  const recentTriageInboxFeedback = useMemo(
    () => visibleTriageInboxFeedbackHistory.slice(1, TRIAGE_INBOX_FEEDBACK_LIMIT),
    [visibleTriageInboxFeedbackHistory]
  );
  const groupedRecentTriageInboxFeedback = useMemo(() => {
    const groups = new Map<string, TriageInboxFeedbackGroup>();
    recentTriageInboxFeedback.forEach((feedback) => {
      const existing = groups.get(feedback.itemKey);
      if (existing) {
        existing.entries.push(feedback);
        return;
      }
      groups.set(feedback.itemKey, {
        itemKey: feedback.itemKey,
        itemLabel: feedback.itemLabel,
        entries: [feedback],
        isActive: triageInboxItems.some((item) => item.key === feedback.itemKey),
      });
    });
    return Array.from(groups.values());
  }, [recentTriageInboxFeedback, triageInboxItems]);
  const currentTriageInboxFeedbackGroup = useMemo(
    () =>
      selectedTriageInboxItem
        ? groupedRecentTriageInboxFeedback.find(
            (group) => group.itemKey === selectedTriageInboxItem.key
          ) ?? null
        : null,
    [groupedRecentTriageInboxFeedback, selectedTriageInboxItem]
  );
  useEffect(() => {
    selectedTriageInboxKeyRef.current = selectedTriageInboxKey;
  }, [selectedTriageInboxKey]);
  useEffect(() => {
    setTriageInboxFeedbackHistory([]);
    setTriageInboxFeedbackFilter("all");
    setExpandedTriageInboxResultGroups([]);
  }, [selectedAgentId, selectedSessionId]);
  useEffect(() => {
    setExpandedSessionLineageQueues([...SESSION_LINEAGE_QUEUE_KEYS]);
  }, [selectedSessionId]);
  useEffect(() => {
    setExpandedAgentPriorityQueues([...AGENT_PRIORITY_QUEUE_KEYS]);
  }, [selectedAgentId]);
  useEffect(() => {
    const availableKeys = groupedRecentTriageInboxFeedback.map((group) => group.itemKey);
    setExpandedTriageInboxResultGroups((current) => {
      const next = current.filter((key) => availableKeys.includes(key));
      if (next.length > 0 || availableKeys.length === 0) return next;
      return [availableKeys[0]];
    });
  }, [groupedRecentTriageInboxFeedback]);
  const syncedTriageInboxItem = useMemo(
    () => triageInboxItems.find((item) => item.syncedWithSelection) ?? null,
    [triageInboxItems]
  );
  const nextTriageInboxCursorKey = useCallback(
    (currentKey: string) => {
      if (!triageInboxItems.length) return "";
      const currentIndex = triageInboxItems.findIndex((item) => item.key === currentKey);
      if (currentIndex === -1) return triageInboxItems[0]?.key || "";
      return triageInboxItems[currentIndex + 1]?.key || triageInboxItems[0]?.key || "";
    },
    [triageInboxItems]
  );
  const advanceTriageInboxCursor = useCallback(() => {
    if (!triageInboxItems.length) return;
    setSelectedTriageInboxKey((current) => {
      const currentIndex = triageInboxItems.findIndex((item) => item.key === current);
      if (currentIndex === -1) return triageInboxItems[0]?.key || "";
      return triageInboxItems[currentIndex + 1]?.key || triageInboxItems[0]?.key || "";
    });
  }, [triageInboxItems]);
  const inspectTriageInboxItem = useCallback((item: TriageInboxItem) => {
    setSelectedTriageInboxKey(item.key);
    item.onInspect();
  }, []);
  const openTriageInboxHistoryGroup = useCallback(
    (itemKey: string) => {
      const inboxItem = triageInboxItems.find((item) => item.key === itemKey);
      if (!inboxItem) return;
      inspectTriageInboxItem(inboxItem);
    },
    [inspectTriageInboxItem, triageInboxItems]
  );
  const inspectAndAdvanceTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      item.onInspect();
    },
    [nextTriageInboxCursorKey]
  );
  const snoozeTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} snoozed for 15m.`, "info");
      item.onSnooze();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback]
  );
  const dismissTriageInboxItem = useCallback(
    (item: TriageInboxItem) => {
      const nextKey = nextTriageInboxCursorKey(item.key);
      setSelectedTriageInboxKey(nextKey || item.key);
      recordTriageInboxFeedback(item.key, item.label, `${item.label} dismissed from inbox.`, "info");
      item.onDismiss();
    },
    [nextTriageInboxCursorKey, recordTriageInboxFeedback]
  );
  const syncTriageInboxCursorToSelection = useCallback(() => {
    if (!syncedTriageInboxItem) return;
    setSelectedTriageInboxKey(syncedTriageInboxItem.key);
  }, [syncedTriageInboxItem]);
  const toggleTriageInboxResultGroup = useCallback((itemKey: string) => {
    if (!itemKey) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(itemKey)
        ? current.filter((key) => key !== itemKey)
        : [...current, itemKey]
    );
  }, []);
  const expandAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups(
      groupedRecentTriageInboxFeedback.map((group) => group.itemKey)
    );
  }, [groupedRecentTriageInboxFeedback]);
  const collapseAllTriageInboxResultGroups = useCallback(() => {
    setExpandedTriageInboxResultGroups([]);
  }, []);
  const openCurrentTriageInboxResultGroup = useCallback(() => {
    if (!currentTriageInboxFeedbackGroup) return;
    setExpandedTriageInboxResultGroups((current) =>
      current.includes(currentTriageInboxFeedbackGroup.itemKey)
        ? current
        : [...current, currentTriageInboxFeedbackGroup.itemKey]
    );
  }, [currentTriageInboxFeedbackGroup]);
  useEffect(() => {
    if (!triageInboxItems.length) {
      setSelectedTriageInboxKey("");
      return;
    }
    setSelectedTriageInboxKey((current) => {
      if (triageInboxItems.some((item) => item.key === current)) return current;
      if (syncedTriageInboxItem) return syncedTriageInboxItem.key;
      return triageInboxItems[0].key;
    });
  }, [syncedTriageInboxItem, triageInboxItems]);
  useEffect(() => {
    if (!pendingAgentPriorityAutoAdvance) return;
    const entries =
      pendingAgentPriorityAutoAdvance.priority === "critical"
        ? criticalAgentTimelineEntries
        : highAgentTimelineEntries;
    const currentIndex = entries.findIndex(
      (entry) => agentTimelineEntryKey(entry) === pendingAgentPriorityAutoAdvance.previousKey
    );
    const nextEntry =
      currentIndex === -1 ? (entries[0] ?? null) : (entries[currentIndex + 1] ?? entries[0] ?? null);
    setPendingAgentPriorityAutoAdvance(null);
    if (nextEntry) {
      const nextReason = describeAgentQueueAdvanceReason(nextEntry);
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingAgentPriorityAutoAdvance.priority === "critical" ? "Critical" : "High"} queue auto-advanced`,
        detail: `Moved to "${nextEntry.title}" after the previous queue action completed.`,
        nextTarget: agentQueueAdvanceTarget(pendingAgentPriorityAutoAdvance.priority, nextEntry),
        previousTarget: pendingAgentPriorityAutoAdvance.previousEntry
          ? agentQueueAdvanceTarget(
              pendingAgentPriorityAutoAdvance.priority,
              pendingAgentPriorityAutoAdvance.previousEntry
            )
          : null,
        reasonDetails: nextReason,
      }));
      inspectAgentTimelineEntry(nextEntry);
    } else {
      setAgentQueueAdvanceFeedback(buildQueueAdvanceFeedback({
        title: `${pendingAgentPriorityAutoAdvance.priority === "critical" ? "Critical" : "High"} queue cleared`,
        detail: `No remaining ${pendingAgentPriorityAutoAdvance.priority} items were available after the previous queue action.`,
        previousTarget: pendingAgentPriorityAutoAdvance.previousEntry
          ? agentQueueAdvanceTarget(
              pendingAgentPriorityAutoAdvance.priority,
              pendingAgentPriorityAutoAdvance.previousEntry
            )
          : null,
      }));
    }
  }, [
    criticalAgentTimelineEntries,
    highAgentTimelineEntries,
    inspectAgentTimelineEntry,
    pendingAgentPriorityAutoAdvance,
  ]);
  const selectedSessionContext = useMemo(() => {
    if (selectedSessionContextKind === "issue" && selectedSessionIssue) {
      return { kind: "issue" as const, issue: selectedSessionIssue };
    }
    if (selectedSessionContextKind === "approval" && selectedSessionApproval) {
      return { kind: "approval" as const, approval: selectedSessionApproval };
    }
    if (selectedSessionContextKind === "event" && selectedSessionEvent) {
      return { kind: "event" as const, event: selectedSessionEvent };
    }
    if (selectedSessionIssue) {
      return { kind: "issue" as const, issue: selectedSessionIssue };
    }
    if (selectedSessionApproval) {
      return { kind: "approval" as const, approval: selectedSessionApproval };
    }
    if (selectedSessionEvent) {
      return { kind: "event" as const, event: selectedSessionEvent };
    }
    return null;
  }, [
    selectedSessionApproval,
    selectedSessionContextKind,
    selectedSessionEvent,
    selectedSessionIssue,
  ]);
  const revealSelectedSessionContextRow = useCallback(() => {
    if (!selectedSessionContext) return;
    setEntitySearch("");
    if (selectedSessionContext.kind === "event") {
      setEventFilter("all");
      setPendingSessionRowDomId(
        sessionContextRowDomId("event", selectedSessionEventKey || sessionEventKey(selectedSessionContext.event))
      );
      return;
    }
    if (selectedSessionContext.kind === "approval") {
      setPendingSessionRowDomId(
        sessionContextRowDomId("approval", selectedSessionContext.approval.id)
      );
      return;
    }
    setPendingSessionRowDomId(sessionContextRowDomId("issue", selectedSessionContext.issue.id));
  }, [selectedSessionContext, selectedSessionEventKey]);
  const revealSelectedSessionContextInAgentTimeline = useCallback(() => {
    if (!selectedSessionContext) return;
    const approvalId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.id
        : selectedSessionContext.kind === "issue"
          ? selectedSessionContext.issue.approval_id
          : toStringValue(selectedSessionContext.event.approval_id);
    const issueId =
      selectedSessionContext.kind === "issue"
        ? selectedSessionContext.issue.id
        : selectedSessionContext.kind === "approval"
          ? selectedSessionContext.approval.issue_id
          : toStringValue(selectedSessionContext.event.issue_id);
    const runtimeAgentId =
      selectedSessionContext.kind === "approval"
        ? selectedSessionContext.approval.runtime_agent_ids[0]
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
      runtimeAgentId,
      runId:
        selectedSessionContext.kind === "event"
          ? toStringValue(selectedSessionContext.event.agent_action_run_id) ||
            toStringValue(selectedSessionContext.event.run_id)
          : "",
      event: selectedSessionContext.kind === "event" ? selectedSessionContext.event : null,
    });
  }, [selectedSessionContext, syncLinkedSelection]);
  useEffect(() => {
    if (!pendingAgentTimelineTarget) return;
    if (!selectedAgentId || pendingAgentTimelineTarget.runtimeAgentId !== selectedAgentId) return;
    if (!selectedAgent) return;

    const matchedEntry = resolveAgentTimelineEntryFromTarget(
      agentTimelineEntries,
      pendingAgentTimelineTarget
    );
    if (matchedEntry) {
      const matchedKey = agentTimelineEntryKey(matchedEntry);
      setSelectedAgentTimelineKey(matchedKey);
      setPendingAgentTimelineRowDomId(agentTimelineRowDomId(selectedAgentId, matchedKey));
      setNotice("");
    } else {
      setNotice("Found runtime agent, but no linked timeline item was available for this outcome.");
    }
    setPendingAgentTimelineTarget(null);
  }, [agentTimelineEntries, pendingAgentTimelineTarget, selectedAgent, selectedAgentId]);
  useEffect(() => {
    if (!pendingSessionRowDomId) return;
    if (scrollToDomId(pendingSessionRowDomId)) {
      setPendingSessionRowDomId("");
    }
  }, [
    entitySearch,
    eventFilter,
    pendingSessionRowDomId,
    visibleSessionApprovals,
    visibleSessionEvents,
    visibleSessionIssues,
  ]);
  useEffect(() => {
    if (!pendingAgentTimelineRowDomId) return;
    if (scrollToDomId(pendingAgentTimelineRowDomId)) {
      setPendingAgentTimelineRowDomId("");
    }
  }, [pendingAgentTimelineRowDomId, selectedAgentId, visibleAgentTimelineEntries]);
  const selectedControl = selectedSession?.control ?? null;
  const loading = !controlSummary || !sessionSummary;

  if (loading) {
    return <ControlPlaneLoadingShell health={health} visibleProjects={visibleProjects} />;
  }

  const workspaceSectionProps = {
    recentControlPasses,
    totalControlPassCount: controlPasses.length,
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
            selectedSessionEvents={selectedSession?.events || []}
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
            onOpenInAgentTimeline={openSelectedRunResultInTimeline}
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
      hasSelectedSession: Boolean(selectedSession),
      sessionEventTotalCount: selectedSession?.events.length || 0,
      sessionLineageEntries,
      linkedRunCount: linkedRuns.length,
      linkedApprovalCount: linkedApprovals.length,
      linkedIssueCount: linkedIssues.length,
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
      onSessionLineageFilterChange: (value: "all" | "attention" | "decisions" | "agent-linked") => {
        setSessionLineageFilter(value);
      },
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
      sessionQueueAdvanceNoticeActions: sessionQueueAdvanceNoticeActions,
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
      onSelectRunOutcome: (runId: string, resultIndex: number) => {
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
      triageInboxFeedbackHistoryCount: triageInboxFeedbackHistory.length,
      triageInboxFeedbackFilter,
      onTriageInboxFeedbackFilterChange: setTriageInboxFeedbackFilter,
      triageInboxFeedbackCounts,
      triageInboxFeedback,
      groupedRecentTriageInboxFeedback,
      recentTriageInboxFeedbackCount: recentTriageInboxFeedback.length,
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
    controlPlaneOverviewSectionsProps: {
      controlSummary,
      recentSessions,
      totalSessionCount: sessions.length,
      selectedSessionId,
      onSelectSession: setSelectedSessionId,
      sessionSummary,
    },
  };

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

  const headerSectionProps = {
    latestControlPassAt: controlSummary.latest_control_pass_at,
    latestSessionAt: sessionSummary.latest_session_at,
    selectedSessionId,
    selectedControlState: selectedControl?.state || null,
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
    filteredSessionHistoryCount: filteredSessionHistory.length,
    totalSessionCount: sessions.length,
    filteredControlPassHistoryCount: filteredControlPassHistory.length,
    totalControlPassCount: controlPasses.length,
  };

  const mainSectionsProps = {
    notice,
    errorMessage,
    workspaceSectionProps,
    sessionDrilldownSectionProps,
  };

  return (
    <ControlPlaneLayout
      health={health}
      visibleProjects={visibleProjects}
      headerSectionProps={headerSectionProps}
      mainSectionsProps={mainSectionsProps}
    />
  );
}
