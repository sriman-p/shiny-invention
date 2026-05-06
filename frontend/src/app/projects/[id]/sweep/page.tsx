/**
 * Sweep page — Cursor-agent-panel-inspired detailed evaluation view.
 *
 * Shows a rich real-time dashboard during sweep execution with:
 *   - Summary stats (agent, project, elapsed, ETA)
 *   - Active run panel with stage-by-stage pipeline progress
 *   - Compact run history with mini stage dots and elapsed times
 *   - Results table and statistical analysis after completion
 */
'use client';

import { useParams } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { StatusBadge, StageStatusIcon } from '@/components/status-badge';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';
import { BarChart3, Bot, Clock, Play, StopCircle, Timer, Zap } from 'lucide-react';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/utils';
import type { StageName, Run } from '@/lib/types';

const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];
const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

function generateMatrix(agentId: string, modelId: string) {
  const matrix: Record<string, string>[] = [];
  for (const strategy of STRATEGIES) {
    for (const mode of CONTEXT_MODES) {
      matrix.push({ prompt_strategy: strategy, context_mode: mode, agent_id: agentId, model_id: modelId });
    }
  }
  return matrix;
}

/** Format milliseconds to human-readable elapsed time */
function formatElapsed(ms: number): string {
  const secs = Math.floor(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const remSecs = secs % 60;
  if (mins < 60) return `${mins}m ${remSecs}s`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
}

/** Hook that returns a live elapsed counter in ms, updating every second */
function useElapsed(startedAt: string | null, isActive: boolean): number {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt || !isActive) {
      if (startedAt && !isActive) {
        setElapsed(Date.now() - new Date(startedAt).getTime());
      }
      return;
    }
    const start = new Date(startedAt).getTime();
    setElapsed(Date.now() - start);
    const interval = setInterval(() => setElapsed(Date.now() - start), 1000);
    return () => clearInterval(interval);
  }, [startedAt, isActive]);
  return elapsed;
}

  /** Mini stage pipeline dots for compact run rows */
function MiniStageDots({ run }: { run: Run }) {
  return (
    <div className="flex items-center gap-0.5">
      {STAGES.map((stage) => {
        const se = run.stages?.find((s) => s.stage === stage);
        const status = se?.status || 'pending';
        return (
          <div
            key={stage}
            title={`${stage}: ${status}`}
            className={cn(
              'size-2 rounded-full transition-colors',
              status === 'succeeded' && 'bg-success',
              status === 'running' && 'bg-info animate-pulse',
              status === 'failed' && 'bg-destructive',
              status === 'cancelled' && 'bg-warning',
              status === 'pending' && 'bg-muted-foreground/20',
            )}
          />
        );
      })}
    </div>
  );
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

  // Fetch active run details (with stages) for the pipeline visualization
  const activeRunSummary = sweep?.runs?.find((r) => r.status === 'running');
  const { data: activeRunDetail } = useQuery({
    queryKey: ['run', activeRunSummary?.id],
    queryFn: () => api.getRun(activeRunSummary!.id),
    enabled: !!activeRunSummary?.id,
    refetchInterval: activeRunSummary ? 2000 : false,
  });

  const eventsUrl = sweepId && sweep?.status === 'running' ? api.getSweepEventsUrl(sweepId) : null;
  useEventStream(eventsUrl);

  const queryClient = useQueryClient();

  const startSweepMutation = useMutation({
    mutationFn: () => { const sel = matrix.filter((_, i) => enabled[i]); return api.createSweep(projectId, sel); },
    onSuccess: (data) => setSweepId(data.id),
  });

  const cancelSweepMutation = useMutation({
    mutationFn: () => api.cancelSweep(sweepId!),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['sweep', sweepId] }); },
  });

  const enabledCount = enabled.filter(Boolean).length;
  const finishedRuns = sweep?.runs?.filter((r) => ['succeeded', 'failed', 'cancelled'].includes(r.status)).length || 0;
  const totalConfigs = sweep?.matrix?.length || enabledCount;
  const progressPct = totalConfigs > 0 ? (finishedRuns / totalConfigs) * 100 : 0;

  // Live elapsed timer for the whole sweep
  const sweepElapsed = useElapsed(sweep?.created_at || null, sweep?.status === 'running');

  // Compute ETA based on average run time
  const completedRunTimes = (sweep?.runs || [])
    .filter((r) => r.finished_at && r.started_at)
    .map((r) => new Date(r.finished_at!).getTime() - new Date(r.started_at!).getTime());
  const avgRunTime = completedRunTimes.length > 0 ? completedRunTimes.reduce((a, b) => a + b, 0) / completedRunTimes.length : 0;
  const remainingConfigs = totalConfigs - finishedRuns - (activeRunSummary ? 1 : 0);
  const eta = avgRunTime > 0 && remainingConfigs > 0 ? formatElapsed(avgRunTime * remainingConfigs) : null;

  return (
    <PageWrapper className="p-8 max-w-7xl mx-auto space-y-6">
      <FadeIn>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2"><BarChart3 className="size-5" />Evaluation Sweep</h1>
            <p className="text-sm text-muted-foreground mt-1">
              {project?.name ? `${project.name} · ` : ''}Compare strategies and context modes across {enabledCount} configurations.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {!sweepId && (
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
                <Button onClick={() => startSweepMutation.mutate()} disabled={startSweepMutation.isPending || enabledCount === 0}>
                  {startSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
                  Start sweep ({enabledCount} configs)
                </Button>
              </motion.div>
            )}
            {sweep && sweep.status === 'running' && (
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
                <Button
                  variant="destructive"
                  onClick={() => cancelSweepMutation.mutate()}
                  disabled={cancelSweepMutation.isPending}
                >
                  {cancelSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <StopCircle data-icon="inline-start" />}
                  Stop sweep
                </Button>
              </motion.div>
            )}
          </div>
        </div>
      </FadeIn>

      {/* Matrix config — only before sweep starts */}
      {!sweepId && (
        <FadeIn>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Configuration Matrix</CardTitle>
              <CardDescription>
                Agent: <span className="font-mono text-foreground/80">{agentId}</span>
                {modelId && <> · Model: <span className="font-mono text-foreground/80">{modelId}</span></>}
                {' · '}Toggle cells to include/exclude.
              </CardDescription>
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

      {/* ═══ SWEEP IN PROGRESS ═══ */}
      {sweep && (
        <div className="flex flex-col gap-5">

          {/* Summary stats row */}
          <FadeIn>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="size-9 rounded-lg bg-info/10 flex items-center justify-center">
                    <Bot className="size-4 text-info" />
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wider">Agent</p>
                    <p className="text-sm font-medium font-mono truncate max-w-[120px]">{sweep.matrix[0]?.agent_id || agentId}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="size-9 rounded-lg bg-success/10 flex items-center justify-center">
                    <Zap className="size-4 text-success" />
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wider">Progress</p>
                    <p className="text-sm font-medium tabular-nums">{finishedRuns} / {totalConfigs} configs</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="size-9 rounded-lg bg-secondary flex items-center justify-center">
                    <Clock className="size-4 text-muted-foreground" />
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wider">Elapsed</p>
                    <p className="text-sm font-medium tabular-nums">{formatElapsed(sweepElapsed)}</p>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4 flex items-center gap-3">
                  <div className="size-9 rounded-lg bg-warning/10 flex items-center justify-center">
                    <Timer className="size-4 text-warning" />
                  </div>
                  <div>
                    <p className="text-[11px] text-muted-foreground uppercase tracking-wider">ETA</p>
                    <p className="text-sm font-medium tabular-nums">{eta || (sweep.status === 'running' ? 'Calculating…' : '—')}</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </FadeIn>

          {/* Progress bar */}
          <FadeIn>
            <div className="relative">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <StatusBadge status={sweep.status} />
                  {sweep.status === 'running' && (
                    <span className="text-xs text-muted-foreground animate-pulse">Processing…</span>
                  )}
                </div>
                <span className="text-xs font-mono text-muted-foreground tabular-nums">{Math.round(progressPct)}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-info via-success to-success"
                  initial={{ width: 0 }}
                  animate={{ width: `${progressPct}%` }}
                  transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
                />
              </div>
            </div>
          </FadeIn>

          {/* ═══ ACTIVE RUN — Stage Pipeline ═══ */}
          {activeRunDetail && (
            <FadeIn>
              <Card className="border-info/20 bg-info/[0.02]">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="relative flex size-2.5">
                        <span className="animate-ping absolute inline-flex size-full rounded-full bg-info opacity-75" />
                        <span className="relative inline-flex rounded-full size-2.5 bg-info" />
                      </span>
                      <CardTitle className="text-sm">
                        Running config {(sweep.runs?.length || 0)} of {totalConfigs}
                      </CardTitle>
                    </div>
                    <span className="text-xs font-mono text-muted-foreground">
                      {String((activeRunDetail.config_snapshot as Record<string, unknown>)?.prompt_strategy || '').replace(/_/g, ' ')}
                      {' · '}
                      {String((activeRunDetail.config_snapshot as Record<string, unknown>)?.context_mode || '')}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Stage pipeline visualization */}
                  <div className="relative">
                    {/* Connecting line */}
                    <div className="absolute top-1/2 left-4 right-4 h-px bg-border -translate-y-1/2 z-0" />
                    {/* Progress overlay */}
                    {(() => {
                      const completed = STAGES.filter((s) => {
                        const se = activeRunDetail.stages?.find((st) => st.stage === s);
                        return se?.status === 'succeeded';
                      }).length;
                      const pct = (completed / STAGES.length) * 100;
                      return (
                        <motion.div
                          className="absolute top-1/2 left-4 h-px bg-emerald-500/50 -translate-y-1/2 z-0"
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ duration: 0.6 }}
                        />
                      );
                    })()}

                    <div className="flex items-center justify-between relative z-10">
                      {STAGES.map((stage, i) => {
                        const se = activeRunDetail.stages?.find((s) => s.stage === stage);
                        const status = (se?.status as 'pending' | 'running' | 'succeeded' | 'failed') || 'pending';
                        const latency = se?.latency_ms ? `${(se.latency_ms / 1000).toFixed(1)}s` : null;

                        return (
                          <motion.div
                            key={stage}
                            initial={{ opacity: 0, y: 8 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ delay: i * 0.06, ...springSmooth }}
                            className={cn(
                              'flex flex-col items-center px-2.5 py-2.5 rounded-xl border bg-card min-w-[80px] transition-colors',
                              status === 'running' && 'border-info/30 shadow-sm shadow-info/10',
                              status === 'succeeded' && 'border-success/20',
                              status === 'failed' && 'border-destructive/20',
                              status === 'pending' && 'border-transparent',
                            )}
                          >
                            <span className="text-[10px] font-medium capitalize mb-1 text-muted-foreground">{stage}</span>
                            <StageStatusIcon status={status} />
                            {latency && <span className="text-[10px] text-muted-foreground/60 mt-1 tabular-nums">{latency}</span>}
                            {status === 'running' && <span className="text-[10px] text-info mt-0.5 font-medium">Active</span>}
                          </motion.div>
                        );
                      })}
                    </div>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {/* ═══ RUN HISTORY ═══ */}
          {sweep.runs && sweep.runs.length > 0 && (
            <FadeIn>
              <Card>
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Run History</CardTitle>
                    <CardDescription className="text-xs mt-0">
                      {finishedRuns} completed · {sweep.runs.length - finishedRuns} in progress
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {sweep.runs.map((run, i) => {
                      const snap = (run.config_snapshot || {}) as Record<string, unknown>;
                      const strategy = String(snap.prompt_strategy || sweep.matrix[i]?.prompt_strategy || '—').replace(/_/g, ' ');
                      const context = String(snap.context_mode || sweep.matrix[i]?.context_mode || '—');
                      const isRunning = run.status === 'running';
                      const elapsed = run.started_at && run.finished_at
                        ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()
                        : run.started_at
                          ? Date.now() - new Date(run.started_at).getTime()
                          : 0;

                      return (
                        <motion.div
                          key={run.id}
                          initial={{ opacity: 0, x: -8 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: i * 0.03, ...springSmooth }}
                          className={cn(
                            'flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors',
                            isRunning && 'border-info/20 bg-info/[0.02]',
                            !isRunning && 'border-transparent hover:bg-muted/30',
                          )}
                        >
                          {/* Index */}
                          <span className="text-xs font-mono text-muted-foreground/50 w-5 text-right shrink-0">{i + 1}</span>

                          {/* Status indicator */}
                          <div className="shrink-0">
                            {isRunning ? (
                              <span className="relative flex size-2">
                                <span className="animate-ping absolute inline-flex size-full rounded-full bg-info opacity-75" />
                                <span className="relative inline-flex rounded-full size-2 bg-info" />
                              </span>
                            ) : (
                              <div className={cn(
                                'size-2 rounded-full',
                                run.status === 'succeeded' && 'bg-success',
                                run.status === 'failed' && 'bg-destructive',
                                run.status === 'cancelled' && 'bg-warning',
                                run.status === 'pending' && 'bg-muted-foreground/30',
                              )} />
                            )}
                          </div>

                          {/* Config info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium truncate">{strategy}</span>
                              <span className="text-xs text-muted-foreground capitalize">· {context}</span>
                            </div>
                          </div>

                          {/* Stage dots */}
                          {run.stages && run.stages.length > 0 && (
                            <MiniStageDots run={run} />
                          )}

                          {/* Elapsed time */}
                          <span className="text-xs font-mono text-muted-foreground/60 tabular-nums w-14 text-right shrink-0">
                            {elapsed > 0 ? formatElapsed(elapsed) : '—'}
                          </span>

                          {/* Status badge */}
                          <div className="shrink-0">
                            <StatusBadge status={run.status} className="text-[10px]" />
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          {/* ═══ RESULTS TABLE ═══ */}
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

          {/* ═══ STATISTICAL ANALYSIS ═══ */}
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
