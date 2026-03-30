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

export interface StoryOwnership {
  role: string;
  owner: string;
  acquired_at: string;
}

export interface StoryCheckout {
  mode: string;
  path: string;
  branch_name?: string | null;
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
  ownership?: StoryOwnership | null;
  checkout?: StoryCheckout | null;
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
  budget_policy?: RuntimeBudgetPolicy;
  budget_usage?: RuntimeBudgetUsage;
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

export interface RuntimeBudgetPolicy {
  project_max_worker_iterations: number;
  project_max_critic_reviews: number;
  agent_max_worker_iterations: number;
  agent_max_critic_reviews: number;
  auto_pause_on_exhaustion: boolean;
}

export interface RuntimeBudgetUsage {
  project: {
    worker_iterations: number;
    critic_reviews: number;
  };
  agents: Record<
    string,
    {
      worker_iterations: number;
      critic_reviews: number;
    }
  >;
  last_exhaustion_reason?: string | null;
  auto_paused_at?: string | null;
}

export interface RuntimeLease {
  story_id: number;
  role: string;
  owner: string;
  runtime_pid?: number | null;
  status: string;
  checkout_path?: string | null;
  branch_name?: string | null;
  acquired_at: string;
  updated_at: string;
}

export interface CheckoutHealth {
  status: string;
  lease_status?: string;
  mode: string;
  path?: string | null;
  branch_name?: string | null;
  issues: string[];
}

export interface StoryRuntimeControl {
  story_id: number;
  story_status: StoryStatus | string;
  ownership?: StoryOwnership | null;
  lease?: RuntimeLease | null;
  checkout?: StoryCheckout | null;
  health: CheckoutHealth;
}

export interface OrphanedWorktree {
  story_id?: number | null;
  path: string;
  status: string;
  issues: string[];
}

export interface ProjectRuntimeControl {
  project_id: string;
  leases: RuntimeLease[];
  stories: StoryRuntimeControl[];
  orphaned_worktrees: OrphanedWorktree[];
}

export type ExecutionPlaneCountMap = Record<string, number>;

export interface OrchestratorSessionSummary {
  totals: {
    sessions: number;
    open: number;
    completed: number;
    archived: number;
  };
  by_status: ExecutionPlaneCountMap;
  by_orchestrator: ExecutionPlaneCountMap;
  by_actor: ExecutionPlaneCountMap;
  latest_session_at?: string | null;
}

export interface OrchestratorSessionRecord {
  id: string;
  orchestrator: string;
  actor: string;
  title: string;
  initiative_id: string;
  project_ids: string[];
  status: string;
  reason: string;
  context: Record<string, unknown>;
  linked_run_ids: string[];
  linked_control_pass_ids: string[];
  linked_approval_ids: string[];
  linked_issue_ids: string[];
  linked_runtime_agent_ids: string[];
  created_at: string;
  updated_at: string;
  closed_at?: string | null;
  closed_by: string;
  close_note: string;
}

export interface OrchestratorControlPassSummary {
  totals: {
    control_passes: number;
    ok: number;
    partial: number;
    error: number;
    noop: number;
    customized: number;
    sessions: number;
    projects: number;
    applied_steps: number;
    error_steps: number;
  };
  by_status: ExecutionPlaneCountMap;
  by_profile: ExecutionPlaneCountMap;
  by_actor: ExecutionPlaneCountMap;
  by_orchestrator: ExecutionPlaneCountMap;
  by_final_state: ExecutionPlaneCountMap;
  by_stopped_reason: ExecutionPlaneCountMap;
  by_session_status_before: ExecutionPlaneCountMap;
  by_session_status_after: ExecutionPlaneCountMap;
  latest_control_pass_at?: string | null;
}

export interface OrchestratorControlPassRecord {
  id: string;
  orchestrator_session_id: string;
  actor: string;
  reason: string;
  profile: string;
  customized: boolean;
  recommendation_kinds: string[];
  control_before: Record<string, unknown>;
  control_after: Record<string, unknown>;
  applied: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
  status: string;
  project_ids: string[];
  initiative_id: string;
  orchestrator: string;
  session_status_before: string;
  session_status_after: string;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ExecutionPlaneEvent {
  event: string;
  status: string;
  message: string;
  timestamp: string;
  project_id?: string | null;
  story_id?: number | null;
  orchestrator_session_id?: string | null;
  [key: string]: unknown;
}

export interface OrchestratorSessionActionSummary {
  totals: {
    actions: number;
    suggested_commands: number;
    recommendations: number;
    approval_required: number;
    projects: number;
  };
  by_action_type: ExecutionPlaneCountMap;
  by_priority: ExecutionPlaneCountMap;
  by_project: ExecutionPlaneCountMap;
  by_command: ExecutionPlaneCountMap;
  by_recommendation_kind: ExecutionPlaneCountMap;
}

export interface OrchestratorSessionControlRecommendation {
  kind: string;
  priority: string;
  title: string;
  reason: string;
  counts: Record<string, number>;
  operation: Record<string, unknown>;
}

export interface OrchestratorSessionControl {
  state: string;
  counts: {
    pending_approvals: number;
    open_issues: number;
    safe_actions: number;
    approval_required_actions: number;
    recommendation_actions: number;
  };
  action_summary: OrchestratorSessionActionSummary;
  recommendations: OrchestratorSessionControlRecommendation[];
}

export interface ExecutionApprovalRecord {
  id: string;
  project_id: string;
  project_name: string;
  action: string;
  payload: Record<string, unknown>;
  status: string;
  requested_by: string;
  reason: string;
  initiative_id: string;
  orchestrator: string;
  orchestration_run_id: string;
  issue_id: string;
  runtime_agent_ids: string[];
  policy_reasons: string[];
  created_at: string;
  updated_at: string;
  decided_at?: string | null;
  decided_by?: string | null;
  decision_note: string;
  applied_at?: string | null;
  applied_by?: string | null;
}

export interface ExecutionIssueRecord {
  id: string;
  project_id: string;
  project_name: string;
  title: string;
  description: string;
  root_cause: string;
  category: string;
  severity: string;
  status: string;
  source_event: string;
  related_command: string;
  story_id?: number | null;
  runtime_agent_id: string;
  runtime_agent_ids: string[];
  approval_id: string;
  dedupe_key: string;
  initiative_id: string;
  orchestrator: string;
  orchestration_run_id: string;
  context: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  resolved_by?: string | null;
  resolution_note: string;
}

export interface OrchestratorSessionDetail extends OrchestratorSessionRecord {
  runs: Array<Record<string, unknown>>;
  control_passes: OrchestratorControlPassRecord[];
  approvals: ExecutionApprovalRecord[];
  issues: ExecutionIssueRecord[];
  events: ExecutionPlaneEvent[];
  control: OrchestratorSessionControl;
  summary: {
    run_count: number;
    control_pass_count: number;
    approval_count: number;
    pending_approval_count: number;
    issue_count: number;
    open_issue_count: number;
    event_count: number;
    event_limit: number;
    latest_event_at?: string | null;
    by_event: ExecutionPlaneCountMap;
    by_event_status: ExecutionPlaneCountMap;
  };
}

export interface OrchestratorSessionControlProfile {
  name: string;
  description: string;
  recommendation_kinds: string[];
  repeatable_kinds: string[];
  default: boolean;
}

export interface OrchestratorSessionRecommendationApplyResult {
  status: string;
  session_id: string;
  recommendation: OrchestratorSessionControlRecommendation;
  operation: Record<string, unknown>;
  result: Record<string, unknown>;
  control_before: OrchestratorSessionControl;
  control: OrchestratorSessionControl;
}

export interface OrchestratorSessionControlPlanApplyResult {
  status: string;
  session_id: string;
  profile: {
    name: string;
    description: string;
    recommendation_kinds: string[];
    repeatable_kinds: string[];
    customized: boolean;
  };
  control_pass: OrchestratorControlPassRecord;
  control_before: OrchestratorSessionControl;
  control: OrchestratorSessionControl;
  applied: Array<Record<string, unknown>>;
  errors: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
  skipped_recommendation_kinds: string[];
}

export interface ApprovalDecisionResult {
  status: string;
  approval: ExecutionApprovalRecord;
}

export interface ApprovalApplyResult {
  status: string;
  approval: ExecutionApprovalRecord;
  command_result: Record<string, unknown>;
}

export interface IssueResolutionResult {
  status: string;
  issue: ExecutionIssueRecord;
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
