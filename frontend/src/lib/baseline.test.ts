import { describe, expect, it } from 'vitest';

import { expandSweepCells, formatPercentDelta, summarizeWinnerLift } from './baseline';

describe('formatPercentDelta', () => {
  it('formats a positive lift with a leading +', () => {
    expect(formatPercentDelta(12.345)).toBe('+12.3%');
  });

  it('preserves the negative sign for regressions', () => {
    expect(formatPercentDelta(-4.2)).toBe('-4.2%');
  });

  it('renders an em dash for non-numeric values', () => {
    expect(formatPercentDelta(undefined)).toBe('—');
    expect(formatPercentDelta(Number.NaN)).toBe('—');
  });
});

describe('summarizeWinnerLift', () => {
  it('returns an empty list when no lifts are present', () => {
    expect(summarizeWinnerLift(null)).toEqual([]);
    expect(summarizeWinnerLift({ lifts: [] })).toEqual([]);
  });

  it('reports the four headline metrics in order', () => {
    const formatted = summarizeWinnerLift({
      baseline: { metrics: {} },
      lifts: [
        {
          lift: {
            quality_score: 18.4,
            traceability_score: 9.1,
            latency_total_ms: -22.5,
            tokens_total: 5,
          },
        },
      ],
    });
    expect(formatted.map((row) => row.label)).toEqual(['Quality', 'Traceability', 'Latency', 'Tokens']);
    expect(formatted.map((row) => row.value)).toEqual(['+18.4%', '+9.1%', '-22.5%', '+5.0%']);
    expect(formatted.map((row) => row.positive)).toEqual([true, true, false, true]);
  });
});

describe('expandSweepCells', () => {
  const STRATEGIES = ['zero_shot', 'chain_of_thought'];
  const CONTEXTS = ['minimal', 'full'];

  it('returns the cartesian product when every cell is enabled', () => {
    const cells = expandSweepCells(
      [
        { agent_id: 'codex', model_id: 'gpt-5.5/low' },
        { agent_id: 'claude-code', model_id: 'claude-sonnet-4.5' },
      ],
      [true, true, true, true],
      STRATEGIES,
      CONTEXTS,
    );
    expect(cells).toHaveLength(8);
    expect(cells[0]).toEqual({
      agent_id: 'codex',
      model_id: 'gpt-5.5/low',
      prompt_strategy: 'zero_shot',
      context_mode: 'minimal',
    });
  });

  it('honours the strategy/context enable mask', () => {
    const cells = expandSweepCells(
      [{ agent_id: 'codex', model_id: 'gpt-5.5/low' }],
      [true, false, false, true],
      STRATEGIES,
      CONTEXTS,
    );
    expect(cells.map((cell) => `${cell.prompt_strategy}/${cell.context_mode}`)).toEqual([
      'zero_shot/minimal',
      'chain_of_thought/full',
    ]);
  });
});
