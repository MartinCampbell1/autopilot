import type { OrchestratorSessionControlRecommendation } from "@/lib/types";

export function triagePriorityClass(priority: string): string {
  switch (priority) {
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "high":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    default:
      return "border-[#e5e5e3] bg-[#fafaf9] text-[#37352f]";
  }
}

export function passStatusClass(status: string): string {
  switch (status) {
    case "ok":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "partial":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "error":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "noop":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function sessionStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "completed":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "archived":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function controlStateClass(state: string): string {
  switch (state) {
    case "healthy":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    case "actionable":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "needs_approval":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "attention_required":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "closed":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function priorityClass(priority: string): string {
  switch (priority) {
    case "high":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "low":
      return "border-[#e5e5e3] bg-[#f7f7f5] text-[#787774]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function approvalStatusClass(status: string): string {
  switch (status) {
    case "pending":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "approved":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    case "rejected":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "applied":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function issueStatusClass(status: string): string {
  switch (status) {
    case "open":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "resolved":
      return "border-[#d6e9dc] bg-[#eef8f1] text-[#2b6e3f]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

export function issueSeverityClass(severity: string): string {
  switch (severity) {
    case "high":
    case "critical":
      return "border-[#f0d0c9] bg-[#fff0ed] text-[#93370d]";
    case "medium":
      return "border-[#f4e0c4] bg-[#fff6e8] text-[#9a6700]";
    case "low":
      return "border-[#d3e5ef] bg-[#eef7fb] text-[#2a6690]";
    default:
      return "border-[#e5e5e3] bg-white text-[#37352f]";
  }
}

function stringValue(value: unknown): string {
  return typeof value === "string" && value.trim() ? value : "";
}

export function recommendationActionLabel(
  recommendation: OrchestratorSessionControlRecommendation
): string {
  const operationType = stringValue(recommendation.operation.type);
  const operationMode = stringValue(recommendation.operation.mode);
  if (operationType === "session_action_batch" && operationMode === "preview") return "Create preview";
  if (operationType === "session_action_batch" && operationMode === "execute") return "Execute directly";
  if (operationType === "inspect_session_approvals") return "Inspect approvals";
  if (operationType === "inspect_session_issues") return "Inspect issues";
  if (operationType === "session_status_update") return "Complete session";
  return "Apply";
}
