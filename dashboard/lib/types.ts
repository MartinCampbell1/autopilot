export type StoryStatus = "open" | "in_progress" | "done" | "stuck" | "skipped";
export type ProjectRunStatus = "idle" | "running" | "paused" | "completed" | "failed";

export interface Story {
  id: number;
  title: string;
  description: string;
  position: number;
  phase_id?: string | null;
  phase_title?: string | null;
  phase_goal?: string | null;
  tags?: string[];
  role?: string | null;
  skill_packs?: string[];
  connectors?: string[];
  acceptance_criteria?: string[];
  status: StoryStatus;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  iteration?: number | null;
  agent?: string | null;
  critic?: string | null;
  last_error?: string | null;
}

export interface TimelineEvent {
  event: string;
  project_id: string;
  story_id?: number | null;
  status: string;
  message: string;
  timestamp: string;
  iteration?: number;
  worker?: string;
  critic?: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  path: string;
  priority: "high" | "normal" | "low";
  archived: boolean;
  status: ProjectRunStatus;
  paused: boolean;
  stories_done: number;
  stories_total: number;
  current_story_id?: number | null;
  current_story_title?: string | null;
  last_activity_at?: string | null;
  last_message?: string;
  pid?: number | null;
}

export interface ProjectDetail extends ProjectSummary {
  description: string;
  phases?: Array<{
    id: string;
    title: string;
    goal?: string;
  }>;
  stories: Story[];
  timeline: TimelineEvent[];
  guardrails: string;
  log_tail: string;
  log_path: string;
  last_error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  active_worker?: string | null;
  active_critic?: string | null;
  current_iteration?: number;
}

export interface AccountHealth {
  total: number;
  available: number;
  on_cooldown: number;
}

export interface ProviderAccount {
  name: string;
  available: boolean;
  requests_made: number;
  cooldown_remaining_sec: number;
}

export type AccountsByProvider = Record<string, ProviderAccount[]>;

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
  phases?: Array<{
    id: string;
    title: string;
    goal?: string;
  }>;
  stories: Array<{
    id: number;
    phase_id?: string;
    phase_title?: string;
    title: string;
    description: string;
    acceptance_criteria?: string[];
    tags?: string[];
    role?: string;
    skill_packs?: string[];
    connectors?: string[];
    status?: string;
  }>;
}

export interface MCPConnector {
  id: string;
  name: string;
  connector_type: string;
  description: string;
  transport: string;
  tags: string[];
  providers: string[];
  risk_level: string;
  scopes: string[];
  enabled: boolean;
  built_in: boolean;
  config: Record<string, unknown>;
  validation_status: string;
}

export interface SkillPack {
  id: string;
  name: string;
  description: string;
  prompt: string;
  tags: string[];
  default_roles: string[];
  preferred_connectors: string[];
  enabled: boolean;
  built_in: boolean;
}

export interface CreateProjectResult {
  status: string;
  project_id: string;
  project_name: string;
  project_path: string;
  prd_path: string;
  launched: boolean;
  message: string;
}

export interface LaunchResult {
  status: string;
  project_id: string;
  launched: boolean;
  message: string;
  log_path: string;
}
