"use client";

import Link from "next/link";
import { RelationshipStrip, SessionMetric, type RelationshipStripItem } from "@/components/control-plane-display";
import { approvalStatusClass, issueSeverityClass, issueStatusClass, passStatusClass } from "@/lib/control-plane-ui";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  OrchestratorSessionDetail,
} from "@/lib/types";

type SelectedSessionContextValue =
  | { kind: "approval"; approval: ExecutionApprovalRecord }
  | { kind: "issue"; issue: ExecutionIssueRecord }
  | { kind: "event"; event: Record<string, unknown> };

type RelatedRunLink = {
  run: ExecutionAgentActionRunRecord;
  resultIndex: number;
};

type RunLinkResolverContext = {
  approvalId?: string;
  issueId?: string;
  runId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
  resultIndex?: number;
};

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type LinkedSelectionPayload = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

type SelectedSessionContextCardProps = {
  selectedSession: OrchestratorSessionDetail | null;
  selectedSessionContext: SelectedSessionContextValue | null;
  linkedRuns: ExecutionAgentActionRunRecord[];
  busyActionKey: string;
  currentSessionLineageQueue: "" | "attention" | "decisions" | null;
  formatTimestamp: (value?: string | null) => string;
  formatJson: (value: unknown) => string;
  toStringValue: (value: unknown, fallback?: string) => string;
  toStringArray: (value: unknown) => string[];
  toNullableNumber: (value: unknown) => number | null;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  eventFamily: (eventName: string) => string;
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  resolveRunLinkFromContext: (
    runs: ExecutionAgentActionRunRecord[],
    context: RunLinkResolverContext
  ) => RelatedRunLink | null;
  onCopyLink: () => void;
  onRevealSessionRow: () => void;
  onRevealInAgentTimeline: () => void;
  onOpenRuntimeAgent: (runtimeAgentId: string) => void;
  onSyncLinkedSelection: (payload: LinkedSelectionPayload) => void;
  onOpenRunOutcome: (runId: string, resultIndex: number) => void;
  onApproveApproval: (approval: ExecutionApprovalRecord) => void;
  onRejectApproval: (approval: ExecutionApprovalRecord) => void;
  onApplyApproval: (approval: ExecutionApprovalRecord) => void;
  onResolveIssue: (issue: ExecutionIssueRecord) => void;
  onAdvanceCurrentQueue?: (() => void) | null;
};

export function SelectedSessionContextCard({
  selectedSession,
  selectedSessionContext,
  linkedRuns,
  busyActionKey,
  currentSessionLineageQueue,
  formatTimestamp,
  formatJson,
  toStringValue,
  toStringArray,
  toNullableNumber,
  asRecord,
  eventFamily,
  describeRunResult,
  resolveRunLinkFromContext,
  onCopyLink,
  onRevealSessionRow,
  onRevealInAgentTimeline,
  onOpenRuntimeAgent,
  onSyncLinkedSelection,
  onOpenRunOutcome,
  onApproveApproval,
  onRejectApproval,
  onApplyApproval,
  onResolveIssue,
  onAdvanceCurrentQueue,
}: SelectedSessionContextCardProps) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Selected Session Context
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Compact inspector for the currently selected session approval, issue, or event.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedSession ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a session to inspect linked context.
          </div>
        ) : !selectedSessionContext ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Pick an approval, issue, event, or outcome to open the unified context inspector.
          </div>
        ) : (
          (() => {
            const contextKind = selectedSessionContext.kind;
            const approvalContext =
              contextKind === "approval" ? selectedSessionContext.approval : null;
            const issueContext = contextKind === "issue" ? selectedSessionContext.issue : null;
            const eventContext = contextKind === "event" ? selectedSessionContext.event : null;
            const relatedApprovalId =
              approvalContext?.id ||
              issueContext?.approval_id ||
              toStringValue(eventContext?.approval_id);
            const relatedIssueId =
              issueContext?.id ||
              approvalContext?.issue_id ||
              toStringValue(eventContext?.issue_id);
            const runtimeAgentId =
              approvalContext?.runtime_agent_ids[0] ||
              issueContext?.runtime_agent_ids[0] ||
              issueContext?.runtime_agent_id ||
              toStringValue(eventContext?.runtime_agent_id) ||
              toStringArray(eventContext?.runtime_agent_ids)[0] ||
              "";
            const projectId =
              approvalContext?.project_id ||
              issueContext?.project_id ||
              toStringValue(eventContext?.project_id);
            const storyId =
              issueContext?.story_id ?? toNullableNumber(eventContext?.story_id);
            const workspaceHref =
              projectId && storyId
                ? `/projects/${projectId}?storyId=${storyId}`
                : projectId
                  ? `/projects/${projectId}`
                  : "";
            const relatedRunLink = resolveRunLinkFromContext(linkedRuns, {
              approvalId: relatedApprovalId,
              issueId: relatedIssueId,
              runId:
                toStringValue(eventContext?.agent_action_run_id) ||
                toStringValue(eventContext?.run_id),
              runtimeAgentId,
              event: eventContext,
            });
            const relatedRunResult =
              relatedRunLink && relatedRunLink.run.results[relatedRunLink.resultIndex]
                ? asRecord(relatedRunLink.run.results[relatedRunLink.resultIndex])
                : null;
            const relatedOutcome = relatedRunResult
              ? describeRunResult(relatedRunResult)
              : null;
            const title =
              approvalContext?.action ||
              issueContext?.title ||
              issueContext?.root_cause ||
              issueContext?.id ||
              toStringValue(eventContext?.event, "unknown_event");
            const subtitle =
              approvalContext?.reason ||
              issueContext?.root_cause ||
              issueContext?.description ||
              toStringValue(eventContext?.message, "No event message") ||
              "No detail provided.";
            const timestamp =
              approvalContext?.applied_at ||
              approvalContext?.decided_at ||
              approvalContext?.updated_at ||
              approvalContext?.created_at ||
              issueContext?.resolved_at ||
              issueContext?.updated_at ||
              issueContext?.created_at ||
              toStringValue(eventContext?.timestamp);
            const status =
              approvalContext?.status ||
              issueContext?.status ||
              toStringValue(eventContext?.status, "unknown");
            const statusClass =
              contextKind === "approval"
                ? approvalStatusClass(status)
                : contextKind === "issue"
                  ? issueStatusClass(status)
                  : passStatusClass(status);
            const payload =
              (approvalContext ? asRecord(approvalContext) : null) ||
              (issueContext ? asRecord(issueContext) : null) ||
              eventContext ||
              {};
            const contextId =
              approvalContext?.id ||
              issueContext?.id ||
              toStringValue(eventContext?.id) ||
              title;
            const contextDetail =
              approvalContext?.action ||
              issueContext?.category ||
              toStringValue(eventContext?.event, "event");
            const runtimeAgentDetail =
              approvalContext?.requested_by ||
              issueContext?.related_command ||
              toStringValue(eventContext?.orchestrator_session_id, "No session token");

            return (
              <div className="space-y-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                      >
                        {contextKind}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${statusClass}`}
                      >
                        {status}
                      </Badge>
                      {contextKind === "issue" && (
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issueContext?.severity || "unknown")}`}
                        >
                          {issueContext?.severity || "unknown"}
                        </Badge>
                      )}
                      {contextKind === "event" && (
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {eventFamily(toStringValue(eventContext?.event))}
                        </Badge>
                      )}
                    </div>
                    <p className="mt-3 text-[14px] font-semibold text-[#37352f]">{title}</p>
                    <p className="mt-2 text-[13px] leading-relaxed text-[#6b6b6b]">{subtitle}</p>
                  </div>
                  <div className="flex flex-wrap items-start justify-end gap-2">
                    <p className="text-[12px] text-[#9b9a97]">{formatTimestamp(timestamp)}</p>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={onCopyLink}
                    >
                      Copy context link
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <SessionMetric label="ID" value={contextId} detail={contextDetail} />
                  <SessionMetric
                    label="Related Run"
                    value={relatedRunLink?.run.id || "No linked run"}
                    detail={
                      relatedRunLink
                        ? `${relatedRunLink.run.run_kind} · ${relatedRunLink.run.status}`
                        : "No action run linkage"
                    }
                  />
                  <SessionMetric
                    label="Runtime Agent"
                    value={runtimeAgentId || "No agent linkage"}
                    detail={runtimeAgentDetail}
                  />
                  <SessionMetric
                    label="Workspace"
                    value={projectId || "No project linkage"}
                    detail={storyId ? `story ${storyId}` : "No story linkage"}
                  />
                </div>

                <RelationshipStrip
                  label="Relationship Strip"
                  items={[
                    {
                      key: `context-${contextKind}-${contextId}`,
                      label: `${contextKind} ${contextId}`,
                      tone:
                        contextKind === "approval"
                          ? "approval"
                          : contextKind === "issue"
                            ? "issue"
                            : "event",
                      active: true,
                      onClick: onRevealSessionRow,
                    },
                    relatedRunLink
                      ? {
                          key: `run-${relatedRunLink.run.id}`,
                          label: `run ${relatedRunLink.run.id}`,
                          tone: "run" as const,
                          onClick: () => {
                            onOpenRunOutcome(relatedRunLink.run.id, 0);
                          },
                        }
                      : null,
                    relatedRunLink && relatedRunResult
                      ? {
                          key: `outcome-${relatedRunLink.run.id}-${relatedRunLink.resultIndex}`,
                          label: `outcome ${relatedRunLink.resultIndex + 1}`,
                          tone: "outcome" as const,
                          onClick: () => {
                            onOpenRunOutcome(relatedRunLink.run.id, relatedRunLink.resultIndex);
                          },
                        }
                      : null,
                    relatedApprovalId && contextKind !== "approval"
                      ? {
                          key: `approval-${relatedApprovalId}`,
                          label: `approval ${relatedApprovalId}`,
                          tone: "approval" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              runtimeAgentId,
                              event: eventContext,
                            });
                          },
                        }
                      : null,
                    relatedIssueId && contextKind !== "issue"
                      ? {
                          key: `issue-${relatedIssueId}`,
                          label: `issue ${relatedIssueId}`,
                          tone: "issue" as const,
                          onClick: () => {
                            onSyncLinkedSelection({
                              approvalId: relatedApprovalId,
                              issueId: relatedIssueId,
                              runtimeAgentId,
                              event: eventContext,
                            });
                          },
                        }
                      : null,
                    runtimeAgentId
                      ? {
                          key: `agent-${runtimeAgentId}`,
                          label: `agent ${runtimeAgentId}`,
                          tone: "agent" as const,
                          onClick: onRevealInAgentTimeline,
                        }
                      : null,
                  ].filter(Boolean) as RelationshipStripItem[]}
                />

                {(projectId || storyId || runtimeAgentId || relatedApprovalId || relatedIssueId) && (
                  <div className="flex flex-wrap gap-2">
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
                    {runtimeAgentId && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        agent {runtimeAgentId}
                      </Badge>
                    )}
                    {relatedApprovalId && contextKind !== "approval" && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                      >
                        approval {relatedApprovalId}
                      </Badge>
                    )}
                    {relatedIssueId && contextKind !== "issue" && (
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                      >
                        issue {relatedIssueId}
                      </Badge>
                    )}
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  {approvalContext?.status === "pending" && (
                    <>
                      <Button
                        size="sm"
                        className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onApproveApproval(approvalContext);
                        }}
                      >
                        {busyActionKey === `approval-approve:${approvalContext.id}` ? "Approving..." : "Approve"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                        disabled={Boolean(busyActionKey)}
                        onClick={() => {
                          onRejectApproval(approvalContext);
                        }}
                      >
                        {busyActionKey === `approval-reject:${approvalContext.id}` ? "Rejecting..." : "Reject"}
                      </Button>
                    </>
                  )}
                  {approvalContext?.status === "approved" && (
                    <Button
                      size="sm"
                      className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onApplyApproval(approvalContext);
                      }}
                    >
                      {busyActionKey === `approval-apply:${approvalContext.id}` ? "Applying..." : "Apply"}
                    </Button>
                  )}
                  {issueContext?.status === "open" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      disabled={Boolean(busyActionKey)}
                      onClick={() => {
                        onResolveIssue(issueContext);
                      }}
                    >
                      {busyActionKey === `issue-resolve:${issueContext.id}` ? "Resolving..." : "Resolve"}
                    </Button>
                  )}
                  {runtimeAgentId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onOpenRuntimeAgent(runtimeAgentId);
                      }}
                    >
                      Open agent
                    </Button>
                  )}
                  {currentSessionLineageQueue && onAdvanceCurrentQueue ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={onAdvanceCurrentQueue}
                    >
                      {currentSessionLineageQueue === "attention" ? "Next attention" : "Next decision"}
                    </Button>
                  ) : null}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={onRevealSessionRow}
                  >
                    Reveal session row
                  </Button>
                  {runtimeAgentId && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f2f8]"
                      onClick={onRevealInAgentTimeline}
                    >
                      Reveal in agent timeline
                    </Button>
                  )}
                  {relatedRunLink && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onOpenRunOutcome(relatedRunLink.run.id, relatedRunLink.resultIndex);
                      }}
                    >
                      Open related outcome
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
                </div>

                {relatedOutcome && (
                  <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Related Outcome
                    </p>
                    <p className="mt-2 text-[13px] font-semibold text-[#37352f]">
                      {relatedOutcome.title}
                    </p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">
                      {relatedOutcome.subtitle || "No outcome subtype"}
                    </p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">{relatedOutcome.message}</p>
                  </div>
                )}

                <div className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Payload
                  </p>
                  <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#37352f]">
                    {formatJson(payload)}
                  </pre>
                </div>
              </div>
            );
          })()
        )}
      </CardContent>
    </Card>
  );
}
