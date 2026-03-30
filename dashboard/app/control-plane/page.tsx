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
import {
  applyExecutionPlaneOrchestratorSessionControlPlan,
  applyExecutionPlaneOrchestratorSessionRecommendation,
  applyExecutionPlaneApproval,
  approveExecutionPlaneApproval,
  fetchAccountsHealth,
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

function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
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
  const [selectedRunId, setSelectedRunId] = useState("");
  const [selectedRunResultIndex, setSelectedRunResultIndex] = useState(0);
  const [selectedPassId, setSelectedPassId] = useState("");
  const [selectedSession, setSelectedSession] = useState<OrchestratorSessionDetail | null>(null);
  const [runFilter, setRunFilter] = useState("all");
  const [eventFilter, setEventFilter] = useState("all");
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
      setSelectedRunId("");
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
      setSelectedRunId("");
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
    setSelectedRunResultIndex(0);
  }, [selectedRunId]);

  useEffect(() => {
    const visibleRuns = ((selectedSession?.runs || []) as ExecutionAgentActionRunRecord[]).filter(
      (run) => matchesRunFilter(run, runFilter)
    );
    if (!visibleRuns.length) {
      return;
    }
    if (!selectedRunId || !visibleRuns.some((run) => run.id === selectedRunId)) {
      setSelectedRunId(visibleRuns[0].id);
    }
  }, [runFilter, selectedRunId, selectedSession]);

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
  const recentControlPasses = useMemo(() => controlPasses.slice(0, 8), [controlPasses]);
  const recentSessions = useMemo(() => sessions.slice(0, 6), [sessions]);
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
    () => linkedRuns.filter((run) => matchesRunFilter(run, runFilter)),
    [linkedRuns, runFilter]
  );
  const linkedIssues = useMemo(
    () =>
      [...(selectedSession?.issues || [])].sort((left, right) =>
        right.created_at.localeCompare(left.created_at)
      ),
    [selectedSession]
  );
  const selectedRun = useMemo(() => {
    if (!selectedRunId) return null;
    return linkedRuns.find((run) => run.id === selectedRunId) ?? null;
  }, [linkedRuns, selectedRunId]);
  const filteredEvents = useMemo(
    () => (selectedSession?.events || []).filter((event) => matchesEventFilter(event, eventFilter)),
    [eventFilter, selectedSession]
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
                    No orchestrator control passes recorded yet.
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
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                              Selected Outcome
                            </p>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(selectedRunResult.status, "unknown"))}`}
                            >
                              {toStringValue(selectedRunResult.status, "unknown")}
                            </Badge>
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
                        </div>
                      )}
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
                      No orchestrator sessions recorded yet.
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
                                <p className="mt-2 text-[12px] text-[#9b9a97]">
                                  {formatTimestamp(toStringValue(event.timestamp))}
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
                            {linkedApprovals.length}
                          </Badge>
                        </div>
                        {linkedApprovals.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No linked approvals.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {linkedApprovals.slice(0, 6).map((approval) => (
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
                                    {approval.policy_reasons.length > 0 && (
                                      <div className="mt-2 flex flex-wrap gap-2">
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
                            {linkedIssues.length}
                          </Badge>
                        </div>
                        {linkedIssues.length === 0 ? (
                          <p className="mt-3 text-[13px] text-[#9b9a97]">No linked issues.</p>
                        ) : (
                          <div className="mt-3 space-y-3">
                            {linkedIssues.slice(0, 6).map((issue) => (
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