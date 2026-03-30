"use client";

import Link from "next/link";
import { RuntimeAgentInspectorColumn } from "@/components/runtime-agent-inspector-column";
import {
  QueueAdvanceNotice,
  type QueueAdvanceFeedback,
  type QueueAdvanceFocusDelta,
  type QueueAdvanceFocusSummary,
  type QueueAdvanceNoticeActionProps,
} from "@/components/queue-advance-notice";
import {
  CollapsibleQueuePanel,
  QueueGroupControls,
  QueueItemCard,
} from "@/components/queue-panels";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

type TriagePriority = "critical" | "high" | "normal";
type AgentPriorityQueueKey = "critical" | "high";
type AgentTimelineFilter = "all" | "approvals" | "issues" | "events" | "attention";

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

type RuntimeAgentTimelineSectionProps = {
  selectedAgent: ExecutionRuntimeAgentDetail;
  activeAgentTimelineEntries: AgentTimelineEntry[];
  hiddenAgentTimelineEntryCount: number;
  agentTimelineSearch: string;
  onAgentTimelineSearchChange: (value: string) => void;
  agentTimelineFilter: AgentTimelineFilter;
  onAgentTimelineFilterChange: (value: AgentTimelineFilter) => void;
  persistedDismissedAgentTimelineCount: number;
  persistedSnoozedAgentTimelineCount: number;
  agentTimelinePriorityCounts: Record<TriagePriority, number>;
  nextBestAgentTimelineEntry: AgentTimelineEntry | null;
  hasPersistedAgentTimelinePreferences: boolean;
  onInspectAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  onRestoreAgentTimelineHidden: () => void;
  onExportAgentTimelinePreferences: () => void | Promise<void>;
  onResetAgentTimelinePreferences: () => void;
  agentQueueAdvanceFeedback: QueueAdvanceFeedback<unknown> | null;
  agentQueueAdvanceFocusSummary: QueueAdvanceFocusSummary | null;
  agentQueueFocusDelta: QueueAdvanceFocusDelta | null;
  agentQueueAdvanceNoticeActions: QueueAdvanceNoticeActionProps;
  nextCriticalAgentTimelineEntry: AgentTimelineEntry | null;
  nextHighAgentTimelineEntry: AgentTimelineEntry | null;
  expandedAgentPriorityQueues: AgentPriorityQueueKey[];
  currentAgentPriorityQueue: AgentPriorityQueueKey | "";
  onExpandAllAgentPriorityQueues: () => void;
  onCollapseAllAgentPriorityQueues: () => void;
  onOpenCurrentAgentPriorityQueue: () => void;
  criticalAgentTimelineQueue: AgentTimelineEntry[];
  criticalAgentTimelineTotal: number;
  criticalAgentTimelinePosition: number;
  highAgentTimelineQueue: AgentTimelineEntry[];
  highAgentTimelineTotal: number;
  highAgentTimelinePosition: number;
  onToggleAgentPriorityQueueExpansion: (queue: AgentPriorityQueueKey) => void;
  filteredAgentTimelineEntriesCount: number;
  visibleAgentTimelineEntries: AgentTimelineEntry[];
  selectedAgentTimelineEntry: AgentTimelineEntry | null;
  selectedAgentTimelineRunLink: RelatedRunLink | null;
  selectedAgentTimelinePriority: TriagePriority | null;
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
  onFocusAgentTimeline: (filter: Exclude<AgentTimelineFilter, "all">, entry?: AgentTimelineEntry) => void;
  onFilterSessionByToken: (value: string) => void;
  onSnoozeAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  onDismissAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  onAdvanceAgentPriorityQueueFromEntry: (
    priority: AgentPriorityQueueKey,
    entry: AgentTimelineEntry
  ) => void;
  onFindAgentTimelineEntryInSession: (entry: AgentTimelineEntry) => void;
  onRevealAgentTimelineEntry: (entry: AgentTimelineEntry) => void;
  agentTimelineEntryKey: (entry: AgentTimelineEntry) => string;
  agentTimelinePriority: (entry: AgentTimelineEntry) => TriagePriority;
  agentTimelineRowDomId: (runtimeAgentId: string, entryKey: string) => string;
};

const AGENT_PRIORITY_QUEUE_KEYS: AgentPriorityQueueKey[] = ["critical", "high"];

export function RuntimeAgentTimelineSection({
  selectedAgent,
  activeAgentTimelineEntries,
  hiddenAgentTimelineEntryCount,
  agentTimelineSearch,
  onAgentTimelineSearchChange,
  agentTimelineFilter,
  onAgentTimelineFilterChange,
  persistedDismissedAgentTimelineCount,
  persistedSnoozedAgentTimelineCount,
  agentTimelinePriorityCounts,
  nextBestAgentTimelineEntry,
  hasPersistedAgentTimelinePreferences,
  onInspectAgentTimelineEntry,
  onRestoreAgentTimelineHidden,
  onExportAgentTimelinePreferences,
  onResetAgentTimelinePreferences,
  agentQueueAdvanceFeedback,
  agentQueueAdvanceFocusSummary,
  agentQueueFocusDelta,
  agentQueueAdvanceNoticeActions,
  nextCriticalAgentTimelineEntry,
  nextHighAgentTimelineEntry,
  expandedAgentPriorityQueues,
  currentAgentPriorityQueue,
  onExpandAllAgentPriorityQueues,
  onCollapseAllAgentPriorityQueues,
  onOpenCurrentAgentPriorityQueue,
  criticalAgentTimelineQueue,
  criticalAgentTimelineTotal,
  criticalAgentTimelinePosition,
  highAgentTimelineQueue,
  highAgentTimelineTotal,
  highAgentTimelinePosition,
  onToggleAgentPriorityQueueExpansion,
  filteredAgentTimelineEntriesCount,
  visibleAgentTimelineEntries,
  selectedAgentTimelineEntry,
  selectedAgentTimelineRunLink,
  selectedAgentTimelinePriority,
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
  onSnoozeAgentTimelineEntry,
  onDismissAgentTimelineEntry,
  onAdvanceAgentPriorityQueueFromEntry,
  onFindAgentTimelineEntryInSession,
  onRevealAgentTimelineEntry,
  agentTimelineEntryKey,
  agentTimelinePriority,
  agentTimelineRowDomId,
}: RuntimeAgentTimelineSectionProps) {
  const priorityQueues = [
    {
      key: "critical" as const,
      label: "Critical Queue",
      entries: criticalAgentTimelineQueue,
      total: criticalAgentTimelineTotal,
      position: criticalAgentTimelinePosition,
      buttonLabel: "Inspect next critical",
      nextEntry: nextCriticalAgentTimelineEntry,
      buttonClassName: "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d] hover:bg-[#ffe5df]",
    },
    {
      key: "high" as const,
      label: "High Queue",
      entries: highAgentTimelineQueue,
      total: highAgentTimelineTotal,
      position: highAgentTimelinePosition,
      buttonLabel: "Inspect next high",
      nextEntry: nextHighAgentTimelineEntry,
      buttonClassName: "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700] hover:bg-[#fff0d9]",
    },
  ];

  return (
    <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
            Agent Timeline
          </p>
          <p className="mt-1 text-[13px] text-[#787774]">
            Unified approvals, issues, and runtime events for this agent. Detailed history lives
            here.
          </p>
        </div>
        <Badge
          variant="outline"
          className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
        >
          {activeAgentTimelineEntries.length} active
          {hiddenAgentTimelineEntryCount ? ` · ${hiddenAgentTimelineEntryCount} hidden` : ""}
        </Badge>
      </div>

      <div className="mt-3 space-y-3">
        <Input
          value={agentTimelineSearch}
          onChange={(event) => onAgentTimelineSearchChange(event.target.value)}
          placeholder="Search approvals, issues, and agent events..."
          className="h-9 rounded-xl border-[#e5e5e3] bg-white text-[13px] text-[#37352f] placeholder:text-[#9b9a97]"
        />
        <div className="flex flex-wrap gap-2">
          {[
            { value: "all", label: "All" },
            { value: "approvals", label: "Approvals" },
            { value: "issues", label: "Issues" },
            { value: "events", label: "Events" },
            { value: "attention", label: "Attention" },
          ].map((option) => {
            const selected = agentTimelineFilter === option.value;
            return (
              <Button
                key={`agent-timeline-filter-${option.value}`}
                size="sm"
                variant={selected ? "default" : "outline"}
                className={`h-7 rounded-full px-3 text-[11px] ${
                  selected
                    ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                    : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                }`}
                onClick={() => {
                  onAgentTimelineFilterChange(option.value as AgentTimelineFilter);
                }}
              >
                {option.label}
              </Button>
            );
          })}
        </div>

        <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Operator State
              </p>
              <p className="mt-1 text-[12px] text-[#787774]">
                {persistedDismissedAgentTimelineCount} dismissed ·{" "}
                {persistedSnoozedAgentTimelineCount} snoozed persisted for this agent
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(["critical", "high", "normal"] as TriagePriority[]).map((priority) =>
                  agentTimelinePriorityCounts[priority] ? (
                    <Badge
                      key={`agent-timeline-priority-${priority}`}
                      variant="outline"
                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(priority)}`}
                    >
                      {priority} {agentTimelinePriorityCounts[priority]}
                    </Badge>
                  ) : null
                )}
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={() => {
                  if (nextBestAgentTimelineEntry) {
                    onInspectAgentTimelineEntry(nextBestAgentTimelineEntry);
                  }
                }}
                disabled={!nextBestAgentTimelineEntry}
              >
                Inspect next best
              </Button>
              {hiddenAgentTimelineEntryCount ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                  onClick={() => {
                    onRestoreAgentTimelineHidden();
                  }}
                >
                  Restore hidden
                </Button>
              ) : null}
              <Button
                size="sm"
                variant="outline"
                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={() => {
                  void onExportAgentTimelinePreferences();
                }}
                disabled={!hasPersistedAgentTimelinePreferences}
              >
                Copy timeline state
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                onClick={() => {
                  onResetAgentTimelinePreferences();
                }}
                disabled={!hasPersistedAgentTimelinePreferences}
              >
                Reset timeline state
              </Button>
            </div>
          </div>
        </div>

        <QueueAdvanceNotice
          label="Queue Advance"
          feedback={agentQueueAdvanceFeedback}
          focusSummary={agentQueueAdvanceFocusSummary}
          focusDelta={agentQueueFocusDelta}
          {...agentQueueAdvanceNoticeActions}
        />

        <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                Priority Queue
              </p>
              <p className="mt-1 text-[12px] text-[#787774]">
                Next-best triage for the current agent timeline slice.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                className="h-7 rounded-lg border-[#f0d0c9] bg-[#fff0ed] px-2 text-[11px] text-[#93370d] hover:bg-[#ffe5df]"
                onClick={() => {
                  if (nextCriticalAgentTimelineEntry) {
                    onInspectAgentTimelineEntry(nextCriticalAgentTimelineEntry);
                  }
                }}
                disabled={!nextCriticalAgentTimelineEntry}
              >
                Inspect next critical
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="h-7 rounded-lg border-[#f4e0c4] bg-[#fff6e8] px-2 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                onClick={() => {
                  if (nextHighAgentTimelineEntry) {
                    onInspectAgentTimelineEntry(nextHighAgentTimelineEntry);
                  }
                }}
                disabled={!nextHighAgentTimelineEntry}
              >
                Inspect next high
              </Button>
            </div>
          </div>
          <div className="mt-3">
            <QueueGroupControls
              title="Queue Groups"
              detail="Critical and high slices now share the same group controls as the other triage surfaces."
              openCount={expandedAgentPriorityQueues.length}
              totalCount={AGENT_PRIORITY_QUEUE_KEYS.length}
              onExpandAll={onExpandAllAgentPriorityQueues}
              onCollapseAll={onCollapseAllAgentPriorityQueues}
              onOpenCurrent={onOpenCurrentAgentPriorityQueue}
              canOpenCurrent={Boolean(currentAgentPriorityQueue)}
            />
          </div>
          <div className="mt-3 grid gap-3 xl:grid-cols-2">
            {priorityQueues.map((queue) => (
              <CollapsibleQueuePanel
                key={`agent-priority-queue-${queue.key}`}
                title={queue.label}
                detail={
                  queue.position >= 0
                    ? `Selected ${queue.position + 1} of ${queue.total}`
                    : `${queue.total} queued`
                }
                expanded={expandedAgentPriorityQueues.includes(queue.key)}
                onToggle={() => {
                  onToggleAgentPriorityQueueExpansion(queue.key);
                }}
                collapsedSummary={
                  queue.total
                    ? `${queue.total} visible queue item${queue.total === 1 ? "" : "s"} hidden`
                    : "Queue collapsed."
                }
                emptyText={`No ${queue.key} entries in the current slice.`}
                isEmpty={!queue.entries.length}
                badge={
                  <Badge
                    variant="outline"
                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(queue.key)}`}
                  >
                    {queue.total}
                  </Badge>
                }
                actions={
                  <Button
                    size="sm"
                    variant="outline"
                    className={`h-7 rounded-lg px-2 text-[11px] ${queue.buttonClassName}`}
                    onClick={() => {
                      if (queue.nextEntry) {
                        onInspectAgentTimelineEntry(queue.nextEntry);
                      }
                    }}
                    disabled={!queue.nextEntry}
                  >
                    {queue.buttonLabel}
                  </Button>
                }
                className="rounded-xl border border-[#ecebe8] bg-[#fbfbf9] p-3"
              >
                <div className="mt-3 space-y-2">
                  {queue.entries.map((entry) => {
                    const selected =
                      selectedAgentTimelineEntry &&
                      agentTimelineEntryKey(selectedAgentTimelineEntry) === agentTimelineEntryKey(entry);
                    const workspaceProjectId =
                      entry.issue?.project_id || entry.approval?.project_id || selectedAgent.project_id || "";
                    const workspaceStoryId = entry.issue?.story_id ?? selectedAgent.story_id ?? null;
                    const workspaceHref = workspaceProjectId
                      ? workspaceStoryId
                        ? `/projects/${workspaceProjectId}?storyId=${workspaceStoryId}`
                        : `/projects/${workspaceProjectId}`
                      : "";

                    return (
                      <QueueItemCard
                        key={`agent-priority-${queue.key}-${agentTimelineEntryKey(entry)}`}
                        title={entry.title}
                        subtitle={`${entry.kind} · ${entry.subtitle || "No scope metadata"}`}
                        timestamp={formatTimestamp(entry.timestamp)}
                        selected={Boolean(selected)}
                        className="rounded-lg border p-2.5"
                        unselectedClassName="border-[#ecebe8] bg-white"
                        subtitleClassName="mt-1 text-[11px] text-[#787774]"
                        badgeRowClassName="mt-2 flex flex-wrap items-center gap-2"
                        actionRowClassName="mt-2 flex flex-wrap items-center gap-2"
                        badges={
                          <Badge
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
                              entry.kind === "approval"
                                ? approvalStatusClass(entry.status)
                                : entry.kind === "issue"
                                  ? passStatusClass(entry.status === "open" ? "partial" : "ok")
                                  : passStatusClass(entry.status)
                            }`}
                          >
                            {entry.status}
                          </Badge>
                        }
                        actions={
                          <>
                            <Button
                              size="sm"
                              variant={selected ? "default" : "outline"}
                              className={`h-7 rounded-lg px-2 text-[11px] ${
                                selected
                                  ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                  : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                              }`}
                              onClick={() => {
                                onInspectAgentTimelineEntry(entry);
                              }}
                            >
                              {selected ? "Selected" : "Inspect"}
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                onSnoozeAgentTimelineEntry(entry);
                              }}
                            >
                              Snooze 15m
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#d3e5ef] bg-[#eef7fb] px-2 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                              onClick={() => {
                                onAdvanceAgentPriorityQueueFromEntry(queue.key, entry);
                              }}
                            >
                              Next in queue
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                onDismissAgentTimelineEntry(entry);
                              }}
                            >
                              Dismiss
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                onFindAgentTimelineEntryInSession(entry);
                              }}
                            >
                              Find in session
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#d3e5ef] bg-[#eef7fb] px-2 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                              onClick={() => {
                                onRevealAgentTimelineEntry(entry);
                              }}
                            >
                              Reveal in timeline
                            </Button>
                            {workspaceHref ? (
                              <Link
                                href={workspaceHref}
                                className="inline-flex h-7 items-center rounded-lg border border-[#e5e5e3] bg-white px-2 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                              >
                                Open workspace
                              </Link>
                            ) : null}
                          </>
                        }
                      />
                    );
                  })}
                </div>
              </CollapsibleQueuePanel>
            ))}
          </div>
        </div>

        {filteredAgentTimelineEntriesCount === 0 ? (
          <p className="mt-3 text-[13px] text-[#9b9a97]">No timeline entries match the current filters.</p>
        ) : (
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div className="space-y-3">
              {visibleAgentTimelineEntries.map((entry) => {
                const selected =
                  selectedAgentTimelineEntry &&
                  agentTimelineEntryKey(selectedAgentTimelineEntry) === agentTimelineEntryKey(entry);
                const eventApprovalId = toStringValue(entry.event?.approval_id);
                const eventIssueId = toStringValue(entry.event?.issue_id);
                const eventToken =
                  toStringValue(entry.event?.event) || toStringValue(entry.event?.message) || entry.id;

                return (
                  <div
                    key={`${selectedAgent.runtime_agent_id}-timeline-${entry.kind}-${entry.id}`}
                    id={agentTimelineRowDomId(
                      selectedAgent.runtime_agent_id,
                      agentTimelineEntryKey(entry)
                    )}
                    className={`rounded-xl border p-3 ${
                      selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium capitalize text-[#37352f]"
                        >
                          {entry.kind}
                        </Badge>
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(agentTimelinePriority(entry))}`}
                        >
                          {agentTimelinePriority(entry)}
                        </Badge>
                        <p className="text-[13px] font-semibold text-[#37352f]">{entry.title}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${
                            entry.kind === "approval"
                              ? approvalStatusClass(entry.status)
                              : entry.kind === "issue"
                                ? passStatusClass(entry.status === "open" ? "partial" : "ok")
                                : passStatusClass(entry.status)
                          }`}
                        >
                          {entry.status}
                        </Badge>
                        <p className="text-[11px] text-[#9b9a97]">{formatTimestamp(entry.timestamp)}</p>
                        <Button
                          size="sm"
                          variant={selected ? "default" : "outline"}
                          className={`h-7 rounded-lg px-2 text-[11px] ${
                            selected
                              ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                              : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                          }`}
                          onClick={() => {
                            onInspectAgentTimelineEntry(entry);
                          }}
                        >
                          {selected ? "Selected" : "Inspect"}
                        </Button>
                      </div>
                    </div>

                    <p className="mt-2 text-[12px] text-[#787774]">{entry.subtitle}</p>
                    <p className="mt-2 text-[12px] text-[#6b6b6b]">{entry.message}</p>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {entry.approval?.status === "pending" && (
                        <>
                          <Button
                            size="sm"
                            className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
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
                            className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
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
                          className="h-7 rounded-full bg-[#1a1a1a] px-2.5 text-[11px] text-white hover:bg-[#333]"
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
                          className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
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
                      {(entry.approval?.id || entry.issue?.id) && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                          onClick={() => {
                            onSearchEntity(entry.approval?.id || entry.issue?.id || "");
                          }}
                        >
                          Find in session
                        </Button>
                      )}
                      {eventApprovalId && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#d3e5ef] bg-[#eef7fb] px-2.5 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                          onClick={() => {
                            onSearchEntity(eventApprovalId);
                          }}
                        >
                          Find approval
                        </Button>
                      )}
                      {eventIssueId && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#f4e0c4] bg-[#fff6e8] px-2.5 text-[11px] text-[#9a6700] hover:bg-[#fff0d9]"
                          onClick={() => {
                            onSearchEntity(eventIssueId);
                          }}
                        >
                          Find issue
                        </Button>
                      )}
                      {entry.kind === "event" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                          onClick={() => {
                            onFilterSessionByToken(eventToken);
                          }}
                        >
                          Filter session
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                        onClick={() => {
                          onSnoozeAgentTimelineEntry(entry);
                        }}
                      >
                        Snooze 15m
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-full border-[#e5e5e3] bg-white px-2.5 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                        onClick={() => {
                          onDismissAgentTimelineEntry(entry);
                        }}
                      >
                        Dismiss
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>

            <RuntimeAgentInspectorColumn
              selectedAgent={selectedAgent}
              selectedAgentTimelineEntry={selectedAgentTimelineEntry}
              selectedAgentTimelineRunLink={selectedAgentTimelineRunLink}
              selectedAgentTimelinePriority={selectedAgentTimelinePriority}
              currentAgentPriorityQueue={currentAgentPriorityQueue || null}
              latestAgentIssueEntry={latestAgentIssueEntry}
              latestAgentApprovalEntry={latestAgentApprovalEntry}
              latestAgentEventEntry={latestAgentEventEntry}
              busyActionKey={busyActionKey}
              formatTimestamp={formatTimestamp}
              formatJson={formatJson}
              toStringValue={toStringValue}
              toNullableNumber={toNullableNumber}
              asRecord={asRecord}
              describeRunResult={describeRunResult}
              onSelectTimelineEntry={onSelectTimelineEntry}
              onSyncLinkedSelection={onSyncLinkedSelection}
              onFocusRuntimeAgent={onFocusRuntimeAgent}
              onSelectRun={onSelectRun}
              onApproveApproval={onApproveApproval}
              onRejectApproval={onRejectApproval}
              onApplyApproval={onApplyApproval}
              onResolveIssue={onResolveIssue}
              onAdvanceCurrentPriorityQueue={onAdvanceCurrentPriorityQueue}
              onSearchEntity={onSearchEntity}
              onFocusAgentTimeline={onFocusAgentTimeline}
              onFilterSessionByToken={onFilterSessionByToken}
            />
          </div>
        )}
      </div>
    </div>
  );
}
