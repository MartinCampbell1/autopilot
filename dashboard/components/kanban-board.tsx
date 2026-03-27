"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { StoryCard } from "./story-card";
import type { ProjectDetail, StoryStatus } from "@/lib/types";

const COLUMNS: Array<{ key: StoryStatus; label: string; emptyText: string }> = [
  { key: "open", label: "Open", emptyText: "No open stories" },
  { key: "in_progress", label: "In Progress", emptyText: "Nothing running" },
  { key: "done", label: "Done", emptyText: "Nothing completed" },
  { key: "stuck", label: "Stuck", emptyText: "All clear" },
];

interface KanbanBoardProps {
  project: ProjectDetail;
  selectedStoryId?: number | null;
  onStoryClick?: (storyId: number) => void;
  className?: string;
}

export function KanbanBoard({ project, selectedStoryId, onStoryClick, className }: KanbanBoardProps) {
  return (
    <div className={className}>
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-4">
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
              <ScrollArea className="h-[calc(100vh-260px)] min-h-[200px]">
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
