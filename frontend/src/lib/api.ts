/**
 * API client for the Django backend.
 */

import type { AgentConfig, AgentSpec, Project, Run, Sweep } from './types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000/api/v1';

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

export const api = {
  getAgents: () => request<AgentSpec[]>('/agents'),
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
  createSweep: (projectId: string, matrix: Record<string, string>[]) =>
    request<Sweep>(`/projects/${projectId}/sweeps`, {
      method: 'POST',
      body: JSON.stringify({ matrix }),
    }),
  getSweep: (id: string) => request<Sweep>(`/sweeps/${id}`),
  getSweepEventsUrl: (sweepId: string) => `${API_BASE_URL}/sweeps/${sweepId}/events`,
  validatePath: (path: string) => request<{ path: string; exists: boolean }>(`/fs/validate?path=${encodeURIComponent(path)}`),
};
