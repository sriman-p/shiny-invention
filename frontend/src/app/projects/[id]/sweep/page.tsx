/**
 * projects/[id]/sweep/page.tsx — Evaluation sweep page.
 *
 * The sweep runs the pipeline multiple times with different configurations
 * to compare prompt strategies and context modes. The default matrix is
 * 4 strategies x 4 context modes = 16 configurations.
 *
 * Layout (two-pane as specified):
 *   Left pane:  Matrix configuration — 4x4 grid of toggleable cells
 *   Right pane: Live results table — one row per finished run with metrics
 *
 * After all runs complete, displays a "Statistical Analysis" card with
 * ANOVA + Bonferroni-corrected t-test results and effect sizes.
 *
 * The page uses SSE to track progress in real time and polls the sweep
 * endpoint every 3 seconds while the sweep is running.
 */
'use client';

import { useParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { StatusBadge } from '@/components/status-badge';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { BarChart3, Loader2, Play } from 'lucide-react';

// ---------------------------------------------------------------------------
// Constants — the axes of the evaluation matrix
// ---------------------------------------------------------------------------

/** The 4 prompt engineering strategies (rows of the matrix) */
const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];

/** The 4 context inclusion levels (columns of the matrix) */
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];

/**
 * Generate the full 4x4 configuration matrix.
 * Each entry specifies a unique (strategy, context_mode, agent) triple.
 */
function generateMatrix(agentId: string = 'claude-code') {
  const matrix: Record<string, string>[] = [];
  for (const strategy of STRATEGIES) {
    for (const mode of CONTEXT_MODES) {
      matrix.push({ prompt_strategy: strategy, context_mode: mode, agent_id: agentId });
    }
  }
  return matrix;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function SweepPage() {
  const params = useParams();
  const projectId = params.id as string;

  // Track the sweep ID after creation (null = not started yet)
  const [sweepId, setSweepId] = useState<string | null>(null);

  // Matrix toggle state: 16 booleans, one per cell, all enabled by default
  const [enabled, setEnabled] = useState<boolean[]>(Array(16).fill(true));

  // The full 4x4 matrix of configurations
  const matrix = generateMatrix();

  /**
   * Fetch sweep status — only runs after a sweep is created.
   * Polls every 3 seconds while the sweep is running.
   */
  const { data: sweep } = useQuery({
    queryKey: ['sweep', sweepId],
    queryFn: () => api.getSweep(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (query) => {
      const s = query.state.data;
      return s && s.status === 'running' ? 3000 : false;
    },
  });

  // SSE connection for real-time sweep progress events
  const eventsUrl =
    sweepId && sweep?.status === 'running' ? api.getSweepEventsUrl(sweepId) : null;
  useEventStream(eventsUrl);

  // Mutation: create the sweep with only the enabled matrix cells
  const startSweepMutation = useMutation({
    mutationFn: () => {
      const selectedMatrix = matrix.filter((_, i) => enabled[i]);
      return api.createSweep(projectId, selectedMatrix);
    },
    onSuccess: (data) => setSweepId(data.id),
  });

  // Compute progress stats
  const completedRuns = sweep?.runs?.filter((r) => r.status === 'succeeded').length || 0;
  const totalRuns = sweep?.runs?.length || 0;
  const enabledCount = enabled.filter(Boolean).length;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* ---- Page header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            Evaluation Sweep
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Run the pipeline across multiple configurations to compare strategies and context modes.
          </p>
        </div>
        {/* Show start button only before sweep begins */}
        {!sweepId && (
          <Button
            onClick={() => startSweepMutation.mutate()}
            disabled={startSweepMutation.isPending || enabledCount === 0}
          >
            {startSweepMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Start sweep ({enabledCount} configs)
          </Button>
        )}
      </div>

      {/* ---- Matrix configuration (shown before sweep starts) ---- */}
      {!sweepId && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Configuration Matrix</CardTitle>
            <CardDescription>
              Toggle cells to include/exclude specific (strategy, context) combinations.
              Default: all 16 enabled.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[180px]">Strategy \ Context</TableHead>
                    {CONTEXT_MODES.map((m) => (
                      <TableHead key={m} className="text-center capitalize text-xs w-[100px]">
                        {m}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {STRATEGIES.map((strategy, si) => (
                    <TableRow key={strategy}>
                      <TableCell className="font-medium text-sm">
                        {strategy.replace(/_/g, ' ')}
                      </TableCell>
                      {CONTEXT_MODES.map((_, ci) => {
                        const idx = si * 4 + ci;
                        return (
                          <TableCell key={ci} className="text-center">
                            <Switch
                              checked={enabled[idx]}
                              onCheckedChange={() => {
                                const next = [...enabled];
                                next[idx] = !next[idx];
                                setEnabled(next);
                              }}
                            />
                          </TableCell>
                        );
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* ---- Sweep progress (shown after sweep starts) ---- */}
      {sweep && (
        <div className="space-y-6">
          {/* Progress card */}
          <Card>
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-medium">Sweep progress</h3>
                  <StatusBadge status={sweep.status} />
                </div>
                <span className="text-sm text-muted-foreground">
                  {completedRuns} / {totalRuns} runs
                </span>
              </div>
              <Progress value={totalRuns > 0 ? (completedRuns / totalRuns) * 100 : 0} />
            </CardContent>
          </Card>

          {/* ---- Results table (shown when metrics are available) ---- */}
          {sweep.metrics_summary && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Results</CardTitle>
                <CardDescription>
                  Metrics for each completed configuration run.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Strategy</TableHead>
                        <TableHead>Context</TableHead>
                        <TableHead className="text-right">Traceability</TableHead>
                        <TableHead className="text-right">Accept Rate</TableHead>
                        <TableHead className="text-right">Latency</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(sweep.metrics_summary as Record<string, unknown>[]).map((m, i) => (
                        <TableRow key={i}>
                          <TableCell className="text-sm">
                            {String(m.prompt_strategy || '').replace(/_/g, ' ')}
                          </TableCell>
                          <TableCell className="text-sm capitalize">
                            {String(m.context_mode || '')}
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {((m.traceability_score as number) * 100).toFixed(1)}%
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {((m.critique_accept_rate as number) * 100).toFixed(1)}%
                          </TableCell>
                          <TableCell className="text-right font-mono text-sm">
                            {String(m.latency_total_ms || 0)}ms
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* ---- Statistical analysis (shown after all runs complete) ---- */}
          {sweep.stats_report && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" />
                  Statistical Analysis
                </CardTitle>
                <CardDescription>
                  ANOVA results with Bonferroni-corrected pairwise comparisons.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="bg-muted/30 rounded-md p-4">
                  <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto max-h-96">
                    {(sweep.stats_report as Record<string, unknown>).markdown
                      ? String((sweep.stats_report as Record<string, unknown>).markdown)
                      : JSON.stringify(sweep.stats_report, null, 2)}
                  </pre>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
