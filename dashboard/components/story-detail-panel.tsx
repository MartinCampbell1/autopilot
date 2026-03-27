"use client";

import { useEffect, useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Separator } from "@/components/ui/separator";
import { ActionButtons } from "./action-buttons";
import { fetchProject } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Story, StoryStatus } from "@/lib/types";

const STATUS_STYLES: Record<StoryStatus, string> = {
  open: "bg-neutral-100 text-neutral-600",
  in_progress: "bg-blue-50 text-blue-600",
  done: "bg-emerald-50 text-emerald-600",
  stuck: "bg-red-50 text-red-600",
  skipped: "bg-neutral-100 text-neutral-500",
};

const STATUS_LABELS: Record<StoryStatus, string> = {
  open: "Open",
  in_progress: "In Progress",
  done: "Done",
  stuck: "Stuck",
  skipped: "Skipped",
};

interface StoryDetailPanelProps {
  story: Story | null;
  projectName: string;
  open: boolean;
  onClose: () => void;
  onAction?: () => void;
}

export function StoryDetailPanel({
  story,
  projectName,
  open,
  onClose,
  onAction,
}: StoryDetailPanelProps) {
  const [criticFeedback, setCriticFeedback] = useState<string>("");

  useEffect(() => {
    if (!open || !projectName) return;

    fetchProject(projectName)
      .then((data) => {
        setCriticFeedback(data.progress || "");
      })
      .catch(() => setCriticFeedback(""));
  }, [open, projectName]);

  if (!story) return null;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="w-[420px] overflow-y-auto border-l border-border/40 bg-white p-0 sm:max-w-[420px]">
        <SheetHeader className="px-5 pt-5 pb-0">
          <div className="flex items-start justify-between gap-3">
            <div className="space-y-1">
              <SheetTitle className="text-[15px] font-semibold leading-snug tracking-[-0.01em]">
                {story.title}
              </SheetTitle>
              <span className="text-[11px] tabular-nums text-muted-foreground">
                #{story.id}
              </span>
            </div>
            <span
              className={cn(
                "mt-0.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium",
                STATUS_STYLES[story.status]
              )}
            >
              {STATUS_LABELS[story.status]}
            </span>
          </div>
        </SheetHeader>

        <div className="px-5 py-4 space-y-5">
          {/* Description */}
          {story.description && (
            <div>
              <h4 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-1.5">
                Description
              </h4>
              <p className="text-[13px] leading-relaxed text-foreground/80">
                {story.description}
              </p>
            </div>
          )}

          {/* Agent info */}
          {story.agent && (
            <>
              <Separator className="bg-border/40" />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Agent
                  </span>
                  <p className="mt-0.5 text-[13px] font-medium">{story.agent}</p>
                </div>
                {story.iteration !== undefined && (
                  <div>
                    <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Iteration
                    </span>
                    <p className="mt-0.5 text-[13px] font-medium tabular-nums">
                      {story.iteration}
                    </p>
                  </div>
                )}
                {story.elapsed_min !== undefined && (
                  <div>
                    <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Elapsed
                    </span>
                    <p className="mt-0.5 text-[13px] font-medium tabular-nums">
                      {story.elapsed_min} min
                    </p>
                  </div>
                )}
              </div>
            </>
          )}

          {/* Critic feedback */}
          {criticFeedback && (
            <>
              <Separator className="bg-border/40" />
              <div>
                <h4 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                  Progress Notes
                </h4>
                <div className="rounded-lg bg-secondary/50 p-3">
                  <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/70 font-mono">
                    {criticFeedback}
                  </pre>
                </div>
              </div>
            </>
          )}

          {/* Actions */}
          <Separator className="bg-border/40" />
          <div>
            <h4 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground mb-2.5">
              Actions
            </h4>
            <ActionButtons
              projectName={projectName}
              storyId={story.id}
              onAction={onAction}
            />
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
