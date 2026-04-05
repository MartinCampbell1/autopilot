export type StoryStatus = "open" | "in_progress" | "done" | "stuck" | "skipped" | "merge_blocked";
export type ProjectRunStatus = "idle" | "running" | "paused" | "completed" | "failed";

export interface LaunchProfile {
  preset: "fast" | "team" | "parallel" | string;
  provider?: string;
  provider_config_id?: string;
  runtime_profile_id?: string;
  story_execution_mode: "solo" | "team" | string;
  project_concurrency_mode: "sequential" | "parallel" | string;
  max_parallel_stories: number;
  story_pipeline?: string[];
  review_phases?: string[];
}

export interface ProviderConfig {
  id: string;
  family: string;
  mode: string;
  transport: string;
  endpoint?: string | null;
  command?: string[];
  auth_strategy: string;
  capabilities: string[];
}

export interface RuntimeProfile {
  id: string;
  sandbox_mode: string;
  network_policy: string;
  filesystem_policy: string;
  default_tools: string[];
}

export interface TaskSource {
  source_kind: string;
  external_id: string;
  repo: string;
  branch_policy: string;
  brief_ref: string;
}

export interface ProjectHandoffSummary {
  story_id: number;
  story_title: string;
  head_branch: string;
  number?: number | null;
  url: string;
  state: string;
  ci_status: string;
  review_status: string;
  handoff_status: string;
  merge_state: string;
  updated_at?: string | null;
}

export interface ProjectHandoffArtifact {
  artifact_id: string;
  artifact_type: string;
  project_id: string;
  project_name: string;
  story: {
    id: number;
    title: string;
  };
  task_source: TaskSource;
  brief: {
    title: string;
    relpath: string;
    path: string;
    present: boolean;
  };
  ref: string;
  ref_label: string;
  relpath: string;
  path: string;
  present: boolean;
  generated_at?: string | null;
  handoff: {
    provider: string;
    head_branch: string;
    base_branch: string;
    number?: number | null;
    url: string;
    title: string;
    state: string;
    ci_status: string;
    review_status: string;
    handoff_status: string;
    merge_state: string;
    updated_at?: string | null;
  };
}

export interface ProjectDeliveryLoop {
  source: TaskSource;
  brief: {
    title: string;
    relpath: string;
    path: string;
    present: boolean;
  };
  run: {
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    current_story_id?: number | null;
    current_story_title?: string | null;
    last_event?: {
      event?: string | null;
      status?: string | null;
      message?: string | null;
      timestamp?: string | null;
    } | null;
  };
  handoff?: ProjectHandoffSummary | null;
  artifact?: ProjectHandoffArtifact | null;
}

export interface ProjectDeliveryStatus {
  stage: string;
  status: string;
  headline: string;
  detail: string;
  next_step: string;
  handoff_ref: string;
  artifact_present: boolean;
  brief_present: boolean;
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

export interface ToolContract {
  tool_id: string;
  connector_id: string;
  name: string;
  kind: string;
  transport: string;
  scope: string;
  approval_policy: string;
  provider_compatibility: string[];
  description: string;
  enabled: boolean;
  built_in: boolean;
  validation_status: string;
}

export interface ToolActivation {
  tool_id: string;
  connector_id: string;
  name: string;
  kind: string;
  transport: string;
  scope: string;
  approval_policy: string;
  provider_compatibility: string[];
  provider: string;
  required: boolean;
  status: string;
  reason: string;
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

export interface StoryGitHubPullRequest {
  provider: string;
  head_branch: string;
  base_branch: string;
  number?: number | null;
  url: string;
  title: string;
  state: string;
  ci_status: string;
  review_status: string;
  handoff_status: string;
  merge_state: string;
  draft: boolean;
  author: string;
  labels: string[];
  comment_count: number;
  review_comment_count: number;
  last_commit_sha: string;
  checks_url: string;
  latest_event: string;
  opened_at?: string | null;
  merged_at?: string | null;
  closed_at?: string | null;
  updated_at?: string | null;
}

export interface DiscoveryMarker {
  id: string;
  story_id?: number | null;
  source: string;
  kind: string;
  title: string;
  detail: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
  metadata?: Record<string, unknown>;
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
  story_pipeline?: string[];
  review_phases?: string[];
  discoveries?: DiscoveryMarker[];
  connector_activation?: ConnectorActivation[];
  tools?: ToolContract[];
  active_tools?: ToolActivation[];
  activation_errors?: string[];
  worktree_path?: string | null;
  branch_name?: string | null;
  ownership?: StoryOwnership | null;
  checkout?: StoryCheckout | null;
  github_pr?: StoryGitHubPullRequest | null;
  handoff_artifact?: ProjectHandoffArtifact | null;
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
  task_source?: TaskSource;
  handoff?: ProjectHandoffSummary | null;
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
  runtime_session_id?: string;
  runtime_control_available?: boolean;
  tool_permission_runtime_count?: number;
  pending_tool_permission_runtime_count?: number;
  launch_profile?: LaunchProfile;
  provider_config?: ProviderConfig;
  runtime_profile?: RuntimeProfile;
  task_source?: TaskSource;
  latest_handoff?: ProjectHandoffSummary | null;
  delivery_loop?: ProjectDeliveryLoop;
  delivery_status?: ProjectDeliveryStatus;
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
  active_tools: Record<string, ToolActivation[]>;
  activation_errors: Record<string, string[]>;
  cost_usage?: Record<string, unknown>;
  trace_summary?: Record<string, unknown>;
  trace_path?: string;
  monitoring?: ProjectMonitoringSnapshot;
  audit?: ProjectAuditChainSummary;
  bootstrap?: ProjectBootstrapStatus;
  runtime_diagnostics?: ProjectRuntimeDiagnosticsReport;
  company?: ProjectCompanyShell;
}

export interface ProjectAuditVerificationSummary {
  verified?: boolean;
  latest_hash?: string;
  entry_count?: number;
  errors?: Array<Record<string, unknown>>;
}

export interface ProjectAuditChainSummary {
  schema_version?: number;
  chain_kind?: string;
  package_chain_kind?: string;
  project_id?: string;
  run_id?: string;
  story_id?: number | null;
  entry_count?: number;
  source_entry_count?: number;
  verification?: ProjectAuditVerificationSummary;
  source_verification?: ProjectAuditVerificationSummary;
}

export interface ProjectBootstrapVerificationStatus {
  configured?: boolean;
  artifact_relpath?: string;
  artifact_path?: string;
  artifact_exists?: boolean;
  updated_at?: string;
  gate_count?: number;
  check_count?: number;
}

export interface ProjectBootstrapGithubStatus {
  configured?: boolean;
  workflow_relpath?: string;
  workflow_path?: string;
  workflow_exists?: boolean;
  updated_at?: string;
  github_repo?: string;
  current_branch?: string;
  default_branch?: string;
  compare_url?: string;
  gh_authenticated?: boolean;
}

export interface ProjectBootstrapStatus {
  verification?: ProjectBootstrapVerificationStatus;
  github?: ProjectBootstrapGithubStatus;
}

export interface ProjectRuntimeDiagnostic {
  code: string;
  severity: string;
  scope: string;
  message: string;
  fix: string;
  metadata?: Record<string, unknown>;
}

export interface ProjectRuntimeDiagnosticsReport {
  diagnostics: ProjectRuntimeDiagnostic[];
  summary?: {
    error_count?: number;
    warning_count?: number;
    info_count?: number;
    [key: string]: unknown;
  };
}

export interface ProjectCompanyGoal {
  id: string;
  title: string;
  goal?: string;
  status: string;
  progress_pct?: number;
  stories_total?: number;
  stories_done?: number;
  stories_active?: number;
  stories_blocked?: number;
  stories_queued?: number;
  current_story_id?: number | null;
  current_story_title?: string | null;
}

export interface ProjectCompanyRoutineAction {
  action_id: string;
  label: string;
  project_id?: string;
  url?: string;
  command?: string;
}

export interface ProjectCompanyRoutine {
  id: string;
  title: string;
  cadence: string;
  status: string;
  description: string;
  guardrail: string;
  blocked_by?: string[];
  recommended_action?: ProjectCompanyRoutineAction;
}

export interface ProjectCompanyChannel {
  id: string;
  name: string;
  kind: string;
  enabled: boolean;
  ready: boolean;
  status: string;
  target?: string;
  events?: string[];
  capabilities?: string[];
  approval_capable?: boolean;
  wall_enforced?: boolean;
  message_count?: number;
  note?: string;
}

export interface ProjectCompanySecret {
  id: string;
  channel_name: string;
  kind: string;
  ready: boolean;
  status: string;
  required_keys: string[];
  resolved_keys: string[];
  missing_keys: string[];
}

export interface ProjectCompanyLiveEvent {
  id: string;
  kind: string;
  timestamp?: string;
  headline: string;
  detail: string;
  source: string;
  story_id?: number | null;
  session_id?: string;
}

export interface ProjectCompanyShell {
  status?: {
    always_on_ready?: boolean;
    runtime_wall_enforced?: boolean;
    runtime_control_available?: boolean;
    goal_count?: number;
    active_routine_count?: number;
    ready_channel_count?: number;
    missing_secret_count?: number;
    live_event_count?: number;
  };
  goals?: {
    items: ProjectCompanyGoal[];
    summary?: Record<string, unknown>;
  };
  routines?: {
    items: ProjectCompanyRoutine[];
    summary?: Record<string, unknown>;
  };
  channels?: {
    items: ProjectCompanyChannel[];
    summary?: Record<string, unknown>;
  };
  secrets?: {
    items: ProjectCompanySecret[];
    summary?: Record<string, unknown>;
  };
  live_events?: {
    items: ProjectCompanyLiveEvent[];
    summary?: Record<string, unknown>;
  };
}

export interface ProjectMonitoringCostBucket {
  invocations?: number;
  tracked_invocations?: number;
  priced_invocations?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached_tokens?: number;
  total_tokens?: number;
  estimated_cost_usd?: number;
  started_at?: string | null;
  story_id?: string | number;
  agent_label?: string;
}

export interface ProjectMonitoringRunSummary {
  run_id: string;
  run_sequence?: number;
  started_at?: string | null;
  finished_at?: string | null;
  last_timestamp?: string | null;
  status: string;
  entry_count?: number;
  iteration_count?: number;
  failure_count?: number;
  critic_rejection_count?: number;
  quality_regression_count?: number;
  story_ids?: Array<number | string>;
  judge_outcomes?: Record<string, number>;
  cost?: ProjectMonitoringCostBucket;
}

export interface ProjectMonitoringSnapshot {
  cost: {
    project: ProjectMonitoringCostBucket;
    run: ProjectMonitoringCostBucket;
    pricing_source?: string;
    top_stories: ProjectMonitoringCostBucket[];
    top_agents: ProjectMonitoringCostBucket[];
  };
  trace: {
    runs: ProjectMonitoringRunSummary[];
    recent_failures: Array<Record<string, unknown>>;
    comparison: Record<string, unknown>;
  };
  feedback: {
    count: number;
    blocking_count: number;
    approved_count: number;
    by_kind: Record<string, number>;
    judge_outcomes: Record<string, number>;
    phases: Record<string, number>;
    recent: Array<Record<string, unknown>>;
  };
  benchmarks: {
    count: number;
    latest?: ProjectMonitoringRunSummary | null;
    previous?: ProjectMonitoringRunSummary | null;
    comparison: Record<string, unknown>;
    history: ProjectMonitoringRunSummary[];
  };
  latest_run?: ProjectMonitoringRunSummary | null;
  regressions: {
    cost: boolean;
    reliability: boolean;
  };
}

export interface RuntimeBudgetPolicy {
  project_max_worker_iterations: number;
  project_max_critic_reviews: number;
  run_max_worker_iterations: number;
  run_max_critic_reviews: number;
  story_max_worker_iterations: number;
  story_max_critic_reviews: number;
  agent_max_worker_iterations: number;
  agent_max_critic_reviews: number;
  run_max_runtime_seconds: number;
  story_max_runtime_seconds: number;
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
  runtime_session_id?: string;
  runtime_control_available?: boolean;
  company?: ProjectCompanyShell;
}

export interface ExecutionPlaneProjectRuntimeAgentRecord {
  agent_id: string;
  role: string;
  label: string;
  provider?: string | null;
  profile_name?: string | null;
  member_id?: string | null;
  role_id?: string | null;
  specialist?: boolean;
  status: string;
  pipeline_stage?: string | null;
  pipeline_order?: number | null;
  pipeline_status?: string | null;
  story_id?: number | null;
  story_title?: string | null;
  story_status?: string | null;
  ownership?: Record<string, unknown> | null;
  checkout?: Record<string, unknown> | null;
  skill_packs?: string[];
  planned_connectors?: string[];
  active_connectors?: Array<Record<string, unknown>>;
  open_issue_count: number;
  pending_approval_count: number;
  tool_permission_runtime_count?: number;
  pending_tool_permission_runtime_count?: number;
  active_async_task_count?: number;
  pending_async_run_count?: number;
  budget?: ExecutionRuntimeAgentBudgetSummary;
  attention?: ExecutionRuntimeAgentAttentionSummary;
  recommendations?: Array<Record<string, unknown>>;
  suggested_commands?: Array<Record<string, unknown>>;
}

export interface ExecutionPlaneProjectDetail {
  project_id: string;
  runtime_agents: ExecutionPlaneProjectRuntimeAgentRecord[];
  monitoring?: ProjectMonitoringSnapshot;
  trace?: {
    summary?: Record<string, unknown>;
    path?: string;
    monitoring?: Record<string, unknown>;
  };
}

export interface ToolPermissionRuntimeRecord {
  id: string;
  key: string;
  project_id: string;
  status: string;
  claim_id: string;
  resolution_id: string;
  approval_id: string;
  issue_id: string;
  permission_sync_key: string;
  runtime_agent_ids: string[];
  winner_source: string;
  outcome: string;
  message: string;
  payload: Record<string, unknown>;
  metadata: Record<string, unknown>;
  settlement_attempts: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  kind: string;
  pending_stage: string;
  tool_name: string;
  tool_use_id: string;
  resolved_behavior: string;
  resolved_by: string;
  resolved_source: string;
}

export interface ToolPermissionRuntimeListResponse {
  summary: {
    count: number;
    pending_count: number;
  };
  runtimes: ToolPermissionRuntimeRecord[];
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
  runtime_state: "idle" | "running" | "requires_action" | string;
  pending_action?: OrchestratorPendingAction | null;
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

export interface OrchestratorPendingActionOperation {
  type: string;
  session_id: string;
  endpoint: string;
  mode: string;
  payload: Record<string, unknown>;
}

export interface OrchestratorPendingAction {
  kind: string;
  priority: string;
  title: string;
  reason: string;
  session_id: string;
  counts: Record<string, number>;
  operation?: OrchestratorPendingActionOperation | null;
}

export interface OrchestratorSessionControl {
  state: string;
  session_state: "idle" | "running" | "requires_action" | string;
  pending_action?: OrchestratorPendingAction | null;
  counts: {
    pending_approvals: number;
    pending_tool_permission_runtimes?: number;
    open_issues: number;
    active_async_tasks: number;
    pending_async_runs?: number;
    safe_actions: number;
    approval_required_actions: number;
    recommendation_actions: number;
  };
  action_summary: OrchestratorSessionActionSummary;
  recommendations: OrchestratorSessionControlRecommendation[];
}

export interface ControlRequestMessage {
  type: "control_request";
  request_id: string;
  request: {
    subtype: string;
    [key: string]: unknown;
  };
  session_id?: string | null;
}

export interface ProjectRuntimeControlRequestResult {
  status: string;
  project_id: string;
  runtime_session_id: string;
  request: ControlRequestMessage;
}

export interface ControlSuccessResponsePayload {
  subtype: "success";
  request_id: string;
  response: Record<string, unknown>;
}

export interface ControlErrorResponsePayload {
  subtype: "error";
  request_id: string;
  error: string;
}

export type ControlResponsePayload = ControlSuccessResponsePayload | ControlErrorResponsePayload;

export interface ControlResponseMessage {
  type: "control_response";
  response: ControlResponsePayload;
  session_id?: string | null;
}

export type ProjectRuntimeControlExchangePhase =
  | "queued"
  | "acknowledged"
  | "success"
  | "error"
  | "stale";

export interface ProjectRuntimeControlExchangeRecord {
  requestId: string;
  projectId: string;
  runtimeSessionId: string;
  subtype: string;
  phase: ProjectRuntimeControlExchangePhase;
  source: "local" | "external";
  queuedAt: string;
  updatedAt: string;
  request?: ControlRequestMessage | null;
  response?: ControlResponsePayload | null;
  errorMessage?: string | null;
}

export interface StructuredEventEnvelope {
  type: "event";
  event: string;
  event_id: string;
  sequence: number;
  data: Record<string, unknown>;
  source: string;
  session_id?: string | null;
  timestamp?: string | null;
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

export interface ExecutionRuntimeAgentTaskResumeContract {
  task_id: string;
  project_id: string;
  command: string;
  status: string;
  orchestrator_session_id: string;
  agent_action_run_id: string;
  approval_id: string;
  issue_id: string;
  runtime_agent_id: string;
  runtime_agent_ids: string[];
  output_artifact_id?: string;
  output_artifact_ref?: string;
  output_origin?: string;
  output_source_available?: boolean;
  output_generated_from_project_state?: boolean;
  settlement_source?: string;
  settlement_reason?: string;
  settlement_state_status?: string;
  settlement_state_timestamp?: string;
  transcript_artifact_id?: string;
  transcript_artifact_ref?: string;
  active: boolean;
  terminal: boolean;
  output_quarantined?: boolean;
  output_was_quarantined?: boolean;
  open_shadow_audit_count?: number;
  shadow_audit_id?: string;
}

export interface ExecutionArtifactRecord {
  id: string;
  owner_kind: string;
  owner_id: string;
  source_path: string;
  content_path: string;
  content_bytes: number;
  truncated: boolean;
  preview: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  artifact_ref?: string;
  content: string;
}

export interface ExecutionShadowAuditRecord {
  id: string;
  project_id: string;
  orchestrator_session_id: string;
  runtime_agent_ids: string[];
  source_kind: string;
  source_name: string;
  source_id: string;
  action: string;
  summary: string;
  findings: string[];
  artifact_id: string;
  blocked_artifact_id: string;
  blocked_artifact_owner_kind: string;
  blocked_artifact_owner_id: string;
  status: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  resolved_at?: string | null;
  resolution: Record<string, unknown>;
  artifact_ref: string;
  resolve_ref: string;
  blocked_artifact_ref: string;
  open: boolean;
}

export interface ExecutionShadowAuditDetail extends ExecutionShadowAuditRecord {
  audit_artifact?: ExecutionArtifactRecord | null;
  blocked_artifact?: ExecutionArtifactRecord | null;
}

export interface ExecutionRuntimeAgentTaskRecord {
  id: string;
  project_id: string;
  orchestrator_session_id: string;
  agent_action_run_id: string;
  approval_id: string;
  issue_id: string;
  command: string;
  actor: string;
  reason: string;
  title: string;
  status: string;
  runtime_agent_id: string;
  runtime_agent_ids: string[];
  placeholder_result: string;
  result_summary: string;
  result_payload: Record<string, unknown>;
  output_path: string;
  output_artifact_id: string;
  output_origin: string;
  output_source_available: boolean;
  settlement_source: string;
  settlement_reason: string;
  settlement_state_status: string;
  settlement_state_timestamp: string;
  output_preview: string;
  history: Array<Record<string, unknown>>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  artifact_ref?: string;
  output_artifact_ref?: string;
  transcript_artifact_id?: string;
  transcript_artifact_ref?: string;
  output_available?: boolean;
  active?: boolean;
  terminal?: boolean;
  resume_contract?: ExecutionRuntimeAgentTaskResumeContract | null;
  shadow_audits?: ExecutionShadowAuditRecord[];
  open_shadow_audit_count?: number;
  output_quarantined?: boolean;
  output_was_quarantined?: boolean;
}

export interface ExecutionRuntimeAgentTaskCancelResponse {
  status: string;
  task: ExecutionRuntimeAgentTaskRecord;
  cancel_applied: boolean;
  message: string;
}

export interface ExecutionAgentActionRunCancelResponse {
  status: string;
  run: ExecutionAgentActionRunRecord;
  cancel_applied: boolean;
  cancelled_task_ids: string[];
  message: string;
}

export interface ExecutionRuntimeAgentTaskOutputArtifact extends ExecutionArtifactRecord {
  task_id: string;
  status?: string;
  message?: string;
  content_blocked?: boolean;
  quarantined?: boolean;
  shadow_audits?: ExecutionShadowAuditRecord[];
}

export interface ExecutionRuntimeAgentTaskTranscriptArtifact {
  id: string;
  owner_kind: string;
  owner_id: string;
  content_path: string;
  preview: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  task_id: string;
  artifact_ref: string;
  content: string;
}

export interface ExecutionAgentActionRunSummary {
  selected_count?: number;
  processed_count?: number;
  status_counts?: ExecutionPlaneCountMap;
  [key: string]: unknown;
}

export interface ExecutionAgentActionRunRecord {
  id: string;
  run_kind: string;
  orchestrator_session_id: string;
  idempotency_key: string;
  request_fingerprint: string;
  actor: string;
  mode: string;
  reason: string;
  dry_run: boolean;
  policy_profile: string;
  policy: Record<string, unknown>;
  selection: Record<string, unknown>;
  summary: ExecutionAgentActionRunSummary;
  diff_summary?: Record<string, unknown>;
  patch_bundle?: Record<string, unknown>;
  preview_id?: string;
  artifact_ref?: string;
  approval_required?: boolean;
  apply_mode?: string;
  completion_state: string;
  completion_message: string;
  async_task_status_counts: ExecutionPlaneCountMap;
  async_task_count?: number;
  active_async_task_count?: number;
  async_tasks?: ExecutionRuntimeAgentTaskRecord[];
  resume_contracts?: ExecutionRuntimeAgentTaskResumeContract[];
  resume_contract?: ExecutionRuntimeAgentTaskResumeContract | null;
  shadow_audits?: ExecutionShadowAuditRecord[];
  open_shadow_audit_count?: number;
  handoff_state?: string;
  handoff_blocked?: boolean;
  results: Array<Record<string, unknown>>;
  status: string;
  project_ids: string[];
  initiative_ids: string[];
  orchestrators: string[];
  runtime_agent_ids: string[];
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface ExecutionRuntimeAgentBudgetSummary {
  tracked: boolean;
  usage_label?: string | null;
  metric?: string | null;
  used?: number | null;
  limit?: number | null;
  remaining?: number | null;
  exhausted: boolean;
  auto_pause_on_exhaustion: boolean;
  last_exhaustion_reason?: string | null;
  auto_paused_at?: string | null;
}

export interface ExecutionRuntimeAgentAttentionSummary {
  state: string;
  recommended_action: string;
  reasons: string[];
}

export interface ExecutionRuntimeAgentProjectContext {
  project_id: string;
  name: string;
  path: string;
  status: string;
  paused: boolean;
  current_story_id?: number | null;
  current_iteration?: number | null;
}

export interface ExecutionRuntimeAgentStoryContext {
  id: number;
  title?: string | null;
  status: string;
  phase_id?: string | null;
  phase_title?: string | null;
  iteration?: number | null;
  discoveries?: DiscoveryMarker[];
  github_pr?: StoryGitHubPullRequest | null;
}

export interface ExecutionRuntimeAgentHistorySummary {
  issue_count: number;
  open_issue_count: number;
  approval_count: number;
  pending_approval_count: number;
  tool_permission_runtime_count?: number;
  pending_tool_permission_runtime_count?: number;
  async_task_count?: number;
  active_async_task_count?: number;
  event_count: number;
  last_event_at?: string | null;
}

export interface ExecutionRuntimeAgentDetail {
  runtime_agent_id: string;
  project_id: string;
  project_name: string;
  initiative: Record<string, unknown>;
  orchestration: Record<string, unknown>;
  role: string;
  status: string;
  budget: ExecutionRuntimeAgentBudgetSummary;
  attention: ExecutionRuntimeAgentAttentionSummary;
  recommendations: Array<Record<string, unknown>>;
  suggested_commands: Array<Record<string, unknown>>;
  story_id?: number | null;
  story_title?: string | null;
  project: ExecutionRuntimeAgentProjectContext;
  story: ExecutionRuntimeAgentStoryContext;
  current: Record<string, unknown> | null;
  history: ExecutionRuntimeAgentHistorySummary;
  issues: ExecutionIssueRecord[];
  approvals: ExecutionApprovalRecord[];
  tool_permission_runtimes?: ToolPermissionRuntimeRecord[];
  async_tasks?: ExecutionRuntimeAgentTaskRecord[];
  events: ExecutionPlaneEvent[];
}

export interface ExecutionAgentActionExecuteResult {
  status: string;
  message?: string;
  action?: Record<string, unknown>;
  command_result?: Record<string, unknown>;
  approval?: ExecutionApprovalRecord;
  issue?: ExecutionIssueRecord;
  project?: Record<string, unknown>;
  diff_summary?: Record<string, unknown>;
  patch_bundle?: Record<string, unknown>;
  preview_id?: string;
  artifact_ref?: string;
  approval_required?: boolean;
  apply_mode?: string;
  completion_state?: string;
  completion_message?: string;
  async_task_count?: number;
  active_async_task_count?: number;
  async_tasks?: ExecutionRuntimeAgentTaskRecord[];
  resume_contracts?: ExecutionRuntimeAgentTaskResumeContract[];
  resume_contract?: ExecutionRuntimeAgentTaskResumeContract | null;
  async_task?: ExecutionRuntimeAgentTaskRecord;
  run?: ExecutionAgentActionRunRecord;
  idempotent_replay?: boolean;
}

export interface ExecutionAgentActionBatchResult {
  status: string;
  selection: Record<string, unknown>;
  policy: Record<string, unknown>;
  summary: ExecutionAgentActionRunSummary;
  diff_summary?: Record<string, unknown>;
  patch_bundle?: Record<string, unknown>;
  preview_id?: string;
  artifact_ref?: string;
  approval_required?: boolean;
  apply_mode?: string;
  completion_state?: string;
  completion_message?: string;
  async_task_count?: number;
  active_async_task_count?: number;
  async_tasks?: ExecutionRuntimeAgentTaskRecord[];
  resume_contracts?: ExecutionRuntimeAgentTaskResumeContract[];
  resume_contract?: ExecutionRuntimeAgentTaskResumeContract | null;
  dry_run: boolean;
  results: Array<Record<string, unknown>>;
  run: ExecutionAgentActionRunRecord;
  idempotent_replay?: boolean;
  session_id?: string;
}

export interface OrchestratorSessionDetail extends OrchestratorSessionRecord {
  runs: ExecutionAgentActionRunRecord[];
  control_passes: OrchestratorControlPassRecord[];
  approvals: ExecutionApprovalRecord[];
  issues: ExecutionIssueRecord[];
  tool_permission_runtimes?: ToolPermissionRuntimeRecord[];
  async_tasks?: ExecutionRuntimeAgentTaskRecord[];
  shadow_audits?: ExecutionShadowAuditRecord[];
  events: ExecutionPlaneEvent[];
  control: OrchestratorSessionControl;
  summary: {
    run_count: number;
    control_pass_count: number;
    approval_count: number;
    pending_approval_count: number;
    issue_count: number;
    open_issue_count: number;
    tool_permission_runtime_count?: number;
    pending_tool_permission_runtime_count?: number;
    async_task_count?: number;
    active_async_task_count?: number;
    shadow_audit_count?: number;
    open_shadow_audit_count?: number;
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
  bootstrap_ready?: boolean;
}

export interface SpecBootstrap {
  title: string;
  summary: string;
  goals: string[];
  tech_stack: string[];
  execution_context: string[];
  integrations: string[];
  constraints: string[];
  deliverables: string[];
  open_questions: string[];
  rendered_spec: string;
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

export interface ExtensionRegistryItem {
  extension_id: string;
  display_name: string;
  kind: string;
  provider_family?: string | null;
  adapter_id?: string | null;
  runtime_id?: string | null;
  transport?: string | null;
  metadata: Record<string, unknown>;
}

export interface ExtensionRegistry {
  lifecycle: string[];
  plugins: ExtensionRegistryItem[];
  agent_providers: ExtensionRegistryItem[];
  runtimes: ExtensionRegistryItem[];
  trackers: ExtensionRegistryItem[];
  notifiers: ExtensionRegistryItem[];
}

export interface CapabilitiesCatalog {
  connectors: MCPConnector[];
  tools: ToolContract[];
  skill_packs: SkillPack[];
  roles: RoleTemplate[];
  connector_types: ConnectorTypeSchema[];
  routing_policies: RoutingPolicy[];
  launch_presets: LaunchPreset[];
  provider_configs: ProviderConfig[];
  runtime_profiles: RuntimeProfile[];
  extensions: ExtensionRegistry;
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
