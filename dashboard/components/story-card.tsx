"use client";

import { cn } from "@/lib/utils";
import type { Story, StoryStatus } from "@/lib/types";

const STATUS_CONFIG: Record<StoryStatus, { label: string; badge: string }> = {
  open: { label: "Open", badge: "bg-[#f1f1ef] text-[#787774]" },
  in_progress: { label: "In Progress", badge: "bg-[#d3e5ef] text-[#2a6690]" },
  done: { label: "Done", badge: "bg-[#dbeddb] text-[#2b6e3f]" },
  stuck: { label: "Stuck", badge: "bg-[#ffe2dd] text-[#93370d]" },
  skipped: { label: "Skipped", badge: "bg-[#f1f1ef] text-[#9b9b97]" },
};

interface StoryCardProps {
  story: Story;
  onClick?: () => void;
  isSelected?: boolean;
}

export function StoryCard({ story, onClick, isSelected }: StoryCardProps) {
  const cfg = STATUS_CONFIG[story.status] || STATUS_CONFIG.open;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group w-full text-left rounded-[8px] bg-white transition-all duration-150",
        "px-5 py-4",
        "border border-[rgba(15,15,15,0.04)]",
        "shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]",
        "hover:shadow-[0_4px_12px_rgba(15,15,15,0.1),0_0_1px_rgba(15,15,15,0.04)] hover:-translate-y-px",
        isSelected && "ring-2 ring-[#2563eb]/25 shadow-[0_4px_12px_rgba(15,15,15,0.1)]"
      )}
    >
      {/* Title — 14px medium, primary text */}
      <p className="text-[14px] font-medium leading-[1.55] text-[#37352f]">
        {story.title}
      </p>

      {/* Metadata pills */}
      {(story.agent || story.iteration !== undefined || story.elapsed_min !== undefined) && (
        <div className="mt-2.5 flex items-center gap-1.5 flex-wrap">
          {story.agent && (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium">
              {story.agent}
            </span>
          )}
          {story.iteration !== undefined && (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium tabular-nums">
              iter {story.iteration}
            </span>
          )}
          {story.elapsed_min !== undefined && (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium tabular-nums">
              {story.elapsed_min}m
            </span>
          )}
        </div>
      )}

      {/* Status badge — always bottom-right */}
      <div className="mt-2.5 flex justify-end">
        <span className={cn(
          "rounded-[4px] px-2.5 py-[3px] text-[12px] font-medium",
          cfg.badge
        )}>
          {cfg.label}
        </span>
      </div>
    </button>
  );
}
