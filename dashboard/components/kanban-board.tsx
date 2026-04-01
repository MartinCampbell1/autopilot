"use client";

import { ScrollArea } from "@/components/ui/scroll-area";
import { StoryCard } from "./story-card";
import type { ProjectDetail, StoryStatus } from "@/lib/types";

const COLUMNS: Array<{ key: StoryStatus; label: string; emptyText: string }> = [
  { key: "open", label: "Open", emptyText: "No open stories" },
  { key: "in_progress", label: "In Progress", emptyText: "Nothing running" },
  { key: "done", label: "Done", emptyText: "Nothing completed" },
  { key: "stuck", label: "Stuck", emptyText: "All clear" },
  { key: "merge_blocked", label: "Merge Blocked", emptyText: "No merge issues" },
];

interface KanbanBoardProps {
  project: ProjectDetail;
  selectedStoryId?: number | null;
  onStoryClick?: (storyId: number) => void;
  className?: string;
}

function sentenceCase(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "Unknown";
}

function taskSourceLabel(project: ProjectDetail) {
  const taskSource = project.task_source;
  if (!taskSource) return "Task source not recorded";
  return [taskSource.source_kind, taskSource.external_id, taskSource.repo].filter(Boolean).join(" / ");
}

export function KanbanBoard({ project, selectedStoryId, onStoryClick, className }: KanbanBoardProps) {
  const deliveryLoop = project.delivery_loop;
  const deliveryStatus = project.delivery_status;
  const handoffArtifact = deliveryLoop?.artifact;
  const handoffLabel = handoffArtifact?.ref_label
    || (deliveryLoop?.handoff?.number
      ? `PR #${deliveryLoop.handoff.number}`
      : deliveryLoop?.handoff?.head_branch || "No handoff yet");
  const lastEvent = deliveryLoop?.run?.last_event;

  return (
    <div className={className}>
      <div className="mb-4 rounded-2xl border border-[#e5e5e3] bg-white p-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Delivery Loop</p>
            <h2 className="mt-1 text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
              {deliveryStatus?.headline || "Source to handoff"}
            </h2>
            <p className="mt-2 max-w-3xl text-[13px] leading-relaxed text-[#6b6b6b]">
              {deliveryStatus?.detail || "Track the path from source item to final PR or handoff artifact."}
            </p>
          </div>
          <div className="min-w-[220px] rounded-xl border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Next step</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">
              {deliveryStatus?.next_step || "Keep the project moving toward handoff."}
            </p>
            <p className="mt-2 text-[12px] text-[#787774]">
              {sentenceCase(deliveryStatus?.stage)} / {sentenceCase(deliveryStatus?.status)}
            </p>
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Source</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{taskSourceLabel(project)}</p>
            <p className="mt-2 text-[12px] text-[#787774]">
              Branch policy: {project.task_source?.branch_policy || "shared_main"}
            </p>
          </div>

          <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Brief</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">
              {deliveryLoop?.brief?.title || "No brief title"}
            </p>
            <p className="mt-2 break-all text-[12px] text-[#787774]">
              {deliveryLoop?.brief?.relpath || "No brief reference"}
            </p>
          </div>

          <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Execution</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">
              {sentenceCase(deliveryLoop?.run?.status)}
            </p>
            <p className="mt-2 text-[12px] text-[#787774]">
              {deliveryLoop?.run?.current_story_title || "No story active"}
            </p>
            <p className="mt-1 line-clamp-2 text-[12px] text-[#787774]">
              {lastEvent?.message || "No run event recorded yet."}
            </p>
          </div>

          <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Handoff</p>
            <p className="mt-1 text-[13px] font-medium text-[#37352f]">{handoffLabel}</p>
            <p className="mt-2 text-[12px] text-[#787774]">
              {sentenceCase(deliveryLoop?.handoff?.handoff_status)} / {sentenceCase(deliveryLoop?.handoff?.merge_state)}
            </p>
            <p className="mt-1 line-clamp-2 break-all text-[12px] text-[#787774]">
              {handoffArtifact?.path || deliveryLoop?.handoff?.url || "No artifact recorded yet."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-5">
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
