/**
 * API client for the Django backend.
 */

import type { AgentConfig, AgentSpec, BackgroundTaskRow, Project, Run, Sweep } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export interface SweepAxesRequest {
  agents: { agent_id: string; model_id: string }[];
  /** Add one direct, single-pass ACP generation baseline per agent/model. */
  include_direct_baseline?: boolean;
  /** Prefer this when individual cells are toggled -- avoids accidental
   *  cartesian explosions when the same enabled strategy/context list is
   *  echoed across both axes. */
  pairs?: { prompt_strategy: string; context_mode: string }[];
  /** Legacy cartesian form: every strategy x every context per agent. */
  strategies?: string[];
  contexts?: string[];
}

export interface SweepPreview {
  matrix: {
    agent_id: string;
    model_id: string;
    prompt_strategy: string;
    context_mode: string;
    run_mode?: string;
    comparison_baseline?: boolean;
  }[];
  summary: {
    agent_count: number;
    strategy_count: number;
    context_count: number;
    pair_count: number;
    total_cells: number;
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const message =
      data && typeof data === 'object' && 'error' in data ? String(data.error) : `Request failed: ${response.status}`;
    throw new Error(message);
  }

  return data as T;
}

export interface AgentModelDiscovery {
  agent_id: string;
  discovered: boolean;
  models: string[];
  static: string[];
  cached?: boolean;
  error?: string;
}

export const api = {
  getAgents: () => request<AgentSpec[]>('/agents'),
  getAgentModels: (agentId: string) =>
    request<AgentModelDiscovery>(`/agents/${encodeURIComponent(agentId)}/models`),
  getProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (project: Pick<Project, 'name' | 'code_path' | 'requirements_path'> & Partial<Project>) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(project) }),
  updateProjectAgents: (projectId: string, configs: Partial<AgentConfig>[]) =>
    request<AgentConfig[]>(`/projects/${projectId}/agents`, {
      method: 'PATCH',
      body: JSON.stringify(configs),
    }),
  getRecentRuns: () => request<Run[]>('/runs'),
  getRun: (id: string) => request<Run>(`/runs/${id}`),
  cancelRun: (runId: string) => request<Run>(`/runs/${runId}/cancel`, { method: 'POST', body: '{}' }),
  createRun: (projectId: string, body: Record<string, unknown> = {}) =>
    request<Run>(`/projects/${projectId}/runs`, { method: 'POST', body: JSON.stringify(body) }),
  getRunEventsUrl: (runId: string) => `${API_BASE_URL}/runs/${runId}/events`,
  createSweep: (projectId: string, matrix: Record<string, unknown>[]) =>
    request<Sweep>(`/projects/${projectId}/sweeps`, {
      method: 'POST',
      body: JSON.stringify({ matrix }),
    }),
  createSweepFromAxes: (projectId: string, axes: SweepAxesRequest) =>
    request<Sweep>(`/projects/${projectId}/sweeps`, {
      method: 'POST',
      body: JSON.stringify({ axes }),
    }),
  previewSweep: (projectId: string, axes: SweepAxesRequest) =>
    request<SweepPreview>(`/projects/${projectId}/sweeps/preview`, {
      method: 'POST',
      body: JSON.stringify({ axes }),
    }),
  getProjectSweeps: (projectId: string) => request<Sweep[]>(`/projects/${projectId}/sweeps`),
  getSweep: (id: string) => request<Sweep>(`/sweeps/${id}`),
  cancelSweep: (sweepId: string) => request<Sweep>(`/sweeps/${sweepId}/cancel`, { method: 'POST', body: '{}' }),
  getSweepEventsUrl: (sweepId: string) => `${API_BASE_URL}/sweeps/${sweepId}/events`,
  resolveRunPermission: (runId: string, promptId: string, outcome: 'allowed_once' | 'cancelled') =>
    request<{ resolved: boolean; outcome: string }>(
      `/runs/${runId}/permissions/${encodeURIComponent(promptId)}`,
      {
        method: 'POST',
        body: JSON.stringify({ outcome }),
      },
    ),
  getBackgroundTasks: () => request<BackgroundTaskRow[]>('/background-tasks'),
  validatePath: (path: string) => request<{ path: string; exists: boolean }>(`/fs/validate?path=${encodeURIComponent(path)}`),
};
