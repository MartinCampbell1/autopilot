"use client";

import { useRef, useState } from "react";
import type {
  QueueAdvanceFeedback,
  QueueAdvanceFocusDelta,
} from "@/components/queue-advance-notice";
import {
  emptySnoozedVisibilityRecord,
  emptyVisibilityKeysRecord,
} from "@/lib/control-plane-operator-state";
import {
  AGENT_PRIORITY_QUEUE_KEYS,
  SESSION_LINEAGE_QUEUE_KEYS,
  type AgentTimelineEntry,
  type LineageQueueKind,
  type PendingAgentTimelineTarget,
  type QueueAdvanceTarget,
  type SessionContextKind,
  type SessionLineageEntry,
  type TriageInboxFeedback,
} from "@/lib/control-plane-models";
import type {
  AccountHealth,
  ExecutionRuntimeAgentDetail,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
  OrchestratorSessionControlProfile,
  OrchestratorSessionDetail,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  ProjectSummary,
} from "@/lib/types";
import type {
  PendingAgentPriorityAutoAdvance,
  PendingLineageAutoAdvance,
} from "@/lib/use-control-plane-actions";

export type ControlPlaneViewSelection = {
  sessionId?: string | null;
  agentId?: string | null;
  runId?: string | null;
  resultIndex?: number | null;
  passId?: string | null;
  sessionContextKind?: SessionContextKind | null;
  approvalId?: string | null;
  issueId?: string | null;
  eventKey?: string | null;
};

function normalizeSelectionValue(value?: string | null): string {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeResultIndex(value?: number | null): number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? Math.floor(value) : 0;
}

function normalizeSessionContextKind(value?: string | null): SessionContextKind {
  if (value === "approval" || value === "issue" || value === "event") {
    return value;
  }
  return "";
}

export function useControlPlaneViewState(initialSelection?: ControlPlaneViewSelection) {
  const initialSessionId = normalizeSelectionValue(initialSelection?.sessionId);
  const initialAgentId = normalizeSelectionValue(initialSelection?.agentId);
  const initialRunId = normalizeSelectionValue(initialSelection?.runId);
  const initialResultIndex = normalizeResultIndex(initialSelection?.resultIndex);
  const initialPassId = normalizeSelectionValue(initialSelection?.passId);
  const initialSessionContextKind = normalizeSessionContextKind(
    initialSelection?.sessionContextKind
  );
  const initialApprovalId = normalizeSelectionValue(initialSelection?.approvalId);
  const initialIssueId = normalizeSelectionValue(initialSelection?.issueId);
  const initialEventKey = normalizeSelectionValue(initialSelection?.eventKey);
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [controlPasses, setControlPasses] = useState<OrchestratorControlPassRecord[]>([]);
  const [controlSummary, setControlSummary] = useState<OrchestratorControlPassSummary | null>(null);
  const [sessions, setSessions] = useState<OrchestratorSessionRecord[]>([]);
  const [sessionSummary, setSessionSummary] = useState<OrchestratorSessionSummary | null>(null);
  const [controlProfiles, setControlProfiles] = useState<OrchestratorSessionControlProfile[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState(initialSessionId);
  const [selectedAgentId, setSelectedAgentId] = useState(initialAgentId);
  const [selectedRunId, setSelectedRunId] = useState(initialRunId);
  const [selectedRunResultIndex, setSelectedRunResultIndex] = useState(initialResultIndex);
  const [selectedPassId, setSelectedPassId] = useState(initialPassId);
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
  const [selectedSessionApprovalId, setSelectedSessionApprovalId] = useState(initialApprovalId);
  const [selectedSessionIssueId, setSelectedSessionIssueId] = useState(initialIssueId);
  const [selectedSessionEventKey, setSelectedSessionEventKey] = useState(initialEventKey);
  const [selectedSessionContextKind, setSelectedSessionContextKind] =
    useState<SessionContextKind>(initialSessionContextKind);
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

  return {
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
  };
}
