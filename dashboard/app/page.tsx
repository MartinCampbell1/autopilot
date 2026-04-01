"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { PortfolioProjectCard } from "@/components/portfolio-project-card";
import { archiveProject, fetchAccountsHealth, fetchProjects, launchProject, pauseProject, resumeProject } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import { useProjectRuntimeControlClient } from "@/lib/use-project-runtime-control-client";
import type { AccountHealth, ProjectSummary, ToolPermissionRuntimeRecord } from "@/lib/types";

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
      void loadData();
    }, [handleSSEEvent, loadData])
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
      <AppSidebar health={health} projects={visibleProjects} />

      <main className="flex-1 pl-[260px]">
        <header className="sticky top-0 z-30 flex h-[52px] items-center justify-between border-b border-[#e5e5e3] bg-white px-6">
          <div>
            <h1 className="text-[15px] font-semibold tracking-[-0.02em] text-[#1a1a1a]">Projects</h1>
            <p className="mt-0.5 text-[12px] text-[#9b9a97]">
              Portfolio view for active workspaces and live runs.
            </p>
          </div>
          {health && (
            <div className="flex items-center gap-2 text-[13px]">
              <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
              <span className="tabular-nums text-[#787774]">{health.available} agents available</span>
            </div>
          )}
        </header>

        <div className="px-6 py-6">
          {message && (
            <div className="mb-4 rounded-xl border border-[#e5e5e3] bg-white px-4 py-3 text-[13px] text-[#6b6b6b]">
              {message}
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
