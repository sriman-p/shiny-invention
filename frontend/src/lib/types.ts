export type RunStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
export type StageStatus = RunStatus | 'skipped';
export type StageName = 'parse' | 'analyze' | 'map' | 'generate' | 'critique' | 'trace';
export type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

export interface StreamEvent {
  type: string;
  stage?: StageName;
  payload?: JsonValue;
  [key: string]: JsonValue | undefined;
}

export interface ModelGroup {
  label: string;
  model_ids: string[];
}

export interface AuthMode {
  id: string;
  label: string;
  env_required: string[];
  notes: string;
}

export interface AuthModeState {
  id: string;
  label: string;
  satisfied: boolean;
  missing: string[];
}

export interface AgentSpec {
  id: string;
  display_name: string;
  command: string;
  args: string[];
  runner: string;
  model: string | null;
  model_options: string[];
  model_groups?: ModelGroup[];
  available: boolean;
  command_on_path: boolean;
  env_vars_set: boolean;
  env_required: string[];
  auth_modes?: AuthMode[];
  auth_mode_states?: AuthModeState[];
  active_auth_mode?: string | null;
  notes: string;
}

export interface AgentConfig {
  id: string;
  stage: StageName;
  agent_id: string;
  model_id: string;
  prompt_strategy: string;
  context_mode: string;
  enabled: boolean;
}

export interface Project {
  id: string;
  name: string;
  code_path: string;
  requirements_path: string;
  test_framework: string;
  language: string;
  created_at: string;
  updated_at?: string;
  agents?: AgentConfig[];
}

export type ReasoningKind =
  | 'thought'
  | 'text'
  | 'tool_call'
  | 'tool_result'
  | 'model_message'
  | 'status';

export interface ReasoningChunk {
  kind: ReasoningKind;
  content: string;
  metadata?: Record<string, unknown>;
  ts?: string;
}

export interface StageExecution {
  id: string;
  stage: StageName;
  agent_id: string;
  model_id: string;
  status: StageStatus;
  started_at: string | null;
  finished_at: string | null;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
  raw_updates: Record<string, unknown>[];
  reasoning?: ReasoningChunk[];
  error: string;
  token_usage: Record<string, number>;
  latency_ms: number | null;
}

export interface Run {
  id: string;
  project: string;
  project_name: string;
  status: RunStatus;
  config_snapshot?: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  artifacts_path?: string;
  created_at: string;
  stages?: StageExecution[];
}

export interface SweepMetric {
  prompt_strategy?: string;
  context_mode?: string;
  agent_id?: string;
  model_id?: string;
  run_id?: string;
  run_mode?: string;
  comparison_baseline?: boolean;
  traceability_score?: number;
  strict_coverage_score?: number;
  critique_accept_rate?: number;
  critique_mean_score?: number;
  critique_coverage_rate?: number;
  mapped_requirements_rate?: number;
  mapping_confidence_avg?: number;
  faiss_evidence_count?: number;
  faiss_evidence_per_mapping?: number;
  generation_coverage_rate?: number;
  trace_matrix_completion_rate?: number;
  stage_success_rate?: number;
  quality_score?: number;
  latency_total_ms?: number;
  tokens_total?: number;
  total_requirements?: number;
  generated_tests_count?: number;
  completed_stages?: number;
  failed_stages?: number;
  output_bytes?: number;
  rank?: number;
  is_winner?: boolean;
  [key: string]: unknown;
}

export interface BaselineLift {
  run_id?: string | null;
  agent_id?: string | null;
  model_id?: string | null;
  prompt_strategy?: string | null;
  context_mode?: string | null;
  rank?: number | null;
  label?: string;
  lift?: Record<string, number>;
  absolute_diff?: Record<string, number>;
}

export interface BaselineSummary {
  baseline?: {
    run_id?: string | null;
    rank?: number | null;
    label?: string;
    agent_id?: string | null;
    model_id?: string | null;
    prompt_strategy?: string | null;
    context_mode?: string | null;
    metrics?: Record<string, number>;
  };
  lifts?: BaselineLift[];
}

export interface Sweep {
  id: string;
  project: string;
  matrix: Record<string, unknown>[];
  status: RunStatus;
  runs?: Run[];
  metrics_summary: SweepMetric[] | null;
  stats_report: JsonValue | null;
  baseline_summary?: BaselineSummary | null;
  created_at: string;
}

export interface BackgroundTaskRow {
  id: string;
  kind: 'run' | 'sweep';
  related_id: string;
  status: RunStatus;
  last_heartbeat: string | null;
  pid: number | null;
  stale: boolean;
}

export interface PathValidation {
  path: string;
  exists: boolean;
}
