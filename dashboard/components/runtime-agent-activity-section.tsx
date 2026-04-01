"use client";

import { SessionMetric } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AgentScopedOutcome } from "@/lib/control-plane-models";
import { passStatusClass } from "@/lib/control-plane-ui";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionRuntimeAgentDetail,
} from "@/lib/types";

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type RuntimeAgentActivitySectionProps = {
  selectedAgent: ExecutionRuntimeAgentDetail;
  agentScopedRuns: ExecutionAgentActionRunRecord[];
  agentActivitySearch: string;
  onAgentActivitySearchChange: (value: string) => void;
  agentActivityFilter: string;
  onAgentActivityFilterChange: (value: string) => void;
  filteredAgentScopedRuns: ExecutionAgentActionRunRecord[];
  selectedRunId: string;
  selectedRunResultIndex: number;
  onSelectRun: (runId: string, resultIndex: number) => void;
  formatTimestamp: (value?: string | null) => string;
  toNumber: (value: unknown, fallback?: number) => number;
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  agentScopedOutcomes: AgentScopedOutcome[];
  filteredAgentScopedOutcomes: AgentScopedOutcome[];
  outcomeProjectId: (result: Record<string, unknown>) => string;
  outcomeStoryId: (result: Record<string, unknown>) => number | null;
  toStringValue: (value: unknown, fallback?: string) => string;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  onFindOutcomeInSession: (runId: string, resultIndex: number) => void;
};

export function RuntimeAgentActivitySection({
  selectedAgent,
  agentScopedRuns,
  agentActivitySearch,
  onAgentActivitySearchChange,
  agentActivityFilter,
  onAgentActivityFilterChange,
  filteredAgentScopedRuns,
  selectedRunId,
  selectedRunResultIndex,
  onSelectRun,
  formatTimestamp,
  toNumber,
  describeRunResult,
  agentScopedOutcomes,
  filteredAgentScopedOutcomes,
  outcomeProjectId,
  outcomeStoryId,
  toStringValue,
  asRecord,
  onFindOutcomeInSession,
}: RuntimeAgentActivitySectionProps) {
  const discoveries = selectedAgent.story.discoveries ?? [];

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Agent Action Runs
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {agentScopedRuns.length} run{agentScopedRuns.length === 1 ? "" : "s"}
          </Badge>
        </div>
        <div className="mt-3 space-y-3">
          <Input
            value={agentActivitySearch}
            onChange={(event) => onAgentActivitySearchChange(event.target.value)}
            placeholder="Search agent runs, outcomes, approvals, issues..."
            className="h-9 rounded-xl border-[#e5e5e3] bg-white text-[13px] text-[#37352f] placeholder:text-[#9b9a97]"
          />
          <div className="flex flex-wrap gap-2">
            {[
              { value: "all", label: "All" },
              { value: "execute", label: "Execute" },
              { value: "preview", label: "Preview" },
              { value: "attention", label: "Attention" },
            ].map((option) => {
              const selected = agentActivityFilter === option.value;
              return (
                <Button
                  key={`agent-activity-filter-${option.value}`}
                  size="sm"
                  variant={selected ? "default" : "outline"}
                  className={`h-7 rounded-full px-3 text-[11px] ${
                    selected
                      ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                      : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                  }`}
                  onClick={() => {
                    onAgentActivityFilterChange(option.value);
                  }}
                >
                  {option.label}
                </Button>
              );
            })}
          </div>
        </div>
        {filteredAgentScopedRuns.length === 0 ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            No agent runs match the current filters.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {filteredAgentScopedRuns.slice(0, 4).map((run) => {
              const selected = selectedRunId === run.id;
              return (
                <div
                  key={`${selectedAgent.runtime_agent_id}-run-${run.id}`}
                  className={`rounded-xl border p-3 ${
                    selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-mono text-[11px] text-[#37352f]">{run.id}</p>
                    <div className="flex flex-wrap items-center gap-2">
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
                        {run.dry_run ? "preview" : "execute"}
                      </Badge>
                      {run.completion_state === "pending_async" && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                        >
                          async pending
                        </Badge>
                      )}
                    </div>
                  </div>
                  <p className="mt-2 text-[12px] text-[#6b6b6b]">
                    {run.actor || "unknown actor"}
                    {" · "}
                    {formatTimestamp(run.created_at)}
                  </p>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <SessionMetric
                      label="Outcomes"
                      value={String(run.results.length)}
                      detail={`${toNumber(run.summary.processed_count, run.results.length)} processed`}
                    />
                    <SessionMetric
                      label="Policy"
                      value={run.policy_profile || "Custom"}
                      detail={
                        run.completion_state === "pending_async"
                          ? `${run.mode || "auto"} · ${run.active_async_task_count ?? 0} active async task${(run.active_async_task_count ?? 0) === 1 ? "" : "s"}`
                          : run.mode || "auto"
                      }
                    />
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant={selected ? "default" : "outline"}
                      className={`h-7 rounded-lg px-2 text-[11px] ${
                        selected
                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                      }`}
                      onClick={() => {
                        onSelectRun(run.id, 0);
                      }}
                    >
                      {selected ? "Selected" : "Inspect run"}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Recent Outcomes
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {agentScopedOutcomes.length} outcome{agentScopedOutcomes.length === 1 ? "" : "s"}
          </Badge>
        </div>
        {filteredAgentScopedOutcomes.length === 0 ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            No agent outcomes match the current filters.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {filteredAgentScopedOutcomes.slice(0, 4).map((entry) => {
              const details = describeRunResult(entry.result);
              const selected =
                selectedRunId === entry.run.id && selectedRunResultIndex === entry.resultIndex;
              const projectId = outcomeProjectId(entry.result);
              const storyId = outcomeStoryId(entry.result);
              const linkedApprovalId = toStringValue(asRecord(entry.result.approval)?.id);
              const linkedIssueId = toStringValue(asRecord(entry.result.issue)?.id);
              return (
                <div
                  key={`${entry.run.id}-result-${entry.resultIndex}`}
                  className={`rounded-xl border p-3 ${
                    selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[13px] font-semibold text-[#37352f]">{details.title}</p>
                    <Badge
                      variant="outline"
                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(entry.result.status, "unknown"))}`}
                    >
                      {toStringValue(entry.result.status, "unknown")}
                    </Badge>
                  </div>
                  <p className="mt-2 text-[12px] text-[#787774]">
                    {details.subtitle || "No outcome subtype"}
                    {" · "}
                    {formatTimestamp(entry.timestamp)}
                  </p>
                  <p className="mt-2 text-[12px] text-[#6b6b6b]">{details.message}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {projectId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        project {projectId}
                      </Badge>
                    )}
                    {storyId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        story {storyId}
                      </Badge>
                    )}
                    {linkedApprovalId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        approval {linkedApprovalId}
                      </Badge>
                    )}
                    {linkedIssueId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        issue {linkedIssueId}
                      </Badge>
                    )}
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant={selected ? "default" : "outline"}
                      className={`h-7 rounded-lg px-2 text-[11px] ${
                        selected
                          ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                          : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                      }`}
                      onClick={() => {
                        onSelectRun(entry.run.id, entry.resultIndex);
                      }}
                    >
                      {selected ? "Selected" : "Inspect outcome"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onFindOutcomeInSession(entry.run.id, entry.resultIndex);
                      }}
                    >
                      Find in session
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Discovery Board
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {discoveries.length} marker{discoveries.length === 1 ? "" : "s"}
          </Badge>
        </div>
        {discoveries.length === 0 ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            No shared warnings, intents, or constraints recorded for this story yet.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {discoveries.slice(-5).reverse().map((marker) => (
              <div
                key={marker.id}
                className="rounded-xl border border-[#ecebe8] bg-white p-3"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-[13px] font-semibold text-[#37352f]">{marker.title}</p>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.04em] text-[#2a6690]"
                  >
                    {marker.kind}
                  </Badge>
                </div>
                <p className="mt-2 text-[12px] text-[#787774]">
                  {marker.source}
                  {" · "}
                  {formatTimestamp(marker.updated_at ?? marker.created_at)}
                </p>
                <p className="mt-2 text-[12px] text-[#6b6b6b]">{marker.detail}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
