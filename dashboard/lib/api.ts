import type {
  ApprovalApplyResult,
  ApprovalDecisionResult,
  CapabilitiesCatalog,
  AccountHealth,
  AccountsByProvider,
  ConnectorValidationResult,
  CreateProjectResult,
  IssueResolutionResult,
  IntakeSession,
  LaunchResult,
  LaunchProfile,
  LaunchPreset,
  OrchestratorControlPassRecord,
  OrchestratorControlPassSummary,
  OrchestratorSessionControlPlanApplyResult,
  OrchestratorSessionControlProfile,
  OrchestratorSessionDetail,
  OrchestratorSessionRecommendationApplyResult,
  OrchestratorSessionRecord,
  OrchestratorSessionSummary,
  PRD,
  ProjectDetail,
  ProjectRuntimeControl,
  ProjectSummary,
  MCPConnector,
  RoutingPolicy,
  SkillPack,
} from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

function buildQuery(
  params: Record<string, string | number | boolean | null | undefined>
): string {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return;
    query.set(key, String(value));
  });
  const rendered = query.toString();
  return rendered ? `?${rendered}` : "";
}

async function parseError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;

  try {
    const data = await res.json();
    if (typeof data?.detail === "string" && data.detail.trim()) {
      detail = data.detail;
    } else if (typeof data?.message === "string" && data.message.trim()) {
      detail = data.message;
    }
  } catch {
    // Keep fallback.
  }

  throw new Error(detail);
}

async function jsonOrThrow<T>(res: Response, fallback: string): Promise<T> {
  if (!res.ok) return parseError(res, fallback);
  return res.json() as Promise<T>;
}

export async function fetchProjects(includeArchived = false) {
  const res = await fetch(`${API_BASE}/projects/?include_archived=${includeArchived ? "true" : "false"}`);
  return jsonOrThrow<{ projects: ProjectSummary[] }>(res, `Failed to fetch projects: ${res.status}`);
}

export async function fetchProject(projectId: string): Promise<ProjectDetail> {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}`);
  return jsonOrThrow<ProjectDetail>(res, `Failed to fetch project: ${res.status}`);
}

export async function fetchProjectRuntimeControl(
  projectId: string,
  options?: { staleAfterSec?: number }
): Promise<ProjectRuntimeControl> {
  const staleAfterSec = options?.staleAfterSec ?? 900;
  const res = await fetch(
    `${API_BASE}/projects/${encodeURIComponent(projectId)}/runtime-control?stale_after_sec=${staleAfterSec}`
  );
  return jsonOrThrow<ProjectRuntimeControl>(res, `Failed to fetch runtime control state: ${res.status}`);
}

export async function fetchExecutionPlaneOrchestratorSessions(
  filters?: {
    sessionId?: string;
    projectId?: string;
    initiativeId?: string;
    orchestrator?: string;
    actor?: string;
    status?: string;
  }
): Promise<{ sessions: OrchestratorSessionRecord[] }> {
  const query = buildQuery({
    session_id: filters?.sessionId,
    project_id: filters?.projectId,
    initiative_id: filters?.initiativeId,
    orchestrator: filters?.orchestrator,
    actor: filters?.actor,
    status: filters?.status,
  });
  const res = await fetch(`${API_BASE}/execution-plane/orchestrator-sessions${query}`);
  return jsonOrThrow<{ sessions: OrchestratorSessionRecord[] }>(
    res,
    `Failed to fetch orchestrator sessions: ${res.status}`
  );
}

export async function fetchExecutionPlaneOrchestratorSessionSummary(
  filters?: {
    projectId?: string;
    initiativeId?: string;
    orchestrator?: string;
    actor?: string;
    status?: string;
  }
): Promise<OrchestratorSessionSummary> {
  const query = buildQuery({
    project_id: filters?.projectId,
    initiative_id: filters?.initiativeId,
    orchestrator: filters?.orchestrator,
    actor: filters?.actor,
    status: filters?.status,
  });
  const res = await fetch(`${API_BASE}/execution-plane/orchestrator-sessions/summary${query}`);
  return jsonOrThrow<OrchestratorSessionSummary>(
    res,
    `Failed to fetch orchestrator session summary: ${res.status}`
  );
}

export async function fetchExecutionPlaneOrchestratorSession(
  sessionId: string,
  options?: { eventLimit?: number }
): Promise<OrchestratorSessionDetail> {
  const query = buildQuery({
    event_limit: options?.eventLimit ?? 25,
  });
  const res = await fetch(
    `${API_BASE}/execution-plane/orchestrator-sessions/${encodeURIComponent(sessionId)}${query}`
  );
  return jsonOrThrow<OrchestratorSessionDetail>(
    res,
    `Failed to fetch orchestrator session detail: ${res.status}`
  );
}

export async function fetchExecutionPlaneControlPasses(
  filters?: {
    orchestratorSessionId?: string;
    projectId?: string;
    initiativeId?: string;
    orchestrator?: string;
    actor?: string;
    profile?: string;
    status?: string;
  }
): Promise<{ control_passes: OrchestratorControlPassRecord[] }> {
  const query = buildQuery({
    orchestrator_session_id: filters?.orchestratorSessionId,
    project_id: filters?.projectId,
    initiative_id: filters?.initiativeId,
    orchestrator: filters?.orchestrator,
    actor: filters?.actor,
    profile: filters?.profile,
    status: filters?.status,
  });
  const res = await fetch(`${API_BASE}/execution-plane/orchestrator-sessions/control/passes${query}`);
  return jsonOrThrow<{ control_passes: OrchestratorControlPassRecord[] }>(
    res,
    `Failed to fetch control passes: ${res.status}`
  );
}

export async function fetchExecutionPlaneControlPassSummary(
  filters?: {
    orchestratorSessionId?: string;
    projectId?: string;
    initiativeId?: string;
    orchestrator?: string;
    actor?: string;
    profile?: string;
    status?: string;
  }
): Promise<OrchestratorControlPassSummary> {
  const query = buildQuery({
    orchestrator_session_id: filters?.orchestratorSessionId,
    project_id: filters?.projectId,
    initiative_id: filters?.initiativeId,
    orchestrator: filters?.orchestrator,
    actor: filters?.actor,
    profile: filters?.profile,
    status: filters?.status,
  });
  const res = await fetch(`${API_BASE}/execution-plane/orchestrator-sessions/control/passes/summary${query}`);
  return jsonOrThrow<OrchestratorControlPassSummary>(
    res,
    `Failed to fetch control pass summary: ${res.status}`
  );
}

export async function fetchExecutionPlaneOrchestratorSessionControlProfiles(): Promise<{
  profiles: OrchestratorSessionControlProfile[];
}> {
  const res = await fetch(`${API_BASE}/execution-plane/orchestrator-sessions/control/profiles`);
  return jsonOrThrow<{ profiles: OrchestratorSessionControlProfile[] }>(
    res,
    `Failed to fetch orchestrator session control profiles: ${res.status}`
  );
}

export async function applyExecutionPlaneOrchestratorSessionRecommendation(
  sessionId: string,
  payload: {
    recommendationKind: string;
    actor?: string;
    reason?: string;
    idempotencyKey?: string;
  }
): Promise<OrchestratorSessionRecommendationApplyResult> {
  const res = await fetch(
    `${API_BASE}/execution-plane/orchestrator-sessions/${encodeURIComponent(sessionId)}/control/apply`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recommendation_kind: payload.recommendationKind,
        actor: payload.actor ?? "dashboard-control-plane",
        reason: payload.reason ?? "",
        idempotency_key: payload.idempotencyKey ?? "",
      }),
    }
  );
  return jsonOrThrow<OrchestratorSessionRecommendationApplyResult>(
    res,
    `Failed to apply session recommendation: ${res.status}`
  );
}

export async function applyExecutionPlaneOrchestratorSessionControlPlan(
  sessionId: string,
  payload: {
    profile: string;
    actor?: string;
    reason?: string;
    recommendationKinds?: string[];
    maxOperations?: number;
    continueOnError?: boolean;
  }
): Promise<OrchestratorSessionControlPlanApplyResult> {
  const res = await fetch(
    `${API_BASE}/execution-plane/orchestrator-sessions/${encodeURIComponent(sessionId)}/control/apply-plan`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        profile: payload.profile,
        actor: payload.actor ?? "dashboard-control-plane",
        reason: payload.reason ?? "",
        recommendation_kinds: payload.recommendationKinds ?? [],
        max_operations: payload.maxOperations ?? 10,
        continue_on_error: payload.continueOnError ?? true,
      }),
    }
  );
  return jsonOrThrow<OrchestratorSessionControlPlanApplyResult>(
    res,
    `Failed to apply session control plan: ${res.status}`
  );
}

export async function approveExecutionPlaneApproval(
  approvalId: string,
  payload?: { actor?: string; note?: string }
): Promise<ApprovalDecisionResult> {
  const res = await fetch(`${API_BASE}/execution-plane/approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload?.actor ?? "dashboard-control-plane",
      note: payload?.note ?? "",
    }),
  });
  return jsonOrThrow<ApprovalDecisionResult>(res, `Failed to approve control-plane approval: ${res.status}`);
}

export async function rejectExecutionPlaneApproval(
  approvalId: string,
  payload?: { actor?: string; note?: string }
): Promise<ApprovalDecisionResult> {
  const res = await fetch(`${API_BASE}/execution-plane/approvals/${encodeURIComponent(approvalId)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload?.actor ?? "dashboard-control-plane",
      note: payload?.note ?? "",
    }),
  });
  return jsonOrThrow<ApprovalDecisionResult>(res, `Failed to reject control-plane approval: ${res.status}`);
}

export async function applyExecutionPlaneApproval(
  approvalId: string,
  payload?: { actor?: string; note?: string }
): Promise<ApprovalApplyResult> {
  const res = await fetch(`${API_BASE}/execution-plane/approvals/${encodeURIComponent(approvalId)}/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload?.actor ?? "dashboard-control-plane",
      note: payload?.note ?? "",
    }),
  });
  return jsonOrThrow<ApprovalApplyResult>(res, `Failed to apply control-plane approval: ${res.status}`);
}

export async function resolveExecutionPlaneIssue(
  issueId: string,
  payload?: { actor?: string; note?: string }
): Promise<IssueResolutionResult> {
  const res = await fetch(`${API_BASE}/execution-plane/issues/${encodeURIComponent(issueId)}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      actor: payload?.actor ?? "dashboard-control-plane",
      note: payload?.note ?? "",
    }),
  });
  return jsonOrThrow<IssueResolutionResult>(res, `Failed to resolve control-plane issue: ${res.status}`);
}

export async function createProjectFromPrd(
  prd: object,
  projectName?: string,
  projectPath?: string
): Promise<CreateProjectResult> {
  const res = await fetch(`${API_BASE}/projects/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prd,
      project_name: projectName || null,
      project_path: projectPath || null,
    }),
  });
  return jsonOrThrow<CreateProjectResult>(res, `Project creation failed: ${res.status}`);
}

export async function launchProject(
  projectId: string,
  launchProfile?: Partial<LaunchProfile>
): Promise<LaunchResult> {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/launch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ launch_profile: launchProfile ?? null }),
  });
  return jsonOrThrow<LaunchResult>(res, `Launch failed: ${res.status}`);
}

export async function pauseProject(projectId: string) {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/pause`, {
    method: "POST",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Pause failed: ${res.status}`);
}

export async function resumeProject(projectId: string): Promise<LaunchResult> {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/resume`, {
    method: "POST",
  });
  return jsonOrThrow<LaunchResult>(res, `Resume failed: ${res.status}`);
}

export async function skipStory(projectId: string, storyId: number) {
  const res = await fetch(
    `${API_BASE}/projects/${encodeURIComponent(projectId)}/stories/${storyId}/skip`,
    { method: "POST" }
  );
  return jsonOrThrow<{ status: string; message: string }>(res, `Skip failed: ${res.status}`);
}

export async function recoverStoryCheckout(
  projectId: string,
  storyId: number,
  options?: { cleanup_worktree?: boolean; reopen_story?: boolean }
) {
  const res = await fetch(
    `${API_BASE}/projects/${encodeURIComponent(projectId)}/stories/${storyId}/recover-checkout`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cleanup_worktree: options?.cleanup_worktree ?? true,
        reopen_story: options?.reopen_story ?? false,
      }),
    }
  );
  return jsonOrThrow<{ status: string; project_id: string; story_id: number; cleanup_performed: boolean; reopened: boolean }>(
    res,
    `Checkout recovery failed: ${res.status}`
  );
}

export async function recoverStaleProjectCheckouts(
  projectId: string,
  options?: { cleanup_worktrees?: boolean; reopen_stories?: boolean; stale_after_sec?: number }
) {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/runtime-control/recover-stale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cleanup_worktrees: options?.cleanup_worktrees ?? true,
      reopen_stories: options?.reopen_stories ?? true,
      stale_after_sec: options?.stale_after_sec ?? 900,
    }),
  });
  return jsonOrThrow<{ status: string; project_id: string; stale_after_sec: number; recovered: Array<{ story_id: number; cleanup_performed: boolean; reopened: boolean }> }>(
    res,
    `Stale checkout recovery failed: ${res.status}`
  );
}

export async function addStoryGuidance(projectId: string, storyId: number, payload: string) {
  const res = await fetch(
    `${API_BASE}/projects/${encodeURIComponent(projectId)}/stories/${storyId}/guidance`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    }
  );
  return jsonOrThrow<{ status: string; message: string }>(res, `Guidance failed: ${res.status}`);
}

export async function archiveProject(projectId: string) {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/archive`, {
    method: "POST",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Archive failed: ${res.status}`);
}

export async function fetchAccountsHealth(): Promise<AccountHealth> {
  const res = await fetch(`${API_BASE}/accounts/health`);
  return jsonOrThrow<AccountHealth>(res, `Failed to fetch health: ${res.status}`);
}

export async function fetchAccounts(): Promise<{ accounts: AccountsByProvider }> {
  const res = await fetch(`${API_BASE}/accounts/`);
  return jsonOrThrow<{ accounts: AccountsByProvider }>(res, `Failed to fetch accounts: ${res.status}`);
}

export async function sendIntakeMessage(message: string, sessionId?: string | null) {
  const res = await fetch(`${API_BASE}/intake/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  return jsonOrThrow<{ session_id: string; response: string; prd_ready: boolean; prd: PRD | null }>(
    res,
    `Intake failed: ${res.status}`
  );
}

export async function fetchIntakeSessions(): Promise<{ sessions: IntakeSession[] }> {
  const res = await fetch(`${API_BASE}/intake/sessions`);
  return jsonOrThrow<{ sessions: IntakeSession[] }>(res, `Failed to fetch sessions: ${res.status}`);
}

export async function importSpec(spec: string): Promise<{ prd: PRD }> {
  const res = await fetch(`${API_BASE}/intake/spec`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spec }),
  });
  return jsonOrThrow<{ prd: PRD }>(res, `Spec import failed: ${res.status}`);
}

export async function openProviderLogin(provider: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/accounts/${encodeURIComponent(provider)}/open-login`, {
    method: "POST",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Login launch failed: ${res.status}`);
}

export async function importProviderSession(provider: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/accounts/${encodeURIComponent(provider)}/import`, {
    method: "POST",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Session import failed: ${res.status}`);
}

export async function fetchCapabilitiesCatalog(): Promise<CapabilitiesCatalog> {
  const res = await fetch(`${API_BASE}/capabilities/catalog`);
  return jsonOrThrow<CapabilitiesCatalog>(res, `Failed to fetch capabilities catalog: ${res.status}`);
}

export async function fetchRoutingPolicies(): Promise<{ routing_policies: RoutingPolicy[] }> {
  const res = await fetch(`${API_BASE}/capabilities/routing-policies`);
  return jsonOrThrow<{ routing_policies: RoutingPolicy[] }>(res, `Failed to fetch routing policies: ${res.status}`);
}

export async function updateRoutingPolicy(
  roleId: string,
  policy: RoutingPolicy
): Promise<{ status: string; routing_policy: RoutingPolicy }> {
  const res = await fetch(`${API_BASE}/capabilities/routing-policies/${encodeURIComponent(roleId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(policy),
  });
  return jsonOrThrow<{ status: string; routing_policy: RoutingPolicy }>(
    res,
    `Routing policy update failed: ${res.status}`
  );
}

export async function fetchLaunchPresets(): Promise<{ launch_presets: LaunchPreset[] }> {
  const res = await fetch(`${API_BASE}/capabilities/launch-presets`);
  return jsonOrThrow<{ launch_presets: LaunchPreset[] }>(res, `Failed to fetch launch presets: ${res.status}`);
}

export async function fetchConnectors(): Promise<{ connectors: MCPConnector[] }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors`);
  return jsonOrThrow<{ connectors: MCPConnector[] }>(res, `Failed to fetch connectors: ${res.status}`);
}

export async function createConnector(
  connector: Omit<MCPConnector, "built_in" | "validation_status" | "last_validation_result">
): Promise<{ status: string; connector: MCPConnector }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(connector),
  });
  return jsonOrThrow<{ status: string; connector: MCPConnector }>(res, `Connector creation failed: ${res.status}`);
}

export async function updateConnector(
  connectorId: string,
  connector: Omit<MCPConnector, "built_in" | "validation_status" | "last_validation_result">
): Promise<{ status: string; connector: MCPConnector }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors/${encodeURIComponent(connectorId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(connector),
  });
  return jsonOrThrow<{ status: string; connector: MCPConnector }>(res, `Connector update failed: ${res.status}`);
}

export async function deleteConnector(connectorId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors/${encodeURIComponent(connectorId)}`, {
    method: "DELETE",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Connector delete failed: ${res.status}`);
}

export async function validateConnectorDraft(
  connector: Omit<MCPConnector, "built_in" | "validation_status" | "last_validation_result">
): Promise<{ status: string; result: ConnectorValidationResult }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(connector),
  });
  return jsonOrThrow<{ status: string; result: ConnectorValidationResult }>(res, `Connector validation failed: ${res.status}`);
}

export async function validateSavedConnector(
  connectorId: string
): Promise<{ status: string; result: ConnectorValidationResult; connector: MCPConnector }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors/${encodeURIComponent(connectorId)}/validate`, {
    method: "POST",
  });
  return jsonOrThrow<{ status: string; result: ConnectorValidationResult; connector: MCPConnector }>(
    res,
    `Saved connector validation failed: ${res.status}`
  );
}

export async function fetchSkillPacks(): Promise<{ skill_packs: SkillPack[] }> {
  const res = await fetch(`${API_BASE}/capabilities/skill-packs`);
  return jsonOrThrow<{ skill_packs: SkillPack[] }>(res, `Failed to fetch skill packs: ${res.status}`);
}

export async function createSkillPack(
  skillPack: Omit<SkillPack, "built_in">
): Promise<{ status: string; skill_pack: SkillPack }> {
  const res = await fetch(`${API_BASE}/capabilities/skill-packs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(skillPack),
  });
  return jsonOrThrow<{ status: string; skill_pack: SkillPack }>(res, `Skill pack creation failed: ${res.status}`);
}

export async function updateSkillPack(
  skillPackId: string,
  skillPack: Omit<SkillPack, "built_in">
): Promise<{ status: string; skill_pack: SkillPack }> {
  const res = await fetch(`${API_BASE}/capabilities/skill-packs/${encodeURIComponent(skillPackId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(skillPack),
  });
  return jsonOrThrow<{ status: string; skill_pack: SkillPack }>(res, `Skill pack update failed: ${res.status}`);
}

export async function deleteSkillPack(skillPackId: string): Promise<{ status: string; message: string }> {
  const res = await fetch(`${API_BASE}/capabilities/skill-packs/${encodeURIComponent(skillPackId)}`, {
    method: "DELETE",
  });
  return jsonOrThrow<{ status: string; message: string }>(res, `Skill pack delete failed: ${res.status}`);
}
