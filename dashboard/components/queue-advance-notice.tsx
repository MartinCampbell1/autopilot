"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export type QueueAdvanceSignal = {
  key: string;
  label: string;
  className: string;
  focusFilter?: string;
};

export type QueueAdvanceReasonDetails = {
  priority: "critical" | "high" | "normal";
  reason: string;
  signals: QueueAdvanceSignal[];
};

export type QueueAdvanceFeedback<TTarget = unknown> = {
  title: string;
  detail: string;
  timestamp: string;
  nextTarget?: TTarget | null;
  previousTarget?: TTarget | null;
  reason?: string;
  reasonPriority?: "critical" | "high" | "normal";
  signals?: QueueAdvanceSignal[];
};

export type QueueAdvanceFocusSummary = {
  label: string;
  detail: string;
  activeFilter: string;
  badgeClassName: string;
};

export type QueueAdvanceFocusDelta = {
  fromLabel: string;
  toLabel: string;
  fromCount: number;
  toCount: number;
  timestamp: string;
};

export type QueueAdvanceNoticeActionProps = {
  onOpenSelectedNext?: (() => void) | undefined;
  onReopenPrevious?: (() => void) | undefined;
  onSignalClick?: ((signal: QueueAdvanceSignal) => void) | undefined;
  onResetFocus?: (() => void) | undefined;
  onOpenMatchingQueue?: (() => void) | undefined;
};

type QueueAdvanceNoticeProps<TTarget = unknown> = {
  label: string;
  feedback: QueueAdvanceFeedback<TTarget> | null;
  onOpenSelectedNext?: (() => void) | undefined;
  onReopenPrevious?: (() => void) | undefined;
  onSignalClick?: ((signal: QueueAdvanceSignal) => void) | undefined;
  focusSummary?: QueueAdvanceFocusSummary | null;
  focusDelta?: QueueAdvanceFocusDelta | null;
  onResetFocus?: (() => void) | undefined;
  onOpenMatchingQueue?: (() => void) | undefined;
};

function formatTimestamp(value: string): string {
  if (!value) return "n/a";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function triagePriorityClass(priority: "critical" | "high" | "normal"): string {
  switch (priority) {
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "high":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function triagePriorityLabel(priority: "critical" | "high" | "normal"): string {
  switch (priority) {
    case "critical":
      return "Critical";
    case "high":
      return "High";
    default:
      return "Normal";
  }
}

function queueFocusDeltaChangeLabel(delta: QueueAdvanceFocusDelta): string {
  const change = delta.toCount - delta.fromCount;
  if (change > 0) return `+${change} visible`;
  if (change < 0) return `${change} visible`;
  return "No change";
}

function queueFocusDeltaBadgeClass(delta: QueueAdvanceFocusDelta): string {
  const change = delta.toCount - delta.fromCount;
  if (change > 0) return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
  if (change < 0) return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
  return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
}

export function QueueAdvanceNotice<TTarget = unknown>({
  label,
  feedback,
  onOpenSelectedNext,
  onReopenPrevious,
  onSignalClick,
  focusSummary,
  focusDelta,
  onResetFocus,
  onOpenMatchingQueue,
}: QueueAdvanceNoticeProps<TTarget>) {
  if (!feedback) return null;

  return (
    <div className="rounded-xl border border-[#d3e5ef] bg-[#eef7fb] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#2a6690]">
          {label}
        </p>
        <p className="text-[11px] text-[#5d7c92]">{formatTimestamp(feedback.timestamp)}</p>
      </div>
      <p className="mt-2 text-[13px] font-semibold text-[#214d69]">{feedback.title}</p>
      <p className="mt-1 text-[12px] text-[#46667d]">{feedback.detail}</p>
      {feedback.reason ? (
        <div className="mt-3 rounded-lg border border-[#cfe2ee] bg-white/80 p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5d7c92]">
              Why this next item
            </p>
            {feedback.reasonPriority ? (
              <Badge
                variant="outline"
                className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${triagePriorityClass(feedback.reasonPriority)}`}
              >
                {triagePriorityLabel(feedback.reasonPriority)}
              </Badge>
            ) : null}
          </div>
          {feedback.signals?.length ? (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {feedback.signals.map((signal) => (
                <button
                  key={signal.key}
                  type="button"
                  className={`rounded-full border px-2 py-0.5 text-[10px] font-medium transition hover:opacity-90 ${signal.className} ${
                    onSignalClick && signal.focusFilter ? "cursor-pointer" : "cursor-default"
                  } ${
                    focusSummary?.activeFilter && signal.focusFilter === focusSummary.activeFilter
                      ? "ring-2 ring-[#8bbad4] ring-offset-1"
                      : ""
                  }`}
                  onClick={() => {
                    if (!signal.focusFilter || !onSignalClick) return;
                    onSignalClick(signal);
                  }}
                  disabled={!signal.focusFilter || !onSignalClick}
                >
                  {signal.label}
                </button>
              ))}
            </div>
          ) : null}
          <p className="mt-1.5 text-[12px] text-[#46667d]">{feedback.reason}</p>
        </div>
      ) : null}
      {focusSummary ? (
        <div className="mt-3 rounded-lg border border-[#cfe2ee] bg-white/80 p-2.5">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5d7c92]">
              Current Focus
            </p>
            <Badge
              variant="outline"
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${focusSummary.badgeClassName}`}
            >
              {focusSummary.label}
            </Badge>
          </div>
          <p className="mt-1.5 text-[12px] text-[#46667d]">{focusSummary.detail}</p>
          {focusDelta ? (
            <div className="mt-3 rounded-lg border border-[#d8e6ef] bg-[#f8fcfe] p-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5d7c92]">
                  Focus Delta
                </p>
                <Badge
                  variant="outline"
                  className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${queueFocusDeltaBadgeClass(focusDelta)}`}
                >
                  {queueFocusDeltaChangeLabel(focusDelta)}
                </Badge>
              </div>
              <p className="mt-1.5 text-[12px] text-[#46667d]">
                {focusDelta.fromLabel} showed {focusDelta.fromCount} item
                {focusDelta.fromCount === 1 ? "" : "s"}, now {focusDelta.toLabel.toLowerCase()} shows{" "}
                {focusDelta.toCount}.
              </p>
            </div>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              className="h-7 rounded-lg border-[#b6d6e8] bg-white px-2 text-[11px] text-[#214d69] hover:bg-[#f8fcfe]"
              onClick={onResetFocus}
              disabled={!onResetFocus || focusSummary.activeFilter === "all"}
            >
              Reset to all
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 rounded-lg border-[#b6d6e8] bg-white px-2 text-[11px] text-[#214d69] hover:bg-[#f8fcfe]"
              onClick={onOpenMatchingQueue}
              disabled={!onOpenMatchingQueue}
            >
              Open matching queue
            </Button>
          </div>
        </div>
      ) : null}
      {feedback.nextTarget || feedback.previousTarget ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-7 rounded-lg border-[#b6d6e8] bg-white px-2 text-[11px] text-[#214d69] hover:bg-[#f8fcfe]"
            onClick={onOpenSelectedNext}
            disabled={!feedback.nextTarget || !onOpenSelectedNext}
          >
            Open selected next
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 rounded-lg border-[#b6d6e8] bg-white px-2 text-[11px] text-[#214d69] hover:bg-[#f8fcfe]"
            onClick={onReopenPrevious}
            disabled={!feedback.previousTarget || !onReopenPrevious}
          >
            Re-open previous
          </Button>
        </div>
      ) : null}
    </div>
  );
}
