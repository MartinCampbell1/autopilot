"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { PortfolioProjectCard } from "@/components/portfolio-project-card";
import { archiveProject, fetchAccountsHealth, fetchProjects, launchProject, pauseProject, resumeProject } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import type { AccountHealth, ProjectSummary } from "@/lib/types";

export default function DashboardPage() {
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [busyProjectId, setBusyProjectId] = useState<string>("");
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

  useSSE(
    useCallback(() => {
      void loadData();
    }, [loadData])
  );

  const visibleProjects = useMemo(
    () => projects.filter((project) => !project.archived),
    [projects]
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
              {visibleProjects.map((project) => (
                <PortfolioProjectCard
                  key={project.id}
                  project={project}
                  busy={busyProjectId === project.id}
                  onLaunch={() => {
                    const fn = project.status === "paused"
                      ? () => resumeProject(project.id)
                      : () => launchProject(project.id);
                    void runAction(project.id, fn);
                  }}
                  onPause={() => {
                    void runAction(project.id, () => pauseProject(project.id));
                  }}
                  onArchive={() => {
                    void runAction(project.id, () => archiveProject(project.id));
                  }}
                />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
