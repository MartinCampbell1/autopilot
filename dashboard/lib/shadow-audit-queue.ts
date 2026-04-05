import type { ExecutionShadowAuditRecord } from "@/lib/types";

export function compareShadowAuditsByRecency(
  left: ExecutionShadowAuditRecord,
  right: ExecutionShadowAuditRecord
): number {
  const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
  if (updatedDelta !== 0) return updatedDelta;
  return right.id.localeCompare(left.id);
}

export function sortShadowAuditsByRecency(
  audits: ExecutionShadowAuditRecord[]
): ExecutionShadowAuditRecord[] {
  return [...audits].sort(compareShadowAuditsByRecency);
}
