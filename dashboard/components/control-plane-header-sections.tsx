"use client";

import { SummaryStat } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { controlStateClass } from "@/lib/control-plane-ui";
import type {
  OrchestratorControlPassSummary,
  OrchestratorSessionSummary,
} from "@/lib/types";

type ControlPlaneHeaderSectionsProps = {
  latestControlPassAt?: string | null;
  latestSessionAt?: string | null;
  selectedSessionId: string;
  selectedControlState?: string | null;
  refreshing: boolean;
  onRefresh: () => void;
  formatTimestamp: (value?: string | null) => string;
  controlSummary: OrchestratorControlPassSummary;
  sessionSummary: OrchestratorSessionSummary;
  historySearch: string;
  onHistorySearchChange: (value: string) => void;
  onClearHistorySearch: () => void;
  filteredSessionHistoryCount: number;
  totalSessionCount: number;
  filteredControlPassHistoryCount: number;
  totalControlPassCount: number;
  onCopyCurrentLink: () => void;
};

export function ControlPlaneHeaderSections({
  latestControlPassAt,
  latestSessionAt,
  selectedSessionId,
  selectedControlState,
  refreshing,
  onRefresh,
  formatTimestamp,
  controlSummary,
  sessionSummary,
  historySearch,
  onHistorySearchChange,
  onClearHistorySearch,
  filteredSessionHistoryCount,
  totalSessionCount,
  filteredControlPassHistoryCount,
  totalControlPassCount,
  onCopyCurrentLink,
}: ControlPlaneHeaderSectionsProps) {
  return (
    <>
      <header className="sticky top-0 z-30 border-b border-[#e5e5e3] bg-white px-6 py-4">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">
              FounderOS Execution Plane
            </p>
            <h1 className="mt-1 text-[24px] font-semibold tracking-[-0.03em] text-[#37352f]">
              Control Plane
            </h1>
            <p className="mt-2 max-w-3xl text-[14px] leading-relaxed text-[#6b6b6b]">
              Observe session-level orchestration passes, inspect current execution state, and
              apply FounderOS control recommendations directly from Autopilot.
            </p>
          </div>
          <div className="min-w-[280px] rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
            <div className="flex items-center justify-between text-[13px]">
              <span className="text-[#9b9a97]">Latest control pass</span>
              <span className="font-semibold text-[#37352f]">
                {formatTimestamp(latestControlPassAt)}
              </span>
            </div>
            <div className="mt-3 flex items-center justify-between text-[13px]">
              <span className="text-[#9b9a97]">Latest session</span>
              <span className="font-semibold text-[#37352f]">
                {formatTimestamp(latestSessionAt)}
              </span>
            </div>
            <div className="mt-3 flex items-center justify-between text-[13px]">
              <span className="text-[#9b9a97]">Selected session</span>
              <span className="font-mono text-[12px] font-semibold text-[#37352f]">
                {selectedSessionId || "none"}
              </span>
            </div>
            <div className="mt-3 flex items-center justify-between text-[13px]">
              <span className="text-[#9b9a97]">Control state</span>
              {selectedControlState ? (
                <Badge
                  variant="outline"
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControlState)}`}
                >
                  {selectedControlState}
                </Badge>
              ) : (
                <span className="text-[#9b9a97]">No session selected</span>
              )}
            </div>
            <div className="mt-4 grid gap-2">
              <Button
                size="sm"
                className="h-9 w-full rounded-lg bg-[#1a1a1a] text-[13px] hover:bg-[#333]"
                disabled={refreshing}
                onClick={onRefresh}
              >
                {refreshing ? "Refreshing..." : "Refresh control plane"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-9 w-full rounded-lg border-[#e5e5e3] bg-white text-[13px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={onCopyCurrentLink}
              >
                Copy current link
              </Button>
            </div>
          </div>
        </div>
      </header>

      <section className="grid gap-4 xl:grid-cols-4">
        <SummaryStat
          eyebrow="Control Passes"
          value={String(controlSummary.totals.control_passes)}
          detail={`${controlSummary.totals.ok} ok · ${controlSummary.totals.partial} partial · ${controlSummary.totals.error} error`}
        />
        <SummaryStat
          eyebrow="Coverage"
          value={`${controlSummary.totals.sessions} sessions`}
          detail={`${controlSummary.totals.projects} projects touched · ${controlSummary.totals.customized} customized passes`}
        />
        <SummaryStat
          eyebrow="Applied Steps"
          value={String(controlSummary.totals.applied_steps)}
          detail={`${controlSummary.totals.error_steps} error steps across persisted control passes`}
        />
        <SummaryStat
          eyebrow="Session Status"
          value={String(sessionSummary.totals.open)}
          detail={`${sessionSummary.totals.completed} completed · ${sessionSummary.totals.archived} archived`}
        />
      </section>

      <section className="rounded-2xl border border-[#e5e5e3] bg-white p-4 shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
              History Search
            </p>
            <p className="mt-2 text-[13px] text-[#787774]">
              Search recent sessions and control passes by session id, actor, profile, initiative,
              project, or linked entity ids.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredSessionHistoryCount}/{totalSessionCount} sessions
            </Badge>
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredControlPassHistoryCount}/{totalControlPassCount} passes
            </Badge>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          <Input
            value={historySearch}
            onChange={(event) => {
              onHistorySearchChange(event.target.value);
            }}
            placeholder="session id, control pass id, actor, project, initiative, approval, issue..."
            className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
          />
          <Button
            size="sm"
            variant="outline"
            className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
            disabled={!historySearch.trim()}
            onClick={onClearHistorySearch}
          >
            Clear search
          </Button>
        </div>
      </section>
    </>
  );
}
