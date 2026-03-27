"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AppSidebar } from "@/components/app-sidebar";
import { KanbanBoard } from "@/components/kanban-board";
import { StoryDetailPanel } from "@/components/story-detail-panel";
import { Button } from "@/components/ui/button";
import {
  archiveProject,
  fetchAccountsHealth,
  fetchProject,
  fetchProjects,
  launchProject,
  pauseProject,
  resumeProject,
} from "@/lib/api";
import { useSSE } from "@/lib/sse";
import type { AccountHealth, ProjectDetail, ProjectSummary, Story } from "@/lib/types";

const STATUS_COPY: Record<ProjectDetail["status"], string> = {
  idle: "Idle",
  running: "Running",
  paused: "Paused",
  completed: "Completed",
  failed: "Needs Attention",
};

export default function ProjectWorkspacePage() {
  const params = useParams<{ projectId: string }>();
  const router = useRouter();
  const projectId = String(params.projectId);

  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [projectData, projectsData, healthData] = await Promise.all([
        fetchProject(projectId),
        fetchProjects(false),
        fetchAccountsHealth(),
      ]);
      const detail = projectData as ProjectDetail;
      setProject(detail);
      setProjects((projectsData.projects || []) as ProjectSummary[]);
      setHealth(healthData as AccountHealth);
      setSelectedStoryId((current) => {
        if (current && detail.stories.some((story) => story.id === current)) return current;
        return detail.current_story_id ?? detail.stories[0]?.id ?? null;
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load project.");
    }
  }, [projectId]);

  useEffect(() => {
    void load();
  }, [load]);

  useSSE(
    useCallback((_, data) => {
      if (typeof data === "object" && data && "project_id" in (data as Record<string, unknown>)) {
        if ((data as { project_id?: string }).project_id === projectId) {
          void load();
        }
      } else {
        void load();
      }
    }, [load, projectId])
  );

  const selectedStory: Story | null = useMemo(() => {
    if (!project || !selectedStoryId) return null;
    return project.stories.find((story) => story.id === selectedStoryId) ?? null;
  }, [project, selectedStoryId]);

  const runAction = async (task: () => Promise<{ message: string }>, next?: () => void) => {
    setBusy(true);
    setMessage("");
    try {
      const result = await task();
      setMessage(result.message);
      await load();
      next?.();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!project) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#fafaf9] text-[14px] text-[#787774]">
        Loading workspace...
      </div>
    );
  }

  const progress = project.stories_total > 0
    ? Math.round((project.stories_done / project.stories_total) * 100)
    : 0;

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={health} projects={projects.filter((entry) => !entry.archived)} activeProjectId={projectId} />

      <main className="flex flex-1 pl-[260px]">
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-30 border-b border-[#e5e5e3] bg-white px-6 py-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Workspace</p>
                <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[#37352f]">
                  {project.name}
                </h1>
                <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[#6b6b6b]">
                  {project.description || "No project description provided."}
                </p>
              </div>
              <div className="min-w-[260px] space-y-3 rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <div className="flex items-center justify-between text-[13px]">
                  <span className="text-[#9b9a97]">Run status</span>
                  <span className="font-semibold text-[#37352f]">{STATUS_COPY[project.status]}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-[8px] flex-1 overflow-hidden rounded-full bg-[#ecebe8]">
                    <div className="h-full rounded-full bg-[#37352f]" style={{ width: `${progress}%` }} />
                  </div>
                  <span className="text-[13px] font-semibold text-[#37352f]">{progress}%</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {project.status === "running" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-9 rounded-lg text-[13px]"
                      disabled={busy}
                      onClick={() => {
                        void runAction(() => pauseProject(project.id));
                      }}
                    >
                      Pause
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      className="h-9 rounded-lg bg-[#1a1a1a] text-[13px] hover:bg-[#333]"
                      disabled={busy}
                      onClick={() => {
                        const fn = project.status === "paused"
                          ? () => resumeProject(project.id)
                          : () => launchProject(project.id);
                        void runAction(fn);
                      }}
                    >
                      {project.status === "paused" ? "Resume" : "Launch"}
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-9 rounded-lg text-[13px]"
                    disabled={busy}
                    onClick={() => {
                      void runAction(
                        () => archiveProject(project.id),
                        () => router.push("/")
                      );
                    }}
                  >
                    Archive
                  </Button>
                </div>
              </div>
            </div>
          </header>

          <div className="px-6 py-6">
            {message && (
              <div className="mb-4 rounded-xl border border-[#e5e5e3] bg-white px-4 py-3 text-[13px] text-[#6b6b6b]">
                {message}
              </div>
            )}
            <KanbanBoard
              project={project}
              selectedStoryId={selectedStoryId}
              onStoryClick={setSelectedStoryId}
            />
          </div>
        </div>

        <StoryDetailPanel
          projectId={project.id}
          projectStatus={project.status}
          story={selectedStory}
          timeline={project.timeline}
          guardrails={project.guardrails}
          logTail={project.log_tail}
          onAction={load}
        />
      </main>
    </div>
  );
}
