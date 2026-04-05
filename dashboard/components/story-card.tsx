"use client";

import { cn } from "@/lib/utils";
import type { Story, StoryStatus } from "@/lib/types";

const STATUS_CONFIG: Record<StoryStatus, { label: string; badge: string }> = {
  open: { label: "Open", badge: "bg-[#f1f1ef] text-[#787774]" },
  in_progress: { label: "In Progress", badge: "bg-[#d3e5ef] text-[#2a6690]" },
  done: { label: "Done", badge: "bg-[#dbeddb] text-[#2b6e3f]" },
  stuck: { label: "Stuck", badge: "bg-[#ffe2dd] text-[#93370d]" },
  skipped: { label: "Skipped", badge: "bg-[#f1f1ef] text-[#9b9b97]" },
  merge_blocked: { label: "Merge Blocked", badge: "bg-[#fff1cc] text-[#9a6700]" },
};

interface StoryCardProps {
  story: Story;
  onClick?: () => void;
  isSelected?: boolean;
  runtimeHandoffSummary?: {
    runtimeAgentCount: number;
    blockedHandoffCount: number;
    openShadowAuditCount: number;
  } | null;
}

export function StoryCard({ story, onClick, isSelected, runtimeHandoffSummary }: StoryCardProps) {
  const cfg = STATUS_CONFIG[story.status] || STATUS_CONFIG.open;
  const updated = story.updated_at
    ? new Intl.DateTimeFormat("en", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(story.updated_at))
    : null;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group w-full text-left rounded-[8px] bg-white transition-all duration-150",
        "px-5 py-4",
        "border border-[rgba(15,15,15,0.04)]",
        "shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]",
        "hover:shadow-[0_4px_12px_rgba(15,15,15,0.1),0_0_1px_rgba(15,15,15,0.04)] hover:-translate-y-px",
        runtimeHandoffSummary?.openShadowAuditCount
          ? "border-[#f4e0c4] bg-[#fffdf8] shadow-[0_1px_3px_rgba(154,103,0,0.1),0_0_1px_rgba(154,103,0,0.08)]"
          : null,
        isSelected && "ring-2 ring-[#2563eb]/25 shadow-[0_4px_12px_rgba(15,15,15,0.1)]"
      )}
    >
      {/* Title — 14px medium, primary text */}
      <p className="text-[14px] font-medium leading-[1.55] text-[#37352f]">
        {story.title}
      </p>

      {/* Metadata pills */}
      {(story.agent || story.iteration !== undefined || updated || story.team_mode || story.connector_activation?.length) && (
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
          {updated && (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium tabular-nums">
              {updated}
            </span>
          )}
          {story.team_mode && (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium">
              {story.team_mode}
            </span>
          )}
          {story.connector_activation?.length ? (
            <span className="rounded-[4px] bg-[#f1f1ef] px-2.5 py-[3px] text-[11px] text-[#6b6b6b] font-medium">
              {story.connector_activation.filter((item) => item.status === "active").length} active tools
            </span>
          ) : null}
          {runtimeHandoffSummary?.blockedHandoffCount ? (
            <span className="rounded-[4px] bg-[#fff1cc] px-2.5 py-[3px] text-[11px] font-medium text-[#9a6700]">
              handoff blocked
            </span>
          ) : null}
          {runtimeHandoffSummary?.openShadowAuditCount ? (
            <span className="rounded-[4px] bg-[#fff6e8] px-2.5 py-[3px] text-[11px] font-medium text-[#9a6700]">
              {runtimeHandoffSummary.openShadowAuditCount} shadow audit
              {runtimeHandoffSummary.openShadowAuditCount === 1 ? "" : "s"}
            </span>
          ) : null}
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
