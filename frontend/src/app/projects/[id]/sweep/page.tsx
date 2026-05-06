'use client';

import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { BarChart3, Clock, ExternalLink, Play, Plus, Square, Trophy } from 'lucide-react';

import { BackButton } from '@/components/back-button';
import { PageWrapper } from '@/components/motion';
import { StatusBadge } from '@/components/status-badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { cn } from '@/lib/utils';
import type { AgentSpec, Run, StageName, StreamEvent, Sweep, SweepMetric } from '@/lib/types';

const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];
const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];
const AGENT_DEFAULT_MODEL = 'agent-default';

function generateMatrix(agentId: string, modelId: string) {
  return STRATEGIES.flatMap((prompt_strategy) =>
    CONTEXT_MODES.map((context_mode) => ({ prompt_strategy, context_mode, agent_id: agentId, model_id: modelId })),
  );
}

function modelValueForMatrix(modelId: string) {
  return modelId === AGENT_DEFAULT_MODEL ? '' : modelId;
}

function formatElapsed(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatInteger(value: unknown) {
  return metricNumber(value).toLocaleString();
}

function formatBytes(value: unknown) {
  const bytes = metricNumber(value);
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function useElapsed(startedAt: string | null, isActive: boolean) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    const updateElapsed = () => setElapsed(Date.now() - start);
    updateElapsed();
    if (!isActive) return;
    const timer = setInterval(updateElapsed, 1000);
    return () => clearInterval(timer);
  }, [startedAt, isActive]);
  return elapsed;
}

function metricNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function metricPercent(value: unknown) {
  return `${(metricNumber(value) * 100).toFixed(1)}%`;
}

function label(value: string) {
  return value.replace(/_/g, ' ');
}

function isActiveStatus(status: string) {
  return status === 'running' || status === 'pending';
}

function rankedMetrics(sweep?: Sweep | null) {
  return [...(sweep?.metrics_summary ?? [])].sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999));
}

function StageDots({ run }: { run: Run }) {
  return (
    <div className="flex items-center gap-1">
      {STAGES.map((stage) => {
        const status = run.stages?.find((s) => s.stage === stage)?.status ?? 'pending';
        return (
          <span
            key={stage}
            title={`${stage}: ${status}`}
            className={cn(
              'size-2 rounded-full',
              status === 'succeeded' && 'bg-success',
              status === 'running' && 'bg-info',
              status === 'failed' && 'bg-destructive',
              status === 'cancelled' && 'bg-warning',
              status === 'pending' && 'bg-muted-foreground/25',
            )}
          />
        );
      })}
    </div>
  );
}

function EventLine({ event }: { event: StreamEvent }) {
  const nested = event.event && typeof event.event === 'object' && !Array.isArray(event.event) ? (event.event as StreamEvent) : null;
  const shown = nested ?? event;
  const payload = shown.payload && typeof shown.payload === 'object' ? JSON.stringify(shown.payload) : shown.payload;
  return (
    <div className="grid grid-cols-[140px_90px_1fr] gap-3 border-b py-2 text-xs last:border-0">
      <span className="font-medium">{shown.type}</span>
      <span className="capitalize text-muted-foreground">{shown.stage ?? ''}</span>
      <span className="truncate text-muted-foreground">{payload ? String(payload) : String(event.run_id ?? '')}</span>
    </div>
  );
}

function SweepHistory({
  sweeps,
  activeSweepId,
  onSelect,
}: {
  sweeps: Sweep[];
  activeSweepId: string | null;
  onSelect: (id: string) => void;
}) {
  if (sweeps.length === 0) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Saved Sweeps</CardTitle>
        <CardDescription>Reopen a running or completed sweep. Metrics are stored after every completed run.</CardDescription>
      </CardHeader>
      <CardContent>
        <ScrollArea className="max-h-[220px]">
          <div className="grid gap-2 pr-3 md:grid-cols-2 lg:grid-cols-3">
            {sweeps.map((item) => {
              const metricsCount = item.metrics_summary?.length ?? 0;
              const selected = item.id === activeSweepId;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  className={cn(
                    'rounded-md border p-3 text-left transition-colors hover:bg-muted/40',
                    selected && 'border-foreground/25 bg-muted/30',
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-xs">{item.id.slice(0, 8)}</span>
                    <StatusBadge status={item.status} />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {metricsCount}/{item.matrix.length} metric rows · {new Date(item.created_at).toLocaleString()}
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

export default function SweepPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const projectId = params.id as string;
  const queryClient = useQueryClient();
  const requestedSweepId = searchParams.get('sweep');

  const [selectedSweepId, setSelectedSweepId] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const [enabled, setEnabled] = useState<boolean[]>(Array(16).fill(true));
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [customModelId, setCustomModelId] = useState('');

  const { data: project } = useQuery({ queryKey: ['project', projectId], queryFn: () => api.getProject(projectId) });
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });
  const { data: projectSweeps = [] } = useQuery({
    queryKey: ['project-sweeps', projectId],
    queryFn: () => api.getProjectSweeps(projectId),
    refetchInterval: (query) => {
      const sweeps = query.state.data ?? [];
      return sweeps.some((item) => isActiveStatus(item.status)) ? 2500 : false;
    },
  });

  const projectAgent = project?.agents?.[0];
  const agentId = selectedAgentId || projectAgent?.agent_id || 'codex';
  const selectedAgent = agents.find((agent) => agent.id === agentId);
  const modelOptions = Array.from(
    new Set([AGENT_DEFAULT_MODEL, selectedAgent?.model, ...(selectedAgent?.model_options ?? [])].filter(Boolean)),
  ) as string[];
  const modelId = customModelId.trim() || selectedModelId || projectAgent?.model_id || selectedAgent?.model || AGENT_DEFAULT_MODEL;
  const matrixModelId = modelValueForMatrix(modelId);
  const matrix = useMemo(() => generateMatrix(agentId, matrixModelId), [agentId, matrixModelId]);

  const selectSweep = useCallback(
    (id: string) => {
      setSelectedSweepId(id);
      setShowConfig(false);
      router.replace(`/projects/${projectId}/sweep?sweep=${id}`, { scroll: false });
    },
    [projectId, router],
  );

  const defaultSweep = projectSweeps.find((item) => isActiveStatus(item.status)) ?? projectSweeps[0];
  const sweepId = showConfig ? null : requestedSweepId || selectedSweepId || defaultSweep?.id || null;

  const { data: sweep } = useQuery({
    queryKey: ['sweep', sweepId],
    queryFn: () => api.getSweep(sweepId!),
    enabled: !!sweepId && !showConfig,
    refetchInterval: (query) => {
      const s = query.state.data;
      return s && isActiveStatus(s.status) ? 1500 : false;
    },
  });

  const activeSweep = showConfig ? null : sweep;
  const activeRun = activeSweep?.runs?.find((r) => r.status === 'running') ?? activeSweep?.runs?.find((r) => r.status === 'pending');
  const { data: activeRunDetail } = useQuery({
    queryKey: ['run', activeRun?.id],
    queryFn: () => api.getRun(activeRun!.id),
    enabled: !!activeRun?.id,
    refetchInterval: activeRun ? 1200 : false,
  });

  const eventsUrl = activeSweep && isActiveStatus(activeSweep.status) ? api.getSweepEventsUrl(activeSweep.id) : null;
  const { events } = useEventStream(eventsUrl);

  const startSweepMutation = useMutation({
    mutationFn: () => api.createSweep(projectId, matrix.filter((_, index) => enabled[index])),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['project-sweeps', projectId] });
      selectSweep(data.id);
    },
  });

  const cancelSweepMutation = useMutation({
    mutationFn: () => api.cancelSweep(activeSweep!.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sweep', activeSweep?.id] });
      queryClient.invalidateQueries({ queryKey: ['project-sweeps', projectId] });
    },
  });

  const selectedCount = enabled.filter(Boolean).length;
  const totalConfigs = activeSweep?.matrix.length || selectedCount;
  const finishedRuns = activeSweep?.runs?.filter((r) => ['succeeded', 'failed', 'cancelled'].includes(r.status)).length ?? 0;
  const progress = totalConfigs ? Math.round((finishedRuns / totalConfigs) * 100) : 0;
  const elapsed = useElapsed(activeSweep?.created_at ?? null, activeSweep?.status === 'running');
  const metrics = rankedMetrics(activeSweep);
  const bestMetric = metrics.find((row) => row.is_winner) ?? metrics[0];
  const averageAccept =
    metrics.length > 0 ? metrics.reduce((sum, row) => sum + metricNumber(row.critique_accept_rate), 0) / metrics.length : 0;
  const completedDurations = (activeSweep?.runs ?? [])
    .filter((run) => run.started_at && run.finished_at)
    .map((run) => new Date(run.finished_at!).getTime() - new Date(run.started_at!).getTime());
  const averageDuration = completedDurations.length
    ? completedDurations.reduce((sum, value) => sum + value, 0) / completedDurations.length
    : 0;
  const remaining = Math.max(totalConfigs - finishedRuns - (activeRun ? 1 : 0), 0);
  const eta = averageDuration && remaining ? formatElapsed(averageDuration * remaining) : 'pending';
  const selectedModelLabel = matrixModelId || 'agent default';

  return (
    <PageWrapper className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-3">
          <BackButton fallbackHref={`/projects/${projectId}`} />
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Sweep Evaluation</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {project?.name ?? 'Project'} · compare provider, model, prompt strategy, and context mode.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {activeSweep && isActiveStatus(activeSweep.status) && (
            <Button variant="destructive" onClick={() => cancelSweepMutation.mutate()} disabled={cancelSweepMutation.isPending}>
              {cancelSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <Square data-icon="inline-start" />}
              Stop
            </Button>
          )}
          {activeSweep && !isActiveStatus(activeSweep.status) && (
            <Button variant="outline" onClick={() => setShowConfig(true)}>
              <Plus data-icon="inline-start" />
              New sweep
            </Button>
          )}
          {!activeSweep && (
            <Button onClick={() => startSweepMutation.mutate()} disabled={startSweepMutation.isPending || selectedCount === 0}>
              {startSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
              Start {selectedCount} configs
            </Button>
          )}
        </div>
      </div>

      <SweepHistory sweeps={projectSweeps} activeSweepId={activeSweep?.id ?? sweepId} onSelect={selectSweep} />

      {!activeSweep && sweepId && (
        <Card>
          <CardContent className="flex h-32 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Spinner data-icon="inline-start" />
            Loading saved sweep
          </CardContent>
        </Card>
      )}

      {!activeSweep && !sweepId && (
        <Card>
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle className="text-base">Configuration Matrix</CardTitle>
                <CardDescription>
                  Choose the provider and model up front, then run any subset of the strategy/context grid.
                </CardDescription>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <Select
                  value={agentId}
                  onValueChange={(value) => {
                    const nextAgent = agents.find((agent) => agent.id === value);
                    setSelectedAgentId(value);
                    setSelectedModelId(nextAgent?.model || AGENT_DEFAULT_MODEL);
                    setCustomModelId('');
                  }}
                >
                  <SelectTrigger className="h-9 w-[220px] text-xs">
                    <SelectValue placeholder="Provider" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {agents.map((agent: AgentSpec) => (
                        <SelectItem key={agent.id} value={agent.id}>
                          {agent.display_name}{agent.available ? '' : ' (not configured)'}
                        </SelectItem>
                      ))}
                      {agents.length === 0 && <SelectItem value="codex">OpenAI Codex CLI</SelectItem>}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Select value={selectedModelId || projectAgent?.model_id || selectedAgent?.model || AGENT_DEFAULT_MODEL} onValueChange={setSelectedModelId}>
                  <SelectTrigger className="h-9 w-[220px] text-xs">
                    <SelectValue placeholder="Model" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectGroup>
                      {modelOptions.map((model) => (
                        <SelectItem key={model} value={model}>
                          {model === AGENT_DEFAULT_MODEL ? 'Agent default' : model}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  </SelectContent>
                </Select>
                <Input
                  value={customModelId}
                  onChange={(event) => setCustomModelId(event.target.value)}
                  placeholder="custom model id"
                  className="h-9 w-[220px] text-xs font-mono"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Provider</p>
                <p className="mt-1 truncate text-sm font-medium">{selectedAgent?.display_name || agentId}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Model</p>
                <p className="mt-1 truncate text-sm font-medium">{selectedModelLabel}</p>
              </div>
              <div className="rounded-md border p-3">
                <p className="text-xs text-muted-foreground">Selected configs</p>
                <p className="mt-1 text-sm font-medium">{selectedCount}/16</p>
              </div>
            </div>
            <div className="overflow-hidden rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prompt strategy</TableHead>
                    {CONTEXT_MODES.map((mode) => (
                      <TableHead key={mode} className="text-center capitalize">{mode}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {STRATEGIES.map((strategy, strategyIndex) => (
                    <TableRow key={strategy}>
                      <TableCell className="font-medium">{label(strategy)}</TableCell>
                      {CONTEXT_MODES.map((mode, contextIndex) => {
                        const index = strategyIndex * CONTEXT_MODES.length + contextIndex;
                        return (
                          <TableCell key={mode} className="text-center">
                            <Switch
                              checked={enabled[index]}
                              onCheckedChange={(checked) => {
                                const next = [...enabled];
                                next[index] = checked;
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

      {activeSweep && (
        <>
          <div className="grid gap-3 md:grid-cols-5">
            {[
              ['Status', <StatusBadge key="status" status={activeSweep.status} />],
              ['Progress', `${finishedRuns}/${totalConfigs}`],
              ['Elapsed', formatElapsed(elapsed)],
              ['ETA', activeSweep.status === 'running' ? eta : 'complete'],
              ['Winner', bestMetric ? `${label(String(bestMetric.prompt_strategy))} / ${bestMetric.context_mode}` : 'pending'],
            ].map(([title, value]) => (
              <Card key={String(title)}>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">{title}</p>
                  <div className="mt-2 truncate text-sm font-medium tabular-nums">{value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardContent className="p-4">
              <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                <span>Overall progress</span>
                <span>{progress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-foreground transition-all" style={{ width: `${progress}%` }} />
              </div>
            </CardContent>
          </Card>

          {bestMetric && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base"><Trophy className="size-4" />Best Performer</CardTitle>
                <CardDescription>Ranked by quality score first, then lower latency and token cost.</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3 md:grid-cols-5">
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Configuration</p>
                  <p className="mt-1 truncate text-sm font-medium">{label(String(bestMetric.prompt_strategy))} / {bestMetric.context_mode}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Quality</p>
                  <p className="mt-1 text-sm font-medium">{metricPercent(bestMetric.quality_score)}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Traceability</p>
                  <p className="mt-1 text-sm font-medium">{metricPercent(bestMetric.traceability_score)}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Accept rate</p>
                  <p className="mt-1 text-sm font-medium">{metricPercent(bestMetric.critique_accept_rate)}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Latency</p>
                  <p className="mt-1 text-sm font-medium">{formatElapsed(metricNumber(bestMetric.latency_total_ms))}</p>
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Run Queue</CardTitle>
                <CardDescription>{activeSweep.runs?.length ?? 0} runs created. Reopening this page reads the same stored sweep.</CardDescription>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[420px]">
                  <div className="space-y-2 pr-3">
                    {(activeSweep.runs ?? []).map((run, index) => {
                      const snap = (run.config_snapshot ?? {}) as Record<string, unknown>;
                      const strategy = String(snap.prompt_strategy || activeSweep.matrix[index]?.prompt_strategy || '');
                      const context = String(snap.context_mode || activeSweep.matrix[index]?.context_mode || '');
                      return (
                        <div key={run.id} className="grid grid-cols-[36px_1fr_auto_auto] items-center gap-3 rounded-md border p-3">
                          <span className="text-right text-xs text-muted-foreground">{index + 1}</span>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-medium">{label(strategy)} · {context}</div>
                            <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
                              <StageDots run={run} />
                              <span>{run.id.slice(0, 8)}</span>
                            </div>
                          </div>
                          <StatusBadge status={run.status} />
                          <Link href={`/projects/${projectId}/runs/${run.id}`}>
                            <Button variant="ghost" size="icon" className="size-8" aria-label={`Open run ${run.id.slice(0, 8)}`}>
                              <ExternalLink className="size-4" />
                            </Button>
                          </Link>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Live Run Detail</CardTitle>
                <CardDescription>{activeRunDetail ? `Run ${activeRunDetail.id.slice(0, 8)}` : 'Waiting for the next run.'}</CardDescription>
              </CardHeader>
              <CardContent>
                {activeRunDetail ? (
                  <div className="space-y-3">
                    {STAGES.map((stage) => {
                      const stageExecution = activeRunDetail.stages?.find((item) => item.stage === stage);
                      const updates = stageExecution?.raw_updates?.length ?? 0;
                      return (
                        <div key={stage} className="rounded-md border p-3">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-medium capitalize">{stage}</span>
                            <StatusBadge status={stageExecution?.status ?? 'pending'} />
                          </div>
                          <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                            <span className="truncate">{stageExecution?.agent_id || agentId}</span>
                            <span className="truncate">{stageExecution?.model_id || selectedModelLabel}</span>
                            <span className="text-right">{updates} updates</span>
                          </div>
                          {stageExecution?.error && <p className="mt-2 text-xs text-destructive">{stageExecution.error}</p>}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">No active run yet.</div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Event Log</CardTitle>
              <CardDescription>Nested run events are forwarded through the sweep stream when the page is open.</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[260px]">
                {events.length ? (
                  <div className="pr-3">{events.slice(-80).map((event, index) => <EventLine key={index} event={event} />)}</div>
                ) : (
                  <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
                    {isActiveStatus(activeSweep.status) ? 'Waiting for streamed events.' : 'Stream closed. Stored outputs and metrics are shown below.'}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>

          {metrics.length > 0 && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><BarChart3 className="size-4" />Quality by Configuration</CardTitle>
                  <CardDescription>Quality combines traceability, critique accept rate, and critique score.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {metrics.map((row) => {
                    const score = metricNumber(row.quality_score);
                    return (
                      <div key={row.run_id ?? `${row.prompt_strategy}-${row.context_mode}`}>
                        <div className="mb-1 flex justify-between gap-3 text-xs">
                          <span className="truncate">#{row.rank ?? '-'} {label(String(row.prompt_strategy))} · {String(row.context_mode)}</span>
                          <span className="tabular-nums">{metricPercent(score)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-chart-2" style={{ width: `${Math.min(score * 100, 100)}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base"><Clock className="size-4" />Result Summary</CardTitle>
                  <CardDescription>Rollup for completed sweep runs.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Metric rows</p>
                      <p className="mt-1 text-lg font-semibold">{metrics.length}</p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Avg accept</p>
                      <p className="mt-1 text-lg font-semibold">{metricPercent(averageAccept)}</p>
                    </div>
                    <div className="rounded-md border p-3">
                      <p className="text-xs text-muted-foreground">Avg time</p>
                      <p className="mt-1 text-lg font-semibold">{averageDuration ? formatElapsed(averageDuration) : 'n/a'}</p>
                    </div>
                  </div>
                  <div className="overflow-hidden rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Rank</TableHead>
                          <TableHead>Configuration</TableHead>
                          <TableHead className="text-right">Quality</TableHead>
                          <TableHead className="text-right">Trace</TableHead>
                          <TableHead className="text-right">Accept</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {metrics.map((row) => (
                          <TableRow key={row.run_id ?? `${row.prompt_strategy}-${row.context_mode}`}>
                            <TableCell className="font-mono text-xs">#{row.rank ?? '-'}</TableCell>
                            <TableCell>{label(String(row.prompt_strategy))} · {String(row.context_mode)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.quality_score)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.traceability_score)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.critique_accept_rate)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {metrics.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Detailed Metrics</CardTitle>
                <CardDescription>Stored output and cost indicators for each run.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="overflow-hidden rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Run</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>Model</TableHead>
                        <TableHead className="text-right">Tests</TableHead>
                        <TableHead className="text-right">Stages</TableHead>
                        <TableHead className="text-right">Tokens</TableHead>
                        <TableHead className="text-right">Outputs</TableHead>
                        <TableHead className="text-right">Latency</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {metrics.map((row: SweepMetric) => (
                        <TableRow key={row.run_id ?? `${row.prompt_strategy}-${row.context_mode}`}>
                          <TableCell>
                            {row.run_id ? (
                              <Link href={`/projects/${projectId}/runs/${row.run_id}`} className="font-mono text-xs hover:underline">
                                {row.run_id.slice(0, 8)}
                              </Link>
                            ) : (
                              <span className="text-muted-foreground">n/a</span>
                            )}
                          </TableCell>
                          <TableCell>{row.agent_id || 'agent'}</TableCell>
                          <TableCell className="max-w-[180px] truncate font-mono text-xs">{row.model_id || 'agent default'}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatInteger(row.generated_tests_count)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatInteger(row.completed_stages)}/6</TableCell>
                          <TableCell className="text-right tabular-nums">{formatInteger(row.tokens_total)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatBytes(row.output_bytes)}</TableCell>
                          <TableCell className="text-right tabular-nums">{formatElapsed(metricNumber(row.latency_total_ms))}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          )}

          {activeSweep.stats_report && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Statistical Report</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="max-h-96 overflow-auto rounded-md border bg-muted/20 p-4 text-xs whitespace-pre-wrap">
                  {(activeSweep.stats_report as Record<string, unknown>).markdown
                    ? String((activeSweep.stats_report as Record<string, unknown>).markdown)
                    : JSON.stringify(activeSweep.stats_report, null, 2)}
                </pre>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </PageWrapper>
  );
}
