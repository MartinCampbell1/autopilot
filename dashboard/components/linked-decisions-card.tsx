"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  approvalStatusClass,
  issueSeverityClass,
  issueStatusClass,
} from "@/lib/control-plane-ui";
import type {
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  OrchestratorSessionDetail,
} from "@/lib/types";

type LinkedDecisionsCardProps = {
  selectedSession: OrchestratorSessionDetail | null;
  linkedApprovals: ExecutionApprovalRecord[];
  filteredApprovals: ExecutionApprovalRecord[];
  visibleSessionApprovals: ExecutionApprovalRecord[];
  selectedSessionApprovalId: string;
  linkedIssues: ExecutionIssueRecord[];
  filteredIssues: ExecutionIssueRecord[];
  visibleSessionIssues: ExecutionIssueRecord[];
  selectedSessionIssueId: string;
  busyActionKey: string;
  formatTimestamp: (value?: string | null) => string;
  sessionContextRowDomId: (kind: "approval" | "issue" | "event", key: string) => string;
  onSearchEntity: (value: string) => void;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  onInspectApproval: (approval: ExecutionApprovalRecord) => void;
  onInspectIssue: (issue: ExecutionIssueRecord) => void;
  onApproveApproval: (approval: ExecutionApprovalRecord) => void;
  onRejectApproval: (approval: ExecutionApprovalRecord) => void;
  onApplyApproval: (approval: ExecutionApprovalRecord) => void;
  onResolveIssue: (issue: ExecutionIssueRecord) => void;
};

export function LinkedDecisionsCard({
  selectedSession,
  linkedApprovals,
  filteredApprovals,
  visibleSessionApprovals,
  selectedSessionApprovalId,
  linkedIssues,
  filteredIssues,
  visibleSessionIssues,
  selectedSessionIssueId,
  busyActionKey,
  formatTimestamp,
  sessionContextRowDomId,
  onSearchEntity,
  onFocusRuntimeAgent,
  onInspectApproval,
  onInspectIssue,
  onApproveApproval,
  onRejectApproval,
  onApplyApproval,
  onResolveIssue,
}: LinkedDecisionsCardProps) {
  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Linked Decisions
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Approvals and issues attached to the selected session, with direct control actions.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedSession ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a session to inspect pending approvals and issues.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                  Session Approvals
                </p>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredApprovals.length}
                </Badge>
              </div>
              {filteredApprovals.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">
                  {linkedApprovals.length
                    ? "No approvals match the current search."
                    : "No linked approvals."}
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {visibleSessionApprovals.map((approval) => {
                    const selected = selectedSessionApprovalId === approval.id;
                    return (
                      <div
                        key={`${selectedSession.id}-approval-${approval.id}`}
                        id={sessionContextRowDomId("approval", approval.id)}
                        className={`rounded-xl border p-3 ${
                          selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-mono text-[11px] text-[#37352f]">{approval.id}</p>
                              <Badge
                                variant="outline"
                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${approvalStatusClass(approval.status)}`}
                              >
                                {approval.status}
                              </Badge>
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                {approval.action}
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
                                  onInspectApproval(approval);
                                }}
                              >
                                {selected ? "Selected" : "Inspect"}
                              </Button>
                            </div>
                            <p className="mt-2 text-[13px] text-[#6b6b6b]">
                              {approval.reason || `Approval requested for ${approval.action}.`}
                            </p>
                            <p className="mt-2 text-[12px] text-[#9b9a97]">
                              Requested by {approval.requested_by || "unknown"} ·{" "}
                              {formatTimestamp(approval.created_at)}
                            </p>
                            {(approval.policy_reasons.length > 0 ||
                              approval.issue_id ||
                              approval.runtime_agent_ids.length > 0) && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {approval.issue_id && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                    onClick={() => {
                                      onSearchEntity(approval.issue_id);
                                    }}
                                  >
                                    issue {approval.issue_id}
                                  </Button>
                                )}
                                {approval.runtime_agent_ids.slice(0, 2).map((runtimeAgentId) => (
                                  <Button
                                    key={`${approval.id}-${runtimeAgentId}`}
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
                                {approval.policy_reasons.slice(0, 3).map((reason) => (
                                  <Badge
                                    key={`${approval.id}-${reason}`}
                                    variant="outline"
                                    className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                                  >
                                    {reason}
                                  </Badge>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {approval.status === "pending" && (
                              <>
                                <Button
                                  size="sm"
                                  className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                  disabled={Boolean(busyActionKey)}
                                  onClick={() => {
                                    onApproveApproval(approval);
                                  }}
                                >
                                  {busyActionKey === `approval-approve:${approval.id}`
                                    ? "Approving..."
                                    : "Approve"}
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                  disabled={Boolean(busyActionKey)}
                                  onClick={() => {
                                    onRejectApproval(approval);
                                  }}
                                >
                                  {busyActionKey === `approval-reject:${approval.id}`
                                    ? "Rejecting..."
                                    : "Reject"}
                                </Button>
                              </>
                            )}
                            {approval.status === "approved" && (
                              <Button
                                size="sm"
                                className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                                disabled={Boolean(busyActionKey)}
                                onClick={() => {
                                  onApplyApproval(approval);
                                }}
                              >
                                {busyActionKey === `approval-apply:${approval.id}`
                                  ? "Applying..."
                                  : "Apply"}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <div className="flex items-center justify-between">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                  Session Issues
                </p>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredIssues.length}
                </Badge>
              </div>
              {filteredIssues.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">
                  {linkedIssues.length ? "No issues match the current search." : "No linked issues."}
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {visibleSessionIssues.map((issue) => {
                    const selected = selectedSessionIssueId === issue.id;
                    const runtimeAgentIds =
                      issue.runtime_agent_ids.length > 0
                        ? issue.runtime_agent_ids.slice(0, 2)
                        : issue.runtime_agent_id
                          ? [issue.runtime_agent_id]
                          : [];
                    return (
                      <div
                        key={`${selectedSession.id}-issue-${issue.id}`}
                        id={sessionContextRowDomId("issue", issue.id)}
                        className={`rounded-xl border p-3 ${
                          selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-mono text-[11px] text-[#37352f]">{issue.id}</p>
                              <Badge
                                variant="outline"
                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueStatusClass(issue.status)}`}
                              >
                                {issue.status}
                              </Badge>
                              <Badge
                                variant="outline"
                                className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${issueSeverityClass(issue.severity)}`}
                              >
                                {issue.severity}
                              </Badge>
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                {issue.category}
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
                                  onInspectIssue(issue);
                                }}
                              >
                                {selected ? "Selected" : "Inspect"}
                              </Button>
                            </div>
                            <p className="mt-2 text-[13px] text-[#6b6b6b]">
                              {issue.title || "Issue requires review"}
                            </p>
                            <p className="mt-2 text-[12px] text-[#9b9a97]">
                              {issue.root_cause || issue.description || "No root cause recorded"}
                            </p>
                            <p className="mt-2 text-[12px] text-[#9b9a97]">
                              {formatTimestamp(issue.created_at)}
                              {issue.related_command ? ` · command ${issue.related_command}` : ""}
                            </p>
                            {(issue.approval_id || runtimeAgentIds.length > 0) && (
                              <div className="mt-2 flex flex-wrap gap-2">
                                {issue.approval_id && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                    onClick={() => {
                                      onSearchEntity(issue.approval_id);
                                    }}
                                  >
                                    approval {issue.approval_id}
                                  </Button>
                                )}
                                {runtimeAgentIds.map((runtimeAgentId) => (
                                  <Button
                                    key={`${issue.id}-${runtimeAgentId}`}
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
                          <div className="flex flex-wrap gap-2">
                            {issue.status === "open" && (
                              <Button
                                size="sm"
                                variant="outline"
                                className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                                disabled={Boolean(busyActionKey)}
                                onClick={() => {
                                  onResolveIssue(issue);
                                }}
                              >
                                {busyActionKey === `issue-resolve:${issue.id}`
                                  ? "Resolving..."
                                  : "Resolve"}
                              </Button>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
