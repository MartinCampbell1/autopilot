"use client";

import Link from "next/link";
import { BreakdownChips, SessionMetric } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  controlStateClass,
  priorityClass,
  recommendationActionLabel,
  sessionStatusClass,
} from "@/lib/control-plane-ui";
import { formatTimestamp } from "@/lib/control-plane-data";
import type {
  ExecutionAgentActionRunRecord,
  OrchestratorSessionControl,
  OrchestratorSessionControlProfile,
  OrchestratorSessionControlRecommendation,
  OrchestratorSessionDetail,
} from "@/lib/types";

type SessionDrilldownControlSectionProps = {
  selectedSession: OrchestratorSessionDetail;
  selectedControl: OrchestratorSessionControl | null;
  linkedAgentIds: string[];
  selectedAgentId: string;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  filteredRunsCount: number;
  linkedRunsCount: number;
  filteredEventsCount: number;
  filteredApprovalsCount: number;
  linkedApprovalsCount: number;
  filteredIssuesCount: number;
  linkedIssuesCount: number;
  entitySearch: string;
  onEntitySearchChange: (value: string) => void;
  onClearEntitySearch: () => void;
  sortedProfiles: OrchestratorSessionControlProfile[];
  busyActionKey: string;
  selectedRunId: string;
  onCopySessionLink: () => void;
  canCopyFocusedLink: boolean;
  onCopyFocusedLink: () => void;
  latestPreviewRun: ExecutionAgentActionRunRecord | null;
  latestPreviewAppliedRun: ExecutionAgentActionRunRecord | null;
  onInspectRun: (runId: string) => void;
  onApplyPreviewRun: (run: ExecutionAgentActionRunRecord) => void;
  onApplyControlPlan: (profile: OrchestratorSessionControlProfile) => void;
  onApplyRecommendation: (recommendation: OrchestratorSessionControlRecommendation) => void;
};

export function SessionDrilldownControlSection({
  selectedSession,
  selectedControl,
  linkedAgentIds,
  selectedAgentId,
  onFocusRuntimeAgent,
  filteredRunsCount,
  linkedRunsCount,
  filteredEventsCount,
  filteredApprovalsCount,
  linkedApprovalsCount,
  filteredIssuesCount,
  linkedIssuesCount,
  entitySearch,
  onEntitySearchChange,
  onClearEntitySearch,
  sortedProfiles,
  busyActionKey,
  selectedRunId,
  onCopySessionLink,
  canCopyFocusedLink,
  onCopyFocusedLink,
  latestPreviewRun,
  latestPreviewAppliedRun,
  onInspectRun,
  onApplyPreviewRun,
  onApplyControlPlan,
  onApplyRecommendation,
}: SessionDrilldownControlSectionProps) {
  const latestPreviewCommandCounts = (latestPreviewRun?.diff_summary?.command_counts ||
    {}) as Record<string, number>;
  const latestPreviewWhy = Array.isArray(latestPreviewRun?.diff_summary?.why)
    ? latestPreviewRun?.diff_summary?.why.filter(
        (item): item is string => typeof item === "string" && item.trim().length > 0
      )
    : [];
  const latestPreviewSelectedCount =
    Number(latestPreviewRun?.summary?.selected_count) || latestPreviewRun?.results.length || 0;
  const latestPreviewProcessedCount =
    Number(latestPreviewRun?.summary?.processed_count) || latestPreviewRun?.results.length || 0;
  const previewActionKey = latestPreviewRun
    ? `preview-apply:${latestPreviewRun.preview_id || latestPreviewRun.id}`
    : "";
  const selectedPreview =
    Boolean(latestPreviewRun) &&
    selectedRunId === (latestPreviewRun?.preview_id || latestPreviewRun?.id || "");
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-[#37352f]">
              {selectedSession.title || selectedSession.id}
            </h2>
            <Badge
              variant="outline"
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${sessionStatusClass(selectedSession.status)}`}
            >
              {selectedSession.status}
            </Badge>
            <Badge
              variant="outline"
              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedControl?.state || "unknown")}`}
            >
              {selectedControl?.state || "unknown"}
            </Badge>
          </div>
          <p className="mt-2 font-mono text-[12px] text-[#9b9a97]">{selectedSession.id}</p>
          <p className="mt-2 text-[14px] text-[#6b6b6b]">
            {selectedSession.orchestrator || "unknown orchestrator"}
            {" · "}
            {selectedSession.actor || "unknown actor"}
            {selectedSession.reason ? ` · ${selectedSession.reason}` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            size="sm"
            variant="outline"
            className="h-8 rounded-full border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] hover:bg-[#f7f7f5]"
            onClick={onCopySessionLink}
          >
            Copy session link
          </Button>
          {canCopyFocusedLink ? (
            <Button
              size="sm"
              variant="outline"
              className="h-8 rounded-full border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] hover:bg-[#f7f7f5]"
              onClick={onCopyFocusedLink}
            >
              Copy focused link
            </Button>
          ) : null}
          {selectedSession.project_ids.map((projectId) => (
            <Link
              key={`${selectedSession.id}-${projectId}`}
              href={`/projects/${projectId}`}
              className="inline-flex h-8 items-center rounded-full border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
            >
              {projectId}
            </Link>
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <SessionMetric
          label="Pending Approvals"
          value={String(selectedSession.summary.pending_approval_count)}
          detail={`${selectedSession.summary.approval_count} linked approvals`}
        />
        <SessionMetric
          label="Open Issues"
          value={String(selectedSession.summary.open_issue_count)}
          detail={`${selectedSession.summary.issue_count} linked issues`}
        />
        <SessionMetric
          label="Safe Actions"
          value={String(selectedControl?.counts.safe_actions || 0)}
          detail={`${selectedControl?.counts.approval_required_actions || 0} approval-gated`}
        />
        <SessionMetric
          label="Control Passes"
          value={String(selectedSession.summary.control_pass_count)}
          detail={`${selectedSession.summary.run_count} linked runs`}
        />
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Linked Runtime Agents
          </p>
          <Badge
            variant="outline"
            className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
          >
            {linkedAgentIds.length}
          </Badge>
        </div>
        {!linkedAgentIds.length ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">No linked runtime agents in this session.</p>
        ) : (
          <div className="mt-3 flex flex-wrap gap-2">
            {linkedAgentIds.slice(0, 12).map((runtimeAgentId) => (
              <Button
                key={`${selectedSession.id}-${runtimeAgentId}`}
                size="sm"
                variant={selectedAgentId === runtimeAgentId ? "default" : "outline"}
                className={`h-8 rounded-full px-3 text-[11px] ${
                  selectedAgentId === runtimeAgentId
                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                }`}
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

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
              Entity Search
            </p>
            <p className="mt-2 text-[13px] text-[#787774]">
              Filter runs, events, approvals, and issues by id, runtime agent, command, story, or
              reason.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredRunsCount}/{linkedRunsCount} runs
            </Badge>
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredEventsCount}/{selectedSession.events.length} events
            </Badge>
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredApprovalsCount}/{linkedApprovalsCount} approvals
            </Badge>
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              {filteredIssuesCount}/{linkedIssuesCount} issues
            </Badge>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-3">
          <Input
            value={entitySearch}
            onChange={(event) => {
              onEntitySearchChange(event.target.value);
            }}
            placeholder="approval id, issue id, runtime agent, action key, command, story..."
            className="min-w-[280px] flex-1 border-[#e5e5e3] bg-white text-[13px]"
          />
          <Button
            size="sm"
            variant="outline"
            className="h-10 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
            disabled={!entitySearch.trim()}
            onClick={onClearEntitySearch}
          >
            Clear search
          </Button>
        </div>
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          Control Pass Profiles
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {sortedProfiles.map((profile) => {
            const busy = busyActionKey === `profile:${profile.name}`;
            return (
              <Button
                key={profile.name}
                size="sm"
                variant={profile.default ? "default" : "outline"}
                className={`h-9 rounded-lg text-[12px] ${
                  profile.default
                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                }`}
                disabled={Boolean(busyActionKey)}
                onClick={() => {
                  onApplyControlPlan(profile);
                }}
              >
                {busy ? "Running..." : profile.name}
              </Button>
            );
          })}
        </div>
        <div className="mt-3 space-y-2">
          {sortedProfiles.map((profile) => (
            <div
              key={`${profile.name}-description`}
              className="flex flex-wrap items-start justify-between gap-2 text-[12px] text-[#787774]"
            >
              <span className="font-medium text-[#37352f]">{profile.name}</span>
              <span className="max-w-[75%] text-right">{profile.description}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-[#d8e7ef] bg-[#f7fbfd] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#6f8a99]">
              Preview Gate
            </p>
            <p className="mt-2 text-[13px] text-[#6b6b6b]">
              Explicit review path for session actions: create a preview, inspect the proposed
              diff, then apply or escalate approvals from that preview.
            </p>
          </div>
          {latestPreviewRun ? (
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={selectedPreview ? "default" : "outline"}
                className={`h-8 rounded-lg text-[12px] ${
                  selectedPreview
                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                    : "border-[#d8e7ef] bg-white text-[#2a6690] hover:bg-[#eef7fb]"
                }`}
                onClick={() => {
                  onInspectRun(latestPreviewRun.id);
                }}
              >
                {selectedPreview ? "Preview selected" : "Inspect preview"}
              </Button>
              {latestPreviewAppliedRun ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#d6e9dc] bg-white text-[12px] text-[#2b6e3f] hover:bg-[#eef8f1]"
                  onClick={() => {
                    onInspectRun(latestPreviewAppliedRun.id);
                  }}
                >
                  Open applied run
                </Button>
              ) : (
                <Button
                  size="sm"
                  className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] text-white hover:bg-[#333]"
                  disabled={Boolean(busyActionKey)}
                  onClick={() => {
                    onApplyPreviewRun(latestPreviewRun);
                  }}
                >
                  {busyActionKey === previewActionKey
                    ? latestPreviewRun.approval_required
                      ? "Requesting..."
                      : "Applying..."
                    : latestPreviewRun.approval_required
                      ? "Request approvals"
                      : "Apply preview"}
                </Button>
              )}
            </div>
          ) : null}
        </div>

        {!latestPreviewRun ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            No session preview is recorded yet. Use “Create preview” on a session recommendation
            before applying mutating actions.
          </p>
        ) : (
          <div className="mt-4 space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                {latestPreviewRun.preview_id || latestPreviewRun.id}
              </p>
              <Badge
                variant="outline"
                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(
                  latestPreviewAppliedRun ? "healthy" : latestPreviewRun.approval_required ? "needs_approval" : "actionable"
                )}`}
              >
                {latestPreviewAppliedRun
                  ? "applied"
                  : latestPreviewRun.approval_required
                    ? "approval-gated"
                    : "ready-to-apply"}
              </Badge>
              <Badge
                variant="outline"
                className="rounded-full border-[#d3e5ef] bg-white px-2.5 py-1 text-[11px] font-medium capitalize text-[#2a6690]"
              >
                {(latestPreviewRun.apply_mode || "manual").replaceAll("_", " ")}
              </Badge>
              <Badge
                variant="outline"
                className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
              >
                {formatTimestamp(latestPreviewRun.created_at)}
              </Badge>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <SessionMetric
                label="Selected"
                value={String(latestPreviewSelectedCount)}
                detail={`${latestPreviewProcessedCount} processed`}
              />
              <SessionMetric
                label="Projects"
                value={String(latestPreviewRun.project_ids.length)}
                detail={`${latestPreviewRun.runtime_agent_ids.length} runtime agents`}
              />
              <SessionMetric
                label="Approval-Gated"
                value={String(Number(latestPreviewRun.diff_summary?.approval_required_count) || 0)}
                detail={
                  latestPreviewRun.approval_required
                    ? "Apply will create approvals instead of mutating directly."
                    : "Policy allows direct apply from this preview."
                }
              />
              <SessionMetric
                label="Applied Result"
                value={latestPreviewAppliedRun ? latestPreviewAppliedRun.status : "Pending"}
                detail={
                  latestPreviewAppliedRun
                    ? latestPreviewAppliedRun.id
                    : "No apply run is linked to this preview yet."
                }
              />
            </div>

            <BreakdownChips
              label="Commands"
              values={latestPreviewCommandCounts}
              emptyText="No command breakdown recorded for this preview."
            />

            {latestPreviewWhy.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {latestPreviewWhy.slice(0, 4).map((reason) => (
                  <Badge
                    key={`${latestPreviewRun.id}-${reason}`}
                    variant="outline"
                    className="rounded-full border-[#d8e7ef] bg-white px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                  >
                    {reason}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Current Recommendations
          </p>
          <p className="text-[12px] text-[#787774]">
            {selectedControl?.recommendations.length || 0} recommendation(s)
          </p>
        </div>
        {!selectedControl?.recommendations.length ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">
            No current recommendations for this session.
          </p>
        ) : (
          <div className="mt-3 space-y-3">
            {selectedControl.recommendations.map((recommendation) => {
              const busy = busyActionKey === `recommendation:${recommendation.kind}`;

              return (
                <div
                  key={recommendation.kind}
                  className="rounded-xl border border-[#ecebe8] bg-white p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[14px] font-semibold text-[#37352f]">
                          {recommendation.title}
                        </p>
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(recommendation.priority)}`}
                        >
                          {recommendation.priority}
                        </Badge>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {recommendation.kind}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">
                        {recommendation.reason}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Object.entries(recommendation.counts || {}).map(([key, value]) => (
                          <Badge
                            key={`${recommendation.kind}-${key}`}
                            variant="outline"
                            className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                          >
                            {key}: {value}
                          </Badge>
                        ))}
                      </div>
                      {recommendation.operation.type === "session_action_batch" &&
                      recommendation.operation.mode === "execute" ? (
                        <p className="mt-3 text-[12px] text-[#9b9a97]">
                          Direct execution bypasses explicit preview review. Prefer the preview gate
                          above when you want inspect-first control.
                        </p>
                      ) : null}
                    </div>
                    <Button
                      size="sm"
                      className="h-9 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onApplyRecommendation(recommendation);
                      }}
                    >
                      {busy ? "Running..." : recommendationActionLabel(recommendation)}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
