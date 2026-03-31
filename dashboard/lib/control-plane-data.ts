import type {
  ExecutionApprovalRecord,
  ExecutionAgentActionRunRecord,
  ExecutionIssueRecord,
  OrchestratorControlPassRecord,
  OrchestratorSessionRecord,
} from "@/lib/types";

const DATE_FORMATTER = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatTimestamp(value?: string | null): string {
  if (!value) return "No activity yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return DATE_FORMATTER.format(date);
}

export function toNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function toNullableNumber(value: unknown): number | null {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

export function normalizeSearchQuery(value: string): string {
  return value.trim().toLowerCase();
}

export function searchText(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value.toLowerCase();
  if (typeof value === "number" || typeof value === "boolean") return String(value).toLowerCase();
  if (Array.isArray(value)) return value.map((item) => searchText(item)).join(" ");
  if (typeof value === "object") {
    return Object.values(value as Record<string, unknown>)
      .map((item) => searchText(item))
      .join(" ");
  }
  return String(value).toLowerCase();
}

export function matchesSearch(values: unknown[], query: string): boolean {
  const normalized = normalizeSearchQuery(query);
  if (!normalized) return true;
  return values.some((value) => searchText(value).includes(normalized));
}

export function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function toStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => toStringValue(item)).filter(Boolean)
    : [];
}

export function extractRunId(value: unknown): string {
  const record = asRecord(value);
  if (!record) return "";
  return toStringValue(asRecord(record.run)?.id);
}

export function extractLatestRunIdFromAppliedSteps(value: Array<Record<string, unknown>>): string {
  for (const step of [...value].reverse()) {
    const runId = extractRunId(step.result);
    if (runId) return runId;
  }
  return "";
}

export function formatScopeList(values: string[], fallback: string): string {
  return values.length ? values.join(", ") : fallback;
}

export function outcomeProjectId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return toStringValue(action?.project_id) || toStringValue(project?.id);
}

export function outcomeProjectName(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const project = asRecord(result.project) || asRecord(commandResult?.project);
  return toStringValue(action?.project_name) || toStringValue(project?.name) || outcomeProjectId(result);
}

export function outcomeStoryId(result: Record<string, unknown>): number | null {
  const action = asRecord(result.action);
  return toNullableNumber(action?.story_id);
}

export function outcomeStoryTitle(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.story_title);
}

export function outcomeRuntimeAgentId(result: Record<string, unknown>): string {
  const action = asRecord(result.action);
  return toStringValue(action?.runtime_agent_id);
}

export function outcomeRuntimeAgentIds(result: Record<string, unknown>): string[] {
  const action = asRecord(result.action);
  const linkedIds = toStringArray(action?.runtime_agent_ids);
  const singleId = toStringValue(action?.runtime_agent_id);
  return [...new Set([...linkedIds, ...(singleId ? [singleId] : [])])];
}

export function formatJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function eventFamily(eventName: string): string {
  if (!eventName) return "other";
  if (
    eventName.includes("approval") ||
    eventName.includes("issue") ||
    eventName.includes("budget_paused")
  ) {
    return "decisions";
  }
  if (
    eventName.startsWith("execution_plane_orchestrator_session") ||
    eventName.includes("control_pass")
  ) {
    return "control";
  }
  if (
    eventName.includes("agent_action") ||
    eventName.includes("agent_batch") ||
    eventName.includes("action_run")
  ) {
    return "actions";
  }
  return "runtime";
}

export function runMatchesSearch(run: ExecutionAgentActionRunRecord, query: string): boolean {
  return matchesSearch(
    [
      run.id,
      run.run_kind,
      run.actor,
      run.mode,
      run.reason,
      run.policy_profile,
      run.preview_id,
      run.artifact_ref,
      run.apply_mode,
      run.approval_required,
      run.status,
      run.project_ids,
      run.initiative_ids,
      run.orchestrators,
      run.runtime_agent_ids,
      run.selection,
      run.summary,
      run.diff_summary,
      run.patch_bundle,
      run.results,
    ],
    query
  );
}

export function approvalMatchesSearch(approval: ExecutionApprovalRecord, query: string): boolean {
  return matchesSearch(
    [
      approval.id,
      approval.action,
      approval.status,
      approval.reason,
      approval.project_id,
      approval.project_name,
      approval.issue_id,
      approval.runtime_agent_ids,
      approval.policy_reasons,
      approval.payload,
    ],
    query
  );
}

export function issueMatchesSearch(issue: ExecutionIssueRecord, query: string): boolean {
  return matchesSearch(
    [
      issue.id,
      issue.title,
      issue.description,
      issue.root_cause,
      issue.category,
      issue.severity,
      issue.status,
      issue.project_id,
      issue.project_name,
      issue.related_command,
      issue.runtime_agent_id,
      issue.runtime_agent_ids,
      issue.approval_id,
      issue.context,
    ],
    query
  );
}

export function eventMatchesSearch(event: Record<string, unknown>, query: string): boolean {
  return matchesSearch(
    [
      event.event,
      event.status,
      event.message,
      event.project_id,
      event.story_id,
      event.orchestrator_session_id,
      event,
    ],
    query
  );
}

export function sessionMatchesSearch(session: OrchestratorSessionRecord, query: string): boolean {
  return matchesSearch(
    [
      session.id,
      session.title,
      session.orchestrator,
      session.actor,
      session.status,
      session.reason,
      session.initiative_id,
      session.project_ids,
      session.linked_run_ids,
      session.linked_control_pass_ids,
      session.linked_approval_ids,
      session.linked_issue_ids,
      session.linked_runtime_agent_ids,
      session.context,
    ],
    query
  );
}

export function controlPassMatchesSearch(
  controlPass: OrchestratorControlPassRecord,
  query: string
): boolean {
  return matchesSearch(
    [
      controlPass.id,
      controlPass.orchestrator_session_id,
      controlPass.actor,
      controlPass.reason,
      controlPass.profile,
      controlPass.recommendation_kinds,
      controlPass.project_ids,
      controlPass.initiative_id,
      controlPass.orchestrator,
      controlPass.status,
      controlPass.summary,
      controlPass.control_before,
      controlPass.control_after,
    ],
    query
  );
}

export function describeRunResult(result: Record<string, unknown>): {
  title: string;
  subtitle: string;
  message: string;
} {
  const action = asRecord(result.action);
  const commandResult = asRecord(result.command_result);
  const approval = asRecord(result.approval);
  const issue = asRecord(result.issue);
  const actionKey = toStringValue(action?.action_key);
  const command = toStringValue(action?.command);
  const kind = toStringValue(action?.kind);
  const actionType = toStringValue(action?.action_type, "operation");
  const title = actionKey || command || kind || toStringValue(result.status, "run-result");
  const subtitleParts = [
    actionType,
    toStringValue(result.planned_mode),
    toStringValue(result.status),
  ].filter(Boolean);
  const message =
    toStringValue(result.message) ||
    toStringValue(commandResult?.message) ||
    (approval ? `Approval ${toStringValue(approval.id, "created")}` : "") ||
    (issue ? `Issue ${toStringValue(issue.id, "linked")}` : "") ||
    "No additional result message.";
  return {
    title,
    subtitle: subtitleParts.join(" · "),
    message,
  };
}
