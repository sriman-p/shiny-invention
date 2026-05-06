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

export interface AgentSpec {
  id: string;
  display_name: string;
  command: string;
  available: boolean;
  command_on_path: boolean;
  env_vars_set: boolean;
  env_required: string[];
  notes: string;
}

export interface AgentConfig {
  id: string;
  stage: StageName;
  agent_id: string;
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

export interface StageExecution {
  id: string;
  stage: StageName;
  agent_id: string;
  status: StageStatus;
  started_at: string | null;
  finished_at: string | null;
  input_payload: Record<string, unknown> | null;
  output_payload: Record<string, unknown> | null;
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

export interface Sweep {
  id: string;
  project: string;
  matrix: Record<string, string>[];
  status: RunStatus;
  runs?: Run[];
  metrics_summary: JsonValue[] | null;
  stats_report: JsonValue | null;
  created_at: string;
}

export interface PathValidation {
  path: string;
  exists: boolean;
}
