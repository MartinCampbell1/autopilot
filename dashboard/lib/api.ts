import type {
  CapabilitiesCatalog,
  AccountHealth,
  AccountsByProvider,
  CreateProjectResult,
  IntakeSession,
  LaunchResult,
  PRD,
  ProjectDetail,
  ProjectSummary,
  MCPConnector,
  SkillPack,
} from "@/lib/types";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

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

export async function launchProject(projectId: string): Promise<LaunchResult> {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(projectId)}/launch`, {
    method: "POST",
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

export async function fetchConnectors(): Promise<{ connectors: MCPConnector[] }> {
  const res = await fetch(`${API_BASE}/capabilities/connectors`);
  return jsonOrThrow<{ connectors: MCPConnector[] }>(res, `Failed to fetch connectors: ${res.status}`);
}

export async function createConnector(
  connector: Omit<MCPConnector, "built_in" | "validation_status">
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
  connector: Omit<MCPConnector, "built_in" | "validation_status">
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
