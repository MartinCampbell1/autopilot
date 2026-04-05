"use client";

import { useMemo } from "react";
import { ShadowAuditReviewSheet } from "@/components/shadow-audit-review-sheet";
import { SessionMetric } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { AgentScopedOutcome } from "@/lib/control-plane-models";
import { passStatusClass } from "@/lib/control-plane-ui";
import { useShadowAuditReviewController } from "@/lib/use-shadow-audit-review-controller";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionShadowAuditRecord,
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
  busyActionKey: string;
  agentActivitySearch: string;
  onAgentActivitySearchChange: (value: string) => void;
  agentActivityFilter: string;
  onAgentActivityFilterChange: (value: string) => void;
  filteredAgentScopedRuns: ExecutionAgentActionRunRecord[];
  selectedRunId: string;
  selectedRunResultIndex: number;
  onSelectRun: (runId: string, resultIndex: number) => void;
  onInspectShadowAudit?: (audit: ExecutionShadowAuditRecord) => void;
  onResolveShadowAudit?: (audit: ExecutionShadowAuditRecord) => void;
  onWaitForAsyncSettlement?: (run: ExecutionAgentActionRunRecord) => void;
  onCancelAsyncSettlement?: (run: ExecutionAgentActionRunRecord) => void;
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
  busyActionKey,
  agentActivitySearch,
  onAgentActivitySearchChange,
  agentActivityFilter,
  onAgentActivityFilterChange,
  filteredAgentScopedRuns,
  selectedRunId,
  selectedRunResultIndex,
  onSelectRun,
  onInspectShadowAudit,
  onResolveShadowAudit,
  onWaitForAsyncSettlement,
  onCancelAsyncSettlement,
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
  const agentRunShadowAuditRows = useMemo(() => {
    const rowsByAuditId = new Map<
      string,
      { audit: ExecutionShadowAuditRecord; run: ExecutionAgentActionRunRecord }
    >();
    filteredAgentScopedRuns.forEach((run) => {
      (run.shadow_audits || [])
        .filter((audit) => audit.open || audit.status === "open")
        .forEach((audit) => {
          if (!rowsByAuditId.has(audit.id)) {
            rowsByAuditId.set(audit.id, { audit, run });
          }
        });
    });
    return Array.from(rowsByAuditId.values());
  }, [filteredAgentScopedRuns]);
  const {
    queueAudits,
    queueOpen,
    setQueueOpen,
    activeQueueAudit,
    activeQueueAuditIndex,
    reviewQueueLabel,
    openReviewQueue: openAgentActivityShadowAuditQueue,
    handleSelectNextQueuedAudit,
    handleSelectPreviousQueuedAudit,
    handleResolveQueuedShadowAudit,
  } = useShadowAuditReviewController({
    audits: agentRunShadowAuditRows.map((entry) => entry.audit),
    onInspectShadowAudit: (audit) => {
      const relatedRun =
        agentRunShadowAuditRows.find((entry) => entry.audit.id === audit.id)?.run || null;
      if (relatedRun) {
        onSelectRun(relatedRun.id, 0);
      }
      onInspectShadowAudit?.(audit);
    },
    onResolveShadowAudit,
  });

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
              const waitActionKey = `run-wait:${run.id}`;
              const cancelActionKey = `run-cancel:${run.id}`;
              const openShadowAudits = (run.shadow_audits || [])
                .filter((audit) => audit.open || audit.status === "open");
              const primaryShadowAudit = openShadowAudits[0] || null;
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
                      {run.completion_state === "quarantined" && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                        >
                          handoff blocked
                        </Badge>
                      )}
                      {openShadowAudits.length > 0 && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                        >
                          {openShadowAudits.length} shadow audit
                          {openShadowAudits.length === 1 ? "" : "s"}
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
                          : run.completion_state === "quarantined"
                            ? `${run.mode || "auto"} · ${run.open_shadow_audit_count ?? 0} shadow audit${(run.open_shadow_audit_count ?? 0) === 1 ? "" : "s"} open`
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
                    {primaryShadowAudit ? (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#f4e0c4] bg-[#fff6e8] px-2 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                        onClick={() => {
                          openAgentActivityShadowAuditQueue(primaryShadowAudit.id);
                        }}
                      >
                        {reviewQueueLabel}
                      </Button>
                    ) : null}
                    {run.completion_state === "pending_async" && onWaitForAsyncSettlement && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#d6e9dc] bg-[#eef8f1] px-2 text-[11px] text-[#2b6e3f] hover:bg-[#e4f3e8]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onWaitForAsyncSettlement(run);
                        }}
                      >
                        {busyActionKey === waitActionKey ? "Waiting..." : "Wait"}
                      </Button>
                    )}
                    {run.completion_state === "pending_async" && onCancelAsyncSettlement && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-lg border-[#f0d0c9] bg-[#fff0ed] px-2 text-[11px] text-[#93370d] hover:bg-[#ffe7e1]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onCancelAsyncSettlement(run);
                        }}
                      >
                        {busyActionKey === cancelActionKey ? "Cancelling..." : "Cancel"}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
            {activeQueueAudit ? (
              <ShadowAuditReviewSheet
                audit={activeQueueAudit}
                open={queueOpen}
                onOpenChange={setQueueOpen}
                hideTrigger
                busyActionKey={busyActionKey}
                formatTimestamp={formatTimestamp}
                onResolveShadowAudit={handleResolveQueuedShadowAudit}
                queueState={{
                  currentIndex: Math.max(activeQueueAuditIndex, 0),
                  totalCount: queueAudits.length,
                  onSelectNext: handleSelectNextQueuedAudit,
                  onSelectPrevious: handleSelectPreviousQueuedAudit,
                }}
              />
            ) : null}
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
