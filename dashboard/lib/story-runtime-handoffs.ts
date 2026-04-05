import type {
  ExecutionAgentActionRunRecord,
  ExecutionPlaneProjectDetail,
  ExecutionPlaneProjectRuntimeAgentRecord,
  ExecutionShadowAuditRecord,
} from "@/lib/types";
import { compareShadowAuditsByRecency } from "@/lib/shadow-audit-queue";

export type StoryRuntimeHandoffRow = {
  audit: ExecutionShadowAuditRecord;
  run: ExecutionAgentActionRunRecord;
  agents: ExecutionPlaneProjectRuntimeAgentRecord[];
};

export type StoryRuntimeHandoffSnapshot = {
  storyId: number;
  agents: ExecutionPlaneProjectRuntimeAgentRecord[];
  storyRuns: ExecutionAgentActionRunRecord[];
  blockedRuns: ExecutionAgentActionRunRecord[];
  openShadowAudits: ExecutionShadowAuditRecord[];
  handoffRows: StoryRuntimeHandoffRow[];
};

export type ProjectRuntimeHandoffSummary = {
  projectId: string;
  storyCountWithRuntimeAgents: number;
  blockedStoryCount: number;
  blockedHandoffCount: number;
  openShadowAuditCount: number;
  primaryStoryId?: number | null;
  primaryShadowAudit?: ExecutionShadowAuditRecord | null;
  openShadowAudits: ExecutionShadowAuditRecord[];
};

export type ProjectRuntimeHandoffAggregate = {
  blockedProjectCount: number;
  blockedStoryCount: number;
  blockedHandoffCount: number;
  openShadowAuditCount: number;
};

function isOpenShadowAudit(audit: ExecutionShadowAuditRecord): boolean {
  return Boolean(audit.open) || audit.status === "open";
}

function isBlockedRun(run: ExecutionAgentActionRunRecord): boolean {
  if (run.handoff_blocked || run.completion_state === "quarantined") return true;
  if ((run.open_shadow_audit_count ?? 0) > 0) return true;
  return (run.shadow_audits || []).some(isOpenShadowAudit);
}

export function buildStoryRuntimeHandoffSnapshot(
  storyId: number,
  projectDetail: ExecutionPlaneProjectDetail | null,
  runs: ExecutionAgentActionRunRecord[]
): StoryRuntimeHandoffSnapshot {
  const agents = (projectDetail?.runtime_agents || [])
    .filter((agent) => agent.story_id === storyId)
    .sort((left, right) => {
      const orderDelta = (left.pipeline_order ?? 0) - (right.pipeline_order ?? 0);
      if (orderDelta !== 0) return orderDelta;
      return left.label.localeCompare(right.label);
    });

  const agentIds = new Set(agents.map((agent) => agent.agent_id));
  const storyRuns = runs
    .filter((run) => run.runtime_agent_ids.some((agentId) => agentIds.has(agentId)))
    .sort((left, right) => {
      const updatedDelta = Date.parse(right.updated_at) - Date.parse(left.updated_at);
      if (updatedDelta !== 0) return updatedDelta;
      return right.id.localeCompare(left.id);
    });
  const blockedRuns = storyRuns.filter(isBlockedRun);
  const auditsById = new Map<string, ExecutionShadowAuditRecord>();
  const rowsById = new Map<string, StoryRuntimeHandoffRow>();

  blockedRuns.forEach((run) => {
    const relatedAgents = agents.filter((agent) => run.runtime_agent_ids.includes(agent.agent_id));
    (run.shadow_audits || []).forEach((audit) => {
      if (!isOpenShadowAudit(audit)) return;
      if (!auditsById.has(audit.id)) {
        auditsById.set(audit.id, audit);
      }
      if (!rowsById.has(audit.id)) {
        rowsById.set(audit.id, {
          audit,
          run,
          agents: relatedAgents,
        });
      }
    });
  });

  const openShadowAudits = Array.from(auditsById.values()).sort((left, right) => {
    return compareShadowAuditsByRecency(left, right);
  });
  const handoffRows = Array.from(rowsById.values()).sort((left, right) => {
    const updatedDelta = Date.parse(right.audit.updated_at) - Date.parse(left.audit.updated_at);
    if (updatedDelta !== 0) return updatedDelta;
    return right.audit.id.localeCompare(left.audit.id);
  });

  return {
    storyId,
    agents,
    storyRuns,
    blockedRuns,
    openShadowAudits,
    handoffRows,
  };
}

export function buildStoryRuntimeHandoffIndex(
  projectDetail: ExecutionPlaneProjectDetail | null,
  runs: ExecutionAgentActionRunRecord[]
): Map<number, StoryRuntimeHandoffSnapshot> {
  const index = new Map<number, StoryRuntimeHandoffSnapshot>();
  (projectDetail?.runtime_agents || []).forEach((agent) => {
    if (typeof agent.story_id !== "number") return;
    if (index.has(agent.story_id)) return;
    index.set(agent.story_id, buildStoryRuntimeHandoffSnapshot(agent.story_id, projectDetail, runs));
  });
  return index;
}

export function buildProjectRuntimeHandoffSummary(
  projectDetail: ExecutionPlaneProjectDetail | null,
  runs: ExecutionAgentActionRunRecord[]
): ProjectRuntimeHandoffSummary {
  const storyIndex = buildStoryRuntimeHandoffIndex(projectDetail, runs);
  const storySnapshots = Array.from(storyIndex.values());
  const blockedSnapshots = storySnapshots.filter(
    (snapshot) => snapshot.blockedRuns.length > 0 || snapshot.openShadowAudits.length > 0
  );
  const openShadowAudits = blockedSnapshots
    .flatMap((snapshot) => snapshot.openShadowAudits)
    .sort((left, right) => compareShadowAuditsByRecency(left, right));

  return {
    projectId: projectDetail?.project_id || "",
    storyCountWithRuntimeAgents: storySnapshots.length,
    blockedStoryCount: blockedSnapshots.length,
    blockedHandoffCount: blockedSnapshots.reduce(
      (sum, snapshot) => sum + snapshot.blockedRuns.length,
      0
    ),
    openShadowAuditCount: openShadowAudits.length,
    primaryStoryId: blockedSnapshots[0]?.storyId ?? null,
    primaryShadowAudit: openShadowAudits[0] ?? null,
    openShadowAudits,
  };
}

export function summarizeProjectRuntimeHandoffSignals(
  signals: Record<string, ProjectRuntimeHandoffSummary | undefined>
): ProjectRuntimeHandoffAggregate {
  const values = Object.values(signals).filter(
    (signal): signal is ProjectRuntimeHandoffSummary => Boolean(signal)
  );
  return {
    blockedProjectCount: values.filter((signal) => signal.openShadowAuditCount > 0).length,
    blockedStoryCount: values.reduce((sum, signal) => sum + signal.blockedStoryCount, 0),
    blockedHandoffCount: values.reduce((sum, signal) => sum + signal.blockedHandoffCount, 0),
    openShadowAuditCount: values.reduce((sum, signal) => sum + signal.openShadowAuditCount, 0),
  };
}
