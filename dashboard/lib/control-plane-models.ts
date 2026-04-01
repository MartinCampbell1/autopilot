import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
} from "@/lib/types";

export type SessionContextKind =
  | ""
  | "approval"
  | "issue"
  | "event"
  | "tool_permission_runtime"
  | "async_task";
export type LineageQueueKind = "attention" | "decisions";
export type TriagePriority = "critical" | "high" | "normal";
export type AgentPriorityQueueKind = "critical" | "high";

export const SESSION_LINEAGE_QUEUE_KEYS: LineageQueueKind[] = ["attention", "decisions"];
export const AGENT_PRIORITY_QUEUE_KEYS: AgentPriorityQueueKind[] = ["critical", "high"];

export type AgentScopedOutcome = {
  run: ExecutionAgentActionRunRecord;
  result: Record<string, unknown>;
  resultIndex: number;
  timestamp: string;
  runtimeAgentIds: string[];
};

export type AgentTimelineEntry = {
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

export type PendingAgentTimelineTarget = {
  runtimeAgentId: string;
  runId: string;
  approvalId: string;
  issueId: string;
};

export type LinkedSelectionContext = {
  runId?: string;
  resultIndex?: number;
  approvalId?: string;
  issueId?: string;
  toolPermissionRuntimeId?: string;
  asyncTaskId?: string;
  runtimeAgentId?: string;
  event?: Record<string, unknown> | null;
};

export type SessionLineageEntry = {
  kind: "run_result" | "tool_permission_runtime" | "async_task";
  key: string;
  runId: string;
  resultIndex: number;
  timestamp: string;
  status: string;
  title: string;
  subtitle: string;
  message: string;
  approvalId: string;
  issueId: string;
  eventKey: string;
  eventName: string;
  runtimeAgentId: string;
  projectId: string;
  projectName: string;
  storyId: number | null;
  storyTitle: string;
  event: Record<string, unknown> | null;
  toolPermissionRuntimeId: string;
  toolPermissionPendingStage: string;
  toolPermissionToolUseId: string;
  asyncTaskId: string;
  asyncTaskStatus: string;
  asyncTaskCommand: string;
};

export type SessionLineageTrait = {
  key: string;
  label: string;
  className: string;
};

export type TriageInboxItem = {
  key: string;
  label: string;
  queueDetail: string;
  title: string;
  subtitle: string;
  timestamp: string;
  status: string;
  statusClassName: string;
  priority: TriagePriority;
  syncedWithSelection: boolean;
  onInspect: () => void;
  onSnooze: () => void;
  onDismiss: () => void;
};

export type TriageInboxFeedback = {
  itemKey: string;
  itemLabel: string;
  message: string;
  tone: "info" | "success";
  timestamp: string;
};

export type TriageInboxFeedbackGroup = {
  itemKey: string;
  itemLabel: string;
  entries: TriageInboxFeedback[];
  isActive: boolean;
};

export type SessionQueueAdvanceTarget = {
  kind: "session-lineage";
  filter: string;
  entry: SessionLineageEntry;
};

export type AgentQueueAdvanceTarget = {
  kind: "agent-timeline";
  priority: AgentPriorityQueueKind;
  entry: AgentTimelineEntry;
};

export type QueueAdvanceTarget = SessionQueueAdvanceTarget | AgentQueueAdvanceTarget;
