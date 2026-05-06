'use client';

import { useParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];

function generateMatrix(agent_id: string = 'claude-code') {
  const matrix: Record<string, string>[] = [];
  for (const strategy of STRATEGIES) {
    for (const mode of CONTEXT_MODES) {
      matrix.push({ prompt_strategy: strategy, context_mode: mode, agent_id });
    }
  }
  return matrix;
}

export default function SweepPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [sweepId, setSweepId] = useState<string | null>(null);
  const [enabled, setEnabled] = useState<boolean[]>(Array(16).fill(true));

  const matrix = generateMatrix();

  const { data: sweep } = useQuery({
    queryKey: ['sweep', sweepId],
    queryFn: () => api.getSweep(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (query) => {
      const s = query.state.data;
      return s && s.status === 'running' ? 3000 : false;
    },
  });

  const eventsUrl = sweepId && sweep?.status === 'running' ? api.getSweepEventsUrl(sweepId) : null;
  useEventStream(eventsUrl);

  const startSweepMutation = useMutation({
    mutationFn: () => {
      const selectedMatrix = matrix.filter((_, i) => enabled[i]);
      return api.createSweep(projectId, selectedMatrix);
    },
    onSuccess: (data) => setSweepId(data.id),
  });

  const completedRuns = sweep?.runs?.filter((r) => r.status === 'succeeded').length || 0;
  const totalRuns = sweep?.runs?.length || 0;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Evaluation Sweep</h1>
        {!sweepId && (
          <Button onClick={() => startSweepMutation.mutate()} disabled={startSweepMutation.isPending}>
            {startSweepMutation.isPending ? 'Starting...' : 'Start sweep'}
          </Button>
        )}
      </div>

      {!sweepId && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configuration Matrix (4 x 4 = 16 configs)</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead></TableHead>
                  {CONTEXT_MODES.map((m) => (
                    <TableHead key={m} className="text-center capitalize text-xs">
                      {m}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {STRATEGIES.map((strategy, si) => (
                  <TableRow key={strategy}>
                    <TableCell className="font-medium text-xs">{strategy.replace(/_/g, ' ')}</TableCell>
                    {CONTEXT_MODES.map((_, ci) => {
                      const idx = si * 4 + ci;
                      return (
                        <TableCell key={ci} className="text-center">
                          <input
                            type="checkbox"
                            checked={enabled[idx]}
                            onChange={() => {
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
          </CardContent>
        </Card>
      )}

      {sweep && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                Sweep progress
                <Badge variant="outline">{sweep.status}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Progress value={totalRuns > 0 ? (completedRuns / totalRuns) * 100 : 0} />
              <p className="text-sm text-muted-foreground">
                {completedRuns} of {totalRuns} runs completed
              </p>
            </CardContent>
          </Card>

          {sweep.metrics_summary && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Results</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Strategy</TableHead>
                      <TableHead>Context</TableHead>
                      <TableHead>Traceability</TableHead>
                      <TableHead>Accept Rate</TableHead>
                      <TableHead>Latency (ms)</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(sweep.metrics_summary as Record<string, unknown>[]).map((m, i) => (
                      <TableRow key={i}>
                        <TableCell className="text-xs">{String(m.prompt_strategy || '').replace(/_/g, ' ')}</TableCell>
                        <TableCell className="text-xs">{String(m.context_mode || '')}</TableCell>
                        <TableCell className="text-xs">{((m.traceability_score as number) * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-xs">{((m.critique_accept_rate as number) * 100).toFixed(1)}%</TableCell>
                        <TableCell className="text-xs">{String(m.latency_total_ms || 0)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {sweep.stats_report && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Statistical Analysis</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto max-h-96">
                  {(sweep.stats_report as Record<string, unknown>).markdown
                    ? String((sweep.stats_report as Record<string, unknown>).markdown)
                    : JSON.stringify(sweep.stats_report, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
