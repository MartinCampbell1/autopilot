"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ShadowAuditReviewSheet } from "@/components/shadow-audit-review-sheet";
import { SessionMetric } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  fetchExecutionPlaneAgentActionRuns,
  fetchExecutionPlaneProject,
  resolveExecutionPlaneShadowAudit,
} from "@/lib/api";
import { buildStoryRuntimeHandoffSnapshot } from "@/lib/story-runtime-handoffs";
import { useShadowAuditReviewController } from "@/lib/use-shadow-audit-review-controller";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionPlaneProjectDetail,
  ExecutionShadowAuditRecord,
  Story,
} from "@/lib/types";

type StoryRuntimeHandoffsPanelProps = {
  projectId: string;
  story: Story;
};

function formatTimestamp(value?: string | null) {
  if (!value) return "No timestamp";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function sentenceCase(value?: string | null) {
  return value ? value.replaceAll("_", " ") : "Unknown";
}

function attentionClass(state?: string | null): string {
  switch ((state || "").trim()) {
    case "critical":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "needs_attention":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "healthy":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function statusClass(status?: string | null): string {
  switch ((status || "").trim()) {
    case "quarantined":
    case "blocked":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "running":
    case "active":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "completed":
    case "resolved":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function sourceLabel(audit: ExecutionShadowAuditRecord) {
  const sourceName = (audit.source_name || "").trim();
  if (sourceName) return sourceName;
  const sourceKind = (audit.source_kind || "").trim();
  return sourceKind ? sourceKind.replaceAll("_", " ") : "shadow audit";
}

export function StoryRuntimeHandoffsPanel({
  projectId,
  story,
}: StoryRuntimeHandoffsPanelProps) {
  const [projectDetail, setProjectDetail] = useState<ExecutionPlaneProjectDetail | null>(null);
  const [runs, setRuns] = useState<ExecutionAgentActionRunRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [busyActionKey, setBusyActionKey] = useState("");

  const load = useCallback(async () => {
    if (!projectId || !Number.isFinite(story.id)) return;
    setLoading(true);
    setError("");
    try {
      const [projectPayload, runsPayload] = await Promise.all([
        fetchExecutionPlaneProject(projectId),
        fetchExecutionPlaneAgentActionRuns({ projectId }),
      ]);
      setProjectDetail(projectPayload);
      setRuns(runsPayload.runs || []);
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load runtime handoff state."
      );
    } finally {
      setLoading(false);
    }
  }, [projectId, story.id]);

  useEffect(() => {
    void load();
  }, [load, story.status, story.updated_at]);

  const snapshot = useMemo(
    () => buildStoryRuntimeHandoffSnapshot(story.id, projectDetail, runs),
    [projectDetail, runs, story.id]
  );
  const storyAgents = snapshot.agents;
  const storyRuns = snapshot.storyRuns;
  const blockedRuns = snapshot.blockedRuns;
  const handoffRows = snapshot.handoffRows;
  const agentOpenIssueCount = useMemo(
    () => storyAgents.reduce((sum, agent) => sum + agent.open_issue_count, 0),
    [storyAgents]
  );
  const agentPendingApprovalCount = useMemo(
    () => storyAgents.reduce((sum, agent) => sum + agent.pending_approval_count, 0),
    [storyAgents]
  );
  const agentAsyncTaskCount = useMemo(
    () => storyAgents.reduce((sum, agent) => sum + (agent.active_async_task_count ?? 0), 0),
    [storyAgents]
  );

  const handleResolveShadowAudit = useCallback(
    async (audit: ExecutionShadowAuditRecord) => {
      const actionKey = `shadow-audit-resolve:${audit.id}`;
      setBusyActionKey(actionKey);
      setError("");
      try {
        await resolveExecutionPlaneShadowAudit(audit.id, {
          actor: "dashboard-project-workspace",
        });
        await load();
      } catch (resolveError) {
        setError(
          resolveError instanceof Error
            ? resolveError.message
            : "Failed to release shadow-audit quarantine."
        );
        throw resolveError;
      } finally {
        setBusyActionKey("");
      }
    },
    [load]
  );
  const {
    queueAudits,
    queueOpen,
    setQueueOpen,
    activeQueueAudit,
    activeQueueAuditIndex,
    reviewQueueLabel,
    openReviewQueue: openStoryShadowAuditQueue,
    handleSelectNextQueuedAudit,
    handleSelectPreviousQueuedAudit,
    handleResolveQueuedShadowAudit,
  } = useShadowAuditReviewController({
    audits: snapshot.openShadowAudits,
    onResolveShadowAudit: handleResolveShadowAudit,
  });

  return (
    <div className="mt-4 space-y-4 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-4 text-[13px] text-[#6b6b6b]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">Runtime Handoffs</p>
          <p className="mt-1 text-[#37352f]">
            Story-scoped runtime agents, blocked handoffs, and `shadow_audit` release controls.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
          disabled={loading}
          onClick={() => {
            void load();
          }}
        >
          {loading ? "Refreshing..." : "Refresh"}
        </Button>
      </div>

      {error ? (
        <div className="rounded-xl border border-[#f4e0c4] bg-[#fff6e8] px-3 py-3 text-[12px] text-[#9a6700]">
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-3">
        <SessionMetric
          label="Runtime Agents"
          value={String(storyAgents.length)}
          detail={`${agentOpenIssueCount} open issue${agentOpenIssueCount === 1 ? "" : "s"}`}
        />
        <SessionMetric
          label="Blocked Handoffs"
          value={String(blockedRuns.length)}
          detail={`${handoffRows.length} reviewable shadow audit${handoffRows.length === 1 ? "" : "s"}`}
        />
        <SessionMetric
          label="Pending Approvals"
          value={String(agentPendingApprovalCount)}
          detail={`${agentAsyncTaskCount} active async task${agentAsyncTaskCount === 1 ? "" : "s"}`}
        />
        <SessionMetric
          label="Story Runs"
          value={String(storyRuns.length)}
          detail={storyAgents.length > 0 ? "Linked by runtime agent ownership" : "Waiting for runtime agent mapping"}
        />
      </div>

      {loading && !projectDetail ? (
        <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-white px-4 py-6 text-[#9b9a97]">
          Loading runtime handoff state...
        </div>
      ) : storyAgents.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-white px-4 py-6 text-[#9b9a97]">
          No runtime agents are mapped to this story yet.
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {storyAgents.map((agent) => (
              <div
                key={agent.agent_id}
                className="rounded-xl border border-[#ecebe8] bg-white px-3 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[13px] font-medium text-[#37352f]">
                        {agent.label || agent.agent_id}
                      </p>
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusClass(agent.status)}`}
                      >
                        {sentenceCase(agent.status)}
                      </Badge>
                      {agent.attention?.state ? (
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${attentionClass(agent.attention.state)}`}
                        >
                          {sentenceCase(agent.attention.state)}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="mt-2 text-[12px] text-[#787774]">
                      {agent.role}
                      {agent.provider ? ` · ${agent.provider}` : ""}
                      {agent.profile_name ? ` · ${agent.profile_name}` : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      {agent.open_issue_count} issue{agent.open_issue_count === 1 ? "" : "s"}
                    </Badge>
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                    >
                      {agent.pending_approval_count} approval{agent.pending_approval_count === 1 ? "" : "s"}
                    </Badge>
                    {(agent.active_async_task_count ?? 0) > 0 ? (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d6e9dc] bg-[#eef8f1] px-2.5 py-1 text-[11px] font-medium text-[#2b6e3f]"
                      >
                        {agent.active_async_task_count} async
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {handoffRows.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-white px-4 py-6 text-[#9b9a97]">
              No blocked runtime handoffs for this story right now.
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] uppercase tracking-[0.08em] text-[#9b9a97]">
                  Open Shadow Audits
                </p>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                >
                  {handoffRows.length} blocked handoff{handoffRows.length === 1 ? "" : "s"}
                </Badge>
              </div>
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
              {handoffRows.map(({ audit, run, agents }) => (
                <div
                  key={audit.id}
                  className="rounded-xl border border-[#f4e0c4] bg-white px-3 py-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="text-[13px] font-medium text-[#37352f]">
                          {audit.summary || "Blocked runtime handoff requires review."}
                        </p>
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                        >
                          {sourceLabel(audit)}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[12px] text-[#787774]">
                        {agents.length > 0
                          ? agents.map((agent) => agent.label || agent.agent_id).join(", ")
                          : "Runtime agent link unavailable"}
                        {" · "}
                        run {run.id}
                      </p>
                      <p className="mt-2 text-[12px] text-[#6b6b6b]">
                        {audit.findings?.length
                          ? audit.findings.join(" · ")
                          : "Quarantined handoff is waiting for explicit operator release."}
                      </p>
                      <p className="mt-2 text-[11px] text-[#9b9a97]">
                        created {formatTimestamp(audit.created_at)}
                        {" · "}
                        updated {formatTimestamp(audit.updated_at)}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusClass(run.completion_state || run.status)}`}
                      >
                        {sentenceCase(run.completion_state || run.status)}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                        onClick={() => {
                          openStoryShadowAuditQueue(audit.id);
                        }}
                      >
                        {reviewQueueLabel}
                      </Button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
