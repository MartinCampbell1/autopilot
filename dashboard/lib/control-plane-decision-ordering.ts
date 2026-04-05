import type {
  ExecutionApprovalRecord,
  ExecutionIssueRecord,
  ToolPermissionRuntimeRecord,
} from "@/lib/types";

export function compareApprovalsBySessionOrder(
  left: ExecutionApprovalRecord,
  right: ExecutionApprovalRecord
): number {
  const createdDelta = Date.parse(right.created_at) - Date.parse(left.created_at);
  if (createdDelta !== 0) return createdDelta;
  const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
  if (updatedDelta !== 0) return updatedDelta;
  return right.id.localeCompare(left.id);
}

export function sortApprovalsBySessionOrder(
  approvals: ExecutionApprovalRecord[]
): ExecutionApprovalRecord[] {
  return [...approvals].sort(compareApprovalsBySessionOrder);
}

export function compareIssuesBySessionOrder(
  left: ExecutionIssueRecord,
  right: ExecutionIssueRecord
): number {
  const createdDelta = Date.parse(right.created_at) - Date.parse(left.created_at);
  if (createdDelta !== 0) return createdDelta;
  const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
  if (updatedDelta !== 0) return updatedDelta;
  return right.id.localeCompare(left.id);
}

export function sortIssuesBySessionOrder(issues: ExecutionIssueRecord[]): ExecutionIssueRecord[] {
  return [...issues].sort(compareIssuesBySessionOrder);
}

export function compareToolPermissionRuntimesByRecency(
  left: ToolPermissionRuntimeRecord,
  right: ToolPermissionRuntimeRecord
): number {
  const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
  if (updatedDelta !== 0) return updatedDelta;
  return right.id.localeCompare(left.id);
}

export function sortToolPermissionRuntimesByRecency(
  runtimes: ToolPermissionRuntimeRecord[]
): ToolPermissionRuntimeRecord[] {
  return [...runtimes].sort(compareToolPermissionRuntimesByRecency);
}
