"use client";

import Link from "next/link";
import {
  BreakdownChips,
  FilterChip,
  RelationshipStrip,
  type RelationshipStripItem,
  SessionMetric,
} from "@/components/control-plane-display";
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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SESSION_LINEAGE_QUEUE_KEYS } from "@/lib/control-plane-models";
import type {
  LineageQueueKind,
  SessionLineageEntry,
  SessionLineageTrait,
  TriagePriority,
} from "@/lib/control-plane-models";
import { passStatusClass, triagePriorityClass } from "@/lib/control-plane-ui";
import type { ExecutionPlaneCountMap } from "@/lib/types";

type SessionLineageFilter = "all" | LineageQueueKind | "agent-linked";

type SessionLineageSectionProps = {
  hasSelectedSession: boolean;
  sessionEventTotalCount: number;
  sessionLineageEntries: SessionLineageEntry[];
  linkedRunCount: number;
  linkedApprovalCount: number;
  linkedIssueCount: number;
  linkedAgentCount: number;
  sessionLineageDecisionCount: number;
  sessionLineageEventCount: number;
  sessionLineageAgentCount: number;
  sessionLineageStatusCounts: ExecutionPlaneCountMap;
  filteredSessionLineageEntriesCount: number;
  sessionLineageFilter: SessionLineageFilter;
  onSessionLineageFilterChange: (value: SessionLineageFilter) => void;
  sessionLineageAttentionCount: number;
  sessionLineageAgentLinkedCount: number;
  persistedDismissedLineageQueueCount: number;
  persistedSnoozedLineageQueueCount: number;
  sessionLineagePriorityCounts: Record<TriagePriority, number>;
  hasPersistedLineageQueuePreferences: boolean;
  onExportSessionLineageQueuePreferences: () => void | Promise<void>;
  onResetSessionLineageQueuePreferences: () => void;
  selectedSessionLineageEntry: SessionLineageEntry | null;
  selectedSessionLineagePriority: TriagePriority | null;
  selectedSessionLineageTraits: SessionLineageTrait[];
  formatTimestamp: (value?: string | null) => string;
  nextBestSessionLineageEntry: SessionLineageEntry | null;
  attentionSessionLineageEntries: SessionLineageEntry[];
  decisionSessionLineageEntries: SessionLineageEntry[];
  latestAgentLinkedLineageEntry: SessionLineageEntry | null;
  onInspectSessionLineageEntry: (entry: SessionLineageEntry) => void;
  onAdvanceSessionLineageQueue: (filter: LineageQueueKind) => void;
  onFocusSessionLineageEntry: (entry: SessionLineageEntry, filter: SessionLineageFilter) => void;
  expandedSessionLineageQueues: LineageQueueKind[];
  currentSessionLineageQueue: LineageQueueKind | "";
  onExpandAllSessionLineageQueues: () => void;
  onCollapseAllSessionLineageQueues: () => void;
  onOpenCurrentSessionLineageQueue: () => void;
  sessionQueueAdvanceFeedback: QueueAdvanceFeedback<unknown> | null;
  sessionQueueAdvanceFocusSummary: QueueAdvanceFocusSummary | null;
  sessionQueueFocusDelta: QueueAdvanceFocusDelta | null;
  sessionQueueAdvanceNoticeActions: QueueAdvanceNoticeActionProps;
  attentionQueuePosition: number;
  hiddenAttentionQueueCount: number;
  attentionSessionLineageQueue: SessionLineageEntry[];
  onToggleSessionLineageQueueExpansion: (filter: LineageQueueKind) => void;
  onRestoreSessionLineageQueue: (filter: LineageQueueKind) => void;
  sessionLineagePriority: (entry: SessionLineageEntry) => TriagePriority;
  sessionLineageTraits: (entry: SessionLineageEntry | null) => SessionLineageTrait[];
  onSnoozeSessionLineageQueueEntry: (filter: LineageQueueKind, entry: SessionLineageEntry) => void;
  onAdvanceSessionLineageQueueFromEntry: (
    filter: LineageQueueKind,
    entry: SessionLineageEntry
  ) => void;
  onDismissSessionLineageQueueEntry: (
    filter: LineageQueueKind,
    entry: SessionLineageEntry
  ) => void;
  onFindSessionLineageEntryInSession: (entry: SessionLineageEntry) => void;
  onRevealSessionLineageEntryInTimeline: (entry: SessionLineageEntry) => void;
  decisionQueuePosition: number;
  hiddenDecisionQueueCount: number;
  decisionSessionLineageQueue: SessionLineageEntry[];
  visibleSessionLineageEntries: SessionLineageEntry[];
  onSelectRunOutcome: (runId: string, resultIndex: number) => void;
};

function workspaceHrefForEntry(entry: SessionLineageEntry): string {
  if (entry.projectId && entry.storyId) {
    return `/projects/${entry.projectId}?storyId=${entry.storyId}`;
  }
  if (entry.projectId) {
    return `/projects/${entry.projectId}`;
  }
  return "";
}

export function SessionLineageSection({
  hasSelectedSession,
  sessionEventTotalCount,
  sessionLineageEntries,
  linkedRunCount,
  linkedApprovalCount,
  linkedIssueCount,
  linkedAgentCount,
  sessionLineageDecisionCount,
  sessionLineageEventCount,
  sessionLineageAgentCount,
  sessionLineageStatusCounts,
  filteredSessionLineageEntriesCount,
  sessionLineageFilter,
  onSessionLineageFilterChange,
  sessionLineageAttentionCount,
  sessionLineageAgentLinkedCount,
  persistedDismissedLineageQueueCount,
  persistedSnoozedLineageQueueCount,
  sessionLineagePriorityCounts,
  hasPersistedLineageQueuePreferences,
  onExportSessionLineageQueuePreferences,
  onResetSessionLineageQueuePreferences,
  selectedSessionLineageEntry,
  selectedSessionLineagePriority,
  selectedSessionLineageTraits,
  formatTimestamp,
  nextBestSessionLineageEntry,
  attentionSessionLineageEntries,
  decisionSessionLineageEntries,
  latestAgentLinkedLineageEntry,
  onInspectSessionLineageEntry,
  onAdvanceSessionLineageQueue,
  onFocusSessionLineageEntry,
  expandedSessionLineageQueues,
  currentSessionLineageQueue,
  onExpandAllSessionLineageQueues,
  onCollapseAllSessionLineageQueues,
  onOpenCurrentSessionLineageQueue,
  sessionQueueAdvanceFeedback,
  sessionQueueAdvanceFocusSummary,
  sessionQueueFocusDelta,
  sessionQueueAdvanceNoticeActions,
  attentionQueuePosition,
  hiddenAttentionQueueCount,
  attentionSessionLineageQueue,
  onToggleSessionLineageQueueExpansion,
  onRestoreSessionLineageQueue,
  sessionLineagePriority,
  sessionLineageTraits,
  onSnoozeSessionLineageQueueEntry,
  onAdvanceSessionLineageQueueFromEntry,
  onDismissSessionLineageQueueEntry,
  onFindSessionLineageEntryInSession,
  onRevealSessionLineageEntryInTimeline,
  decisionQueuePosition,
  hiddenDecisionQueueCount,
  decisionSessionLineageQueue,
  visibleSessionLineageEntries,
  onSelectRunOutcome,
}: SessionLineageSectionProps) {
  const queueConfigs = [
    {
      key: "attention" as const,
      title: "Attention Queue",
      entries: attentionSessionLineageQueue,
      total: attentionSessionLineageEntries.length,
      position: attentionQueuePosition,
      hiddenCount: hiddenAttentionQueueCount,
      count: sessionLineageAttentionCount,
      emptyText: "No attention-linked chains in this session.",
      excludedTraitKey: "attention",
    },
    {
      key: "decisions" as const,
      title: "Decision Queue",
      entries: decisionSessionLineageQueue,
      total: decisionSessionLineageEntries.length,
      position: decisionQueuePosition,
      hiddenCount: hiddenDecisionQueueCount,
      count: sessionLineageDecisionCount,
      emptyText: "No decision-linked chains in this session.",
      excludedTraitKey: "decision",
    },
  ];

  return (
    <Card className="border border-[#e5e5e3] bg-white shadow-[0_1px_3px_rgba(15,15,15,0.08),0_0_1px_rgba(15,15,15,0.04)]">
      <CardHeader>
        <CardTitle className="text-[18px] font-semibold tracking-[-0.02em] text-[#37352f]">
          Session Lineage
        </CardTitle>
        <CardDescription className="text-[13px] text-[#787774]">
          Run-linked picture of recent outcomes, decisions, events, and agents across the current
          session.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!hasSelectedSession ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            Select a session to inspect recent lineage chains.
          </div>
        ) : sessionLineageEntries.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[#e5e5e3] bg-[#fafaf9] px-5 py-8 text-[13px] text-[#9b9a97]">
            No run-linked lineage recorded for this session yet.
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <SessionMetric
                label="Outcomes"
                value={String(sessionLineageEntries.length)}
                detail={`${linkedRunCount} run${linkedRunCount === 1 ? "" : "s"} linked`}
              />
              <SessionMetric
                label="Decisions"
                value={String(sessionLineageDecisionCount)}
                detail={`${linkedApprovalCount} approvals · ${linkedIssueCount} issues`}
              />
              <SessionMetric
                label="Events"
                value={String(sessionLineageEventCount)}
                detail={`${sessionEventTotalCount} session event${sessionEventTotalCount === 1 ? "" : "s"}`}
              />
              <SessionMetric
                label="Agents"
                value={String(sessionLineageAgentCount)}
                detail={`${linkedAgentCount} linked agent${linkedAgentCount === 1 ? "" : "s"} in session`}
              />
            </div>

            <BreakdownChips
              label="Lineage Statuses"
              values={sessionLineageStatusCounts}
              emptyText="No lineage statuses recorded."
            />

            <div className="rounded-2xl border border-[#ecebe8] bg-[#fbfbf9] p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                  Recent Chains
                </p>
                <Badge
                  variant="outline"
                  className="rounded-full border-[#e5e5e3] bg-white px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                >
                  {filteredSessionLineageEntriesCount}
                </Badge>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <FilterChip
                  label="All"
                  active={sessionLineageFilter === "all"}
                  count={sessionLineageEntries.length}
                  onClick={() => {
                    onSessionLineageFilterChange("all");
                  }}
                />
                <FilterChip
                  label="Attention"
                  active={sessionLineageFilter === "attention"}
                  count={sessionLineageAttentionCount}
                  onClick={() => {
                    onSessionLineageFilterChange("attention");
                  }}
                />
                <FilterChip
                  label="Decisions"
                  active={sessionLineageFilter === "decisions"}
                  count={sessionLineageDecisionCount}
                  onClick={() => {
                    onSessionLineageFilterChange("decisions");
                  }}
                />
                <FilterChip
                  label="Agent-linked"
                  active={sessionLineageFilter === "agent-linked"}
                  count={sessionLineageAgentLinkedCount}
                  onClick={() => {
                    onSessionLineageFilterChange("agent-linked");
                  }}
                />
              </div>
              <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                      Operator State
                    </p>
                    <p className="mt-1 text-[12px] text-[#787774]">
                      {persistedDismissedLineageQueueCount} dismissed ·{" "}
                      {persistedSnoozedLineageQueueCount} snoozed persisted for this session
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {(["critical", "high", "normal"] as TriagePriority[]).map((priority) =>
                        sessionLineagePriorityCounts[priority] ? (
                          <Badge
                            key={`session-lineage-priority-${priority}`}
                            variant="outline"
                            className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(priority)}`}
                          >
                            {priority} {sessionLineagePriorityCounts[priority]}
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
                        void onExportSessionLineageQueuePreferences();
                      }}
                      disabled={!hasPersistedLineageQueuePreferences}
                    >
                      Copy queue state
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onResetSessionLineageQueuePreferences();
                      }}
                      disabled={!hasPersistedLineageQueuePreferences}
                    >
                      Reset queue state
                    </Button>
                  </div>
                </div>
              </div>
              <div className="rounded-xl border border-[#ecebe8] bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#9b9a97]">
                    Active Focus
                  </p>
                  {selectedSessionLineageEntry ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {selectedSessionLineagePriority ? (
                        <Badge
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(selectedSessionLineagePriority)}`}
                        >
                          {selectedSessionLineagePriority}
                        </Badge>
                      ) : null}
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        {formatTimestamp(selectedSessionLineageEntry.timestamp)}
                      </Badge>
                    </div>
                  ) : null}
                </div>
                {!selectedSessionLineageEntry ? (
                  <p className="mt-3 text-[13px] text-[#9b9a97]">
                    Select a lineage chain to inspect its linked context.
                  </p>
                ) : (
                  <>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        run {selectedSessionLineageEntry.runId}
                      </Badge>
                      <Badge
                        variant="outline"
                        className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                      >
                        outcome {selectedSessionLineageEntry.resultIndex + 1}
                      </Badge>
                      {selectedSessionLineageTraits.map((trait) => (
                        <Badge
                          key={trait.key}
                          variant="outline"
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${trait.className}`}
                        >
                          {trait.label}
                        </Badge>
                      ))}
                    </div>
                    <p className="mt-3 text-[12px] text-[#6b6b6b]">
                      {selectedSessionLineageEntry.title}
                      {selectedSessionLineageEntry.subtitle
                        ? ` · ${selectedSessionLineageEntry.subtitle}`
                        : ""}
                    </p>
                  </>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={() => {
                      if (nextBestSessionLineageEntry) {
                        onInspectSessionLineageEntry(nextBestSessionLineageEntry);
                      }
                    }}
                    disabled={!nextBestSessionLineageEntry}
                  >
                    Inspect next best
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={() => {
                      onAdvanceSessionLineageQueue("attention");
                    }}
                    disabled={!attentionSessionLineageEntries.length}
                  >
                    Inspect next attention
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={() => {
                      onAdvanceSessionLineageQueue("decisions");
                    }}
                    disabled={!decisionSessionLineageEntries.length}
                  >
                    Inspect next decision
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                    onClick={() => {
                      if (latestAgentLinkedLineageEntry) {
                        onFocusSessionLineageEntry(latestAgentLinkedLineageEntry, "agent-linked");
                      }
                    }}
                    disabled={!latestAgentLinkedLineageEntry}
                  >
                    Latest agent-linked
                  </Button>
                  {selectedSessionLineageEntry ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                      onClick={() => {
                        onInspectSessionLineageEntry(selectedSessionLineageEntry);
                      }}
                    >
                      Re-open selection
                    </Button>
                  ) : null}
                </div>
              </div>
              <div className="space-y-3">
                <QueueGroupControls
                  title="Queue Groups"
                  detail="Attention and decision queues now share the same group controls as the inbox."
                  openCount={expandedSessionLineageQueues.length}
                  totalCount={SESSION_LINEAGE_QUEUE_KEYS.length}
                  onExpandAll={onExpandAllSessionLineageQueues}
                  onCollapseAll={onCollapseAllSessionLineageQueues}
                  onOpenCurrent={onOpenCurrentSessionLineageQueue}
                  canOpenCurrent={Boolean(currentSessionLineageQueue)}
                />
                <QueueAdvanceNotice
                  label="Queue Advance"
                  feedback={sessionQueueAdvanceFeedback}
                  focusSummary={sessionQueueAdvanceFocusSummary}
                  focusDelta={sessionQueueFocusDelta}
                  {...sessionQueueAdvanceNoticeActions}
                />
                <div className="grid gap-3 xl:grid-cols-2">
                  {queueConfigs.map((queue) => (
                    <CollapsibleQueuePanel
                      key={queue.key}
                      title={queue.title}
                      detail={`${
                        queue.position >= 0
                          ? `Selected ${queue.position + 1} of ${queue.total}`
                          : `${queue.total} queued`
                      }${queue.hiddenCount ? ` · ${queue.hiddenCount} hidden` : ""}`}
                      expanded={expandedSessionLineageQueues.includes(queue.key)}
                      onToggle={() => {
                        onToggleSessionLineageQueueExpansion(queue.key);
                      }}
                      collapsedSummary={
                        queue.total
                          ? `${queue.total} visible queue item${queue.total === 1 ? "" : "s"} hidden`
                          : "Queue collapsed."
                      }
                      emptyText={queue.emptyText}
                      isEmpty={!queue.entries.length}
                      badge={
                        <Badge
                          variant="outline"
                          className="rounded-full border-[#e5e5e3] bg-[#fafaf9] px-2.5 py-1 text-[11px] font-medium text-[#37352f]"
                        >
                          {queue.count}
                        </Badge>
                      }
                      actions={
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                            onClick={() => {
                              onAdvanceSessionLineageQueue(queue.key);
                            }}
                            disabled={!queue.total}
                          >
                            Inspect next
                          </Button>
                          {queue.hiddenCount ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                              onClick={() => {
                                onRestoreSessionLineageQueue(queue.key);
                              }}
                            >
                              Restore hidden
                            </Button>
                          ) : null}
                        </>
                      }
                    >
                      <div className="mt-3 space-y-3">
                        {queue.entries.map((entry) => {
                          const selected = selectedSessionLineageEntry?.key === entry.key;
                          const queueTraits = sessionLineageTraits(entry).filter(
                            (trait) => trait.key !== queue.excludedTraitKey
                          );
                          const workspaceHref = workspaceHrefForEntry(entry);
                          const priority = sessionLineagePriority(entry);
                          return (
                            <QueueItemCard
                              key={`${queue.key}-queue-${entry.key}`}
                              title={entry.title}
                              subtitle={`run ${entry.runId} · outcome ${entry.resultIndex + 1}`}
                              timestamp={formatTimestamp(entry.timestamp)}
                              selected={selected}
                              badges={
                                <>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(priority)}`}
                                  >
                                    {priority}
                                  </Badge>
                                  <Badge
                                    variant="outline"
                                    className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(entry.status)}`}
                                  >
                                    {entry.status}
                                  </Badge>
                                  {queueTraits.slice(0, 2).map((trait) => (
                                    <Badge
                                      key={`${entry.key}-${trait.key}`}
                                      variant="outline"
                                      className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${trait.className}`}
                                    >
                                      {trait.label}
                                    </Badge>
                                  ))}
                                </>
                              }
                              actions={
                                <>
                                  <Button
                                    size="sm"
                                    variant={
                                      selected && sessionLineageFilter === queue.key
                                        ? "default"
                                        : "outline"
                                    }
                                    className={`h-7 rounded-lg px-2 text-[11px] ${
                                      selected && sessionLineageFilter === queue.key
                                        ? "bg-[#1a1a1a] text-white hover:bg-[#333]"
                                        : "border-[#e5e5e3] bg-white text-[#37352f] hover:bg-[#f7f7f5]"
                                    }`}
                                    onClick={() => {
                                      onFocusSessionLineageEntry(entry, queue.key);
                                    }}
                                  >
                                    {selected && sessionLineageFilter === queue.key
                                      ? "Selected"
                                      : "Inspect"}
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      onSnoozeSessionLineageQueueEntry(queue.key, entry);
                                    }}
                                  >
                                    Snooze 15m
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#d3e5ef] bg-[#eef7fb] px-2 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                    onClick={() => {
                                      onAdvanceSessionLineageQueueFromEntry(queue.key, entry);
                                    }}
                                  >
                                    Next in queue
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      onDismissSessionLineageQueueEntry(queue.key, entry);
                                    }}
                                  >
                                    Dismiss
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#e5e5e3] bg-white px-2 text-[11px] text-[#37352f] hover:bg-[#f7f7f5]"
                                    onClick={() => {
                                      onFindSessionLineageEntryInSession(entry);
                                    }}
                                  >
                                    Find in session
                                  </Button>
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="h-7 rounded-lg border-[#d3e5ef] bg-[#eef7fb] px-2 text-[11px] text-[#2a6690] hover:bg-[#e3f2f8]"
                                    onClick={() => {
                                      onRevealSessionLineageEntryInTimeline(entry);
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
              {!filteredSessionLineageEntriesCount ? (
                <p className="mt-3 text-[13px] text-[#9b9a97]">
                  No lineage chains match the current focus mode.
                </p>
              ) : (
                <div className="mt-3 space-y-3">
                  {visibleSessionLineageEntries.map((entry) => {
                    const selected = selectedSessionLineageEntry?.key === entry.key;
                    const workspaceHref = workspaceHrefForEntry(entry);
                    return (
                      <div
                        key={entry.key}
                        className={`rounded-xl border p-3 ${
                          selected ? "border-[#d3e5ef] bg-[#f7fbfd]" : "border-[#ecebe8] bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <p className="text-[13px] font-semibold text-[#37352f]">{entry.title}</p>
                            <p className="mt-2 text-[12px] text-[#787774]">
                              {entry.subtitle || "No outcome subtype"}
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${triagePriorityClass(sessionLineagePriority(entry))}`}
                            >
                              {sessionLineagePriority(entry)}
                            </Badge>
                            <Badge
                              variant="outline"
                              className={`rounded-full px-2.5 py-1 text-[11px] font-semibold capitalize ${passStatusClass(entry.status)}`}
                            >
                              {entry.status}
                            </Badge>
                            <p className="text-[11px] text-[#9b9a97]">
                              {formatTimestamp(entry.timestamp)}
                            </p>
                          </div>
                        </div>

                        <RelationshipStrip
                          label="Lineage Chain"
                          items={[
                            {
                              key: `lineage-run-${entry.runId}`,
                              label: `run ${entry.runId}`,
                              tone: "run",
                              onClick: () => {
                                onSelectRunOutcome(entry.runId, 0);
                              },
                            },
                            {
                              key: `lineage-outcome-${entry.key}`,
                              label: `outcome ${entry.resultIndex + 1}`,
                              tone: "outcome",
                              active: selected,
                              onClick: () => onInspectSessionLineageEntry(entry),
                            },
                            entry.approvalId
                              ? {
                                  key: `lineage-approval-${entry.approvalId}`,
                                  label: `approval ${entry.approvalId}`,
                                  tone: "approval" as const,
                                  onClick: () => onInspectSessionLineageEntry(entry),
                                }
                              : null,
                            entry.issueId
                              ? {
                                  key: `lineage-issue-${entry.issueId}`,
                                  label: `issue ${entry.issueId}`,
                                  tone: "issue" as const,
                                  onClick: () => onInspectSessionLineageEntry(entry),
                                }
                              : null,
                            entry.eventKey
                              ? {
                                  key: `lineage-event-${entry.eventKey}`,
                                  label: `event ${entry.eventName || "event"}`,
                                  tone: "event" as const,
                                  onClick: () => onInspectSessionLineageEntry(entry),
                                }
                              : null,
                            entry.runtimeAgentId
                              ? {
                                  key: `lineage-agent-${entry.runtimeAgentId}`,
                                  label: `agent ${entry.runtimeAgentId}`,
                                  tone: "agent" as const,
                                  onClick: () => onInspectSessionLineageEntry(entry),
                                }
                              : null,
                          ].filter(Boolean) as RelationshipStripItem[]}
                        />

                        <p className="mt-3 text-[12px] text-[#6b6b6b]">{entry.message}</p>

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
                              onInspectSessionLineageEntry(entry);
                            }}
                          >
                            {selected ? "Selected" : "Inspect chain"}
                          </Button>
                          {workspaceHref ? (
                            <Link
                              href={workspaceHref}
                              className="inline-flex h-7 items-center rounded-lg border border-[#e5e5e3] bg-white px-2 text-[11px] font-medium text-[#37352f] transition-colors hover:bg-[#f7f7f5]"
                            >
                              Open workspace
                            </Link>
                          ) : null}
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
