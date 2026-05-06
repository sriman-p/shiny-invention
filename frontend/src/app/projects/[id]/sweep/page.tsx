/**
 * Sweep page — animated evaluation matrix with visual progress tracking.
 */
'use client';

import { useParams } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusBadge } from '@/components/status-badge';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';
import { BarChart3, Loader2, Play } from 'lucide-react';

const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];

function generateMatrix(agentId: string, modelId: string) {
  const matrix: Record<string, string>[] = [];
  for (const strategy of STRATEGIES) {
    for (const mode of CONTEXT_MODES) {
      matrix.push({ prompt_strategy: strategy, context_mode: mode, agent_id: agentId, model_id: modelId });
    }
  }
  return matrix;
}

export default function SweepPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [sweepId, setSweepId] = useState<string | null>(null);
  const [enabled, setEnabled] = useState<boolean[]>(Array(16).fill(true));

  const { data: project } = useQuery({ queryKey: ['project', projectId], queryFn: () => api.getProject(projectId) });

  // Use the agent configured on the project (from the first stage config), falling back to 'claude-code'
  const projectAgent = project?.agents?.[0];
  const agentId = projectAgent?.agent_id || 'claude-code';
  const modelId = projectAgent?.model_id || '';
  const matrix = generateMatrix(agentId, modelId);

  const { data: sweep } = useQuery({
    queryKey: ['sweep', sweepId],
    queryFn: () => api.getSweep(sweepId!),
    enabled: !!sweepId,
    refetchInterval: (query) => { const s = query.state.data; return s && s.status === 'running' ? 3000 : false; },
  });

  const eventsUrl = sweepId && sweep?.status === 'running' ? api.getSweepEventsUrl(sweepId) : null;
  useEventStream(eventsUrl);

  const startSweepMutation = useMutation({
    mutationFn: () => { const sel = matrix.filter((_, i) => enabled[i]); return api.createSweep(projectId, sel); },
    onSuccess: (data) => setSweepId(data.id),
  });

  const enabledCount = enabled.filter(Boolean).length;
  const finishedRuns = sweep?.runs?.filter((r) => ['succeeded', 'failed', 'cancelled'].includes(r.status)).length || 0;
  const totalConfigs = sweep?.matrix?.length || enabledCount;
  const activeRun = sweep?.runs?.find((r) => r.status === 'running');
  const progressPct = totalConfigs > 0 ? (finishedRuns / totalConfigs) * 100 : 0;

  return (
    <PageWrapper className="p-8 max-w-7xl mx-auto space-y-6">
      <FadeIn>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2"><BarChart3 className="h-5 w-5" />Evaluation Sweep</h1>
            <p className="text-sm text-muted-foreground mt-1">Compare strategies and context modes across 16 configurations.</p>
          </div>
          {!sweepId && (
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Button onClick={() => startSweepMutation.mutate()} disabled={startSweepMutation.isPending || enabledCount === 0}>
                {startSweepMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                Start sweep ({enabledCount} configs)
              </Button>
            </motion.div>
          )}
        </div>
      </FadeIn>

      {/* Matrix config */}
      {!sweepId && (
        <FadeIn>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Configuration Matrix</CardTitle>
              <CardDescription>Toggle cells to include/exclude (strategy, context) combinations.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="rounded-lg border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">Strategy \ Context</TableHead>
                      {CONTEXT_MODES.map((m) => (<TableHead key={m} className="text-center capitalize text-xs w-[100px]">{m}</TableHead>))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {STRATEGIES.map((strategy, si) => (
                      <TableRow key={strategy}>
                        <TableCell className="font-medium text-sm">{strategy.replace(/_/g, ' ')}</TableCell>
                        {CONTEXT_MODES.map((_, ci) => {
                          const idx = si * 4 + ci;
                          return (
                            <TableCell key={ci} className="text-center">
                              <motion.div whileTap={{ scale: 0.9 }} className="inline-flex">
                                <Switch checked={enabled[idx]} onCheckedChange={() => { const next = [...enabled]; next[idx] = !next[idx]; setEnabled(next); }} />
                              </motion.div>
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
        </FadeIn>
      )}

      {/* Progress */}
      {sweep && (
        <div className="space-y-6">
          <FadeIn>
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <h3 className="text-sm font-medium">Sweep progress</h3>
                    <StatusBadge status={sweep.status} />
                  </div>
                  <span className="text-sm text-muted-foreground tabular-nums">{finishedRuns} / {totalConfigs} configs</span>
                </div>
                {/* Animated progress bar */}
                <div className="h-2 bg-muted rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${progressPct}%` }}
                    transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
                  />
                </div>
              </CardContent>
            </Card>
          </FadeIn>

          {/* Live run status list */}
          {sweep.runs && sweep.runs.length > 0 && (
            <FadeIn>
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base">Runs</CardTitle>
                  <CardDescription>
                    {activeRun
                      ? <>Currently running config {(sweep.runs?.length || 0)} of {totalConfigs}…</>
                      : sweep.status === 'succeeded'
                        ? 'All configs completed.'
                        : sweep.status === 'failed'
                          ? 'Sweep stopped.'
                          : 'Waiting…'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-lg border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow><TableHead>#</TableHead><TableHead>Strategy</TableHead><TableHead>Context</TableHead><TableHead>Status</TableHead><TableHead className="text-right">Started</TableHead></TableRow>
                      </TableHeader>
                      <TableBody>
                        {sweep.runs.map((run, i) => (
                          <motion.tr key={run.id} initial={{ opacity: 0, x: -6 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03, ...springSmooth }} className="border-b border-border last:border-0">
                            <TableCell className="font-mono text-xs text-muted-foreground">{i + 1}</TableCell>
                            <TableCell className="text-sm">{String((run.config_snapshot as Record<string, unknown>)?.prompt_strategy || sweep.matrix[i]?.prompt_strategy || '—').replace(/_/g, ' ')}</TableCell>
                            <TableCell className="text-sm capitalize">{String((run.config_snapshot as Record<string, unknown>)?.context_mode || sweep.matrix[i]?.context_mode || '—')}</TableCell>
                            <TableCell><StatusBadge status={run.status} /></TableCell>
                            <TableCell className="text-right text-xs text-muted-foreground">{run.started_at ? new Date(run.started_at).toLocaleTimeString() : '—'}</TableCell>
                          </motion.tr>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {/* Results table */}
          {sweep.metrics_summary && (
            <FadeIn>
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-base">Results</CardTitle></CardHeader>
                <CardContent>
                  <div className="rounded-lg border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow><TableHead>Strategy</TableHead><TableHead>Context</TableHead><TableHead className="text-right">Traceability</TableHead><TableHead className="text-right">Accept Rate</TableHead><TableHead className="text-right">Latency</TableHead></TableRow>
                      </TableHeader>
                      <TableBody>
                        {(sweep.metrics_summary as Record<string, unknown>[]).map((m, i) => (
                          <motion.tr key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, ...springSmooth }} className="border-b border-border last:border-0">
                            <TableCell className="text-sm">{String(m.prompt_strategy || '').replace(/_/g, ' ')}</TableCell>
                            <TableCell className="text-sm capitalize">{String(m.context_mode || '')}</TableCell>
                            <TableCell className="text-right font-mono text-sm">{((m.traceability_score as number) * 100).toFixed(1)}%</TableCell>
                            <TableCell className="text-right font-mono text-sm">{((m.critique_accept_rate as number) * 100).toFixed(1)}%</TableCell>
                            <TableCell className="text-right font-mono text-sm tabular-nums">{String(m.latency_total_ms || 0)}ms</TableCell>
                          </motion.tr>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {/* Stats */}
          {sweep.stats_report && (
            <FadeIn>
              <Card>
                <CardHeader className="pb-3"><CardTitle className="text-base flex items-center gap-2"><BarChart3 className="h-4 w-4" />Statistical Analysis</CardTitle></CardHeader>
                <CardContent>
                  <div className="bg-muted/20 rounded-lg p-4 border border-border/50">
                    <pre className="font-mono text-xs whitespace-pre-wrap overflow-auto max-h-96">
                      {(sweep.stats_report as Record<string, unknown>).markdown ? String((sweep.stats_report as Record<string, unknown>).markdown) : JSON.stringify(sweep.stats_report, null, 2)}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}
        </div>
      )}
    </PageWrapper>
  );
}
