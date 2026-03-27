export type StoryStatus = "open" | "in_progress" | "done" | "stuck" | "skipped";

export interface Story {
  id: number;
  title: string;
  description: string;
  status: StoryStatus;
  agent?: string;
  iteration?: number;
  elapsed_min?: number;
}

export interface Project {
  name: string;
  path: string;
  priority: "high" | "normal" | "low";
  stories: Story[];
  stories_done: number;
  stories_total: number;
  progress?: string;
  guardrails?: string;
}

export interface AccountHealth {
  total: number;
  available: number;
  on_cooldown: number;
}

export interface IntakeMessage {
  role: "user" | "assistant";
  content: string;
}

export interface IntakeSession {
  id: string;
  messages: number;
  prd_ready: boolean;
}

export interface PRD {
  title: string;
  description: string;
  stories: Array<{
    id: number;
    title: string;
    description: string;
    status: string;
  }>;
}
