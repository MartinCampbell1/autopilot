"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export function QueueGroupControls({
  title,
  detail,
  openCount,
  totalCount,
  onExpandAll,
  onCollapseAll,
  onOpenCurrent,
  canOpenCurrent,
}: {
  title: string;
  detail: string;
  openCount: number;
  totalCount: number;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  onOpenCurrent: () => void;
  canOpenCurrent: boolean;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
      <div>
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          {title}
        </p>
        <p className="mt-1 text-[12px] text-[#787774]">{detail}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge
          variant="outline"
          className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
        >
          {openCount}/{totalCount} open
        </Badge>
        <Button
          size="sm"
          variant="outline"
          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
          onClick={onExpandAll}
          disabled={openCount >= totalCount}
        >
          Expand all
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
          onClick={onCollapseAll}
          disabled={!openCount}
        >
          Collapse all
        </Button>
        <Button
          size="sm"
          variant="outline"
          className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
          onClick={onOpenCurrent}
          disabled={!canOpenCurrent}
        >
          Open current queue
        </Button>
      </div>
    </div>
  );
}

export function CollapsibleQueuePanel({
  title,
  detail,
  expanded,
  onToggle,
  collapsedSummary,
  emptyText,
  isEmpty,
  badge,
  actions,
  children,
  className = "rounded-xl border border-[#ecebe8] bg-white p-3",
}: {
  title: string;
  detail: string;
  expanded: boolean;
  onToggle: () => void;
  collapsedSummary: string;
  emptyText: string;
  isEmpty: boolean;
  badge?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            {title}
          </p>
          <p className="mt-1 text-[12px] text-[#787774]">{detail}</p>
        </div>
        <div className="flex items-center gap-2">
          {badge}
          {actions}
          <Button
            size="sm"
            variant="outline"
            className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
            onClick={onToggle}
          >
            {expanded ? "Collapse" : "Expand"}
          </Button>
        </div>
      </div>
      {!expanded ? (
        <p className="mt-3 text-[12px] text-[#9b9a97]">{collapsedSummary}</p>
      ) : isEmpty ? (
        <p className="mt-3 text-[12px] text-[#9b9a97]">{emptyText}</p>
      ) : (
        children
      )}
    </div>
  );
}

export function QueueItemCard({
  title,
  subtitle,
  timestamp,
  selected,
  badges,
  actions,
  className = "rounded-xl border p-3",
  selectedClassName = "border-[#d3e5ef] bg-[#f7fbfd]",
  unselectedClassName = "border-[#ecebe8] bg-[#fbfbf9]",
  subtitleClassName = "mt-2 text-[12px] text-[#787774]",
  badgeRowClassName = "mt-3 flex flex-wrap gap-2",
  actionRowClassName = "mt-3 flex flex-wrap gap-2",
}: {
  title: string;
  subtitle: string;
  timestamp: string;
  selected: boolean;
  badges?: ReactNode;
  actions?: ReactNode;
  className?: string;
  selectedClassName?: string;
  unselectedClassName?: string;
  subtitleClassName?: string;
  badgeRowClassName?: string;
  actionRowClassName?: string;
}) {
  return (
    <div className={`${className} ${selected ? selectedClassName : unselectedClassName}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[13px] font-semibold text-[#37352f]">{title}</p>
          <p className={subtitleClassName}>{subtitle}</p>
        </div>
        <p className="text-[11px] text-[#9b9a97]">{timestamp}</p>
      </div>
      {badges ? <div className={badgeRowClassName}>{badges}</div> : null}
      {actions ? <div className={actionRowClassName}>{actions}</div> : null}
    </div>
  );
}
