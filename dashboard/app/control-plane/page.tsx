"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  applyExecutionPlaneOrchestratorSessionControlPlan,
  applyExecutionPlaneOrchestratorSessionRecommendation,
  applyExecutionPlaneApproval,
  approveExecutionPlaneApproval,
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

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

const DEFAULT_CONTROL_ACTOR = "dashboard-control-plane";

function formatTimestamp(value?: string | null): string {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return DATE_FORMATTER.format(date);
}

function countEntries(
  value: ExecutionPlaneCountMap | undefined,
  limit = 4
): Array<[string, number]> {
  return Object.entries(value || {})
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, limit);
}

function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function toNullableNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function normalizeSearchQuery(value: string): string {
  return value.trim().toLowerCase();
}

function searchText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.toLowerCase();
  if (typeof value === "number" || typeof value === "boolean") return String(value).toLowerCase();
  if (Array.isArray(value)) return value.map((item) => searchText(item)).join(" ");
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>)
      .map((item) => searchText(item))
      .join(" ");
  }
  return String(value).toLowerCase();
}

function matchesSearch(values: unknown[], query: string): boolean {
  const normalized = normalizeSearchQuery(query);
  if (!normalized) return true;
  return values.some((value) => searchText(value).includes(normalized));
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function toStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => toStringValue(item)).filter(Boolean)
    : [];
}

function extractRunId(value: unknown): string {
  const record = asRecord(value);
  if (!record) return "";
  return toStringValue(asRecord(record.run)?.id);
}

function extractLatestRunIdFromAppliedSteps(value: Array<Record<string, unknown>>): string {
  for (const step of [...value].reverse()) {
    const runId = extractRunId(step.result);
    if (runId) return runId;
  }
  return "";
}

function formatScopeList(values: string[], fallback: string): string {
  return values.length ? values.join(", ") : fallback;
}

function outcomeProjectId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return (
    toStringValue(action?.project_id) ||
    toStringValue(project?.id)
  );
}

function outcomeProjectName(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return (
    toStringValue(action?.project_name) ||
    toStringValue(project?.name) ||
    outcomeProjectId(result)
  );
}

function outcomeStoryId(result: Record<string, unknown>): number | null {
  const action = asRecord(result.action);
  return toNullableNumber(action?.story_id);
}

function outcomeStoryTitle(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.story_title);
}

function outcomeRuntimeAgentId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.runtime_agent_id);
}

function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function eventFamily(eventName: string): string {
  if (!eventName) return "other";
  if (
    eventName.includes("approval") ||
    eventName.includes("issue") ||
    eventName.includes("budget_paused")
  ) {
    return "decisions";
  }
  if (
    eventName.startsWith("execution_plane_orchestrator_session") ||
    eventName.includes("control_pass")
  ) {
    return "control";
  }
  if (
    eventName.includes("agent_action") ||
    eventName.includes("agent_batch") ||
    eventName.includes("action_run")
  ) {
    return "actions";
  }
  return "runtime";
}

function matchesRunFilter(run: ExecutionAgentActionRunRecord, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "execute") return !run.dry_run;
  if (filter === "preview") return run.dry_run;
  if (filter === "attention") {
    return (
      run.status === "error" ||
      run.status === "partial" ||
      run.results.some((result) =>
        ["error", "pending_approval", "not_executable"].includes(toStringValue(result.status))
      )
    );
  }
  return true;
}

function matchesEventFilter(event: Record<string, unknown>, filter: string): boolean {
  if (filter === "all") return true;
  const name = toStringValue(event.event);
  const status = toStringValue(event.status);
  if (filter === "attention") {
    return ["error", "partial", "pending_approval", "failed"].includes(status);
  }
  return eventFamily(name) === filter;
}

function runMatchesSearch(run: ExecutionAgentActionRunRecord, query: string): boolean {
  return matchesSearch(
    [
      run.id,
      run.run_kind,
      run.actor,
      run.mode,
      run.reason,
      run.policy_profile,
      run.status,
      run.project_ids,
      run.initiative_ids,
      run.orchestrators,
      run.runtime_agent_ids,
      run.selection,
      run.summary,
      run.results,
    ],
    query
  );
}

function approvalMatchesSearch(approval: ExecutionApprovalRecord, query: string): boolean {
  return matchesSearch(
    [
      approval.id,
      approval.action,
      approval.status,
      approval.reason,
      approval.project_id,
      approval.project_name,
      approval.issue_id,
      approval.runtime_agent_ids,
      approval.policy_reasons,
      approval.payload,
    ],
    query
  );
}

function issueMatchesSearch(issue: ExecutionIssueRecord, query: string): boolean {
  return matchesSearch(
    [
      issue.id,
      issue.title,
      issue.description,
      issue.root_cause,
      issue.category,
      issue.severity,
      issue.status,
      issue.project_id,
      issue.project_name,
      issue.related_command,
      issue.runtime_agent_id,
      issue.runtime_agent_ids,
      issue.approval_id,
      issue.context,
    ],
    query
  );
}

function eventMatchesSearch(event: Record<string, unknown>, query: string): boolean {
  return matchesSearch(
    [
      event.event,
      event.status,
      event.message,
      event.project_id,
      event.story_id,
      event.orchestrator_session_id,
      event,
    ],
    query
  );
}

function sessionMatchesSearch(session: OrchestratorSessionRecord, query: string): boolean {
  return matchesSearch(
    [
      session.id,
      session.title,
      session.orchestrator,
      session.actor,
      session.status,
      session.reason,
      session.initiative_id,
      session.project_ids,
      session.linked_run_ids,
      session.linked_control_pass_ids,
      session.linked_approval_ids,
      session.linked_issue_ids,
      session.linked_runtime_agent_ids,
      session.context,
    ],
    query
  );
}

function controlPassMatchesSearch(controlPass: OrchestratorControlPassRecord, query: string): boolean {
  return matchesSearch(
    [
      controlPass.id,
      controlPass.orchestrator_session_id,
      controlPass.actor,
      controlPass.reason,
      controlPass.profile,
      controlPass.recommendation_kinds,
      controlPass.project_ids,
      controlPass.initiative_id,
      controlPass.orchestrator,
      controlPass.status,
      controlPass.summary,
      controlPass.control_before,
      controlPass.control_after,
    ],
    query
  );
}

function describeRunResult(result: Record<string, unknown>): {
  title: string;
  subtitle: string;
  message: string;
} {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const approval = asRecord(result.approval);
  const issue = asRecord(result.issue);
  const actionKey = toStringValue(action?.action_key);
  const command = toStringValue(action?.command);
  const kind = toStringValue(action?.kind);
  const actionType = toStringValue(action?.action_type, "operation");
  const title =
    actionKey || command || kind || toStringValue(result.status, "run-result");
  const subtitleParts = [
    actionType,
    toStringValue(result.planned_mode),
    toStringValue(result.status),
  ].filter(Boolean);
  const message =
    toStringValue(result.message) ||
    toStringValue(commandResult?.message) ||
    (approval ? `Approval ${toStringValue(approval.id, "created")}` : "") ||
    (issue ? `Issue ${toStringValue(issue.id, "linked")}` : "") ||
    "No additional result message.";
  return {
    title,
    subtitle: subtitleParts.join(" · "),
    message,
  };
}

function passStatusClass(status: string): string {
  switch (status) {
    case "ok":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "partial":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "error":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "noop":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function sessionStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "completed":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "archived":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function controlStateClass(state: string): string {
  switch (state) {
    case "healthy":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "actionable":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "needs_approval":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "attention_required":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "closed":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function priorityClass(priority: string): string {
  switch (priority) {
    case "high":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "low":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function approvalStatusClass(status: string): string {
  switch (status) {
    case "pending":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "approved":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "rejected":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "applied":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function issueStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "resolved":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function issueSeverityClass(severity: string): string {
  switch (severity) {
    case "high":
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "low":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function recommendationActionLabel(recommendation: OrchestratorSessionControlRecommendation): string {
  const operationType = toStringValue(recommendation.operation.type);
  const operationMode = toStringValue(recommendation.operation.mode);
  if (operationType === "session_action_batch" && operationMode === "preview") return "Preview";
  if (operationType === "inspect_session_approvals") return "Inspect approvals";
  if (operationType === "inspect_session_issues") return "Inspect issues";
  if (operationType === "session_status_update") return "Complete session";
  return "Apply";
}

function FilterChip({
  label,
  active,
  count,
  onClick,
}: {
  label: string;
  active: boolean;
  count?: number;
  onClick: () => void;
}) {
  return (
    <Button
      size="sm"
      variant="outline"
      className={`h-8 rounded-full px-3 text-[11px] ${
        active
          ? "border-[#1a1a1a] bg-[#1a1a1a] text-white hover:bg-[#333]"
          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
      }`}
      onClick={onClick}
    >
      {label}
      {typeof count === "number" ? ` · ${count}` : ""}
    </Button>
  );
}

function BreakdownChips({
  label,
  values,
  emptyText,
}: {
  label: string;
  values: ExecutionPlaneCountMap | undefined;
  emptyText: string;
}) {
  const items = countEntries(values);

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      {items.length === 0 ? (
        <p className="mt-2 text-[13px] text-[#9b9a97]">{emptyText}</p>
      ) : (
        <div className="mt-2 flex flex-wrap gap-2">
          {items.map(([key, value]) => (
            <Badge
              key={`${label}-${key}`}
              variant="outline"
              className="gap-1 rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[12px] font-medium text-[#37352f]"
            >
              <span>{key}</span>
              <span className="text-[#9b9a97]">{value}</span>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryStat({
  eyebrow,
  value,
  detail,
}: {
  eyebrow: string;
  value: string;
  detail: string;
}) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader className="gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">{eyebrow}</p>
        <CardTitle className="text-[28px] font-semibold tracking-[-0.04em] text-[#37352f]">
          {value}
        </CardTitle>
        <CardDescription className="text-[13px] text-[#6b6b6b]">{detail}</CardDescription>
      </CardHeader>
    </Card>
  );
}

function SessionMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">{label}</p>
      <p className="mt-1 text-[16px] font-semibold text-[#37352f]">{value}</p>
      <p className="mt-1 text-[12px] text-[#787774]">{detail}</p>
    </div>
  );
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
  const [historySearch, setHistorySearch] = useState("");
  const [entitySearch, setEntitySearch] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [busyActionKey, setBusyActionKey] = useState("");
  const [notice, setNotice] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

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
  }, [selectedSessionId]);

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

  const runDecisionAction = useCallback(
    async (actionKey: string, task: () => Promise<string>) => {
      if (!selectedSessionId) return;
      setBusyActionKey(actionKey);
      setNotice("");
      setErrorMessage("");
      try {
        const message = await task();
        setNotice(message);
        await refreshAfterMutation(selectedSessionId);
      } catch (error) {
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to apply linked decision action."
        );
      } finally {
        setBusyActionKey("");
      }
    },
    [refreshAfterMutation, selectedSessionId]
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
    await runDecisionAction(`approval-approve:${approval.id}`, async () => {
      const payload = await approveExecutionPlaneApproval(approval.id, {
        actor: DEFAULT_CONTROL_ACTOR,
        note: `Dashboard approved ${approval.action} for session ${selectedSessionId}`,
      });
      return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
    });
  };

  const rejectApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(`approval-reject:${approval.id}`, async () => {
      const payload = await rejectExecutionPlaneApproval(approval.id, {
        actor: DEFAULT_CONTROL_ACTOR,
        note: `Dashboard rejected ${approval.action} for session ${selectedSessionId}`,
      });
      return `Approval ${payload.approval.id} marked ${payload.approval.status}.`;
    });
  };

  const applyApproval = async (approval: ExecutionApprovalRecord) => {
    await runDecisionAction(`approval-apply:${approval.id}`, async () => {
      const payload = await applyExecutionPlaneApproval(approval.id, {
        actor: DEFAULT_CONTROL_ACTOR,
        note: `Dashboard applied ${approval.action} for session ${selectedSessionId}`,
      });
      return toStringValue(
        payload.command_result.message,
        `Approval ${payload.approval.id} applied successfully.`
      );
    });
  };

  const resolveIssue = async (issue: ExecutionIssueRecord) => {
    await runDecisionAction(`issue-resolve:${issue.id}`, async () => {
      const payload = await resolveExecutionPlaneIssue(issue.id, {
        actor: DEFAULT_CONTROL_ACTOR,
        note: `Dashboard resolved issue ${issue.id} for session ${selectedSessionId}`,
      });
      return `Issue ${payload.issue.id} marked ${payload.issue.status}.`;
    });
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
  const selectedRunResult = useMemo(() => {
    if (!selectedRun) return null;
    return selectedRun.results[selectedRunResultIndex] ?? selectedRun.results[0] ?? null;
  }, [selectedRun, selectedRunResultIndex]);
  const selectedControl = selectedSession?.control ?? null;
  const loading = !controlSummary || !sessionSummary;

  if (loading) {
    return (
      <div className="flex min-h-screen bg-[#fafaf9]">
        <AppSidebar health={health} projects={visibleProjects} />
        <main className="flex flex-1 items-center justify-center pl-[260px] text-[14px] text-[#787774]">
          Loading control plane...
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={visibleProjects} />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 border-b border-[#e5e5e3] bg-white px-6 py-4">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">FounderOS Execution Plane</p>
              <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[#37352f]">
                Control Plane
              </h1>
              <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[#6b6b6b]">
                Observe session-level orchestration passes, inspect current execution state, and
                apply FounderOS control recommendations directly from Autopilot.
              </p>
            </div>
            <div className="min-w-[280px] rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <div className="flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Latest control pass</span>
                <span className="font-semibold text-[#37352f]">
                  {formatTimestamp(controlSummary.latest_control_pass_at)}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Latest session</span>
                <span className="font-semibold text-[#37352f]">
                  {formatTimestamp(sessionSummary.latest_session_at)}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Selected session</span>
                <span className="font-mono text-[12px] font-semibold text-[#37352f]">
                  {selectedSessionId || "none"}
                </span>
              </div>
              <div className="mt-3 flex items-center justify-between text-[13px]">
                <span className="text-[#9b9a97]">Control state</span>
                {selectedControl ? (
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControl.state)}`}
                  >
                    {selectedControl.state}
                  </Badge>
                ) : (
                  <span className="text-[#9b9a97]">No session selected</span>
                )}
              </div>
              <Button
                size="sm"
                className="mt-4 h-9 w-full rounded-lg bg-[#1a1a1a] text-[13px] hover:bg-[#333]"
                disabled={refreshing}
                onClick={() => {
                  void refresh();
                }}
              >
                {refreshing ? "Refreshing..." : "Refresh control plane"}
              </Button>
            </div>
          </div>
        </header>

        <div className="space-y-6 px-6 py-6">
          {notice && (
            <div className="rounded-xl border border-[#d6e9dc] bg-[#eef8f1] px-4 py-3 text-[13px] text-[#2b6e3f]">
              {notice}
            </div>
          )}
          {errorMessage && (
            <div className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] px-4 py-3 text-[13px] text-[#93370d]">
              {errorMessage}
            </div>
          )}

          <section className="grid gap-4 xl:grid-cols-4">
            <SummaryStat
              eyebrow="Control Passes"
              value={String(controlSummary.totals.control_passes)}
              detail={`${controlSummary.totals.ok} ok · ${controlSummary.totals.partial} partial · ${controlSummary.totals.error} error`}
            />
            <SummaryStat
              eyebrow="Coverage"
              value={`${controlSummary.totals.sessions} sessions`}
              detail={`${controlSummary.totals.projects} projects touched · ${controlSummary.totals.customized} customized passes`}
            />
            <SummaryStat
              eyebrow="Applied Steps"
              value={String(controlSummary.totals.applied_steps)}
              detail={`${controlSummary.totals.error_steps} error steps across persisted control passes`}
            />
            <SummaryStat
              eyebrow="Session Status"
              value={String(sessionSummary.totals.open)}
              detail={`${sessionSummary.totals.completed} completed · ${sessionSummary.totals.archived} archived`}
            />
          </section>

          <section className="rounded-2xl border border-[#e5e5e3] bg-white p-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                  History Search
                </p>
                <p className="mt-2 text-[13px] text-[#787774]">
                  Search recent sessions and control passes by session id, actor, profile, initiative, project, or linked entity ids.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredSessionHistory.length}/{sessions.length} sessions
                </Badge>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredControlPassHistory.length}/{controlPasses.length} passes
                </Badge>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-3">
              <Input
                value={historySearch}
                onChange={(event) => {
                  setHistorySearch(event.target.value);
                }}
                placeholder="session id, control pass id, actor, project, initiative, approval, issue..."
                className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
              />
              <Button
                size="sm"
                variant="outline"
                className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                disabled={!historySearch.trim()}
                onClick={() => {
                  setHistorySearch("");
                }}
              >
                Clear search
              </Button>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,0.9fr)]">
            <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <CardHeader>
                <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                  Recent Control Passes
                </CardTitle>
                <CardDescription className="text-[13px] text-[#787774]">
                  Latest session-level FounderOS control passes, now selectable for drill-down.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {recentControlPasses.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    {controlPasses.length
                      ? "No orchestrator control passes match the current history search."
                      : "No orchestrator control passes recorded yet."}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {recentControlPasses.map((controlPass) => {
                      const finalState = toStringValue(controlPass.summary.final_state, "unknown");
                      const stoppedReason = toStringValue(controlPass.summary.stopped_reason);
                      const appliedSteps = toNumber(controlPass.summary.applied, controlPass.applied.length);
                      const errorSteps = toNumber(controlPass.summary.errors, controlPass.errors.length);
                      const selected = selectedPassId === controlPass.id;

                      return (
                        <div
                          key={controlPass.id}
                          className={`rounded-2xl border p-4 ${
                            selected
                              ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                              : "border-[#ecebe8] bg-[#fbfbf9]"
                          }`}
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                                  {controlPass.id}
                                </p>
                                <Badge
                                  variant="outline"
                                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(controlPass.status)}`}
                                >
                                  {controlPass.status}
                                </Badge>
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  {controlPass.profile}
                                </Badge>
                              </div>
                              <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                Session{" "}
                                <span className="font-mono text-[#37352f]">
                                  {controlPass.orchestrator_session_id}
                                </span>
                                {" · "}
                                {controlPass.actor || "unknown actor"}
                              </p>
                            </div>
                            <div className="text-right">
                              <p className="text-[12px] text-[#9b9a97]">
                                {formatTimestamp(controlPass.created_at)}
                              </p>
                              <Button
                                size="sm"
                                variant={selected ? "default" : "outline"}
                                className={`mt-2 h-8 rounded-lg text-[12px] ${
                                  selected
                                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                }`}
                                onClick={() => {
                                  setSelectedPassId(controlPass.id);
                                  if (controlPass.orchestrator_session_id) {
                                    setSelectedSessionId(controlPass.orchestrator_session_id);
                                  }
                                }}
                              >
                                {selected ? "Selected" : "Inspect"}
                              </Button>
                            </div>
                          </div>

                          <div className="mt-4 grid gap-3 md:grid-cols-3">
                            <SessionMetric
                              label="Outcome"
                              value={finalState}
                              detail={`${appliedSteps} applied · ${errorSteps} errors`}
                            />
                            <SessionMetric
                              label="Coverage"
                              value={`${controlPass.project_ids.length} project${controlPass.project_ids.length === 1 ? "" : "s"}`}
                              detail={controlPass.initiative_id || "No initiative mapping"}
                            />
                            <SessionMetric
                              label="Reason"
                              value={stoppedReason || controlPass.reason || "No stop reason"}
                              detail={`${controlPass.recommendation_kinds.length} recommendation kind(s)`}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Selected Action Run
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Inspect the latest session execution or preview run, including action outcomes.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedRun ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a linked action run to inspect selection scope and result details.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedRun.id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedRun.status)}`}
                            >
                              {selectedRun.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedRun.run_kind}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedRun.dry_run ? "preview" : "execute"}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            {selectedRun.actor || "unknown actor"}
                            {" · "}
                            {selectedRun.mode || "auto"}
                            {selectedRun.reason ? ` · ${selectedRun.reason}` : ""}
                          </p>
                        </div>
                        <p className="text-right text-[12px] text-[#9b9a97]">
                          {formatTimestamp(selectedRun.created_at)}
                          {selectedRun.completed_at
                            ? ` · completed ${formatTimestamp(selectedRun.completed_at)}`
                            : ""}
                        </p>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Selected"
                          value={String(toNumber(selectedRun.summary.selected_count))}
                          detail={`${toNumber(selectedRun.summary.processed_count, selectedRun.results.length)} processed`}
                        />
                        <SessionMetric
                          label="Scope"
                          value={`${selectedRun.project_ids.length} project${selectedRun.project_ids.length === 1 ? "" : "s"}`}
                          detail={selectedRun.policy_profile || "Custom policy"}
                        />
                        <SessionMetric
                          label="Initiatives"
                          value={String(selectedRun.initiative_ids.length)}
                          detail={formatScopeList(selectedRun.initiative_ids, "No initiative mapping")}
                        />
                        <SessionMetric
                          label="Runtime Agents"
                          value={String(selectedRun.runtime_agent_ids.length)}
                          detail={formatScopeList(selectedRun.runtime_agent_ids, "No agent linkage")}
                        />
                      </div>

                      <BreakdownChips
                        label="Result Statuses"
                        values={(selectedRun.summary.status_counts as ExecutionPlaneCountMap | undefined) || {}}
                        emptyText="No result statuses recorded."
                      />

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Selection Scope
                        </p>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <SessionMetric
                            label="Requested Keys"
                            value={String(toStringArray(selectedRun.selection.requested_action_keys).length)}
                            detail={formatScopeList(
                              toStringArray(selectedRun.selection.requested_action_keys).slice(0, 2),
                              "No explicit action keys"
                            )}
                          />
                          <SessionMetric
                            label="Selected Keys"
                            value={String(toStringArray(selectedRun.selection.selected_action_keys).length)}
                            detail={formatScopeList(
                              toStringArray(selectedRun.selection.selected_action_keys).slice(0, 2),
                              "No selected action keys"
                            )}
                          />
                        </div>
                        {(toStringValue(selectedRun.selection.project_id) ||
                          toStringValue(selectedRun.selection.initiative_id) ||
                          toStringValue(selectedRun.selection.orchestrator) ||
                          toStringValue(selectedRun.selection.runtime_agent_id)) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {toStringValue(selectedRun.selection.project_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                project {toStringValue(selectedRun.selection.project_id)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.initiative_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                initiative {toStringValue(selectedRun.selection.initiative_id)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.orchestrator) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                orchestrator {toStringValue(selectedRun.selection.orchestrator)}
                              </Badge>
                            )}
                            {toStringValue(selectedRun.selection.runtime_agent_id) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                agent {toStringValue(selectedRun.selection.runtime_agent_id)}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Action Outcomes
                        </p>
                        {selectedRun.results.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No action results recorded.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedRun.results.slice(0, 8).map((result, index) => {
                              const details = describeRunResult(result);
                              const approval = asRecord(result.approval);
                              const issue = asRecord(result.issue);
                              const commandResult = asRecord(result.command_result);
                              const selected = selectedRunResultIndex === index;
                              return (
                                <div
                                  key={`${selectedRun.id}-result-${index}`}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="text-[13px] font-semibold text-[#37352f]">{details.title}</p>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(result.status, "unknown"))}`}
                                      >
                                        {toStringValue(result.status, "unknown")}
                                      </Badge>
                                      <Button
                                        size="sm"
                                        variant={selected ? "default" : "outline"}
                                        className={`h-7 rounded-lg px-2 text-[11px] ${
                                          selected
                                            ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                            : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                        }`}
                                        onClick={() => {
                                          setSelectedRunResultIndex(index);
                                        }}
                                      >
                                        {selected ? "Selected" : "Inspect"}
                                      </Button>
                                    </div>
                                  </div>
                                  <p className="mt-2 text-[12px] text-[#787774]">{details.subtitle}</p>
                                  <p className="mt-2 text-[12px] text-[#6b6b6b]">{details.message}</p>
                                  {(approval || issue || commandResult) && (
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {approval && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                        >
                                          approval {toStringValue(approval.id, "created")}
                                        </Badge>
                                      )}
                                      {issue && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                        >
                                          issue {toStringValue(issue.id, "linked")}
                                        </Badge>
                                      )}
                                      {commandResult && (
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          command {toStringValue(commandResult.status, "ok")}
                                        </Badge>
                                      )}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      {selectedRunResult && (
                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          {(() => {
                            const actionPayload = asRecord(selectedRunResult.action);
                            const commandResultPayload = asRecord(selectedRunResult.command_result);
                            const projectId = outcomeProjectId(selectedRunResult);
                            const projectName = outcomeProjectName(selectedRunResult);
                            const storyId = outcomeStoryId(selectedRunResult);
                            const storyTitle = outcomeStoryTitle(selectedRunResult);
                            const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
                            const commandName = toStringValue(
                              actionPayload?.command,
                              toStringValue(commandResultPayload?.command)
                            );
                            const workspaceHref =
                              projectId && storyId
                                ? `/projects/${projectId}?storyId=${storyId}`
                                : projectId
                                  ? `/projects/${projectId}`
                                  : "";
                            return (
                              <>
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Selected Outcome
                            </p>
                            <div className="flex flex-wrap items-center gap-2">
                              {runtimeAgentId && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    focusRuntimeAgent(runtimeAgentId, true);
                                  }}
                                >
                                  Find agent
                                </Button>
                              )}
                              {toStringValue(asRecord(selectedRunResult.approval)?.id) && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    setEntitySearch(toStringValue(asRecord(selectedRunResult.approval)?.id));
                                  }}
                                >
                                  Find approval
                                </Button>
                              )}
                              {toStringValue(asRecord(selectedRunResult.issue)?.id) && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  onClick={() => {
                                    setEntitySearch(toStringValue(asRecord(selectedRunResult.issue)?.id));
                                  }}
                                >
                                  Find issue
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
                              <Badge
                                variant="outline"
                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(selectedRunResult.status, "unknown"))}`}
                              >
                                {toStringValue(selectedRunResult.status, "unknown")}
                              </Badge>
                            </div>
                          </div>

                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <SessionMetric
                              label="Action"
                              value={toStringValue(
                                asRecord(selectedRunResult.action)?.action_key,
                                toStringValue(asRecord(selectedRunResult.action)?.command, "unknown")
                              )}
                              detail={toStringValue(
                                asRecord(selectedRunResult.action)?.action_type,
                                "No action type"
                              )}
                            />
                            <SessionMetric
                              label="Mode"
                              value={toStringValue(
                                selectedRunResult.planned_mode,
                                toStringValue(selectedRun.mode, "auto")
                              )}
                              detail={toStringValue(
                                asRecord(selectedRunResult.command_result)?.status,
                                "No command result"
                              )}
                            />
                          </div>

                          <div className="mt-4 grid gap-3 sm:grid-cols-2">
                            <SessionMetric
                              label="Project"
                              value={projectName || "Unknown project"}
                              detail={projectId || "No project id in payload"}
                            />
                            <SessionMetric
                              label="Story"
                              value={storyTitle || (storyId ? `Story ${storyId}` : "No story context")}
                              detail={storyId ? `story_id ${storyId}` : "Outcome is not story-scoped"}
                            />
                            <SessionMetric
                              label="Command"
                              value={commandName || "No command recorded"}
                              detail={toStringValue(
                                commandResultPayload?.status,
                                toStringValue(selectedRunResult.planned_mode, "No command status")
                              )}
                            />
                            <SessionMetric
                              label="Runtime Agent"
                              value={runtimeAgentId || "No agent linkage"}
                              detail={toStringValue(actionPayload?.role, "No execution role")}
                            />
                          </div>

                          {(projectId || storyId || runtimeAgentId) && (
                            <div className="mt-4 flex flex-wrap gap-2">
                              {projectId && (
                                <Badge
                                  variant="outline"
                                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
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
                                  className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                >
                                  agent {runtimeAgentId}
                                </Badge>
                              )}
                            </div>
                          )}

                          <p className="mt-4 text-[13px] leading-relaxed text-[#6b6b6b]">
                            {toStringValue(
                              selectedRunResult.message,
                              toStringValue(
                                asRecord(selectedRunResult.command_result)?.message,
                                "No additional outcome message."
                              )
                            )}
                          </p>

                          <div className="mt-4 space-y-3">
                            <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                Action Payload
                              </p>
                              <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
                                {formatJson(asRecord(selectedRunResult.action) || selectedRunResult)}
                              </pre>
                            </div>

                            {asRecord(selectedRunResult.command_result) && (
                              <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                                  Command Result Payload
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
                                  {formatJson(asRecord(selectedRunResult.command_result))}
                                </pre>
                              </div>
                            )}

                            {asRecord(selectedRunResult.approval) && (
                              <div className="rounded-xl border border-[#d3e5ef] bg-[#eef7fb] p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#2a6690]">
                                  Linked Approval
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#2a6690]">
                                  {formatJson(asRecord(selectedRunResult.approval))}
                                </pre>
                              </div>
                            )}

                            {asRecord(selectedRunResult.issue) && (
                              <div className="rounded-xl border border-[#f4e0c4] bg-[#fff6e8] p-3">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
                                  Linked Issue
                                </p>
                                <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#9a6700]">
                                  {formatJson(asRecord(selectedRunResult.issue))}
                                </pre>
                              </div>
                            )}
                          </div>
                              </>
                            );
                          })()}
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Runtime Agent
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Agent-centric control view for the currently selected runtime agent.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedAgentId ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a linked runtime agent to inspect its current state and history.
                    </div>
                  ) : agentLoading || !selectedAgent ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Loading runtime agent detail...
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedAgent.runtime_agent_id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedAgent.status)}`}
                            >
                              {selectedAgent.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedAgent.attention.state)}`}
                            >
                              {selectedAgent.attention.state}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedAgent.role}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            {selectedAgent.project_name || selectedAgent.project_id}
                            {" · "}
                            {selectedAgent.story_title || `Story ${selectedAgent.story_id || "unknown"}`}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={
                              selectedAgent.story_id
                                ? `/projects/${selectedAgent.project_id}?storyId=${selectedAgent.story_id}`
                                : `/projects/${selectedAgent.project_id}`
                            }
                            className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                          >
                            Open workspace
                          </Link>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                            onClick={() => {
                              focusRuntimeAgent(selectedAgent.runtime_agent_id, true);
                            }}
                          >
                            Filter session
                          </Button>
                        </div>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Open Issues"
                          value={String(selectedAgent.history.open_issue_count)}
                          detail={`${selectedAgent.history.issue_count} total issues`}
                        />
                        <SessionMetric
                          label="Pending Approvals"
                          value={String(selectedAgent.history.pending_approval_count)}
                          detail={`${selectedAgent.history.approval_count} total approvals`}
                        />
                        <SessionMetric
                          label="Events"
                          value={String(selectedAgent.history.event_count)}
                          detail={formatTimestamp(selectedAgent.history.last_event_at)}
                        />
                        <SessionMetric
                          label="Budget"
                          value={
                            selectedAgent.budget.tracked
                              ? `${toNumber(selectedAgent.budget.remaining, 0)} left`
                              : "Untracked"
                          }
                          detail={
                            selectedAgent.budget.tracked
                              ? `${selectedAgent.budget.used ?? 0}/${selectedAgent.budget.limit ?? 0} ${selectedAgent.budget.metric || ""}`.trim()
                              : "No tracked budget metric"
                          }
                        />
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Attention
                        </p>
                        <p className="mt-3 text-[13px] leading-relaxed text-[#6b6b6b]">
                          {selectedAgent.attention.recommended_action}
                        </p>
                        {selectedAgent.attention.reasons.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {selectedAgent.attention.reasons.map((reason) => (
                              <Badge
                                key={`${selectedAgent.runtime_agent_id}-${reason}`}
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                {reason}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Agent Recommendations
                        </p>
                        {selectedAgent.recommendations.length === 0 && selectedAgent.suggested_commands.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No current agent recommendations.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedAgent.recommendations.slice(0, 3).map((recommendation, index) => (
                              <div
                                key={`${selectedAgent.runtime_agent_id}-rec-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(recommendation.title, toStringValue(recommendation.kind, "recommendation"))}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(recommendation.priority, "medium"))}`}
                                  >
                                    {toStringValue(recommendation.priority, "medium")}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                  {toStringValue(recommendation.reason, "No reason provided")}
                                </p>
                              </div>
                            ))}
                            {selectedAgent.suggested_commands.slice(0, 2).map((command, index) => (
                              <div
                                key={`${selectedAgent.runtime_agent_id}-cmd-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(command.title, toStringValue(command.command, "command"))}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(command.priority, "medium"))}`}
                                  >
                                    {toStringValue(command.priority, "medium")}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                  {toStringValue(command.reason, "No reason provided")}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Agent Issues
                          </p>
                          {selectedAgent.issues.length === 0 ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">No agent-linked issues.</p>
                          ) : (
                            <div className="mt-3 space-y-3">
                              {selectedAgent.issues.slice(0, 3).map((issue) => (
                                <div
                                  key={`${selectedAgent.runtime_agent_id}-issue-${issue.id}`}
                                  className="rounded-xl border border-[#ecebe8] bg-white p-3"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="font-mono text-[11px] text-[#37352f]">{issue.id}</p>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                      onClick={() => {
                                        setEntitySearch(issue.id);
                                      }}
                                    >
                                      Find in session
                                    </Button>
                                  </div>
                                  <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                    {issue.title || issue.root_cause || issue.category}
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Agent Events
                          </p>
                          {selectedAgent.events.length === 0 ? (
                            <p className="mt-3 text-[13px] text-[#9b9a97]">No agent-linked events.</p>
                          ) : (
                            <div className="mt-3 space-y-3">
                              {selectedAgent.events.slice(-3).reverse().map((event) => (
                                <div
                                  key={`${selectedAgent.runtime_agent_id}-${toStringValue(event.event)}-${toStringValue(event.timestamp)}`}
                                  className="rounded-xl border border-[#ecebe8] bg-white p-3"
                                >
                                  <div className="flex flex-wrap items-center justify-between gap-2">
                                    <p className="font-mono text-[11px] text-[#37352f]">
                                      {toStringValue(event.event, "unknown_event")}
                                    </p>
                                    <Badge
                                      variant="outline"
                                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(toStringValue(event.status, "unknown"))}`}
                                    >
                                      {toStringValue(event.status, "unknown")}
                                    </Badge>
                                  </div>
                                  <p className="mt-2 text-[12px] text-[#6b6b6b]">
                                    {toStringValue(event.message, "No event message")}
                                  </p>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Control Mix
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Top profile, final-state, and ownership slices from persisted orchestration passes.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <BreakdownChips
                    label="Profiles"
                    values={controlSummary.by_profile}
                    emptyText="No profiles recorded."
                  />
                  <BreakdownChips
                    label="Final States"
                    values={controlSummary.by_final_state}
                    emptyText="No final states recorded."
                  />
                  <BreakdownChips
                    label="Orchestrators"
                    values={controlSummary.by_orchestrator}
                    emptyText="No orchestrator labels recorded."
                  />
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Recent Sessions
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    External FounderOS orchestration sessions, now selectable for direct control.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {recentSessions.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-6 text-[13px] text-[#9b9a97]">
                      {sessions.length
                        ? "No orchestrator sessions match the current history search."
                        : "No orchestrator sessions recorded yet."}
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentSessions.map((session) => {
                        const selected = selectedSessionId === session.id;

                        return (
                          <div
                            key={session.id}
                            className={`rounded-2xl border p-4 ${
                              selected
                                ? "border-[#d3e5ef] bg-[#f7fbfd] shadow-[0_1px_2px_rgba(42,102,144,0.08)]"
                                : "border-[#ecebe8] bg-[#fbfbf9]"
                            }`}
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="flex flex-wrap items-center gap-2">
                                  <p className="text-[14px] font-semibold text-[#37352f]">
                                    {session.title || session.id}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(session.status)}`}
                                  >
                                    {session.status}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#787774]">
                                  {session.orchestrator || "unknown orchestrator"}
                                  {" · "}
                                  {session.actor || "unknown actor"}
                                </p>
                              </div>
                              <div className="text-right">
                                <p className="font-mono text-[11px] text-[#9b9a97]">{session.id}</p>
                                <Button
                                  size="sm"
                                  variant={selected ? "default" : "outline"}
                                  className={`mt-2 h-8 rounded-lg text-[12px] ${
                                    selected
                                      ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                      : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                  }`}
                                  onClick={() => {
                                    setSelectedSessionId(session.id);
                                  }}
                                >
                                  {selected ? "Selected" : "Open control"}
                                </Button>
                              </div>
                            </div>

                            <div className="mt-3 grid gap-3 sm:grid-cols-2">
                              <SessionMetric
                                label="Scope"
                                value={`${session.project_ids.length} project${session.project_ids.length === 1 ? "" : "s"}`}
                                detail={session.initiative_id || "No initiative mapping"}
                              />
                              <SessionMetric
                                label="Linked Objects"
                                value={`${session.linked_control_pass_ids.length} passes`}
                                detail={`${session.linked_run_ids.length} runs · ${session.linked_issue_ids.length} issues`}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Session Overview
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Aggregate session lifecycle and actor coverage for the external orchestrator layer.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <BreakdownChips
                    label="Session Status"
                    values={sessionSummary.by_status}
                    emptyText="No session statuses recorded."
                  />
                  <BreakdownChips
                    label="Actors"
                    values={sessionSummary.by_actor}
                    emptyText="No actors recorded."
                  />
                  <BreakdownChips
                    label="Orchestrators"
                    values={sessionSummary.by_orchestrator}
                    emptyText="No orchestrators recorded."
                  />
                </CardContent>
              </Card>
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.95fr)]">
            <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
              <CardHeader>
                <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                  Session Drill-Down
                </CardTitle>
                <CardDescription className="text-[13px] text-[#787774]">
                  Inspect the selected session, apply direct recommendations, or run a session-level
                  control pass profile from this panel.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {!selectedSessionId ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    Select a recent session or control pass to inspect live control state.
                  </div>
                ) : sessionLoading || !selectedSession ? (
                  <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                    Loading session detail...
                  </div>
                ) : (
                  <div className="space-y-5">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-[#37352f]">
                            {selectedSession.title || selectedSession.id}
                          </h2>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(selectedSession.status)}`}
                          >
                            {selectedSession.status}
                          </Badge>
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControl?.state || "unknown")}`}
                          >
                            {selectedControl?.state || "unknown"}
                          </Badge>
                        </div>
                        <p className="mt-2 font-mono text-[12px] text-[#9b9a97]">{selectedSession.id}</p>
                        <p className="mt-2 text-[14px] text-[#6b6b6b]">
                          {selectedSession.orchestrator || "unknown orchestrator"}
                          {" · "}
                          {selectedSession.actor || "unknown actor"}
                          {selectedSession.reason ? ` · ${selectedSession.reason}` : ""}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {selectedSession.project_ids.map((projectId) => (
                          <Link
                            key={`${selectedSession.id}-${projectId}`}
                            href={`/projects/${projectId}`}
                            className="inline-flex h-8 items-center rounded-full border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                          >
                            {projectId}
                          </Link>
                        ))}
                      </div>
                    </div>

                    <div className="grid gap-3 md:grid-cols-4">
                      <SessionMetric
                        label="Pending Approvals"
                        value={String(selectedSession.summary.pending_approval_count)}
                        detail={`${selectedSession.summary.approval_count} linked approvals`}
                      />
                      <SessionMetric
                        label="Open Issues"
                        value={String(selectedSession.summary.open_issue_count)}
                        detail={`${selectedSession.summary.issue_count} linked issues`}
                      />
                      <SessionMetric
                        label="Safe Actions"
                        value={String(selectedControl?.counts.safe_actions || 0)}
                        detail={`${selectedControl?.counts.approval_required_actions || 0} approval-gated`}
                      />
                      <SessionMetric
                        label="Control Passes"
                        value={String(selectedSession.summary.control_pass_count)}
                        detail={`${selectedSession.summary.run_count} linked runs`}
                      />
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Linked Runtime Agents
                        </p>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {linkedAgentIds.length}
                        </Badge>
                      </div>
                      {!linkedAgentIds.length ? (
                        <p className="mt-3 text-[13px] text-[#9b9a97]">No linked runtime agents in this session.</p>
                      ) : (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {linkedAgentIds.slice(0, 12).map((runtimeAgentId) => (
                            <Button
                              key={`${selectedSession.id}-${runtimeAgentId}`}
                              size="sm"
                              variant={selectedAgentId === runtimeAgentId ? "default" : "outline"}
                              className={`h-8 rounded-full px-3 text-[11px] ${
                                selectedAgentId === runtimeAgentId
                                  ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                  : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                              }`}
                              onClick={() => {
                                focusRuntimeAgent(runtimeAgentId, true);
                              }}
                            >
                              {runtimeAgentId}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Entity Search
                          </p>
                          <p className="mt-2 text-[13px] text-[#787774]">
                            Filter runs, events, approvals, and issues by id, runtime agent, command, story, or reason.
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredRuns.length}/{linkedRuns.length} runs
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredEvents.length}/{selectedSession.events.length} events
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredApprovals.length}/{linkedApprovals.length} approvals
                          </Badge>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredIssues.length}/{linkedIssues.length} issues
                          </Badge>
                        </div>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-3">
                        <Input
                          value={entitySearch}
                          onChange={(event) => {
                            setEntitySearch(event.target.value);
                          }}
                          placeholder="approval id, issue id, runtime agent, action key, command, story..."
                          className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                          disabled={!entitySearch.trim()}
                          onClick={() => {
                            setEntitySearch("");
                          }}
                        >
                          Clear search
                        </Button>
                      </div>
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                        Control Pass Profiles
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {sortedProfiles.map((profile) => {
                          const busy = busyActionKey === `profile:${profile.name}`;
                          return (
                            <Button
                              key={profile.name}
                              size="sm"
                              variant={profile.default ? "default" : "outline"}
                              className={`h-9 rounded-lg text-[12px] ${
                                profile.default
                                  ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                  : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                              }`}
                              disabled={Boolean(busyActionKey)}
                              onClick={() => {
                                void applyControlPlan(profile);
                              }}
                            >
                              {busy ? "Running..." : profile.name}
                            </Button>
                          );
                        })}
                      </div>
                      <div className="mt-3 space-y-2">
                        {sortedProfiles.map((profile) => (
                          <div
                            key={`${profile.name}-description`}
                            className="flex flex-wrap items-start justify-between gap-2 text-[12px] text-[#787774]"
                          >
                            <span className="font-medium text-[#37352f]">{profile.name}</span>
                            <span className="max-w-[75%] text-right">{profile.description}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Current Recommendations
                        </p>
                        <p className="text-[12px] text-[#787774]">
                          {selectedControl?.recommendations.length || 0} recommendation(s)
                        </p>
                      </div>
                      {!selectedControl?.recommendations.length ? (
                        <p className="mt-3 text-[13px] text-[#9b9a97]">
                          No current recommendations for this session.
                        </p>
                      ) : (
                        <div className="mt-3 space-y-3">
                          {selectedControl.recommendations.map((recommendation) => {
                            const busy = busyActionKey === `recommendation:${recommendation.kind}`;

                            return (
                              <div
                                key={recommendation.kind}
                                className="rounded-xl border border-[#ecebe8] bg-white p-4"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="text-[14px] font-semibold text-[#37352f]">
                                        {recommendation.title}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(recommendation.priority)}`}
                                      >
                                        {recommendation.priority}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {recommendation.kind}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">
                                      {recommendation.reason}
                                    </p>
                                    <div className="mt-3 flex flex-wrap gap-2">
                                      {Object.entries(recommendation.counts || {}).map(([key, value]) => (
                                        <Badge
                                          key={`${recommendation.kind}-${key}`}
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {key}: {value}
                                        </Badge>
                                      ))}
                                    </div>
                                  </div>
                                  <Button
                                    size="sm"
                                    className="h-9 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                    disabled={Boolean(busyActionKey)}
                                    onClick={() => {
                                      void applyRecommendation(recommendation);
                                    }}
                                  >
                                    {busy ? "Running..." : recommendationActionLabel(recommendation)}
                                  </Button>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    <div className="grid gap-4 xl:grid-cols-3">
                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Action Summary
                        </p>
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          <SessionMetric
                            label="Actions"
                            value={String(selectedControl?.action_summary.totals.actions || 0)}
                            detail={`${selectedControl?.action_summary.totals.suggested_commands || 0} commands · ${selectedControl?.action_summary.totals.recommendations || 0} recommendations`}
                          />
                          <SessionMetric
                            label="Projects"
                            value={String(selectedControl?.action_summary.totals.projects || 0)}
                            detail={`${selectedControl?.action_summary.totals.approval_required || 0} approval-required actions`}
                          />
                        </div>
                        <div className="mt-4 space-y-4">
                          <BreakdownChips
                            label="Action Types"
                            values={selectedControl?.action_summary.by_action_type}
                            emptyText="No action types recorded."
                          />
                          <BreakdownChips
                            label="Priorities"
                            values={selectedControl?.action_summary.by_priority}
                            emptyText="No priorities recorded."
                          />
                          <BreakdownChips
                            label="Commands"
                            values={selectedControl?.action_summary.by_command}
                            emptyText="No commands recorded."
                          />
                        </div>
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Action Runs
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {linkedRuns.length}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <FilterChip
                            label="All"
                            active={runFilter === "all"}
                            count={linkedRuns.length}
                            onClick={() => {
                              setRunFilter("all");
                            }}
                          />
                          <FilterChip
                            label="Execute"
                            active={runFilter === "execute"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "execute")).length}
                            onClick={() => {
                              setRunFilter("execute");
                            }}
                          />
                          <FilterChip
                            label="Preview"
                            active={runFilter === "preview"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "preview")).length}
                            onClick={() => {
                              setRunFilter("preview");
                            }}
                          />
                          <FilterChip
                            label="Attention"
                            active={runFilter === "attention"}
                            count={linkedRuns.filter((run) => matchesRunFilter(run, "attention")).length}
                            onClick={() => {
                              setRunFilter("attention");
                            }}
                          />
                        </div>
                        {!filteredRuns.length ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedRuns.length
                              ? "No action runs match the current filter."
                              : "No linked action runs recorded yet."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {filteredRuns.slice(0, 6).map((run) => {
                              const selected = selectedRunId === run.id;
                              return (
                                <div
                                  key={`${selectedSession.id}-run-${run.id}`}
                                  className={`rounded-xl border p-3 ${
                                    selected
                                      ? "border-[#d3e5ef] bg-[#f7fbfd]"
                                      : "border-[#ecebe8] bg-white"
                                  }`}
                                >
                                  <div className="flex flex-wrap items-start justify-between gap-3">
                                    <div>
                                      <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-mono text-[11px] text-[#37352f]">{run.id}</p>
                                        <Badge
                                          variant="outline"
                                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(run.status)}`}
                                        >
                                          {run.status}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {run.run_kind}
                                        </Badge>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {run.dry_run ? "preview" : "execute"}
                                        </Badge>
                                      </div>
                                      <p className="mt-2 text-[12px] text-[#787774]">
                                        {run.mode || "auto"}
                                        {run.policy_profile ? ` · ${run.policy_profile}` : ""}
                                      </p>
                                      <p className="mt-2 text-[12px] text-[#9b9a97]">
                                        {toNumber(run.summary.selected_count)} selected ·{" "}
                                        {toNumber(run.summary.processed_count, run.results.length)} processed
                                      </p>
                                      {run.runtime_agent_ids.length > 0 && (
                                        <div className="mt-2 flex flex-wrap gap-2">
                                          {run.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                                            <Button
                                              key={`${run.id}-${runtimeAgentId}`}
                                              size="sm"
                                              variant="outline"
                                              className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                              onClick={() => {
                                                focusRuntimeAgent(runtimeAgentId, true);
                                              }}
                                            >
                                              {runtimeAgentId}
                                            </Button>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                    <Button
                                      size="sm"
                                      variant={selected ? "default" : "outline"}
                                      className={`h-8 rounded-lg text-[12px] ${
                                        selected
                                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                      }`}
                                      onClick={() => {
                                        setSelectedRunId(run.id);
                                      }}
                                    >
                                      {selected ? "Selected" : "Inspect"}
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Latest Session Events
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredEvents.length}
                          </Badge>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <FilterChip
                            label="All"
                            active={eventFilter === "all"}
                            count={(selectedSession.events || []).length}
                            onClick={() => {
                              setEventFilter("all");
                            }}
                          />
                          <FilterChip
                            label="Control"
                            active={eventFilter === "control"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "control")).length}
                            onClick={() => {
                              setEventFilter("control");
                            }}
                          />
                          <FilterChip
                            label="Actions"
                            active={eventFilter === "actions"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "actions")).length}
                            onClick={() => {
                              setEventFilter("actions");
                            }}
                          />
                          <FilterChip
                            label="Decisions"
                            active={eventFilter === "decisions"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "decisions")).length}
                            onClick={() => {
                              setEventFilter("decisions");
                            }}
                          />
                          <FilterChip
                            label="Attention"
                            active={eventFilter === "attention"}
                            count={(selectedSession.events || []).filter((event) => matchesEventFilter(event, "attention")).length}
                            onClick={() => {
                              setEventFilter("attention");
                            }}
                          />
                        </div>
                        {!filteredEvents.length ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {selectedSession.events.length
                              ? "No session events match the current filter."
                              : "No session events recorded yet."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {filteredEvents.slice(-6).reverse().map((event) => (
                              (() => {
                                const eventApprovalId = toStringValue(event.approval_id);
                                const eventIssueId = toStringValue(event.issue_id);
                                const eventProjectId = toStringValue(event.project_id);
                                const eventRuntimeAgentIds = [
                                  toStringValue(event.runtime_agent_id),
                                  ...toStringArray(event.runtime_agent_ids),
                                ].filter(Boolean);
                                return (
                                  <div
                                    key={`${toStringValue(event.event)}-${toStringValue(event.timestamp)}`}
                                    className="rounded-xl border border-[#ecebe8] bg-white p-3"
                                  >
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                      <div className="flex flex-wrap items-center gap-2">
                                        <p className="font-mono text-[11px] text-[#37352f]">
                                          {toStringValue(event.event, "unknown_event")}
                                        </p>
                                        <Badge
                                          variant="outline"
                                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                        >
                                          {eventFamily(toStringValue(event.event))}
                                        </Badge>
                                      </div>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(toStringValue(event.status, "unknown"))}`}
                                      >
                                        {toStringValue(event.status, "unknown")}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {toStringValue(event.message, "No event message")}
                                    </p>
                                    {(eventProjectId ||
                                      toNullableNumber(event.story_id) ||
                                      eventApprovalId ||
                                      eventIssueId ||
                                      eventRuntimeAgentIds.length > 0) && (
                                      <div className="mt-3 flex flex-wrap gap-2">
                                        {eventProjectId && (
                                          <Link
                                            href={`/projects/${eventProjectId}`}
                                            className="inline-flex h-7 items-center rounded-full border border-[#e5e5e3] bg-[#fafaf9] px-2.5 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                                          >
                                            project {eventProjectId}
                                          </Link>
                                        )}
                                        {toNullableNumber(event.story_id) && eventProjectId && (
                                          <Link
                                            href={`/projects/${eventProjectId}?storyId=${toNullableNumber(event.story_id)}`}
                                            className="inline-flex h-7 items-center rounded-full border border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] font-medium text-[#2a6690] transition-colors hover:bg-[#e3f2f8]"
                                          >
                                            story {toNullableNumber(event.story_id)}
                                          </Link>
                                        )}
                                        {eventApprovalId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(eventApprovalId);
                                            }}
                                          >
                                            approval {eventApprovalId}
                                          </Button>
                                        )}
                                        {eventIssueId && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                                            onClick={() => {
                                              setEntitySearch(eventIssueId);
                                            }}
                                          >
                                            issue {eventIssueId}
                                          </Button>
                                        )}
                                        {eventRuntimeAgentIds.slice(0, 2).map((runtimeAgentId) => (
                                          <Button
                                            key={`${toStringValue(event.event)}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                      </div>
                                    )}
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {formatTimestamp(toStringValue(event.timestamp))}
                                    </p>
                                  </div>
                                );
                              })()
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Selected Control Pass
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Inspect the pass currently selected from recent history or session-linked passes.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedPass ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a control pass to inspect applied steps and final state.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                              {selectedPass.id}
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedPass.status)}`}
                            >
                              {selectedPass.status}
                            </Badge>
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                            >
                              {selectedPass.profile}
                            </Badge>
                          </div>
                          <p className="mt-2 text-[13px] text-[#6b6b6b]">
                            Session {selectedPass.orchestrator_session_id} · {selectedPass.actor || "unknown actor"}
                          </p>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                          onClick={() => {
                            setSelectedSessionId(selectedPass.orchestrator_session_id);
                          }}
                        >
                          Open session
                        </Button>
                      </div>

                      <div className="grid gap-3 sm:grid-cols-2">
                        <SessionMetric
                          label="Final State"
                          value={toStringValue(selectedPass.summary.final_state, "unknown")}
                          detail={toStringValue(selectedPass.summary.stopped_reason, "No stop reason")}
                        />
                        <SessionMetric
                          label="Applied"
                          value={String(toNumber(selectedPass.summary.applied, selectedPass.applied.length))}
                          detail={`${toNumber(selectedPass.summary.errors, selectedPass.errors.length)} error step(s)`}
                        />
                        <SessionMetric
                          label="Control Transition"
                          value={`${toStringValue(selectedPass.control_before.state, "unknown")} -> ${toStringValue(selectedPass.control_after.state, "unknown")}`}
                          detail={`${selectedPass.session_status_before || "unknown"} -> ${selectedPass.session_status_after || "unknown"} session status`}
                        />
                        <SessionMetric
                          label="Coverage"
                          value={`${selectedPass.project_ids.length} project${selectedPass.project_ids.length === 1 ? "" : "s"}`}
                          detail={selectedPass.initiative_id || "No initiative mapping"}
                        />
                      </div>

                      <BreakdownChips
                        label="Recommendation Kinds"
                        values={selectedPass.recommendation_kinds.reduce<ExecutionPlaneCountMap>((acc, kind) => {
                          acc[kind] = (acc[kind] || 0) + 1;
                          return acc;
                        }, {})}
                        emptyText="No recommendation kinds recorded."
                      />

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Applied Steps
                        </p>
                        {selectedPass.applied.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No applied steps recorded.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedPass.applied.map((step, index) => (
                              <div
                                key={`${selectedPass.id}-applied-${index}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-[13px] font-semibold text-[#37352f]">
                                    {toStringValue(step.title, toStringValue(step.recommendation_kind, "step"))}
                                  </p>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(step.status, "ok"))}`}
                                  >
                                    {toStringValue(step.status, "ok")}
                                  </Badge>
                                </div>
                                <p className="mt-2 text-[12px] text-[#787774]">
                                  {toStringValue(step.operation_type, "operation")}
                                  {toStringValue(step.operation_mode) ? ` · ${toStringValue(step.operation_mode)}` : ""}
                                </p>
                                <p className="mt-2 text-[12px] text-[#9b9a97]">
                                  {toStringValue(step.control_state_before, "unknown")}
                                  {" -> "}
                                  {toStringValue(step.control_state_after, "unknown")}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                          Errors
                        </p>
                        {selectedPass.errors.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No errors recorded for this pass.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {selectedPass.errors.map((error, index) => (
                              <div
                                key={`${selectedPass.id}-error-${index}`}
                                className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] p-3"
                              >
                                <p className="text-[13px] font-semibold text-[#93370d]">
                                  {toStringValue(error.title, toStringValue(error.recommendation_kind, "error"))}
                                </p>
                                <p className="mt-2 text-[12px] text-[#93370d]">
                                  {toStringValue(error.error, "Unknown control-pass error")}
                                </p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
                <CardHeader>
                  <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
                    Linked Decisions
                  </CardTitle>
                  <CardDescription className="text-[13px] text-[#787774]">
                    Approvals and issues attached to the selected session, with direct control actions.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {!selectedSession ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
                      Select a session to inspect pending approvals and issues.
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Session Approvals
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredApprovals.length}
                          </Badge>
                        </div>
                        {filteredApprovals.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedApprovals.length
                              ? "No approvals match the current search."
                              : "No linked approvals."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {filteredApprovals.slice(0, 6).map((approval) => (
                              <div
                                key={`${selectedSession.id}-approval-${approval.id}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="font-mono text-[11px] text-[#37352f]">
                                        {approval.id}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${approvalStatusClass(approval.status)}`}
                                      >
                                        {approval.status}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {approval.action}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {approval.reason || `Approval requested for ${approval.action}.`}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      Requested by {approval.requested_by || "unknown"} · {formatTimestamp(approval.created_at)}
                                    </p>
                                    {(approval.policy_reasons.length > 0 || approval.issue_id || approval.runtime_agent_ids.length > 0) && (
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {approval.issue_id && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(approval.issue_id);
                                            }}
                                          >
                                            issue {approval.issue_id}
                                          </Button>
                                        )}
                                        {approval.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                                          <Button
                                            key={`${approval.id}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                        {approval.policy_reasons.slice(0, 3).map((reason) => (
                                          <Badge
                                            key={`${approval.id}-${reason}`}
                                            variant="outline"
                                            className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                          >
                                            {reason}
                                          </Badge>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {approval.status === "pending" && (
                                      <>
                                        <Button
                                          size="sm"
                                          className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void approveApproval(approval);
                                          }}
                                        >
                                          {busyActionKey === `approval-approve:${approval.id}` ? "Approving..." : "Approve"}
                                        </Button>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                          disabled={Boolean(busyActionKey)}
                                          onClick={() => {
                                            void rejectApproval(approval);
                                          }}
                                        >
                                          {busyActionKey === `approval-reject:${approval.id}` ? "Rejecting..." : "Reject"}
                                        </Button>
                                      </>
                                    )}
                                    {approval.status === "approved" && (
                                      <Button
                                        size="sm"
                                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void applyApproval(approval);
                                        }}
                                      >
                                        {busyActionKey === `approval-apply:${approval.id}` ? "Applying..." : "Apply"}
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                            Session Issues
                          </p>
                          <Badge
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {filteredIssues.length}
                          </Badge>
                        </div>
                        {filteredIssues.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">
                            {linkedIssues.length
                              ? "No issues match the current search."
                              : "No linked issues."}
                          </p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {filteredIssues.slice(0, 6).map((issue) => (
                              <div
                                key={`${selectedSession.id}-issue-${issue.id}`}
                                className="rounded-xl border border-[#ecebe8] bg-white p-3"
                              >
                                <div className="flex flex-wrap items-start justify-between gap-3">
                                  <div>
                                    <div className="flex flex-wrap items-center gap-2">
                                      <p className="font-mono text-[11px] text-[#37352f]">
                                        {issue.id}
                                      </p>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueStatusClass(issue.status)}`}
                                      >
                                        {issue.status}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issue.severity)}`}
                                      >
                                        {issue.severity}
                                      </Badge>
                                      <Badge
                                        variant="outline"
                                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                                      >
                                        {issue.category}
                                      </Badge>
                                    </div>
                                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                      {issue.title || "Issue requires review"}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {issue.root_cause || issue.description || "No root cause recorded"}
                                    </p>
                                    <p className="mt-2 text-[12px] text-[#9b9a97]">
                                      {formatTimestamp(issue.created_at)}
                                      {issue.related_command ? ` · command ${issue.related_command}` : ""}
                                    </p>
                                    {(issue.approval_id || issue.runtime_agent_ids.length > 0 || issue.runtime_agent_id) && (
                                      <div className="mt-2 flex flex-wrap gap-2">
                                        {issue.approval_id && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                            onClick={() => {
                                              setEntitySearch(issue.approval_id);
                                            }}
                                          >
                                            approval {issue.approval_id}
                                          </Button>
                                        )}
                                        {(issue.runtime_agent_ids.length > 0
                                          ? issue.runtime_agent_ids.slice(0, 2)
                                          : issue.runtime_agent_id
                                            ? [issue.runtime_agent_id]
                                            : []
                                        ).map((runtimeAgentId) => (
                                          <Button
                                            key={`${issue.id}-${runtimeAgentId}`}
                                            size="sm"
                                            variant="outline"
                                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                            onClick={() => {
                                              focusRuntimeAgent(runtimeAgentId, true);
                                            }}
                                          >
                                            {runtimeAgentId}
                                          </Button>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                  <div className="flex flex-wrap gap-2">
                                    {issue.status === "open" && (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                        disabled={Boolean(busyActionKey)}
                                        onClick={() => {
                                          void resolveIssue(issue);
                                        }}
                                      >
                                        {busyActionKey === `issue-resolve:${issue.id}` ? "Resolving..." : "Resolve"}
                                      </Button>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}