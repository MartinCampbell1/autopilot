"use client";

import Link from "next/link";
import {
  RelationshipStrip,
  SessionMetric,
  type RelationshipStripItem,
} from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  approvalStatusClass,
  passStatusClass,
  triagePriorityClass,
} from "@/lib/control-plane-ui";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  ExecutionRuntimeAgentDetail,
} from "@/lib/types";

type AgentTimelineEntry = {
  kind: "approval" | "issue" | "event";
  id: string;
  timestamp: string;
  status: string;
  title: string;
  subtitle: string;
  message: string;
  approval?: ExecutionApprovalRecord;
  issue?: ExecutionIssueRecord;
  event?: Record<string, unknown>;
};

type TriagePriority = "critical" | "high" | "normal";

type RelatedRunLink = {
  run: ExecutionAgentActionRunRecord;
  resultIndex: number;
};

type LinkedSelectionPayload = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type RuntimeAgentInspectorColumnProps = {
  selectedAgent: ExecutionRuntimeAgentDetail;
  selectedAgentTimelineEntry: AgentTimelineEntry | null;
  selectedAgentTimelineRunLink: RelatedRunLink | null;
  selectedAgentTimelinePriority: TriagePriority | null;
  currentAgentPriorityQueue: "critical" | "high" | null;
  latestAgentIssueEntry: AgentTimelineEntry | null;
  latestAgentApprovalEntry: AgentTimelineEntry | null;
  latestAgentEventEntry: AgentTimelineEntry | null;
  busyActionKey: string;
  formatTimestamp: (value?: string | null) => string;
  formatJson: (value: unknown) => string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toNullableNumber: (value: unknown) => number | null;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  onSelectTimelineEntry: (entry: AgentTimelineEntry) => void;
  onSyncLinkedSelection: (payload: LinkedSelectionPayload) => void;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  onSelectRun: (runId: string, resultIndex: number) => void;
  onApproveApproval: (approval: ExecutionApprovalRecord) => void;
  onRejectApproval: (approval: ExecutionApprovalRecord) => void;
  onApplyApproval: (approval: ExecutionApprovalRecord) => void;
  onResolveIssue: (issue: ExecutionIssueRecord) => void;
  onAdvanceCurrentPriorityQueue: (entry: AgentTimelineEntry) => void;
  onSearchEntity: (value: string) => void;
  onFocusAgentTimeline: (
    filter: "issues" | "approvals" | "events" | "attention",
    entry?: AgentTimelineEntry
  ) => void;
  onFilterSessionByToken: (value: string) => void;
};

function entryStatusClass(entry: AgentTimelineEntry): string {
  if (entry.kind === "approval") return approvalStatusClass(entry.status);
  if (entry.kind === "issue") return passStatusClass(entry.status === "open" ? "partial" : "ok");
  return passStatusClass(entry.status);
}

export function RuntimeAgentInspectorColumn({
  selectedAgent,
  selectedAgentTimelineEntry,
  selectedAgentTimelineRunLink,
  selectedAgentTimelinePriority,
  currentAgentPriorityQueue,
  latestAgentIssueEntry,
  latestAgentApprovalEntry,
  latestAgentEventEntry,
  busyActionKey,
  formatTimestamp,
  formatJson,
  toStringValue,
  toNullableNumber,
  asRecord,
  describeRunResult,
  onSelectTimelineEntry,
  onSyncLinkedSelection,
  onFocusRuntimeAgent,
  onSelectRun,
  onApproveApproval,
  onRejectApproval,
  onApplyApproval,
  onResolveIssue,
  onAdvanceCurrentPriorityQueue,
  onSearchEntity,
  onFocusAgentTimeline,
  onFilterSessionByToken,
}: RuntimeAgentInspectorColumnProps) {
  return (
    <>
      {selectedAgentTimelineEntry && (
        <div className="rounded-xl border border-[#ecebe8] bg-white p-4">
          {(() => {
            const entry = selectedAgentTimelineEntry;
            const workspaceProjectId =
              toStringValue(entry.approval?.project_id) ||
              toStringValue(entry.issue?.project_id) ||
              toStringValue(entry.event?.project_id);
            const workspaceStoryId =
              entry.issue?.story_id ?? toNullableNumber(entry.event?.story_id);
            const workspaceHref =
              workspaceProjectId && workspaceStoryId
                ? `/projects/${workspaceProjectId}?storyId=${workspaceStoryId}`
                : workspaceProjectId
                  ? `/projects/${workspaceProjectId}`
                  : "";
            const relatedApprovalId =
              toStringValue(entry.approval?.id) ||
              toStringValue(entry.issue?.approval_id) ||
              toStringValue(entry.event?.approval_id);
            const relatedIssueId =
              toStringValue(entry.issue?.id) || toStringValue(entry.event?.issue_id);
            const relatedRunLink = selectedAgentTimelineRunLink;
            const relatedRunResult =
              relatedRunLink && relatedRunLink.run.results[relatedRunLink.resultIndex]
                ? asRecord(relatedRunLink.run.results[relatedRunLink.resultIndex])
                : null;
            const relatedRunOutcome = relatedRunResult
              ? describeRunResult(relatedRunResult)
              : null;
            const payload =
              entry.approval || entry.issue || entry.event || {
                id: entry.id,
                kind: entry.kind,
                timestamp: entry.timestamp,
                status: entry.status,
                title: entry.title,
                subtitle: entry.subtitle,
                message: entry.message,
              };

            return (
              <>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Selected Timeline Item
                    </p>
                    <p className="mt-2 text-[14px] font-semibold text-[#37352f]">{entry.title}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                    >
                      {entry.kind}
                    </Badge>
                    {selectedAgentTimelinePriority ? (
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(selectedAgentTimelinePriority)}`}
                      >
                        {selectedAgentTimelinePriority}
                      </Badge>
                    ) : null}
                    <Badge
                      variant="outline"
                      className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${entryStatusClass(entry)}`}
                    >
                      {entry.status}
                    </Badge>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  <SessionMetric
                    label="Timestamp"
                    value={formatTimestamp(entry.timestamp)}
                    detail={entry.id}
                  />
                  <SessionMetric
                    label="Scope"
                    value={entry.subtitle || "No scope metadata"}
                    detail={workspaceProjectId || "No project linkage"}
                  />
                  <SessionMetric
                    label="Related Run"
                    value={relatedRunLink?.run.id || "No linked run"}
                    detail={
                      relatedRunLink
                        ? `${relatedRunLink.run.run_kind} · ${relatedRunLink.run.status}`
                        : "No related action run found"
                    }
                  />
                  <SessionMetric
                    label="Outcome"
                    value={
                      relatedRunResult
                        ? toStringValue(
                            relatedRunResult.status,
                            `result #${relatedRunLink?.resultIndex ?? 0}`
                          )
                        : "No linked outcome"
                    }
                    detail={
                      relatedRunOutcome?.title ||
                      (relatedRunLink
                        ? "Related run found without a specific outcome match"
                        : "No outcome linkage")
                    }
                  />
                </div>

                <RelationshipStrip
                  label="Relationship Strip"
                  items={[
                    {
                      key: `timeline-${entry.kind}-${entry.id}`,
                      label: `${entry.kind} ${entry.id}`,
                      tone:
                        entry.kind === "approval"
                          ? "approval"
                          : entry.kind === "issue"
                            ? "issue"
                            : "event",
                      active: true,
                      onClick: () => {
                        onSelectTimelineEntry(entry);
                      },
                    },
                    relatedRunLink
                      ? {
                          key: `run-${relatedRunLink.run.id}`,
                          label: `run ${relatedRunLink.run.id}`,
                          tone: "run" as const,
                          onClick: () => {
                            onSelectRun(relatedRunLink.run.id, 0);
                          },
                        }
                      : null,
                    relatedRunLink && relatedRunResult
                      ? {
                          key: `outcome-${relatedRunLink.run.id}-${relatedRunLink.resultIndex}`,
                          label: `outcome ${relatedRunLink.resultIndex + 1}`,
                          tone: "outcome" as const,
                          onClick: () => {
                            onSelectRun(relatedRunLink.run.id, relatedRunLink.resultIndex);
                          },
                        }
                      : null,
                    relatedApprovalId && entry.kind !== "approval"
                      ? {
                          key: `approval-${relatedApprovalId}`,
                          label: `approval ${relatedApprovalId}`,
                          tone: "approval" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              runId: relatedRunLink?.run.id,
                              resultIndex: relatedRunLink?.resultIndex,
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              runtimeAgentId: selectedAgent.runtime_agent_id,
                              event: entry.event || null,
                            });
                          },
                        }
                      : null,
                    relatedIssueId && entry.kind !== "issue"
                      ? {
                          key: `issue-${relatedIssueId}`,
                          label: `issue ${relatedIssueId}`,
                          tone: "issue" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              runId: relatedRunLink?.run.id,
                              resultIndex: relatedRunLink?.resultIndex,
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              runtimeAgentId: selectedAgent.runtime_agent_id,
                              event: entry.event || null,
                            });
                          },
                        }
                      : null,
                    {
                      key: `agent-${selectedAgent.runtime_agent_id}`,
                      label: `agent ${selectedAgent.runtime_agent_id}`,
                      tone: "agent",
                      onClick: () => {
                        onFocusRuntimeAgent(selectedAgent.runtime_agent_id);
                      },
                    },
                  ].filter(Boolean) as RelationshipStripItem[]}
                />

                <p className="mt-4 text-[13px] leading-relaxed text-[#6b6b6b]">{entry.message}</p>

                <div className="mt-4 flex flex-wrap gap-2">
                  {entry.approval?.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onApproveApproval(entry.approval!);
                        }}
                      >
                        {busyActionKey === `approval-approve:${entry.approval.id}`
                          ? "Approving..."
                          : "Approve"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onRejectApproval(entry.approval!);
                        }}
                      >
                        {busyActionKey === `approval-reject:${entry.approval.id}`
                          ? "Rejecting..."
                          : "Reject"}
                      </Button>
                    </>
                  )}
                  {entry.approval?.status === "approved" && (
                    <Button
                      size="sm"
                      className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onApplyApproval(entry.approval!);
                      }}
                    >
                      {busyActionKey === `approval-apply:${entry.approval.id}`
                        ? "Applying..."
                        : "Apply"}
                    </Button>
                  )}
                  {entry.issue?.status === "open" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onResolveIssue(entry.issue!);
                      }}
                    >
                      {busyActionKey === `issue-resolve:${entry.issue.id}`
                        ? "Resolving..."
                        : "Resolve"}
                    </Button>
                  )}
                  {currentAgentPriorityQueue ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={() => {
                        onAdvanceCurrentPriorityQueue(entry);
                      }}
                    >
                      {currentAgentPriorityQueue === "critical" ? "Next critical" : "Next high"}
                    </Button>
                  ) : null}
                  {relatedApprovalId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={() => {
                        onSearchEntity(relatedApprovalId);
                      }}
                    >
                      Find approval
                    </Button>
                  )}
                  {relatedIssueId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#f4e0c4] bg-[#fff6e8] text-[12px] text-[#9a6700] hover:bg-[#fff0d9]"
                      onClick={() => {
                        onSearchEntity(relatedIssueId);
                      }}
                    >
                      Find issue
                    </Button>
                  )}
                  {workspaceHref && (
                    <Link
                      href={workspaceHref}
                      className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                    >
                      Open workspace
                    </Link>
                  )}
                  {relatedRunLink && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onSelectRun(relatedRunLink.run.id, 0);
                      }}
                    >
                      Open related run
                    </Button>
                  )}
                  {relatedRunLink && relatedRunResult && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={() => {
                        onSelectRun(relatedRunLink.run.id, relatedRunLink.resultIndex);
                      }}
                    >
                      Open related outcome
                    </Button>
                  )}
                </div>

                <div className="mt-4 rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Payload
                  </p>
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                    {formatJson(payload)}
                  </pre>
                </div>
              </>
            );
          })()}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Issues Summary
          </p>
          <div className="mt-3 grid gap-3">
            <SessionMetric
              label="Open Issues"
              value={String(selectedAgent.history.open_issue_count)}
              detail={`${selectedAgent.history.issue_count} total issues`}
            />
          </div>
          {!latestAgentIssueEntry ? (
            <p className="mt-3 text-[13px] text-[#9b9a97]">No issue history for this agent.</p>
          ) : (
            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-[11px] text-[#37352f]">
                  {toStringValue(latestAgentIssueEntry.issue?.id, latestAgentIssueEntry.id)}
                </p>
                <Badge
                  variant="outline"
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(latestAgentIssueEntry.status === "open" ? "partial" : "ok")}`}
                >
                  {latestAgentIssueEntry.status}
                </Badge>
              </div>
              <p className="mt-2 text-[12px] text-[#6b6b6b]">{latestAgentIssueEntry.title}</p>
              <p className="mt-1 text-[11px] text-[#9b9a97]">
                {formatTimestamp(latestAgentIssueEntry.timestamp)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onFocusAgentTimeline("issues", latestAgentIssueEntry);
                  }}
                >
                  Open in timeline
                </Button>
                {latestAgentIssueEntry.issue?.status === "open" && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                    disabled={Boolean(busyActionKey)}
                    onClick={() => {
                      onResolveIssue(latestAgentIssueEntry.issue!);
                    }}
                  >
                    {busyActionKey === `issue-resolve:${latestAgentIssueEntry.issue.id}`
                      ? "Resolving..."
                      : "Resolve"}
                  </Button>
                )}
                {latestAgentIssueEntry.issue?.id && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                    onClick={() => {
                      onSearchEntity(toStringValue(latestAgentIssueEntry.issue?.id));
                    }}
                  >
                    Find in session
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Approvals Summary
          </p>
          <div className="mt-3 grid gap-3">
            <SessionMetric
              label="Pending Approvals"
              value={String(selectedAgent.history.pending_approval_count)}
              detail={`${selectedAgent.history.approval_count} total approvals`}
            />
          </div>
          {!latestAgentApprovalEntry ? (
            <p className="mt-3 text-[13px] text-[#9b9a97]">No approval history for this agent.</p>
          ) : (
            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-[11px] text-[#37352f]">
                  {toStringValue(latestAgentApprovalEntry.approval?.id, latestAgentApprovalEntry.id)}
                </p>
                <Badge
                  variant="outline"
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${approvalStatusClass(latestAgentApprovalEntry.status)}`}
                >
                  {latestAgentApprovalEntry.status}
                </Badge>
              </div>
              <p className="mt-2 text-[12px] text-[#6b6b6b]">{latestAgentApprovalEntry.title}</p>
              <p className="mt-1 text-[11px] text-[#9b9a97]">
                {formatTimestamp(latestAgentApprovalEntry.timestamp)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onFocusAgentTimeline("approvals", latestAgentApprovalEntry);
                  }}
                >
                  Open in timeline
                </Button>
                {latestAgentApprovalEntry.approval?.status === "pending" && (
                  <>
                    <Button
                      size="sm"
                      className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onApproveApproval(latestAgentApprovalEntry.approval!);
                      }}
                    >
                      {busyActionKey === `approval-approve:${latestAgentApprovalEntry.approval.id}`
                        ? "Approving..."
                        : "Approve"}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onRejectApproval(latestAgentApprovalEntry.approval!);
                      }}
                    >
                      {busyActionKey === `approval-reject:${latestAgentApprovalEntry.approval.id}`
                        ? "Rejecting..."
                        : "Reject"}
                    </Button>
                  </>
                )}
                {latestAgentApprovalEntry.approval?.status === "approved" && (
                  <Button
                    size="sm"
                    className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
                    disabled={Boolean(busyActionKey)}
                    onClick={() => {
                      onApplyApproval(latestAgentApprovalEntry.approval!);
                    }}
                  >
                    {busyActionKey === `approval-apply:${latestAgentApprovalEntry.approval.id}`
                      ? "Applying..."
                      : "Apply"}
                  </Button>
                )}
                {latestAgentApprovalEntry.approval?.id && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                    onClick={() => {
                      onSearchEntity(toStringValue(latestAgentApprovalEntry.approval?.id));
                    }}
                  >
                    Find in session
                  </Button>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Events Summary
          </p>
          <div className="mt-3 grid gap-3">
            <SessionMetric
              label="Events"
              value={String(selectedAgent.history.event_count)}
              detail={formatTimestamp(selectedAgent.history.last_event_at)}
            />
          </div>
          {!latestAgentEventEntry ? (
            <p className="mt-3 text-[13px] text-[#9b9a97]">No event history for this agent.</p>
          ) : (
            <div className="mt-3 rounded-xl border border-[#ecebe8] bg-white p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-mono text-[11px] text-[#37352f]">{latestAgentEventEntry.title}</p>
                <Badge
                  variant="outline"
                  className={`rounded-full px-2.5 py-1 text-[11px] font-medium capitalize ${passStatusClass(latestAgentEventEntry.status)}`}
                >
                  {latestAgentEventEntry.status}
                </Badge>
              </div>
              <p className="mt-2 text-[12px] text-[#6b6b6b]">{latestAgentEventEntry.message}</p>
              <p className="mt-1 text-[11px] text-[#9b9a97]">
                {formatTimestamp(latestAgentEventEntry.timestamp)}
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onFocusAgentTimeline("events", latestAgentEventEntry);
                  }}
                >
                  Open in timeline
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                  onClick={() => {
                    onFocusAgentTimeline("attention");
                  }}
                >
                  Show attention
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onFilterSessionByToken(
                      toStringValue(latestAgentEventEntry.event?.event) ||
                        toStringValue(latestAgentEventEntry.event?.message) ||
                        latestAgentEventEntry.id
                    );
                  }}
                >
                  Filter session
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
