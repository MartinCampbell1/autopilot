import type {
  QueueAdvanceFeedback,
  QueueAdvanceFocusSummary,
  QueueAdvanceNoticeActionProps,
  QueueAdvanceReasonDetails,
  QueueAdvanceSignal,
} from "@/components/queue-advance-notice";
import {
  asRecord,
  eventFamily,
  toStringValue,
} from "@/lib/control-plane-data";
import type {
  AgentScopedOutcome,
  AgentTimelineEntry,
  QueueAdvanceTarget,
  SessionLineageEntry,
  SessionLineageTrait,
  TriagePriority,
} from "@/lib/control-plane-models";
import { approvalStatusClass, passStatusClass } from "@/lib/control-plane-ui";

export function matchesRunFilter(run: { dry_run: boolean; status: string; results: Array<Record<string, unknown>> }, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "execute") return !run.dry_run;
  if (filter === "preview") return run.dry_run;
  if (filter === "attention") {
    return (
      run.status === "error" ||
      run.status === "partial" ||
      run.results.some((result) =>
        ["error", "pending_approval", "not_executable"].includes(toStringValue(result.status))
      )
    );
  }
  return true;
}

export function matchesEventFilter(event: Record<string, unknown>, filter: string): boolean {
  if (filter === "all") return true;
  const name = toStringValue(event.event);
  const status = toStringValue(event.status);
  if (filter === "attention") {
    return ["error", "partial", "pending_approval", "failed"].includes(status);
  }
  return eventFamily(name) === filter;
}

export function matchesAgentOutcomeFilter(outcome: AgentScopedOutcome, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "execute") return !outcome.run.dry_run;
  if (filter === "preview") return outcome.run.dry_run;
  if (filter === "attention") {
    const status = toStringValue(outcome.result.status);
    return ["error", "partial", "pending_approval", "not_executable", "failed"].includes(status);
  }
  return true;
}

export function matchesAgentTimelineFilter(entry: AgentTimelineEntry, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "approvals") return entry.kind === "approval";
  if (filter === "issues") return entry.kind === "issue";
  if (filter === "events") return entry.kind === "event";
  if (filter === "attention") {
    if (entry.kind === "approval") {
      return ["pending", "approved"].includes(entry.status);
    }
    if (entry.kind === "issue") {
      return entry.status === "open";
    }
    return ["error", "partial", "pending_approval", "failed"].includes(entry.status);
  }
  return true;
}

export function isAttentionLineageEntry(entry: SessionLineageEntry): boolean {
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  return (
    Boolean(entry.issueId) ||
    ["error", "partial", "pending_approval", "failed", "rejected", "blocked", "not_executable"].includes(
      status
    ) ||
    ["error", "partial", "pending_approval", "failed"].includes(eventStatus)
  );
}

export function matchesSessionLineageFilter(entry: SessionLineageEntry, filter: string): boolean {
  if (filter === "all") return true;
  if (filter === "attention") {
    return isAttentionLineageEntry(entry);
  }
  if (filter === "decisions") return Boolean(entry.approvalId || entry.issueId);
  if (filter === "agent-linked") return Boolean(entry.runtimeAgentId);
  return true;
}

export function sessionLineageTraits(entry: SessionLineageEntry | null): SessionLineageTrait[] {
  if (!entry) return [];
  return [
    isAttentionLineageEntry(entry)
      ? { key: "attention", label: "Attention", className: "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]" }
      : null,
    entry.approvalId || entry.issueId
      ? { key: "decision", label: "Decision-linked", className: "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]" }
      : null,
    entry.eventKey
      ? { key: "event", label: "Event-linked", className: "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]" }
      : null,
    entry.runtimeAgentId
      ? { key: "agent", label: "Agent-linked", className: "border-[#e5e5e3] bg-white text-[#37352f]" }
      : null,
  ].filter(Boolean) as SessionLineageTrait[];
}

export function triagePriorityRank(priority: TriagePriority): number {
  switch (priority) {
    case "critical":
      return 0;
    case "high":
      return 1;
    default:
      return 2;
  }
}

export function triagePriorityLabel(priority: TriagePriority): string {
  switch (priority) {
    case "critical":
      return "Critical";
    case "high":
      return "High";
    default:
      return "Normal";
  }
}

export function sessionLineageFilterLabel(filter: string): string {
  switch (filter) {
    case "attention":
      return "Attention";
    case "decisions":
      return "Decisions";
    case "agent-linked":
      return "Agent-linked";
    default:
      return "All";
  }
}

export function sessionLineageFilterClass(filter: string): string {
  switch (filter) {
    case "attention":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "decisions":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "agent-linked":
      return "border-[#e5e5e3] bg-white text-[#37352f]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

export function agentTimelineFilterLabel(filter: string): string {
  switch (filter) {
    case "approvals":
      return "Approvals";
    case "issues":
      return "Issues";
    case "events":
      return "Events";
    case "attention":
      return "Attention";
    default:
      return "All";
  }
}

export function agentTimelineFilterClass(filter: string): string {
  switch (filter) {
    case "approvals":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "issues":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "events":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "attention":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

function queueAdvanceSignal(
  key: string,
  label: string,
  className: string,
  focusFilter?: string
): QueueAdvanceSignal {
  return { key, label, className, focusFilter };
}

export function buildQueueAdvanceFeedback(args: {
  title: string;
  detail: string;
  nextTarget?: QueueAdvanceTarget | null;
  previousTarget?: QueueAdvanceTarget | null;
  reasonDetails?: QueueAdvanceReasonDetails | null;
}): QueueAdvanceFeedback<QueueAdvanceTarget> {
  return {
    title: args.title,
    detail: args.detail,
    timestamp: new Date().toISOString(),
    nextTarget: args.nextTarget,
    previousTarget: args.previousTarget,
    reason: args.reasonDetails?.reason,
    reasonPriority: args.reasonDetails?.priority,
    signals: args.reasonDetails?.signals,
  };
}

export function buildQueueAdvanceFocusSummary(args: {
  activeFilter: string;
  total: number;
  visible: number;
  labelForFilter: (filter: string) => string;
  classForFilter: (filter: string) => string;
  noun: string;
  scopeLabel: string;
}): QueueAdvanceFocusSummary {
  const { activeFilter, total, visible, labelForFilter, classForFilter, noun, scopeLabel } = args;
  const label = labelForFilter(activeFilter);
  return {
    label,
    detail:
      activeFilter === "all"
        ? `Showing ${visible} of ${total} ${noun} in the full ${scopeLabel} slice.`
        : `Showing ${visible} of ${total} ${noun} in the ${label.toLowerCase()} slice.`,
    activeFilter,
    badgeClassName: classForFilter(activeFilter),
  };
}

export function sessionLineagePriority(entry: SessionLineageEntry): TriagePriority {
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  if (
    entry.issueId ||
    ["error", "failed", "blocked", "rejected", "not_executable"].includes(status) ||
    ["error", "failed"].includes(eventStatus)
  ) {
    return "critical";
  }
  if (entry.approvalId || isAttentionLineageEntry(entry)) {
    return "high";
  }
  return "normal";
}

export function agentTimelinePriority(entry: AgentTimelineEntry): TriagePriority {
  const status = entry.status.toLowerCase();
  if (entry.kind === "issue" && status === "open") {
    return "critical";
  }
  if (entry.kind === "event" && ["error", "failed"].includes(status)) {
    return "critical";
  }
  if (entry.kind === "approval" && ["pending", "approved"].includes(status)) {
    return "high";
  }
  if (entry.kind === "event" && ["partial", "pending_approval", "blocked", "rejected"].includes(status)) {
    return "high";
  }
  return "normal";
}

export function agentTimelineEntryStatusClass(entry: AgentTimelineEntry): string {
  if (entry.kind === "approval") {
    return approvalStatusClass(entry.status);
  }
  if (entry.kind === "issue") {
    return passStatusClass(entry.status === "open" ? "partial" : "ok");
  }
  return passStatusClass(entry.status);
}

export function describeSessionQueueAdvanceReason(entry: SessionLineageEntry): QueueAdvanceReasonDetails {
  const priority = sessionLineagePriority(entry);
  const status = entry.status.toLowerCase();
  const eventStatus = toStringValue(asRecord(entry.event)?.status).toLowerCase();
  if (entry.issueId) {
    return {
      priority,
      reason: "Issue-linked chain stays at the front because it still represents an unresolved execution problem.",
      signals: [
        queueAdvanceSignal(
          "issue",
          "Issue-linked",
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "decisions"
        ),
      ],
    };
  }
  if (["error", "failed", "blocked", "rejected", "not_executable"].includes(status)) {
    return {
      priority,
      reason: `Run status "${status}" keeps this chain at ${triagePriorityLabel(priority).toLowerCase()} priority.`,
      signals: [
        queueAdvanceSignal(
          "run-status",
          `Run ${status}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
      ],
    };
  }
  if (["error", "failed"].includes(eventStatus)) {
    return {
      priority,
      reason: `Linked event status "${eventStatus}" keeps this chain elevated for operator attention.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${eventStatus}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
        queueAdvanceSignal(
          "event-linked",
          "Event-linked",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "all"
        ),
      ],
    };
  }
  if (entry.approvalId) {
    return {
      priority,
      reason: "Approval-linked chain remains next because it still needs an operator decision or apply step.",
      signals: [
        queueAdvanceSignal(
          "approval",
          "Approval-linked",
          "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]",
          "decisions"
        ),
      ],
    };
  }
  if (isAttentionLineageEntry(entry)) {
    return {
      priority,
      reason: "Attention signals on this chain still outweigh normal queue items after the previous transition.",
      signals: [
        queueAdvanceSignal(
          "attention",
          "Attention",
          "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]",
          "attention"
        ),
      ],
    };
  }
  if (entry.runtimeAgentId) {
    return {
      priority,
      reason: "Agent-linked context keeps this chain visible as the next operational handoff point.",
      signals: [
        queueAdvanceSignal(
          "agent",
          "Agent-linked",
          "border-[#e5e5e3] bg-white text-[#37352f]",
          "agent-linked"
        ),
      ],
    };
  }
  return {
    priority,
    reason: "This is the next visible queue item after the previous action completed.",
    signals: [
      queueAdvanceSignal(
        "queue-order",
        "Queue order",
        "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]",
        "all"
      ),
    ],
  };
}

export function describeAgentQueueAdvanceReason(entry: AgentTimelineEntry): QueueAdvanceReasonDetails {
  const priority = agentTimelinePriority(entry);
  const status = entry.status.toLowerCase();
  if (entry.kind === "issue" && status === "open") {
    return {
      priority,
      reason: "Open issue keeps this agent item at the front because it still blocks or degrades execution.",
      signals: [
        queueAdvanceSignal(
          "issue",
          "Open issue",
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "issues"
        ),
      ],
    };
  }
  if (entry.kind === "event" && ["error", "failed"].includes(status)) {
    return {
      priority,
      reason: `Failed runtime event "${status}" keeps this agent item at ${triagePriorityLabel(priority).toLowerCase()} priority.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${status}`,
          "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]",
          "attention"
        ),
        queueAdvanceSignal(
          "runtime-event",
          "Runtime event",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "events"
        ),
      ],
    };
  }
  if (entry.kind === "approval" && ["pending", "approved"].includes(status)) {
    return {
      priority,
      reason: `Approval status "${status}" keeps this agent item active until it is reviewed or applied.`,
      signals: [
        queueAdvanceSignal(
          "approval-status",
          `Approval ${status}`,
          "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]",
          "approvals"
        ),
      ],
    };
  }
  if (entry.kind === "event" && ["partial", "pending_approval", "blocked", "rejected"].includes(status)) {
    return {
      priority,
      reason: `Runtime event status "${status}" still needs operator attention before the agent can move cleanly.`,
      signals: [
        queueAdvanceSignal(
          "event-status",
          `Event ${status}`,
          "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]",
          "attention"
        ),
        queueAdvanceSignal(
          "runtime-event",
          "Runtime event",
          "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]",
          "events"
        ),
      ],
    };
  }
  return {
    priority,
    reason: "This is the next visible agent timeline item after the previous queue transition.",
    signals: [
      queueAdvanceSignal(
        "queue-order",
        "Queue order",
        "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]",
        "all"
      ),
    ],
  };
}

export function countTriagePriorities<T>(
  entries: T[],
  getPriority: (entry: T) => TriagePriority
): Record<TriagePriority, number> {
  return entries.reduce<Record<TriagePriority, number>>(
    (acc, entry) => {
      const priority = getPriority(entry);
      acc[priority] += 1;
      return acc;
    },
    {
      critical: 0,
      high: 0,
      normal: 0,
    }
  );
}

export function nextBestTriageItem<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string,
  getPriority: (entry: T) => TriagePriority
): T | null {
  if (!entries.length) return null;
  const rankedEntries = entries
    .map((entry, index) => ({ entry, index }))
    .sort(
      (left, right) =>
        triagePriorityRank(getPriority(left.entry)) - triagePriorityRank(getPriority(right.entry)) ||
        left.index - right.index
    )
    .map(({ entry }) => entry);
  if (!current) return rankedEntries[0] ?? null;
  const currentIndex = rankedEntries.findIndex((entry) => getKey(entry) === getKey(current));
  if (currentIndex === -1) return rankedEntries[0] ?? null;
  return rankedEntries[currentIndex + 1] ?? rankedEntries[0] ?? null;
}

export function triageQueuePosition<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string
): number {
  if (!current) return -1;
  return entries.findIndex((entry) => getKey(entry) === getKey(current));
}

export function nextTriageEntryByPriority<T>(
  entries: T[],
  current: T | null,
  getKey: (entry: T) => string,
  getPriority: (entry: T) => TriagePriority,
  priority: TriagePriority
): T | null {
  const queue = entries.filter((entry) => getPriority(entry) === priority);
  if (!queue.length) return null;
  if (!current || getPriority(current) !== priority) {
    return queue[0] ?? null;
  }
  const currentIndex = queue.findIndex((entry) => getKey(entry) === getKey(current));
  if (currentIndex === -1) return queue[0] ?? null;
  return queue[currentIndex + 1] ?? queue[0] ?? null;
}

export function nextSessionLineageQueueEntry(
  entries: SessionLineageEntry[],
  current: SessionLineageEntry | null
): SessionLineageEntry | null {
  if (!entries.length) return null;
  if (!current) return entries[0];
  const currentIndex = entries.findIndex((entry) => entry.key === current.key);
  if (currentIndex === -1) return entries[0];
  return entries[currentIndex + 1] ?? entries[0];
}

export function sessionLineageQueuePosition(
  entries: SessionLineageEntry[],
  current: SessionLineageEntry | null
): number {
  if (!current) return -1;
  return entries.findIndex((entry) => entry.key === current.key);
}

export function buildQueueAdvanceNoticeActionProps(args: {
  feedback: QueueAdvanceFeedback<QueueAdvanceTarget> | null;
  onOpenTarget: (target: QueueAdvanceTarget | null | undefined) => void;
  onSignalClick?: ((signal: QueueAdvanceSignal) => void) | undefined;
  onResetFocus?: (() => void) | undefined;
  onOpenMatchingQueue?: (() => void) | undefined;
}): QueueAdvanceNoticeActionProps {
  const { feedback, onOpenTarget, onSignalClick, onResetFocus, onOpenMatchingQueue } = args;
  return {
    onOpenSelectedNext: feedback?.nextTarget
      ? () => {
          onOpenTarget(feedback.nextTarget);
        }
      : undefined,
    onReopenPrevious: feedback?.previousTarget
      ? () => {
          onOpenTarget(feedback.previousTarget);
        }
      : undefined,
    onSignalClick: feedback?.nextTarget ? onSignalClick : undefined,
    onResetFocus,
    onOpenMatchingQueue,
  };
}
