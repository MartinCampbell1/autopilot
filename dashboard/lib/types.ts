export type StoryStatus = "open" | "in_progress" | "done" | "stuck" | "skipped" | "merge_blocked";
export type ProjectRunStatus = "idle" | "running" | "paused" | "completed" | "failed";

export interface LaunchProfile {
  preset: "fast" | "team" | "parallel" | string;
  story_execution_mode: "solo" | "team" | string;
  project_concurrency_mode: "sequential" | "parallel" | string;
  max_parallel_stories: number;
}

export interface LaunchPreset {
  id: string;
  label: string;
  description: string;
  launch_profile: LaunchProfile;
}

export interface RoutingPolicy {
  role_id: string;
  preferred_skill_packs: string[];
  required_connectors: string[];
  preferred_connectors: string[];
  forbidden_connectors: string[];
}

export interface ConnectorActivation {
  id: string;
  name: string;
  connector_type: string;
  provider: string;
  required: boolean;
  status: "active" | "disabled" | "validation_failed" | "unsupported_for_provider" | string;
  reason: string;
  config: Record<string, unknown>;
}

export interface TeamMemberAssignment {
  member_id: string;
  label: string;
  execution_role: string;
  role_id: string;
  provider: string;
  skill_packs: string[];
  planned_connectors: string[];
  active_connectors: ConnectorActivation[];
  specialist: boolean;
}

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
  required_connectors?: string[];
  preferred_connectors?: string[];
  forbidden_connectors?: string[];
  acceptance_criteria?: string[];
  status: StoryStatus;
  started_at?: string | null;
  completed_at?: string | null;
  updated_at?: string | null;
  iteration?: number | null;
  agent?: string | null;
  critic?: string | null;
  last_error?: string | null;
  team_mode?: "solo" | "team" | string;
  team_members?: TeamMemberAssignment[];
  connector_activation?: ConnectorActivation[];
  activation_errors?: string[];
  worktree_path?: string | null;
  branch_name?: string | null;
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
  launch_profile?: LaunchProfile;
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
  launch_profile: LaunchProfile;
  team_assignments: Record<string, TeamMemberAssignment[]>;
  active_connectors: Record<string, ConnectorActivation[]>;
  activation_errors: Record<string, string[]>;
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
    required_connectors?: string[];
    preferred_connectors?: string[];
    forbidden_connectors?: string[];
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
  last_validation_result?: ConnectorValidationResult;
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

export interface RoleTemplate {
  id: string;
  name: string;
  description: string;
  default_skill_packs: string[];
  optional_skill_tags: string[];
  default_connectors: string[];
  optional_connector_tags: string[];
}

export interface ConnectorFieldSchema {
  key: string;
  label: string;
  field_type: string;
  required: boolean;
  placeholder: string;
  help_text: string;
  options: string[];
  sensitive: boolean;
}

export interface ConnectorTypeSchema {
  id: string;
  name: string;
  description: string;
  transport_options: string[];
  default_transport: string;
  suggested_tags: string[];
  suggested_scopes: string[];
  config_fields: ConnectorFieldSchema[];
}

export interface ConnectorValidationResult {
  ok: boolean;
  status: string;
  summary: string;
  log: string;
  checked_fields: string[];
}

export interface CapabilitiesCatalog {
  connectors: MCPConnector[];
  skill_packs: SkillPack[];
  roles: RoleTemplate[];
  connector_types: ConnectorTypeSchema[];
  routing_policies: RoutingPolicy[];
  launch_presets: LaunchPreset[];
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
  launch_profile?: LaunchProfile;
}
