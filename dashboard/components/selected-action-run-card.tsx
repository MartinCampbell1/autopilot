"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { BreakdownChips, SessionMetric } from "@/components/control-plane-display";
import { passStatusClass } from "@/lib/control-plane-ui";
import type {
  ExecutionAgentActionRunRecord,
  ExecutionPlaneCountMap,
} from "@/lib/types";

type RunResultDetails = {
  title: string;
  subtitle: string;
  message: string;
};

type SelectedActionRunCardProps = {
  selectedRun: ExecutionAgentActionRunRecord | null;
  selectedRunResultIndex: number;
  onSelectResult: (index: number) => void;
  onCopyLink: () => void;
  busyActionKey: string;
  onApplyPreviewRun: (run: ExecutionAgentActionRunRecord) => void;
  onWaitForAsyncSettlement?: (run: ExecutionAgentActionRunRecord) => void;
  onCancelAsyncSettlement?: (run: ExecutionAgentActionRunRecord) => void;
  formatTimestamp: (value?: string | null) => string;
  formatScopeList: (items: string[], emptyText: string) => string;
  describeRunResult: (result: Record<string, unknown>) => RunResultDetails;
  toNumber: (value: unknown, fallback?: number) => number;
  toStringArray: (value: unknown) => string[];
  toStringValue: (value: unknown, fallback?: string) => string;
  asRecord: (value: unknown) => Record<string, unknown> | null;
  children?: ReactNode;
};

export function SelectedActionRunCard({
  selectedRun,
  selectedRunResultIndex,
  onSelectResult,
  onCopyLink,
  busyActionKey,
  onApplyPreviewRun,
  onWaitForAsyncSettlement,
  onCancelAsyncSettlement,
  formatTimestamp,
  formatScopeList,
  describeRunResult,
  toNumber,
  toStringArray,
  toStringValue,
  asRecord,
  children,
}: SelectedActionRunCardProps) {
  const diffSummary = asRecord(selectedRun?.diff_summary);
  const patchBundle = asRecord(selectedRun?.patch_bundle);
  const commandCounts = (asRecord(diffSummary?.command_counts) as ExecutionPlaneCountMap | null) || {};
  const plannedModeCounts = (asRecord(diffSummary?.planned_mode_counts) as ExecutionPlaneCountMap | null) || {};
  const previewActionKey = selectedRun
    ? `preview-apply:${toStringValue(selectedRun.preview_id, selectedRun.id)}`
    : "";
  const waitActionKey = selectedRun ? `run-wait:${selectedRun.id}` : "";
  const cancelActionKey = selectedRun ? `run-cancel:${selectedRun.id}` : "";
  const canApplyPreview = Boolean(
    selectedRun?.dry_run &&
      selectedRun?.run_kind === "batch" &&
      toStringArray(selectedRun?.selection.selected_action_keys).length > 0
  );
  const patchOperations = Array.isArray(patchBundle?.operations)
    ? patchBundle.operations
        .map((item) => asRecord(item))
        .filter((item): item is Record<string, unknown> => item !== null)
    : [];

  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Selected Action Run
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Inspect the latest session execution or preview run, including action outcomes.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!selectedRun ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a linked action run to inspect selection scope and result details.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-mono text-[12px] font-semibold text-[#37352f]">
                    {selectedRun.id}
                  </p>
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(selectedRun.status)}`}
                  >
                    {selectedRun.status}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                  >
                    {selectedRun.run_kind}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                  >
                    {selectedRun.dry_run ? "preview" : "execute"}
                  </Badge>
                  <Badge
                    variant="outline"
                    className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium capitalize text-[#2a6690]"
                  >
                    {(selectedRun.apply_mode || (selectedRun.dry_run ? "manual" : "auto")).replaceAll("_", " ")}
                  </Badge>
                  {selectedRun.completion_state === "pending_async" && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                    >
                      waiting on async follow-through
                    </Badge>
                  )}
                  {Boolean(selectedRun.approval_required) && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                    >
                      approval required
                    </Badge>
                  )}
                </div>
                <p className="mt-2 text-[13px] text-[#6b6b6b]">
                  {selectedRun.actor || "unknown actor"}
                  {" · "}
                  {selectedRun.mode || "auto"}
                  {selectedRun.reason ? ` · ${selectedRun.reason}` : ""}
                </p>
              </div>
              <div className="flex flex-wrap items-start justify-end gap-2">
                <p className="text-right text-[12px] text-[#9b9a97]">
                  {formatTimestamp(selectedRun.created_at)}
                  {selectedRun.completed_at
                    ? ` · completed ${formatTimestamp(selectedRun.completed_at)}`
                    : ""}
                </p>
                {canApplyPreview && (
                  <Button
                    size="sm"
                    className="h-8 rounded-lg bg-[#1a1a1a] text-[12px] text-white hover:bg-[#333]"
                    disabled={Boolean(busyActionKey)}
                    onClick={() => {
                      onApplyPreviewRun(selectedRun);
                    }}
                  >
                    {busyActionKey === previewActionKey
                      ? selectedRun.approval_required
                        ? "Requesting..."
                        : "Applying..."
                      : selectedRun.approval_required
                        ? "Request approvals"
                      : "Apply preview"}
                  </Button>
                )}
                {selectedRun.completion_state === "pending_async" && onWaitForAsyncSettlement && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-lg border-[#d3e5ef] bg-[#eef7fb] text-[12px] text-[#2a6690] hover:bg-[#e3f1f8]"
                    disabled={Boolean(busyActionKey)}
                    onClick={() => {
                      onWaitForAsyncSettlement(selectedRun);
                    }}
                  >
                    {busyActionKey === waitActionKey ? "Waiting..." : "Wait for settle"}
                  </Button>
                )}
                {selectedRun.completion_state === "pending_async" && onCancelAsyncSettlement && (
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 rounded-lg border-[#f4d7d4] bg-[#fff5f4] text-[12px] text-[#b42318] hover:bg-[#fdeae8]"
                    disabled={Boolean(busyActionKey)}
                    onClick={() => {
                      onCancelAsyncSettlement(selectedRun);
                    }}
                  >
                    {busyActionKey === cancelActionKey ? "Cancelling..." : "Cancel async"}
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="h-8 rounded-lg border-[#e5e5e3] bg-white text-[12px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={onCopyLink}
                >
                  Copy run link
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <SessionMetric
                label="Selected"
                value={String(toNumber(selectedRun.summary.selected_count))}
                detail={`${toNumber(selectedRun.summary.processed_count, selectedRun.results.length)} processed`}
              />
              <SessionMetric
                label="Scope"
                value={`${selectedRun.project_ids.length} project${selectedRun.project_ids.length === 1 ? "" : "s"}`}
                detail={selectedRun.policy_profile || "Custom policy"}
              />
              <SessionMetric
                label="Initiatives"
                value={String(selectedRun.initiative_ids.length)}
                detail={formatScopeList(selectedRun.initiative_ids, "No initiative mapping")}
              />
              <SessionMetric
                label="Runtime Agents"
                value={String(selectedRun.runtime_agent_ids.length)}
                detail={formatScopeList(selectedRun.runtime_agent_ids, "No agent linkage")}
              />
              <SessionMetric
                label="Async Follow-Through"
                value={String(toNumber(selectedRun.async_task_count))}
                detail={
                  selectedRun.completion_state === "pending_async"
                    ? selectedRun.completion_message || "Background follow-through is still running."
                    : selectedRun.completion_message || "No async follow-through is pending."
                }
              />
            </div>

            <BreakdownChips
              label="Result Statuses"
              values={(selectedRun.summary.status_counts as ExecutionPlaneCountMap | undefined) || {}}
              emptyText="No result statuses recorded."
            />

            {(selectedRun.preview_id || selectedRun.artifact_ref || diffSummary || patchOperations.length > 0) && (
              <div className="rounded-2xl border border-[#d8e7ef] bg-[#f7fbfd] p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#6f8a99]">
                  Preview Contract
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  <SessionMetric
                    label="Apply Mode"
                    value={toStringValue(
                      selectedRun.apply_mode,
                      selectedRun.dry_run ? "manual" : "auto"
                    )}
                    detail={
                      Boolean(selectedRun.approval_required)
                        ? "Policy or approval gate is attached to this run."
                        : "No approval gate recorded for this run."
                    }
                  />
                  <SessionMetric
                    label="Preview Link"
                    value={toStringValue(
                      selectedRun.preview_id,
                      selectedRun.dry_run ? selectedRun.id : "No linked preview"
                    )}
                    detail={toStringValue(selectedRun.artifact_ref, "No preview artifact reference")}
                  />
                  <SessionMetric
                    label="Projects"
                    value={String(toNumber(diffSummary?.project_count, selectedRun.project_ids.length))}
                    detail={`${toNumber(diffSummary?.runtime_agent_count, selectedRun.runtime_agent_ids.length)} runtime agents`}
                  />
                  <SessionMetric
                    label="Approval-Gated"
                    value={String(toNumber(diffSummary?.approval_required_count))}
                    detail={`${patchOperations.length} planned operation${patchOperations.length === 1 ? "" : "s"}`}
                  />
                </div>

                <div className="mt-4 space-y-3">
                  <BreakdownChips
                    label="Commands"
                    values={commandCounts}
                    emptyText="No command breakdown recorded."
                  />
                  <BreakdownChips
                    label="Planned Modes"
                    values={plannedModeCounts}
                    emptyText="No planned-mode breakdown recorded."
                  />
                </div>

                {patchOperations.length > 0 && (
                  <div className="mt-4 space-y-2">
                    {patchOperations.slice(0, 4).map((operation, index) => (
                      <div
                        key={`${selectedRun.id}-patch-operation-${index}`}
                        className="rounded-xl border border-[#d8e7ef] bg-white p-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[13px] font-semibold text-[#37352f]">
                            {toStringValue(
                              operation.title,
                              toStringValue(operation.command, toStringValue(operation.kind, "operation"))
                            )}
                          </p>
                          <div className="flex flex-wrap gap-2">
                            <Badge
                              variant="outline"
                              className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium capitalize text-[#2a6690]"
                            >
                              {toStringValue(operation.apply_mode, "manual")}
                            </Badge>
                            {Boolean(operation.approval_required) && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                              >
                                approval gate
                              </Badge>
                            )}
                          </div>
                        </div>
                        <p className="mt-2 text-[12px] text-[#787774]">
                          {toStringValue(operation.action_key, "No action key")}
                          {toStringValue(operation.runtime_agent_id)
                            ? ` · ${toStringValue(operation.runtime_agent_id)}`
                            : ""}
                        </p>
                        <p className="mt-2 text-[12px] text-[#6b6b6b]">
                          {toStringValue(
                            operation.reason,
                            toStringValue(operation.message, "No preview rationale recorded.")
                          )}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Selection Scope
              </p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <SessionMetric
                  label="Requested Keys"
                  value={String(toStringArray(selectedRun.selection.requested_action_keys).length)}
                  detail={formatScopeList(
                    toStringArray(selectedRun.selection.requested_action_keys).slice(0, 2),
                    "No explicit action keys"
                  )}
                />
                <SessionMetric
                  label="Selected Keys"
                  value={String(toStringArray(selectedRun.selection.selected_action_keys).length)}
                  detail={formatScopeList(
                    toStringArray(selectedRun.selection.selected_action_keys).slice(0, 2),
                    "No selected action keys"
                  )}
                />
              </div>
              {(toStringValue(selectedRun.selection.project_id) ||
                toStringValue(selectedRun.selection.initiative_id) ||
                toStringValue(selectedRun.selection.orchestrator) ||
                toStringValue(selectedRun.selection.runtime_agent_id)) && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {toStringValue(selectedRun.selection.project_id) && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      project {toStringValue(selectedRun.selection.project_id)}
                    </Badge>
                  )}
                  {toStringValue(selectedRun.selection.initiative_id) && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      initiative {toStringValue(selectedRun.selection.initiative_id)}
                    </Badge>
                  )}
                  {toStringValue(selectedRun.selection.orchestrator) && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      orchestrator {toStringValue(selectedRun.selection.orchestrator)}
                    </Badge>
                  )}
                  {toStringValue(selectedRun.selection.runtime_agent_id) && (
                    <Badge
                      variant="outline"
                      className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                    >
                      agent {toStringValue(selectedRun.selection.runtime_agent_id)}
                    </Badge>
                  )}
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Action Outcomes
              </p>
              {selectedRun.results.length === 0 ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">No action results recorded.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  {selectedRun.results.slice(0, 8).map((result, index) => {
                    const resultRecord = asRecord(result) || {};
                    const details = describeRunResult(resultRecord);
                    const approval = asRecord(resultRecord.approval);
                    const issue = asRecord(resultRecord.issue);
                    const commandResult = asRecord(resultRecord.command_result);
                    const selected = selectedRunResultIndex === index;
                    return (
                      <div
                        key={`${selectedRun.id}-result-${index}`}
                        className={`rounded-xl border p-3 ${
                          selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-[13px] font-semibold text-[#37352f]">{details.title}</p>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(toStringValue(resultRecord.status, "unknown"))}`}
                            >
                              {toStringValue(resultRecord.status, "unknown")}
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
                                onSelectResult(index);
                              }}
                            >
                              {selected ? "Selected" : "Inspect"}
                            </Button>
                          </div>
                        </div>
                        <p className="mt-2 text-[12px] text-[#787774]">{details.subtitle}</p>
                        <p className="mt-2 text-[12px] text-[#6b6b6b]">{details.message}</p>
                        {(approval || issue || commandResult) && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {approval && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 py-1 text-[11px] font-medium text-[#2a6690]"
                              >
                                approval {toStringValue(approval.id, "created")}
                              </Badge>
                            )}
                            {issue && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 py-1 text-[11px] font-medium text-[#9a6700]"
                              >
                                issue {toStringValue(issue.id, "linked")}
                              </Badge>
                            )}
                            {commandResult && (
                              <Badge
                                variant="outline"
                                className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                              >
                                command {toStringValue(commandResult.status, "ok")}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
            {children}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
