"use client";

import Link from "next/link";
import { BreakdownChips, FilterChip, SessionMetric } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { passStatusClass } from "@/lib/control-plane-ui";
import type {
  ExecutionAgentActionRunRecord,
  OrchestratorSessionControl,
  OrchestratorSessionDetail,
} from "@/lib/types";

type RunFilter = "all" | "execute" | "preview" | "attention";
type EventFilter = "all" | "control" | "actions" | "decisions" | "attention";

type LinkedSelectionPayload = {
  event?: Record<string, unknown> | null;
  runId?: string;
  approvalId?: string;
  issueId?: string;
  runtimeAgentId?: string;
};

type SessionDrilldownActivitySectionProps = {
  selectedSession: OrchestratorSessionDetail;
  selectedControl: OrchestratorSessionControl | null;
  linkedRuns: ExecutionAgentActionRunRecord[];
  runFilter: RunFilter;
  onRunFilterChange: (filter: RunFilter) => void;
  getRunFilterCount: (filter: Exclude<RunFilter, "all">) => number;
  filteredRuns: ExecutionAgentActionRunRecord[];
  selectedRunId: string;
  onSelectRun: (runId: string) => void;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  toNumber: (value: unknown, fallback?: number) => number;
  eventFilter: EventFilter;
  onEventFilterChange: (filter: EventFilter) => void;
  getEventFilterCount: (filter: Exclude<EventFilter, "all">) => number;
  filteredEvents: Record<string, unknown>[];
  visibleSessionEvents: Record<string, unknown>[];
  selectedSessionEventKey: string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toStringArray: (value: unknown) => string[];
  toNullableNumber: (value: unknown) => number | null;
  formatTimestamp: (value?: string | null) => string;
  eventFamily: (eventName: string) => string;
  sessionEventKey: (event: Record<string, unknown>, fallback?: string) => string;
  sessionContextRowDomId: (kind: "approval" | "issue" | "event", key: string) => string;
  onSyncLinkedSelection: (payload: LinkedSelectionPayload) => void;
  onSearchEntity: (value: string) => void;
};

export function SessionDrilldownActivitySection({
  selectedSession,
  selectedControl,
  linkedRuns,
  runFilter,
  onRunFilterChange,
  getRunFilterCount,
  filteredRuns,
  selectedRunId,
  onSelectRun,
  onFocusRuntimeAgent,
  toNumber,
  eventFilter,
  onEventFilterChange,
  getEventFilterCount,
  filteredEvents,
  visibleSessionEvents,
  selectedSessionEventKey,
  toStringValue,
  toStringArray,
  toNullableNumber,
  formatTimestamp,
  eventFamily,
  sessionEventKey,
  sessionContextRowDomId,
  onSyncLinkedSelection,
  onSearchEntity,
}: SessionDrilldownActivitySectionProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          Action Summary
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <SessionMetric
            label="Actions"
            value={String(selectedControl?.action_summary.totals.actions || 0)}
            detail={`${selectedControl?.action_summary.totals.suggested_commands || 0} commands · ${selectedControl?.action_summary.totals.recommendations || 0} recommendations`}
          />
          <SessionMetric
            label="Projects"
            value={String(selectedControl?.action_summary.totals.projects || 0)}
            detail={`${selectedControl?.action_summary.totals.approval_required || 0} approval-required actions`}
          />
        </div>
        <div className="mt-4 space-y-4">
          <BreakdownChips
            label="Action Types"
            values={selectedControl?.action_summary.by_action_type}
            emptyText="No action types recorded."
          />
          <BreakdownChips
            label="Priorities"
            values={selectedControl?.action_summary.by_priority}
            emptyText="No priorities recorded."
          />
          <BreakdownChips
            label="Commands"
            values={selectedControl?.action_summary.by_command}
            emptyText="No commands recorded."
          />
        </div>
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Action Runs
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {linkedRuns.length}
          </Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <FilterChip
            label="All"
            active={runFilter === "all"}
            count={linkedRuns.length}
            onClick={() => {
              onRunFilterChange("all");
            }}
          />
          <FilterChip
            label="Execute"
            active={runFilter === "execute"}
            count={getRunFilterCount("execute")}
            onClick={() => {
              onRunFilterChange("execute");
            }}
          />
          <FilterChip
            label="Preview"
            active={runFilter === "preview"}
            count={getRunFilterCount("preview")}
            onClick={() => {
              onRunFilterChange("preview");
            }}
          />
          <FilterChip
            label="Attention"
            active={runFilter === "attention"}
            count={getRunFilterCount("attention")}
            onClick={() => {
              onRunFilterChange("attention");
            }}
          />
        </div>
        {!filteredRuns.length ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            {linkedRuns.length
              ? "No action runs match the current filter."
              : "No linked action runs recorded yet."}
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {filteredRuns.slice(0, 6).map((run) => {
              const selected = selectedRunId === run.id;
              return (
                <div
                  key={`${selectedSession.id}-run-${run.id}`}
                  className={`rounded-xl border p-3 ${
                    selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-mono text-[11px] text-[#37352f]">{run.id}</p>
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(run.status)}`}
                        >
                          {run.status}
                        </Badge>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {run.run_kind}
                        </Badge>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {run.dry_run ? "preview" : "execute"}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[12px] text-[#787774]">
                        {run.mode || "auto"}
                        {run.policy_profile ? ` · ${run.policy_profile}` : ""}
                      </p>
                      <p className="mt-2 text-[12px] text-[#9b9a97]">
                        {toNumber(run.summary.selected_count)} selected ·{" "}
                        {toNumber(run.summary.processed_count, run.results.length)} processed
                      </p>
                      {run.runtime_agent_ids.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-2">
                          {run.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                            <Button
                              key={`${run.id}-${runtimeAgentId}`}
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                onFocusRuntimeAgent(runtimeAgentId);
                              }}
                            >
                              {runtimeAgentId}
                            </Button>
                          ))}
                        </div>
                      )}
                    </div>
                    <Button
                      size="sm"
                      variant={selected ? "default" : "outline"}
                      className={`h-8 rounded-lg text-[12px] ${
                        selected
                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                      }`}
                      onClick={() => {
                        onSelectRun(run.id);
                      }}
                    >
                      {selected ? "Selected" : "Inspect"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Latest Session Events
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {filteredEvents.length}
          </Badge>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <FilterChip
            label="All"
            active={eventFilter === "all"}
            count={selectedSession.events.length}
            onClick={() => {
              onEventFilterChange("all");
            }}
          />
          <FilterChip
            label="Control"
            active={eventFilter === "control"}
            count={getEventFilterCount("control")}
            onClick={() => {
              onEventFilterChange("control");
            }}
          />
          <FilterChip
            label="Actions"
            active={eventFilter === "actions"}
            count={getEventFilterCount("actions")}
            onClick={() => {
              onEventFilterChange("actions");
            }}
          />
          <FilterChip
            label="Decisions"
            active={eventFilter === "decisions"}
            count={getEventFilterCount("decisions")}
            onClick={() => {
              onEventFilterChange("decisions");
            }}
          />
          <FilterChip
            label="Attention"
            active={eventFilter === "attention"}
            count={getEventFilterCount("attention")}
            onClick={() => {
              onEventFilterChange("attention");
            }}
          />
        </div>
        {!filteredEvents.length ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            {selectedSession.events.length
              ? "No session events match the current filter."
              : "No session events recorded yet."}
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {visibleSessionEvents.map((event, index) => {
              const eventApprovalId = toStringValue(event.approval_id);
              const eventIssueId = toStringValue(event.issue_id);
              const eventProjectId = toStringValue(event.project_id);
              const eventRuntimeAgentIds = [
                toStringValue(event.runtime_agent_id),
                ...toStringArray(event.runtime_agent_ids),
              ].filter(Boolean);
              const eventKey = sessionEventKey(event, String(index));
              const selected = selectedSessionEventKey === eventKey;
              return (
                <div
                  key={eventKey}
                  id={sessionContextRowDomId("event", eventKey)}
                  className={`rounded-xl border p-3 ${
                    selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-mono text-[11px] text-[#37352f]">
                        {toStringValue(event.event, "unknown_event")}
                      </p>
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        {eventFamily(toStringValue(event.event))}
                      </Badge>
                    </div>
                    <Badge
                      variant="outline"
                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(toStringValue(event.status, "unknown"))}`}
                    >
                      {toStringValue(event.status, "unknown")}
                    </Badge>
                    <Button
                      size="sm"
                      variant={selected ? "default" : "outline"}
                      className={`h-7 rounded-lg px-2 text-[11px] ${
                        selected
                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                      }`}
                      onClick={() => {
                        onSyncLinkedSelection({
                          event,
                          runId:
                            toStringValue(event.agent_action_run_id) ||
                            toStringValue(event.run_id),
                          approvalId: eventApprovalId,
                          issueId: eventIssueId,
                          runtimeAgentId: eventRuntimeAgentIds[0],
                        });
                      }}
                    >
                      {selected ? "Selected" : "Inspect"}
                    </Button>
                  </div>
                  <p className="mt-2 text-[13px] text-[#6b6b6b]">
                    {toStringValue(event.message, "No event message")}
                  </p>
                  {(eventProjectId ||
                    toNullableNumber(event.story_id) ||
                    eventApprovalId ||
                    eventIssueId ||
                    eventRuntimeAgentIds.length > 0) && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {eventProjectId && (
                        <Link
                          href={`/projects/${eventProjectId}`}
                          className="inline-flex h-7 items-center rounded-full border border-[#e5e5e3] bg-[#fafaf9] px-2.5 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                        >
                          project {eventProjectId}
                        </Link>
                      )}
                      {toNullableNumber(event.story_id) && eventProjectId && (
                        <Link
                          href={`/projects/${eventProjectId}?storyId=${toNullableNumber(event.story_id)}`}
                          className="inline-flex h-7 items-center rounded-full border border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] font-medium text-[#2a6690] transition-colors hover:bg-[#e3f2f8]"
                        >
                          story {toNullableNumber(event.story_id)}
                        </Link>
                      )}
                      {eventApprovalId && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                          onClick={() => {
                            onSearchEntity(eventApprovalId);
                          }}
                        >
                          approval {eventApprovalId}
                        </Button>
                      )}
                      {eventIssueId && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                          onClick={() => {
                            onSearchEntity(eventIssueId);
                          }}
                        >
                          issue {eventIssueId}
                        </Button>
                      )}
                      {eventRuntimeAgentIds.slice(0, 2).map((runtimeAgentId) => (
                        <Button
                          key={`${toStringValue(event.event)}-${runtimeAgentId}`}
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                          onClick={() => {
                            onFocusRuntimeAgent(runtimeAgentId);
                          }}
                        >
                          {runtimeAgentId}
                        </Button>
                      ))}
                    </div>
                  )}
                  <p className="mt-2 text-[12px] text-[#9b9a97]">
                    {formatTimestamp(toStringValue(event.timestamp))}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
