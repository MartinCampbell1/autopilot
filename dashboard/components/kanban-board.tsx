"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { StoryCard } from "./story-card";
import type { Project, StoryStatus } from "@/lib/types";

const COLUMNS: Array<{ key: StoryStatus; label: string; emptyText: string }> = [
  { key: "open", label: "Open", emptyText: "No open stories" },
  { key: "in_progress", label: "In Progress", emptyText: "Nothing running" },
  { key: "done", label: "Done", emptyText: "Nothing completed" },
  { key: "stuck", label: "Stuck", emptyText: "All clear" },
];

interface KanbanBoardProps {
  project: Project;
  selectedStoryId?: number | null;
  onStoryClick?: (storyId: number) => void;
}

export function KanbanBoard({ project, selectedStoryId, onStoryClick }: KanbanBoardProps) {
  const progress = project.stories_total > 0
    ? Math.round((project.stories_done / project.stories_total) * 100)
    : 0;

  return (
    <div>
      {/* Project header */}
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[22px] font-semibold tracking-[-0.02em] text-[#37352f]">
            {project.name}
          </h2>
          <span className="text-[14px] text-[#c3c2bf]">
            {project.stories_done} of {project.stories_total}
          </span>
        </div>

        {/* Progress bar */}
        <div className="flex items-center gap-3">
          <div className="h-[6px] w-36 rounded-full bg-[#e3e2e0] overflow-hidden">
            <div
              className="h-[6px] rounded-full bg-[#37352f] transition-all duration-700 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <span className="text-[14px] font-semibold tabular-nums text-[#37352f]">
            {progress}%
          </span>
        </div>
      </div>

      {/* Columns */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {COLUMNS.map((col) => {
          const stories = project.stories.filter((s) => s.status === col.key);
          return (
            <div
              key={col.key}
              className="min-w-0 rounded-xl bg-[#f1f1ef] p-3"
            >
              {/* Column header */}
              <div className="mb-3 flex items-center justify-between px-1">
                <span className="text-[12px] font-medium uppercase tracking-[0.06em] text-[#9b9a97]">
                  {col.label}
                  <span className="ml-1.5 text-[#c3c2bf]">{stories.length}</span>
                </span>
              </div>

              {/* Cards */}
              <ScrollArea className="h-[calc(100vh-300px)] min-h-[200px]">
                <div className="space-y-3">
                  {stories.length === 0 ? (
                    <div className="flex items-center justify-center rounded-lg border border-dashed border-[#e3e2e0] py-12">
                      <span className="text-[13px] text-[#c3c2bf]">
                        {col.emptyText}
                      </span>
                    </div>
                  ) : (
                    stories.map((story) => (
                      <StoryCard
                        key={story.id}
                        story={story}
                        isSelected={selectedStoryId === story.id}
                        onClick={() => onStoryClick?.(story.id)}
                      />
                    ))
                  )}
                </div>
              </ScrollArea>
            </div>
          );
        })}
      </div>
    </div>
  );
}
