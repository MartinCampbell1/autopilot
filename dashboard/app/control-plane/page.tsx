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
  fetchAccountsHealth,
  fetchExecutionPlaneControlPasses,
  fetchExecutionPlaneControlPassSummary,
  fetchExecutionPlaneOrchestratorSessions,
  fetchExecutionPlaneOrchestratorSessionSummary,
  fetchProjects,
} from "@/lib/api";
import { useSSE } from "@/lib/sse";
import type {
  AccountHealth,
  ExecutionPlaneCountMap,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
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

export default function ControlPlanePage() {
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [controlPasses, setControlPasses] = useState<OrchestratorControlPassRecord[]>([]);
  const [controlSummary, setControlSummary] = useState<OrchestratorControlPassSummary | null>(null);
  const [sessions, setSessions] = useState<OrchestratorSessionRecord[]>([]);
  const [sessionSummary, setSessionSummary] = useState<OrchestratorSessionSummary | null>(null);
  const [message, setMessage] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [
        healthData,
        projectData,
        controlPassData,
        controlPassSummaryData,
        sessionData,
        sessionSummaryData,
      ] = await Promise.all([
        fetchAccountsHealth(),
        fetchProjects(false),
        fetchExecutionPlaneControlPasses(),
        fetchExecutionPlaneControlPassSummary(),
        fetchExecutionPlaneOrchestratorSessions(),
        fetchExecutionPlaneOrchestratorSessionSummary(),
      ]);
      setHealth(healthData);
      setProjects((projectData.projects || []) as ProjectSummary[]);
      setControlPasses((controlPassData.control_passes || []) as OrchestratorControlPassRecord[]);
      setControlSummary(controlPassSummaryData);
      setSessions((sessionData.sessions || []) as OrchestratorSessionRecord[]);
      setSessionSummary(sessionSummaryData);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load control plane.");
    }
  }, []);

  useEffect(() => {
    void load();
    const interval = setInterval(() => {
      void load();
    }, 15000);
    return () => clearInterval(interval);
  }, [load]);

  useSSE(
    useCallback(() => {
      void load();
    }, [load])
  );

  const refresh = async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  };

  const visibleProjects = useMemo(
    () => projects.filter((project) => !project.archived),
    [projects]
  );
  const recentControlPasses = useMemo(() => controlPasses.slice(0, 8), [controlPasses]);
  const recentSessions = useMemo(() => sessions.slice(0, 6), [sessions]);
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
                Observe session-level orchestration passes, execution-plane coverage, and current
                FounderOS control traffic without leaving Autopilot.
              </p>
            </div>
            <div className="min-w-[240px] rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
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
          {message && (
            <div className="rounded-xl border border-[#f0d0c9] bg-[#fff6f4] px-4 py-3 text-[13px] text-[#93370d]">
              {message}
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
                  Latest session-level FounderOS control passes, including execution profile,
                  final state, and project coverage.
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

                      return (
                        <div
                          key={controlPass.id}
                          className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4"
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
                                {controlPass.customized && (
                                  <Badge
                                    variant="outline"
                                    className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                                  >
                                    customized
                                  </Badge>
                                )}
                              </div>
                              <p className="mt-2 text-[13px] text-[#6b6b6b]">
                                Session{" "}
                                <span className="font-mono text-[#37352f]">
                                  {controlPass.orchestrator_session_id}
                                </span>
                                {" · "}
                                {controlPass.orchestrator || "unknown orchestrator"}
                                {" · "}
                                {controlPass.actor || "unknown actor"}
                              </p>
                            </div>
                            <p className="text-[12px] text-[#9b9a97]">
                              {formatTimestamp(controlPass.created_at)}
                            </p>
                          </div>

                          <div className="mt-4 grid gap-3 md:grid-cols-3">
                            <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
                              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Outcome</p>
                              <p className="mt-1 text-[14px] font-semibold text-[#37352f]">{finalState}</p>
                              <p className="mt-1 text-[12px] text-[#787774]">
                                {appliedSteps} applied · {errorSteps} errors
                              </p>
                            </div>
                            <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
                              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Coverage</p>
                              <p className="mt-1 text-[14px] font-semibold text-[#37352f]">
                                {controlPass.project_ids.length} project{controlPass.project_ids.length === 1 ? "" : "s"}
                              </p>
                              <p className="mt-1 text-[12px] text-[#787774]">
                                {controlPass.initiative_id || "No initiative mapping"}
                              </p>
                            </div>
                            <div className="rounded-xl border border-[#ecebe8] bg-white px-3 py-2">
                              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Reason</p>
                              <p className="mt-1 text-[14px] font-semibold text-[#37352f]">
                                {stoppedReason || controlPass.reason || "No stop reason"}
                              </p>
                              <p className="mt-1 text-[12px] text-[#787774]">
                                {controlPass.recommendation_kinds.length} recommendation kind(s)
                              </p>
                            </div>
                          </div>

                          <div className="mt-4 flex flex-wrap gap-2">
                            {controlPass.project_ids.slice(0, 3).map((projectId) => (
                              <Link
                                key={`${controlPass.id}-${projectId}`}
                                href={`/projects/${projectId}`}
                                className="inline-flex h-7 items-center rounded-full border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                              >
                                {projectId}
                              </Link>
                            ))}
                            {controlPass.project_ids.length > 3 && (
                              <span className="inline-flex h-7 items-center rounded-full border border-[#ecebe8] bg-[#fafaf9] px-3 text-[12px] text-[#787774]">
                                +{controlPass.project_ids.length - 3} more
                              </span>
                            )}
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
                    External FounderOS orchestration sessions and their current execution-plane scope.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {recentSessions.length === 0 ? (
                    <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-6 text-[13px] text-[#9b9a97]">
                      No orchestrator sessions recorded yet.
                    </div>
                  ) : (
                    <div className="space-y-3">
                      {recentSessions.map((session) => (
                        <div
                          key={session.id}
                          className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4"
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
                            <p className="font-mono text-[11px] text-[#9b9a97]">{session.id}</p>
                          </div>

                          <div className="mt-3 grid gap-3 sm:grid-cols-2">
                            <div>
                              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Scope</p>
                              <p className="mt-1 text-[13px] text-[#37352f]">
                                {session.project_ids.length} project{session.project_ids.length === 1 ? "" : "s"}
                                {session.initiative_id ? ` · ${session.initiative_id}` : ""}
                              </p>
                            </div>
                            <div>
                              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Linked Objects</p>
                              <p className="mt-1 text-[13px] text-[#37352f]">
                                {session.linked_control_pass_ids.length} passes · {session.linked_run_ids.length} runs
                              </p>
                            </div>
                          </div>

                          <div className="mt-3 flex flex-wrap gap-2">
                            {session.project_ids.slice(0, 2).map((projectId) => (
                              <Link
                                key={`${session.id}-${projectId}`}
                                href={`/projects/${projectId}`}
                                className="inline-flex h-7 items-center rounded-full border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                              >
                                {projectId}
                              </Link>
                            ))}
                            {session.project_ids.length > 2 && (
                              <span className="inline-flex h-7 items-center rounded-full border border-[#ecebe8] bg-[#fafaf9] px-3 text-[12px] text-[#787774]">
                                +{session.project_ids.length - 2} more
                              </span>
                            )}
                          </div>

                          <p className="mt-3 text-[12px] text-[#9b9a97]">
                            Updated {formatTimestamp(session.updated_at)}
                          </p>
                        </div>
                      ))}
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
        </div>
      </main>
    </div>
  );
}
