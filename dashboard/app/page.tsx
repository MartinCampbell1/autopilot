"use client";

import { useEffect, useState, useCallback } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { KanbanBoard } from "@/components/kanban-board";
import { StoryDetailPanel } from "@/components/story-detail-panel";
import { fetchProjects, fetchAccountsHealth } from "@/lib/api";
import { useSSE } from "@/lib/sse";
import type { Project, AccountHealth, Story } from "@/lib/types";

export default function DashboardPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<AccountHealth | null>(null);
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [projData, healthData] = await Promise.all([
        fetchProjects(),
        fetchAccountsHealth(),
      ]);
      setProjects(projData.projects || []);
      setHealth(healthData);
    } catch {
      // API not available yet
    }
  }, []);

  useEffect(() => {
    const initialLoad = setTimeout(() => {
      void loadData();
    }, 0);
    const interval = setInterval(() => {
      void loadData();
    }, 10000);
    return () => {
      clearTimeout(initialLoad);
      clearInterval(interval);
    };
  }, [loadData]);

  useSSE(
    useCallback(() => {
      void loadData();
    }, [loadData])
  );

  const handleStoryClick = (projectName: string, storyId: number) => {
    setSelectedProject(projectName);
    setSelectedStoryId(storyId);
    setPanelOpen(true);
  };

  const selectedStory: Story | null = (() => {
    if (!selectedProject || !selectedStoryId) return null;
    const proj = projects.find((p) => p.name === selectedProject);
    return proj?.stories.find((s) => s.id === selectedStoryId) ?? null;
  })();

  return (
    <div className="flex min-h-screen bg-[#fbfbf9]">
      <AppSidebar health={health} />

      <main className="flex-1 pl-[240px]">
        <header className="sticky top-0 z-30 flex h-[48px] items-center justify-between border-b border-[#e3e2e0] bg-white px-6">
          <h1 className="text-[14px] font-semibold text-[#37352f]">Projects</h1>
          <div className="flex items-center gap-3">
            {health && (
              <div className="flex items-center gap-2 text-[13px]">
                <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
                <span className="tabular-nums text-[#787774]">{health.available} agents available</span>
              </div>
            )}
          </div>
        </header>

        <div className="px-6 py-6">
          {projects.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-secondary">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground">
                  <rect x="3" y="3" width="7" height="7" rx="1" />
                  <rect x="14" y="3" width="7" height="7" rx="1" />
                  <rect x="3" y="14" width="7" height="7" rx="1" />
                  <rect x="14" y="14" width="7" height="7" rx="1" />
                </svg>
              </div>
              <h3 className="text-[15px] font-semibold">No projects yet</h3>
              <p className="mt-1 text-[13px] text-muted-foreground max-w-sm">
                Add projects to ~/.autopilot/projects.yaml or create a new one via the Intake chat.
              </p>
            </div>
          ) : (
            <div className="space-y-16 divide-y divide-[#e3e2e0]">
              {projects.map((project) => (
                <KanbanBoard
                  key={project.name}
                  project={project}
                  selectedStoryId={
                    selectedProject === project.name ? selectedStoryId : null
                  }
                  onStoryClick={(id) => handleStoryClick(project.name, id)}
                />
              ))}
            </div>
          )}
        </div>
      </main>

      {/* Story detail slide-out */}
      <StoryDetailPanel
        story={selectedStory}
        projectName={selectedProject}
        open={panelOpen}
        onClose={() => {
          setPanelOpen(false);
          setSelectedStoryId(null);
        }}
        onAction={loadData}
      />
    </div>
  );
}
