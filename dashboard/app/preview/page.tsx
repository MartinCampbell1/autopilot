"use client";

import { useState } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { KanbanBoard } from "@/components/kanban-board";
import { StoryDetailPanel } from "@/components/story-detail-panel";
import type { Project, AccountHealth, Story } from "@/lib/types";

const MOCK_HEALTH: AccountHealth = {
  total: 12,
  available: 9,
  on_cooldown: 3,
};

const MOCK_PROJECTS: Project[] = [
  {
    name: "trading-dashboard",
    path: "/Users/example/projects/trading-dashboard",
    priority: "high",
    stories_done: 4,
    stories_total: 8,
    stories: [
      { id: 1, title: "Set up Next.js project with Tailwind CSS and shadcn/ui", description: "Initialize project scaffold", status: "done" },
      { id: 2, title: "Build real-time price chart with WebSocket feed", description: "Connect to Binance WS API", status: "done", agent: "codex-3", iteration: 2, elapsed_min: 14 },
      { id: 3, title: "Implement portfolio balance widget", description: "Show total balance and P&L", status: "done" },
      { id: 4, title: "Create order entry form with validation", description: "Market and limit orders", status: "done", agent: "claude-1", iteration: 1, elapsed_min: 8 },
      { id: 5, title: "Add trade history table with pagination", description: "Sortable columns, date filters", status: "in_progress", agent: "codex-5", iteration: 3, elapsed_min: 22 },
      { id: 6, title: "Implement watchlist with drag-and-drop reorder", description: "Persist to localStorage", status: "in_progress", agent: "claude-2", iteration: 1, elapsed_min: 5 },
      { id: 7, title: "Add notification system for price alerts", description: "Toast + push notifications", status: "open" },
      { id: 8, title: "Performance optimization and bundle analysis", description: "Target < 200KB initial JS", status: "stuck", agent: "codex-1", iteration: 4, elapsed_min: 35 },
    ],
  },
  {
    name: "api-gateway",
    path: "/Users/example/projects/api-gateway",
    priority: "normal",
    stories_done: 2,
    stories_total: 5,
    stories: [
      { id: 1, title: "Rate limiting middleware with Redis", description: "Sliding window algorithm", status: "done", agent: "codex-2", iteration: 1, elapsed_min: 11 },
      { id: 2, title: "JWT authentication with refresh tokens", description: "RS256 signing, token rotation", status: "done" },
      { id: 3, title: "Request/response logging pipeline", description: "Structured JSON logs to stdout", status: "in_progress", agent: "gemini-1", iteration: 2, elapsed_min: 18 },
      { id: 4, title: "Circuit breaker for downstream services", description: "Configurable thresholds per route", status: "open" },
      { id: 5, title: "API versioning strategy (URL prefix)", description: "v1/v2 routing with deprecation headers", status: "open" },
    ],
  },
];

export default function PreviewPage() {
  const [selectedProject, setSelectedProject] = useState<string>("");
  const [selectedStoryId, setSelectedStoryId] = useState<number | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const handleStoryClick = (projectName: string, storyId: number) => {
    setSelectedProject(projectName);
    setSelectedStoryId(storyId);
    setPanelOpen(true);
  };

  const selectedStory: Story | null = (() => {
    if (!selectedProject || !selectedStoryId) return null;
    const proj = MOCK_PROJECTS.find((p) => p.name === selectedProject);
    return proj?.stories.find((s) => s.id === selectedStoryId) ?? null;
  })();

  return (
    <div className="flex min-h-screen bg-[#fafaf9]">
      <AppSidebar health={MOCK_HEALTH} />

      <main className="flex-1 pl-[240px]">
        <header className="sticky top-0 z-30 flex h-[48px] items-center justify-between border-b border-[#e3e2e0] bg-white px-6">
          <h1 className="text-[14px] font-semibold text-[#37352f]">Projects</h1>
          <div className="flex items-center gap-2 text-[13px]">
            <span className="inline-block h-2 w-2 rounded-full bg-[#2ecc71]" />
            <span className="tabular-nums text-[#787774]">9 agents available</span>
          </div>
        </header>

        <div className="px-6 py-6">
          <div className="space-y-16 divide-y divide-[#e3e2e0]">
            {MOCK_PROJECTS.map((project, i) => (
              <div key={project.name} className={i > 0 ? "pt-12" : ""}>
                <KanbanBoard
                  project={project}
                  selectedStoryId={selectedProject === project.name ? selectedStoryId : null}
                  onStoryClick={(id) => handleStoryClick(project.name, id)}
                />
              </div>
            ))}
          </div>
        </div>
      </main>

      <StoryDetailPanel
        story={selectedStory}
        projectName={selectedProject}
        open={panelOpen}
        onClose={() => { setPanelOpen(false); setSelectedStoryId(null); }}
        onAction={() => {}}
      />
    </div>
  );
}
