/**
 * Pure helpers for the sweep "Lift vs baseline" UI.
 *
 * Keeping these in a dependency-free module makes them straightforward to
 * unit-test under vitest's Node environment without pulling in JSDOM or
 * the React renderer.
 */

import type { BaselineLift, BaselineSummary } from './types';

export interface FormattedLift {
  label: string;
  value: string;
  positive: boolean;
}

/** Always show a sign so reviewers can scan deltas at a glance. */
export function formatPercentDelta(value: unknown): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  const rounded = value.toFixed(1);
  return `${value >= 0 ? '+' : ''}${rounded}%`;
}

/** Render the four headline lift metrics for the sweep summary card. */
export function summarizeWinnerLift(summary: BaselineSummary | null | undefined): FormattedLift[] {
  if (!summary?.lifts || summary.lifts.length === 0) return [];
  const winner: BaselineLift = summary.lifts[0];
  const lift = winner.lift ?? {};
  const out: FormattedLift[] = [
    { label: 'Quality', value: formatPercentDelta(lift.quality_score), positive: (lift.quality_score ?? 0) >= 0 },
    {
      label: 'Traceability',
      value: formatPercentDelta(lift.traceability_score),
      positive: (lift.traceability_score ?? 0) >= 0,
    },
    { label: 'Latency', value: formatPercentDelta(lift.latency_total_ms), positive: (lift.latency_total_ms ?? 0) >= 0 },
    { label: 'Tokens', value: formatPercentDelta(lift.tokens_total), positive: (lift.tokens_total ?? 0) >= 0 },
  ];
  return out;
}

/** Build the full strategy x context expansion the matrix builder needs. */
export function expandSweepCells(
  agents: { agent_id: string; model_id: string }[],
  enabled: boolean[],
  strategies: string[],
  contexts: string[],
): { agent_id: string; model_id: string; prompt_strategy: string; context_mode: string }[] {
  const cells: { agent_id: string; model_id: string; prompt_strategy: string; context_mode: string }[] = [];
  for (const agent of agents) {
    for (let s = 0; s < strategies.length; s += 1) {
      for (let c = 0; c < contexts.length; c += 1) {
        if (enabled[s * contexts.length + c]) {
          cells.push({
            agent_id: agent.agent_id,
            model_id: agent.model_id,
            prompt_strategy: strategies[s],
            context_mode: contexts[c],
          });
        }
      }
    }
  }
  return cells;
}
