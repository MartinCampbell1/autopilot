"use client";

import Link from "next/link";
import { RelationshipStrip, SessionMetric, type RelationshipStripItem } from "@/components/control-plane-display";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { passStatusClass } from "@/lib/control-plane-ui";
import type { ExecutionAgentActionRunRecord } from "@/lib/types";

type LinkedSelectionPayload = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

type SelectedOutcomeInspectorProps = {
  selectedRun: ExecutionAgentActionRunRecord;
  selectedRunResult: Record<string, unknown>;
  selectedRunResultIndex: number;
  selectedSessionEvents: Record<string, unknown>[];
  formatJson: (value: unknown) => string;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  toStringValue: (value: unknown, fallback?: string) => string;
  sessionEventKey: (event: Record<string, unknown>, fallback?: string) => string;
  resolveSessionEventFromContext: (
    events: Record<string, unknown>[],
    context: {
      runId?: string;
      approvalId?: string;
      issueId?: string;
      runtimeAgentId?: string;
      linkedRuntimeAgentId?: string;
      linkedRunId?: string;
      linkedApprovalId?: string;
      linkedIssueId?: string;
    }
  ) => { event: Record<string, unknown>; key: string } | null;
  outcomeProjectId: (result: Record<string, unknown>) => string;
  outcomeProjectName: (result: Record<string, unknown>) => string;
  outcomeStoryId: (result: Record<string, unknown>) => number | null;
  outcomeStoryTitle: (result: Record<string, unknown>) => string;
  outcomeRuntimeAgentId: (result: Record<string, unknown>) => string;
  onOpenInAgentTimeline: () => void;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  onFindApproval: (approvalId: string) => void;
  onFindIssue: (issueId: string) => void;
  onSelectRunOutcome: (runId: string, resultIndex: number) => void;
  onSyncLinkedSelection: (payload: LinkedSelectionPayload) => void;
};

export function SelectedOutcomeInspector({
  selectedRun,
  selectedRunResult,
  selectedRunResultIndex,
  selectedSessionEvents,
  formatJson,
  asRecord,
  toStringValue,
  sessionEventKey,
  resolveSessionEventFromContext,
  outcomeProjectId,
  outcomeProjectName,
  outcomeStoryId,
  outcomeStoryTitle,
  outcomeRuntimeAgentId,
  onOpenInAgentTimeline,
  onFocusRuntimeAgent,
  onFindApproval,
  onFindIssue,
  onSelectRunOutcome,
  onSyncLinkedSelection,
}: SelectedOutcomeInspectorProps) {
  const actionPayload = asRecord(selectedRunResult.action);
  const commandResultPayload = asRecord(selectedRunResult.command_result);
  const projectId = outcomeProjectId(selectedRunResult);
  const projectName = outcomeProjectName(selectedRunResult);
  const storyId = outcomeStoryId(selectedRunResult);
  const storyTitle = outcomeStoryTitle(selectedRunResult);
  const runtimeAgentId = outcomeRuntimeAgentId(selectedRunResult);
  const commandName = toStringValue(
    actionPayload?.command,
    toStringValue(commandResultPayload?.command)
  );
  const linkedApprovalId = toStringValue(asRecord(selectedRunResult.approval)?.id);
  const linkedIssueId = toStringValue(asRecord(selectedRunResult.issue)?.id);
  const linkedEvent =
    resolveSessionEventFromContext(selectedSessionEvents || [], {
      runId: selectedRun.id,
      approvalId: linkedApprovalId,
      issueId: linkedIssueId,
      runtimeAgentId,
    })?.event ?? null;
  const workspaceHref =
    projectId && storyId
      ? `/projects/${projectId}?storyId=${storyId}`
      : projectId
        ? `/projects/${projectId}`
        : "";

  return (
    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
          Selected Outcome
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {runtimeAgentId && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
              onClick={onOpenInAgentTimeline}
            >
              Open in agent timeline
            </Button>
          )}
          {runtimeAgentId && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
              onClick={() => {
                onFocusRuntimeAgent(runtimeAgentId);
              }}
            >
              Find agent
            </Button>
          )}
          {linkedApprovalId && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
              onClick={() => {
                onFindApproval(linkedApprovalId);
              }}
            >
              Find approval
            </Button>
          )}
          {linkedIssueId && (
            <Button
              size="sm"
              variant="outline"
              className="h-8 rounded-lg border-[#e5e5e3] bg-white px-3 text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
              onClick={() => {
                onFindIssue(linkedIssueId);
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
          <Badge
            variant="outline"
            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(selectedRunResult.status, "unknown"))}`}
          >
            {toStringValue(selectedRunResult.status, "unknown")}
          </Badge>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <SessionMetric
          label="Action"
          value={toStringValue(
            asRecord(selectedRunResult.action)?.action_key,
            toStringValue(asRecord(selectedRunResult.action)?.command, "unknown")
          )}
          detail={toStringValue(asRecord(selectedRunResult.action)?.action_type, "No action type")}
        />
        <SessionMetric
          label="Mode"
          value={toStringValue(selectedRunResult.planned_mode, toStringValue(selectedRun.mode, "auto"))}
          detail={toStringValue(asRecord(selectedRunResult.command_result)?.status, "No command result")}
        />
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <SessionMetric
          label="Project"
          value={projectName || "Unknown project"}
          detail={projectId || "No project id in payload"}
        />
        <SessionMetric
          label="Story"
          value={storyTitle || (storyId ? `Story ${storyId}` : "No story context")}
          detail={storyId ? `story_id ${storyId}` : "Outcome is not story-scoped"}
        />
        <SessionMetric
          label="Command"
          value={commandName || "No command recorded"}
          detail={toStringValue(
            commandResultPayload?.status,
            toStringValue(selectedRunResult.planned_mode, "No command status")
          )}
        />
        <SessionMetric
          label="Runtime Agent"
          value={runtimeAgentId || "No agent linkage"}
          detail={toStringValue(actionPayload?.role, "No execution role")}
        />
      </div>

      {(projectId || storyId || runtimeAgentId) && (
        <div className="mt-4 flex flex-wrap gap-2">
          {projectId && (
            <Badge
              variant="outline"
              className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
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
              className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
            >
              agent {runtimeAgentId}
            </Badge>
          )}
        </div>
      )}

      <RelationshipStrip
        label="Relationship Strip"
        items={[
          {
            key: `run-${selectedRun.id}`,
            label: `run ${selectedRun.id}`,
            tone: "run",
            onClick: () => {
              onSelectRunOutcome(selectedRun.id, 0);
            },
          },
          {
            key: `outcome-${selectedRun.id}-${selectedRunResultIndex}`,
            label: `outcome ${selectedRunResultIndex + 1}`,
            tone: "outcome",
            active: true,
            onClick: () => {
              onSelectRunOutcome(selectedRun.id, selectedRunResultIndex);
            },
          },
          linkedApprovalId
            ? {
                key: `approval-${linkedApprovalId}`,
                label: `approval ${linkedApprovalId}`,
                tone: "approval" as const,
                onClick: () => {
                  onSyncLinkedSelection({
                    runId: selectedRun.id,
                    resultIndex: selectedRunResultIndex,
                    approvalId: linkedApprovalId,
                    issueId: linkedIssueId,
                    runtimeAgentId,
                  });
                },
              }
            : null,
          linkedIssueId
            ? {
                key: `issue-${linkedIssueId}`,
                label: `issue ${linkedIssueId}`,
                tone: "issue" as const,
                onClick: () => {
                  onSyncLinkedSelection({
                    runId: selectedRun.id,
                    resultIndex: selectedRunResultIndex,
                    approvalId: linkedApprovalId,
                    issueId: linkedIssueId,
                    runtimeAgentId,
                  });
                },
              }
            : null,
          linkedEvent
            ? {
                key: `event-${sessionEventKey(linkedEvent)}`,
                label: `event ${toStringValue(linkedEvent.event, "event")}`,
                tone: "event" as const,
                onClick: () => {
                  onSyncLinkedSelection({
                    runId: selectedRun.id,
                    resultIndex: selectedRunResultIndex,
                    approvalId: linkedApprovalId,
                    issueId: linkedIssueId,
                    runtimeAgentId,
                    event: linkedEvent,
                  });
                },
              }
            : null,
          runtimeAgentId
            ? {
                key: `agent-${runtimeAgentId}`,
                label: `agent ${runtimeAgentId}`,
                tone: "agent" as const,
                onClick: onOpenInAgentTimeline,
              }
            : null,
        ].filter(Boolean) as RelationshipStripItem[]}
      />

      <p className="mt-4 text-[13px] leading-relaxed text-[#6b6b6b]">
        {toStringValue(
          selectedRunResult.message,
          toStringValue(asRecord(selectedRunResult.command_result)?.message, "No additional outcome message.")
        )}
      </p>

      <div className="mt-4 space-y-3">
        <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Action Payload
          </p>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
            {formatJson(asRecord(selectedRunResult.action) || selectedRunResult)}
          </pre>
        </div>

        {asRecord(selectedRunResult.command_result) && (
          <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
              Command Result Payload
            </p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-[#fafaf9] p-3 text-[11px] leading-relaxed text-[#37352f]">
              {formatJson(asRecord(selectedRunResult.command_result))}
            </pre>
          </div>
        )}

        {asRecord(selectedRunResult.approval) && (
          <div className="rounded-xl border border-[#d3e5ef] bg-[#eef7fb] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#2a6690]">
              Linked Approval
            </p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#2a6690]">
              {formatJson(asRecord(selectedRunResult.approval))}
            </pre>
          </div>
        )}

        {asRecord(selectedRunResult.issue) && (
          <div className="rounded-xl border border-[#f4e0c4] bg-[#fff6e8] p-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9a6700]">
              Linked Issue
            </p>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-white p-3 text-[11px] leading-relaxed text-[#9a6700]">
              {formatJson(asRecord(selectedRunResult.issue))}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
