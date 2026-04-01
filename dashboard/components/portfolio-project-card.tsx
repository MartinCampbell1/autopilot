"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import type { ProjectSummary } from "@/lib/types";

const STATUS_LABELS: Record<ProjectSummary["status"], string> = {
  idle: "Idle",
  running: "Running",
  paused: "Paused",
  completed: "Completed",
  failed: "Needs Attention",
};

const STATUS_STYLES: Record<ProjectSummary["status"], string> = {
  idle: "bg-[#f1f1ef] text-[#787774]",
  running: "bg-[#d3e5ef] text-[#2a6690]",
  paused: "bg-[#fdecc8] text-[#8f5500]",
  completed: "bg-[#dbeddb] text-[#2b6e3f]",
  failed: "bg-[#ffe2dd] text-[#93370d]",
};

interface PortfolioProjectCardProps {
  project: ProjectSummary;
  busy?: boolean;
  interruptBusy?: boolean;
  interruptStateLabel?: string;
  onLaunch?: () => void;
  onPause?: () => void;
  onInterrupt?: () => void;
  onArchive?: () => void;
}

function formatTimestamp(value?: string | null) {
  if (!value) return "No activity yet";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatTaskSource(project: ProjectSummary) {
  const taskSource = project.task_source;
  if (!taskSource) return "Task source not recorded";
  const parts = [taskSource.source_kind];
  if (taskSource.external_id) parts.push(taskSource.external_id);
  if (taskSource.repo) parts.push(taskSource.repo);
  return parts.filter(Boolean).join(" / ");
}

function formatPhrase(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "unknown";
}

export function PortfolioProjectCard({
  project,
  busy = false,
  interruptBusy = false,
  interruptStateLabel = "",
  onLaunch,
  onPause,
  onInterrupt,
  onArchive,
}: PortfolioProjectCardProps) {
  const progress = project.stories_total > 0
    ? Math.round((project.stories_done / project.stories_total) * 100)
    : 0;
  const deliveryStatus = project.delivery_status;
  const handoffArtifact = project.delivery_loop?.artifact;
  const handoffTitle = handoffArtifact?.ref_label
    || (project.latest_handoff?.number
      ? `PR #${project.latest_handoff.number}`
      : project.latest_handoff?.head_branch || project.latest_handoff?.story_title || "");

  return (
    <article className="rounded-[14px] border border-[#e5e5e3] bg-white p-5 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
            {project.name}
          </h2>
          <p className="mt-2 max-w-xl text-[13px] text-[#6b6b6b]">
            {project.current_story_title
              ? `Current story: ${project.current_story_title}`
              : "No story currently active."}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-[12px] font-semibold ${STATUS_STYLES[project.status]}`}>
          {STATUS_LABELS[project.status]}
        </span>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-[1.5fr_1fr]">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-[8px] flex-1 overflow-hidden rounded-full bg-[#ecebe8]">
              <div
                className="h-full rounded-full bg-[#37352f] transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-[13px] font-semibold text-[#37352f]">{progress}%</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-[12px] text-[#9b9a97]">
            <span>{project.stories_done}/{project.stories_total} stories done</span>
            <span>•</span>
            <span>{formatTimestamp(project.last_activity_at)}</span>
          </div>
          <div className="mt-3 grid gap-3 md:grid-cols-3">
            <div className="rounded-[10px] border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Task source</p>
              <p className="mt-1 text-[13px] font-medium text-[#37352f]">{formatTaskSource(project)}</p>
              <p className="mt-2 text-[12px] text-[#787774]">
                Branch policy: {project.task_source?.branch_policy || "shared_main"}
              </p>
            </div>
            <div className="rounded-[10px] border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Delivery loop</p>
              {deliveryStatus ? (
                <>
                  <p className="mt-1 text-[13px] font-medium text-[#37352f]">{deliveryStatus.headline}</p>
                  <p className="mt-2 text-[12px] text-[#787774]">
                    {formatPhrase(deliveryStatus.stage)} / {formatPhrase(deliveryStatus.status)}
                  </p>
                  <p className="mt-1 text-[12px] text-[#787774]">{deliveryStatus.next_step}</p>
                </>
              ) : (
                <p className="mt-1 text-[12px] text-[#787774]">
                  Delivery state has not been synthesized yet.
                </p>
              )}
            </div>
            <div className="rounded-[10px] border border-[#ecebe8] bg-[#fbfbf9] px-3 py-3">
              <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Latest handoff</p>
              {project.latest_handoff ? (
                <>
                  <p className="mt-1 text-[13px] font-medium text-[#37352f]">
                    {handoffTitle}
                  </p>
                  <p className="mt-2 text-[12px] text-[#787774]">
                    {project.latest_handoff.handoff_status} / {project.latest_handoff.merge_state}
                  </p>
                  <p className="mt-1 text-[12px] text-[#787774]">
                    Review: {project.latest_handoff.review_status} - CI: {project.latest_handoff.ci_status}
                  </p>
                  {handoffArtifact?.path && (
                    <p className="mt-1 line-clamp-2 break-all text-[12px] text-[#787774]">
                      Artifact: {handoffArtifact.path}
                    </p>
                  )}
                </>
              ) : (
                <p className="mt-1 text-[12px] text-[#787774]">
                  No PR or handoff artifact recorded yet.
                </p>
              )}
            </div>
          </div>
          {project.last_message && (
            <p className="mt-3 line-clamp-2 text-[13px] leading-relaxed text-[#6b6b6b]">
              {project.last_message}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-start justify-end gap-2">
          <Link
            href={`/projects/${project.id}`}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[13px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
          >
            Open
          </Link>
          {project.status === "running" ? (
            <Button
              size="sm"
              variant="outline"
              className="h-9 rounded-lg text-[13px]"
              disabled={busy}
              onClick={onPause}
            >
              Pause
            </Button>
          ) : (
            <Button
              size="sm"
              className="h-9 rounded-lg bg-[#1a1a1a] text-[13px] hover:bg-[#333]"
              disabled={busy}
              onClick={onLaunch}
            >
              {project.status === "paused" ? "Resume" : "Launch"}
            </Button>
          )}
          {project.status === "running" && project.runtime_control_available && onInterrupt ? (
            <Button
              size="sm"
              variant="outline"
              className="h-9 rounded-lg text-[13px]"
              disabled={busy || interruptBusy}
              onClick={onInterrupt}
            >
              {interruptBusy ? "Interrupting..." : "Interrupt"}
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            className="h-9 rounded-lg text-[13px] text-[#93370d] hover:bg-[#fff2ef] hover:text-[#93370d]"
            disabled={busy}
            onClick={onArchive}
          >
            Archive
          </Button>
          {interruptStateLabel ? (
            <p className="w-full text-right text-[11px] text-[#787774]">
              {interruptStateLabel}
            </p>
          ) : null}
        </div>
      </div>
    </article>
  );
}
