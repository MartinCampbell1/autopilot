"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { RuntimeAgentActivitySection } from "@/components/runtime-agent-activity-section";
import { RuntimeAgentTimelineSection } from "@/components/runtime-agent-timeline-section";
import { SessionMetric } from "@/components/control-plane-display";
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
  controlStateClass,
  passStatusClass,
  priorityClass,
} from "@/lib/control-plane-ui";
import type { ExecutionRuntimeAgentDetail, ToolPermissionRuntimeRecord } from "@/lib/types";

function formatToolPermissionStage(value?: string | null): string {
  const normalized = (value || "").trim();
  if (normalized === "pending_user") return "Waiting for user";
  if (normalized === "pending_hook") return "Waiting for hook";
  if (normalized === "pending_classifier") return "Waiting for classifier";
  return normalized ? normalized.replaceAll("_", " ") : "Pending";
}

function extractToolPermissionMessage(runtime: ToolPermissionRuntimeRecord): string {
  const pendingStage = (runtime.pending_stage || "").trim();
  const stagePayload =
    pendingStage && runtime.payload && typeof runtime.payload === "object" && !Array.isArray(runtime.payload)
      ? runtime.payload[pendingStage]
      : null;
  if (
    stagePayload
    && typeof stagePayload === "object"
    && !Array.isArray(stagePayload)
    && typeof (stagePayload as Record<string, unknown>).message === "string"
    && (stagePayload as Record<string, string>).message
  ) {
    return (stagePayload as Record<string, string>).message;
  }
  return runtime.message || "Tool permission request is waiting for review.";
}

type RuntimeAgentSectionProps = {
  selectedAgentId: string;
  agentLoading: boolean;
  selectedAgent: ExecutionRuntimeAgentDetail | null;
  busyActionKey: string;
  formatTimestamp: (value?: string | null) => string;
  toNumber: (value: unknown, fallback?: number) => number;
  toStringValue: (value: unknown, fallback?: string) => string;
  onAllowToolPermissionRuntime: (runtime: ToolPermissionRuntimeRecord) => void;
  onDenyToolPermissionRuntime: (runtime: ToolPermissionRuntimeRecord) => void;
  onCopyLink: () => void;
  onFocusRuntimeAgent: (runtimeAgentId: string) => void;
  onRunSuggestedCommand: (
    command: Record<string, unknown>,
    mode: "execute_now" | "request_approval"
  ) => void;
  activitySectionProps: ComponentProps<typeof RuntimeAgentActivitySection> | null;
  timelineSectionProps: ComponentProps<typeof RuntimeAgentTimelineSection> | null;
};

export function RuntimeAgentSection({
  selectedAgentId,
  agentLoading,
  selectedAgent,
  busyActionKey,
  formatTimestamp,
  toNumber,
  toStringValue,
  onAllowToolPermissionRuntime,
  onDenyToolPermissionRuntime,
  onCopyLink,
  onFocusRuntimeAgent,
  onRunSuggestedCommand,
  activitySectionProps,
  timelineSectionProps,
}: RuntimeAgentSectionProps) {
  const pendingToolPermissionRuntimes = (selectedAgent?.tool_permission_runtimes || [])
    .filter((runtime) => runtime.status === "pending")
    .sort((left, right) => {
      const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
      if (updatedDelta !== 0) return updatedDelta;
      return right.id.localeCompare(left.id);
    });

  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Runtime Agent
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Agent-centric control view for the currently selected runtime agent.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedAgentId ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a linked runtime agent to inspect its current state and history.
          </div>
        ) : agentLoading || !selectedAgent || !activitySectionProps || !timelineSectionProps ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Loading runtime agent detail...
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                    {selectedAgent.runtime_agent_id}
                  </p>
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedAgent.status)}`}
                  >
                    {selectedAgent.status}
                  </Badge>
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${controlStateClass(selectedAgent.attention.state)}`}
                  >
                    {selectedAgent.attention.state}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                  >
                    {selectedAgent.role}
                  </Badge>
                </div>
                <p className="mt-2 text-[13px] text-[#6b6b6b]">
                  {selectedAgent.project_name || selectedAgent.project_id}
                  {" · "}
                  {selectedAgent.story_title || `Story ${selectedAgent.story_id || "unknown"}`}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={
                    selectedAgent.story_id
                      ? `/projects/${selectedAgent.project_id}?storyId=${selectedAgent.story_id}`
                      : `/projects/${selectedAgent.project_id}`
                  }
                  className="inline-flex h-8 items-center rounded-lg border border-[#e5e5e3] bg-white px-3 text-[12px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                >
                  Open workspace
                </Link>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={onCopyLink}
                >
                  Copy agent link
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onFocusRuntimeAgent(selectedAgent.runtime_agent_id);
                  }}
                >
                  Filter session
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <SessionMetric
                label="Open Issues"
                value={String(selectedAgent.history.open_issue_count)}
                detail={`${selectedAgent.history.issue_count} total issues`}
              />
              <SessionMetric
                label="Pending Approvals"
                value={String(selectedAgent.history.pending_approval_count)}
                detail={`${selectedAgent.history.approval_count} total approvals`}
              />
              <SessionMetric
                label="Pending Tool Permissions"
                value={String(selectedAgent.history.pending_tool_permission_runtime_count || 0)}
                detail={`${selectedAgent.history.tool_permission_runtime_count || 0} total tool-permission runtimes`}
              />
              <SessionMetric
                label="Events"
                value={String(selectedAgent.history.event_count)}
                detail={formatTimestamp(selectedAgent.history.last_event_at)}
              />
              <SessionMetric
                label="Budget"
                value={
                  selectedAgent.budget.tracked
                    ? `${toNumber(selectedAgent.budget.remaining, 0)} left`
                    : "Untracked"
                }
                detail={
                  selectedAgent.budget.tracked
                    ? `${selectedAgent.budget.used ?? 0}/${selectedAgent.budget.limit ?? 0} ${selectedAgent.budget.metric || ""}`.trim()
                    : "No tracked budget metric"
                }
              />
            </div>

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Attention
              </p>
              <p className="mt-3 text-[13px] leading-relaxed text-[#6b6b6b]">
                {selectedAgent.attention.recommended_action}
              </p>
              {selectedAgent.attention.reasons.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {selectedAgent.attention.reasons.map((reason) => (
                    <Badge
                      key={`${selectedAgent.runtime_agent_id}-${reason}`}
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      {reason}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Agent Recommendations
              </p>
              {selectedAgent.recommendations.length === 0 &&
              selectedAgent.suggested_commands.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">No current agent recommendations.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {selectedAgent.recommendations.slice(0, 3).map((recommendation, index) => (
                    <div
                      key={`${selectedAgent.runtime_agent_id}-rec-${index}`}
                      className="rounded-xl border border-[#ecebe8] bg-white p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[13px] font-semibold text-[#37352f]">
                          {toStringValue(
                            recommendation.title,
                            toStringValue(recommendation.kind, "recommendation")
                          )}
                        </p>
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(recommendation.priority, "medium"))}`}
                        >
                          {toStringValue(recommendation.priority, "medium")}
                        </Badge>
                      </div>
                      <p className="mt-2 text-[12px] text-[#6b6b6b]">
                        {toStringValue(recommendation.reason, "No reason provided")}
                      </p>
                    </div>
                  ))}
                  {selectedAgent.suggested_commands.slice(0, 2).map((command, index) => (
                    <div
                      key={`${selectedAgent.runtime_agent_id}-cmd-${index}`}
                      className="rounded-xl border border-[#ecebe8] bg-white p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-[13px] font-semibold text-[#37352f]">
                          {toStringValue(command.title, toStringValue(command.command, "command"))}
                        </p>
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${priorityClass(toStringValue(command.priority, "medium"))}`}
                          >
                            {toStringValue(command.priority, "medium")}
                          </Badge>
                          {Boolean(command.approval_required) && (
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                            >
                              approval required
                            </Badge>
                          )}
                        </div>
                      </div>
                      <p className="mt-2 text-[12px] text-[#6b6b6b]">
                        {toStringValue(command.reason, "No reason provided")}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {!Boolean(command.approval_required) && (
                          <Button
                            size="sm"
                            className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                            disabled={Boolean(busyActionKey)}
                            onClick={() => {
                              onRunSuggestedCommand(command, "execute_now");
                            }}
                          >
                            {busyActionKey ===
                            `agent-command:${selectedAgent.runtime_agent_id}:${toStringValue(command.command)}:execute_now`
                              ? "Executing..."
                              : "Execute"}
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                          disabled={Boolean(busyActionKey)}
                          onClick={() => {
                            onRunSuggestedCommand(command, "request_approval");
                          }}
                        >
                          {busyActionKey ===
                          `agent-command:${selectedAgent.runtime_agent_id}:${toStringValue(command.command)}:request_approval`
                            ? "Requesting..."
                            : "Request approval"}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {pendingToolPermissionRuntimes.length > 0 && (
              <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Tool Permission Review
                    </p>
                    <p className="mt-2 text-[13px] text-[#6b6b6b]">
                      Pending tool-permission runtimes for this agent can be resolved directly here.
                    </p>
                  </div>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                  >
                    {pendingToolPermissionRuntimes.length} pending
                  </Badge>
                </div>
                <div className="mt-3 space-y-3">
                  {pendingToolPermissionRuntimes.map((runtime) => (
                    <div
                      key={runtime.id}
                      className="rounded-xl border border-[#ecebe8] bg-white p-3"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <p className="text-[13px] font-semibold text-[#37352f]">
                            {runtime.tool_name || runtime.id}
                          </p>
                          <p className="mt-1 text-[12px] text-[#787774]">
                            {formatToolPermissionStage(runtime.pending_stage)} · use {runtime.tool_use_id || runtime.id}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-8 rounded-lg text-[12px] text-[#93370d] hover:bg-[#fff2ef] hover:text-[#93370d]"
                            disabled={Boolean(busyActionKey)}
                            onClick={() => {
                              onDenyToolPermissionRuntime(runtime);
                            }}
                          >
                            {busyActionKey === `tool-permission-deny:${runtime.id}` ? "Denying..." : "Deny"}
                          </Button>
                          <Button
                            size="sm"
                            className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] hover:bg-[#333]"
                            disabled={Boolean(busyActionKey)}
                            onClick={() => {
                              onAllowToolPermissionRuntime(runtime);
                            }}
                          >
                            {busyActionKey === `tool-permission-allow:${runtime.id}` ? "Allowing..." : "Allow"}
                          </Button>
                        </div>
                      </div>
                      <p className="mt-2 text-[12px] leading-relaxed text-[#6b6b6b]">
                        {extractToolPermissionMessage(runtime)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <RuntimeAgentActivitySection {...activitySectionProps} />
            <RuntimeAgentTimelineSection {...timelineSectionProps} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}
