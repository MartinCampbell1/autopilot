"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { PortfolioProjectCard } from "@/components/portfolio-project-card";
import { ShadowAuditReviewSheet } from "@/components/shadow-audit-review-sheet";
import { Button } from "@/components/ui/button";
import {
  archiveProject,
  fetchAccountsHealth,
  fetchProjects,
  launchProject,
  pauseProject,
  resolveExecutionPlaneShadowAudit,
  resumeProject,
} from "@/lib/api";
import {
  summarizeProjectRuntimeHandoffSignals,
} from "@/lib/story-runtime-handoffs";
import { compareShadowAuditsByRecency } from "@/lib/shadow-audit-queue";
import { useProjectRuntimeHandoffSignals } from "@/lib/use-project-runtime-handoff-signals";
import { useSSE } from "@/lib/sse";
import { useProjectRuntimeControlClient } from "@/lib/use-project-runtime-control-client";
import type { AccountHealth, ProjectSummary, ToolPermissionRuntimeRecord } from "@/lib/types";

const TOOL_PERMISSION_RUNTIME_EVENTS = new Set([
  "tool_permission_runtime_pending",
  "tool_permission_runtime_resolved",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [busyProjectId, setBusyProjectId] = useState<string>("");
  const [busyToolPermissionKey, setBusyToolPermissionKey] = useState<string>("");
  const [expandedToolPermissionProjects, setExpandedToolPermissionProjects] = useState<Record<string, boolean>>({});
  const [message, setMessage] = useState("");

  const loadData = useCallback(async () => {
    try {
      const [projectData, healthData] = await Promise.all([
        fetchProjects(false),
        fetchAccountsHealth(),
      ]);
      setProjects((projectData.projects || []) as ProjectSummary[]);
      setHealth(healthData as AccountHealth);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load dashboard.");
    }
  }, []);

  useEffect(() => {
    void loadData();
    const interval = setInterval(() => {
      void loadData();
    }, 10000);
    return () => clearInterval(interval);
  }, [loadData]);

  const visibleProjects = useMemo(
    () => projects.filter((project) => !project.archived),
    [projects]
  );
  const {
    signals: projectRuntimeHandoffSignals,
    refresh: refreshProjectRuntimeHandoffSignals,
  } = useProjectRuntimeHandoffSignals(visibleProjects);
  const [busyShadowAuditKey, setBusyShadowAuditKey] = useState("");
  const [shadowAuditMessage, setShadowAuditMessage] = useState("");
  const [queueOpen, setQueueOpen] = useState(false);
  const [activeQueueAuditId, setActiveQueueAuditId] = useState("");
  const quarantineSummary = useMemo(
    () => summarizeProjectRuntimeHandoffSignals(projectRuntimeHandoffSignals),
    [projectRuntimeHandoffSignals]
  );
  const queueAudits = useMemo(
    () =>
      visibleProjects
        .flatMap((project) => projectRuntimeHandoffSignals[project.id]?.openShadowAudits || [])
        .sort((left, right) => compareShadowAuditsByRecency(left, right)),
    [projectRuntimeHandoffSignals, visibleProjects]
  );
  const primaryQuarantineAudit = useMemo(
    () => queueAudits.find((audit) => audit.id === activeQueueAuditId) || queueAudits[0] || null,
    [activeQueueAuditId, queueAudits]
  );
  const activeQueueAuditIndex = useMemo(
    () => (primaryQuarantineAudit ? queueAudits.findIndex((audit) => audit.id === primaryQuarantineAudit.id) : -1),
    [primaryQuarantineAudit, queueAudits]
  );
  const runtimeControl = useProjectRuntimeControlClient({ projects: visibleProjects });
  const {
    getLatestRequest,
    getToolPermissionRuntimes,
    handleSSEEvent,
    isPending,
    requestInterrupt,
    requestListToolPermissionRuntimes,
    requestResolveToolPermissionRuntime,
  } = runtimeControl;

  useSSE(
    useCallback((event, data) => {
      handleSSEEvent(event, data);
      if (TOOL_PERMISSION_RUNTIME_EVENTS.has(event) && isRecord(data)) {
        const projectId = stringValue(data.project_id);
        if (
          projectId
          && expandedToolPermissionProjects[projectId]
          && visibleProjects.some(
            (project) => project.id === projectId && Boolean(project.runtime_control_available)
          )
        ) {
          void requestListToolPermissionRuntimes(projectId, { status: "pending" }).catch(() => {
            // Keep the dashboard responsive; loadData() will still refresh the summary count.
          });
        }
      }
      void loadData();
    }, [
      expandedToolPermissionProjects,
      handleSSEEvent,
      loadData,
      requestListToolPermissionRuntimes,
      visibleProjects,
    ])
  );

  const runAction = async (projectId: string, action: () => Promise<{ message: string }>) => {
    setBusyProjectId(projectId);
    setMessage("");
    try {
      const result = await action();
      setMessage(result.message);
      await loadData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setBusyProjectId("");
    }
  };

  const formatShadowAuditTimestamp = useCallback((value?: string | null) => {
    if (!value) return "No timestamp";
    return new Intl.DateTimeFormat("en", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  }, []);

  const handleResolveShadowAudit = useCallback(
    (audit: NonNullable<typeof primaryQuarantineAudit>) => {
      const actionKey = `shadow-audit-resolve:${audit.id}`;
      const currentIndex = queueAudits.findIndex((entry) => entry.id === audit.id);
      const nextAuditId = queueAudits[currentIndex + 1]?.id || "";
      setBusyShadowAuditKey(actionKey);
      setShadowAuditMessage("");
      void resolveExecutionPlaneShadowAudit(audit.id, {
        actor: "dashboard-portfolio",
      })
        .then(() => {
          setShadowAuditMessage("Shadow-audit quarantine resolved and handoff released.");
          refreshProjectRuntimeHandoffSignals();
          if (nextAuditId) {
            setActiveQueueAuditId(nextAuditId);
            setQueueOpen(true);
          } else {
            setActiveQueueAuditId("");
            setQueueOpen(false);
          }
        })
        .catch((error) => {
          setShadowAuditMessage(
            error instanceof Error
              ? error.message
              : "Failed to resolve shadow-audit quarantine."
          );
        })
        .finally(() => {
          setBusyShadowAuditKey("");
        });
    },
    [queueAudits, refreshProjectRuntimeHandoffSignals]
  );
  const handleSelectNextQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex < 0) return;
    const nextAuditId = queueAudits[activeQueueAuditIndex + 1]?.id;
    if (!nextAuditId) return;
    setShadowAuditMessage("");
    setActiveQueueAuditId(nextAuditId);
  }, [activeQueueAuditIndex, queueAudits]);
  const handleSelectPreviousQueueAudit = useCallback(() => {
    if (activeQueueAuditIndex <= 0) return;
    const previousAuditId = queueAudits[activeQueueAuditIndex - 1]?.id;
    if (!previousAuditId) return;
    setShadowAuditMessage("");
    setActiveQueueAuditId(previousAuditId);
  }, [activeQueueAuditIndex, queueAudits]);

  const runInterruptAction = useCallback(
    async (project: ProjectSummary) => {
      setBusyProjectId(project.id);
      setMessage("");
      try {
        await requestInterrupt(project.id);
        setMessage(`Interrupt queued for ${project.name}. It will apply at the next safe checkpoint.`);
        await loadData();
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to queue interrupt.");
      } finally {
        setBusyProjectId("");
      }
    },
    [loadData, requestInterrupt]
  );

  const interruptStateLabel = useCallback(
    (projectId: string) => {
      const latest = getLatestRequest(projectId, "interrupt");
      if (!latest) return "";
      if (latest.phase === "queued") return "Interrupt queued for runtime delivery.";
      if (latest.phase === "acknowledged") return "Runtime acknowledged interrupt request.";
      if (latest.phase === "success") return "Interrupt will apply at the next safe checkpoint.";
      if (latest.phase === "error") return latest.errorMessage || "Interrupt request failed.";
      if (latest.phase === "stale") return "Previous interrupt request expired with the old runtime session.";
      return "";
    },
    [getLatestRequest]
  );

  const toggleToolPermissionPanel = useCallback(
    async (project: ProjectSummary) => {
      const isOpen = Boolean(expandedToolPermissionProjects[project.id]);
      if (isOpen) {
        setExpandedToolPermissionProjects((current) => {
          const next = { ...current };
          delete next[project.id];
          return next;
        });
        return;
      }
      setExpandedToolPermissionProjects((current) => ({
        ...current,
        [project.id]: true,
      }));
      setMessage("");
      try {
        await requestListToolPermissionRuntimes(project.id, { status: "pending" });
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to load pending tool permissions.");
      }
    },
    [expandedToolPermissionProjects, requestListToolPermissionRuntimes]
  );

  const resolveToolPermission = useCallback(
    async (
      project: ProjectSummary,
      runtime: ToolPermissionRuntimeRecord,
      outcome: "allow" | "deny"
    ) => {
      const actionKey = `${runtime.id}:${outcome}`;
      setBusyToolPermissionKey(actionKey);
      setMessage("");
      try {
        await requestResolveToolPermissionRuntime(project.id, runtime.id, outcome, {
          actor: "dashboard",
          note:
            outcome === "allow"
              ? `Dashboard allowed ${runtime.tool_name || runtime.id}.`
              : `Dashboard denied ${runtime.tool_name || runtime.id}.`,
          source: "user",
        });
        await requestListToolPermissionRuntimes(project.id, { status: "pending" });
        await loadData();
        setMessage(
          `${outcome === "allow" ? "Allowed" : "Denied"} ${runtime.tool_name || "tool request"} for ${project.name}.`
        );
      } catch (error) {
        setMessage(error instanceof Error ? error.message : "Failed to resolve tool permission runtime.");
      } finally {
        setBusyToolPermissionKey("");
      }
    },
    [loadData, requestListToolPermissionRuntimes, requestResolveToolPermissionRuntime]
  );

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar
        health={health}
        projects={visibleProjects}
        projectRuntimeHandoffSignals={projectRuntimeHandoffSignals}
        onRefreshProjectRuntimeHandoffSignals={refreshProjectRuntimeHandoffSignals}
      />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center justify-between border-b border-[#e5e5e3] bg-white px-6">
          <div>
            <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">Projects</h1>
            <p className="mt-0.5 text-[12px] text-[#9b9a97]">
              Portfolio view for active workspaces and live runs.
            </p>
          </div>
          <div className="flex items-center gap-2 text-[13px]">
            {quarantineSummary.openShadowAuditCount > 0 ? (
              <div className="flex items-center gap-2 rounded-full border border-[#f4e0c4] bg-[#fff6e8] px-3 py-1.5 text-[12px] text-[#9a6700]">
                <span className="inline-block h-2 w-2 rounded-full bg-[#d9730d]" />
                <span className="font-medium">
                  {quarantineSummary.blockedProjectCount} blocked project
                  {quarantineSummary.blockedProjectCount === 1 ? "" : "s"}
                </span>
                <span className="text-[#b27700]">
                  {quarantineSummary.openShadowAuditCount} audit
                  {quarantineSummary.openShadowAuditCount === 1 ? "" : "s"}
                </span>
              </div>
            ) : null}
            {primaryQuarantineAudit ? (
              <>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] px-3 text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                  onClick={() => {
                    setQueueOpen(true);
                  }}
                >
                  Review queue
                </Button>
                <ShadowAuditReviewSheet
                  audit={primaryQuarantineAudit}
                  open={queueOpen}
                  onOpenChange={setQueueOpen}
                  hideTrigger
                  busyActionKey={busyShadowAuditKey}
                  formatTimestamp={formatShadowAuditTimestamp}
                  onResolveShadowAudit={handleResolveShadowAudit}
                  queueState={{
                    currentIndex: Math.max(activeQueueAuditIndex, 0),
                    totalCount: queueAudits.length,
                    onSelectNext: handleSelectNextQueueAudit,
                    onSelectPrevious: handleSelectPreviousQueueAudit,
                  }}
                />
              </>
            ) : null}
            {health && (
              <div className="flex items-center gap-2 text-[13px]">
                <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
                <span className="tabular-nums text-[#787774]">{health.available} agents available</span>
              </div>
            )}
          </div>
        </header>

        <div className="px-6 py-6">
          {message && (
            <div className="mb-4 rounded-xl border border-[#e5e5e3] bg-white px-4 py-3 text-[13px] text-[#6b6b6b]">
              {message}
            </div>
          )}
          {shadowAuditMessage && (
            <div className="mb-4 rounded-xl border border-[#f4e0c4] bg-[#fff6e8] px-4 py-3 text-[13px] text-[#9a6700]">
              {shadowAuditMessage}
            </div>
          )}

          {visibleProjects.length === 0 ? (
            <div className="flex min-h-[60vh] items-center justify-center">
              <div className="max-w-md rounded-2xl border border-dashed border-[#e5e5e3] bg-white px-8 py-12 text-center">
                <h2 className="text-[18px] font-semibold text-[#37352f]">No active projects</h2>
                <p className="mt-3 text-[14px] leading-relaxed text-[#787774]">
                  Create a project from the intake chat or import a spec to start a new workspace.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {visibleProjects.map((project) => {
                const pendingToolPermissionRuntimes = getToolPermissionRuntimes(project.id, {
                  pendingOnly: true,
                });
                const pendingToolPermissionCount = Math.max(
                  Number(project.pending_tool_permission_runtime_count || 0),
                  pendingToolPermissionRuntimes.length
                );
                const latestToolPermissionListRequest = getLatestRequest(
                  project.id,
                  "list_tool_permission_runtimes"
                );
                const toolPermissionError =
                  latestToolPermissionListRequest?.phase === "error"
                    ? latestToolPermissionListRequest.errorMessage || ""
                    : "";
                return (
                  <PortfolioProjectCard
                    key={project.id}
                    project={project}
                    runtimeHandoffSummary={projectRuntimeHandoffSignals[project.id] ?? null}
                    busy={busyProjectId === project.id}
                    interruptBusy={isPending(project.id, "interrupt")}
                    interruptStateLabel={interruptStateLabel(project.id)}
                    pendingToolPermissionCount={pendingToolPermissionCount}
                    toolPermissionPanelOpen={Boolean(expandedToolPermissionProjects[project.id])}
                    toolPermissionLoading={isPending(project.id, "list_tool_permission_runtimes")}
                    toolPermissionError={toolPermissionError}
                    toolPermissionBusyKey={busyToolPermissionKey}
                    toolPermissionRuntimes={pendingToolPermissionRuntimes}
                    onToggleToolPermissionPanel={() => {
                      void toggleToolPermissionPanel(project);
                    }}
                    onAllowToolPermission={(runtime) => {
                      void resolveToolPermission(project, runtime, "allow");
                    }}
                    onDenyToolPermission={(runtime) => {
                      void resolveToolPermission(project, runtime, "deny");
                    }}
                    onLaunch={() => {
                      const fn = project.status === "paused"
                        ? () => resumeProject(project.id)
                        : () => launchProject(project.id);
                      void runAction(project.id, fn);
                    }}
                    onPause={() => {
                      void runAction(project.id, () => pauseProject(project.id));
                    }}
                    onInterrupt={() => {
                      void runInterruptAction(project);
                    }}
                    onArchive={() => {
                      void runAction(project.id, () => archiveProject(project.id));
                    }}
                  />
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
