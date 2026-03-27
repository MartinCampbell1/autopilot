export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8420/api";

async function parseError(res: Response, fallback: string): Promise<never> {
  let detail = fallback;

  try {
    const data = await res.json();
    if (typeof data?.detail === "string" && data.detail.trim()) {
      detail = data.detail;
    }
  } catch {
    // Ignore JSON parse failures and keep the fallback message.
  }

  throw new Error(detail);
}

export async function fetchProjects() {
  const res = await fetch(`${API_BASE}/projects/`);
  if (!res.ok) return parseError(res, `Failed to fetch projects: ${res.status}`);
  return res.json();
}

export async function fetchProject(name: string) {
  const res = await fetch(`${API_BASE}/projects/${encodeURIComponent(name)}`);
  if (!res.ok) return parseError(res, `Failed to fetch project: ${res.status}`);
  return res.json();
}

export async function fetchAccountsHealth() {
  const res = await fetch(`${API_BASE}/accounts/health`);
  if (!res.ok) return parseError(res, `Failed to fetch health: ${res.status}`);
  return res.json();
}

export async function storyAction(
  projectName: string,
  storyId: number,
  action: string,
  payload = ""
) {
  const res = await fetch(
    `${API_BASE}/projects/${encodeURIComponent(projectName)}/stories/${storyId}/action`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, payload }),
    }
  );
  if (!res.ok) return parseError(res, `Action failed: ${res.status}`);
  return res.json();
}

export async function sendIntakeMessage(message: string, sessionId?: string | null) {
  const res = await fetch(`${API_BASE}/intake/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId }),
  });
  if (!res.ok) return parseError(res, `Intake failed: ${res.status}`);
  return res.json();
}

export async function fetchIntakeSessions() {
  const res = await fetch(`${API_BASE}/intake/sessions`);
  if (!res.ok) return parseError(res, `Failed to fetch sessions: ${res.status}`);
  return res.json();
}
