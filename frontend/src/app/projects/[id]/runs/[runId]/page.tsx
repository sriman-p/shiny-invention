/**
 * Run detail page — animated pipeline graph with visual progress beam.
 */
'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { StatusBadge, StageStatusIcon } from '@/components/status-badge';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';
import { formatDistanceToNow } from 'date-fns';
import { Clock, Copy, Check, Square } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StageName, StageStatus } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { useMutation, useQueryClient } from '@tanstack/react-query';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;
  const [activeStage, setActiveStage] = useState<StageName>('parse');
  const [copied, setCopied] = useState(false);
  const queryClient = useQueryClient();

  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => {
      const r = query.state.data;
      return r && (r.status === 'running' || r.status === 'pending') ? 2000 : false;
    },
  });

  const cancelRunMutation = useMutation({
    mutationFn: () => api.cancelRun(runId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['run', runId] });
    },
  });

  const eventsUrl = run?.status === 'running' ? api.getRunEventsUrl(runId) : null;
  const { events } = useEventStream(eventsUrl);

  const getStageStatus = (stage: StageName): StageStatus => {
    const se = run?.stages?.find((s) => s.stage === stage);
    return (se?.status as StageStatus) || 'pending';
  };

  const getStageAgent = (stage: StageName): string => {
    const se = run?.stages?.find((s) => s.stage === stage);
    return se?.agent_id || '';
  };

  const getStageModel = (stage: StageName): string => {
    const se = run?.stages?.find((s) => s.stage === stage);
    return se?.model_id || '';
  };

  const getStageLatency = (stage: StageName): string | null => {
    const se = run?.stages?.find((s) => s.stage === stage);
    if (se?.latency_ms) return `${(se.latency_ms / 1000).toFixed(1)}s`;
    return null;
  };

  const activeStageData = run?.stages?.find((s) => s.stage === activeStage);
  const stageEvents = events.filter((e) => !e.stage || e.stage === activeStage);

  // Compute overall pipeline progress: how many stages completed out of 6
  const completedStages = STAGES.filter((s) => getStageStatus(s) === 'succeeded').length;
  const progressPct = (completedStages / STAGES.length) * 100;

  const handleCopy = () => {
    if (activeStageData?.output_payload) {
      navigator.clipboard.writeText(JSON.stringify(activeStageData.output_payload, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
        <Skeleton className="h-8 w-48" />
        <div className="flex gap-2">{STAGES.map((s) => <Skeleton key={s} className="h-24 w-28" />)}</div>
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!run) return <div className="p-8"><p className="text-muted-foreground">Run not found.</p></div>;

  const canCancel = run.status === 'running' || run.status === 'pending';

  return (
    <PageWrapper className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
      {/* Header */}
      <FadeIn>
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold tracking-tight font-mono">Run {run.id.slice(0, 8)}</h1>
            <StatusBadge status={run.status} />
          </div>

          {canCancel && (
            <Button
              variant="destructive"
              size="sm"
              className="gap-2"
              disabled={cancelRunMutation.isPending}
              onClick={() => cancelRunMutation.mutate()}
            >
              {cancelRunMutation.isPending ? <Spinner data-icon="inline-start" /> : <Square data-icon="inline-start" />}
              {cancelRunMutation.isPending ? 'Stopping…' : 'Stop'}
            </Button>
          )}
        </div>
        <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock className="size-3.5" />
            {run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'pending'}
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>{run.project_name}</span>
        </div>
      </FadeIn>

      {/* Pipeline progress bar — smooth animated width */}
      <FadeIn>
        <div className="relative">
          <div className="h-1 bg-muted rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-gradient-to-r from-info via-success to-success rounded-full"
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
            />
          </div>
          <p className="text-[11px] text-muted-foreground mt-1.5">
            {completedStages} of {STAGES.length} stages completed
          </p>
        </div>
      </FadeIn>

      {/* Pipeline graph — animated stage cards with connecting lines */}
      <FadeIn>
        <div className="relative">
          {/* Connecting line behind the cards */}
          <div className="absolute top-1/2 left-6 right-6 h-px bg-border -translate-y-1/2 z-0" />
          {/* Progress line overlay — fills as stages complete */}
          <motion.div
            className="absolute top-1/2 left-6 h-px bg-success/50 -translate-y-1/2 z-0"
            initial={{ width: 0 }}
            animate={{ width: `${progressPct}%` }}
            transition={{ duration: 0.8, ease: [0.4, 0, 0.2, 1] }}
          />

          <div className="flex items-center justify-between relative z-10">
            {STAGES.map((stage, i) => {
              const status = getStageStatus(stage);
              const isActive = activeStage === stage;
              const latency = getStageLatency(stage);
              const agent = getStageAgent(stage);
              const model = getStageModel(stage);

              return (
                <motion.button
                  key={stage}
                  onClick={() => setActiveStage(stage)}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.08, ...springSmooth }}
                  whileHover={{ y: -3, transition: { duration: 0.15 } }}
                  whileTap={{ scale: 0.97 }}
                  className={cn(
                    'flex flex-col items-center px-3 py-3 rounded-xl border-2 bg-card min-w-[100px] transition-colors duration-150',
                    isActive && 'border-foreground/15 shadow-sm',
                    !isActive && status === 'running' && 'border-info/30',
                    !isActive && status !== 'running' && 'border-transparent hover:border-border',
                  )}
                >
                  {/* Running: animated beam across the card */}
                  {status === 'running' && (
                    <div className="absolute inset-0 rounded-xl overflow-hidden">
                      <div className="absolute inset-0 animate-beam" />
                    </div>
                  )}

                  <span className="text-[11px] font-medium capitalize mb-1.5 relative">{stage}</span>
                  <div className="relative">
                    <StageStatusIcon status={status} />
                  </div>
                  {agent && <span className="text-[10px] text-muted-foreground/60 mt-1.5 font-mono truncate max-w-[85px] relative">{agent}</span>}
                  {model && <span className="text-[10px] text-muted-foreground/50 mt-0.5 font-mono truncate max-w-[85px] relative">{model}</span>}
                  {latency && <span className="text-[10px] text-muted-foreground/40 mt-0.5 tabular-nums relative">{latency}</span>}
                </motion.button>
              );
            })}
          </div>
        </div>
      </FadeIn>

      {/* Detail tabs */}
      <FadeIn>
        <Tabs defaultValue="stream">
          <TabsList>
            <TabsTrigger value="stream">Stream</TabsTrigger>
            <TabsTrigger value="output">Output</TabsTrigger>
            <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
          </TabsList>

          <TabsContent value="stream" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm capitalize flex items-center gap-2">
                  {run.status === 'running' && <span className="relative flex size-2"><span className="animate-ping absolute inline-flex size-full rounded-full bg-success opacity-75" /><span className="relative inline-flex rounded-full size-2 bg-success" /></span>}
                  {activeStage} — stream log
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  {stageEvents.length === 0 ? (
                    <div className="flex items-center justify-center h-32">
                      <p className="text-sm text-muted-foreground">{run.status === 'running' ? 'Waiting for events...' : 'No events recorded.'}</p>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-0 font-mono text-xs">
                      {stageEvents.map((e, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, x: -6 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ duration: 0.15 }}
                          className="flex gap-3 py-1.5 px-2 rounded hover:bg-muted/30 transition-colors"
                        >
                          <span className={cn(
                            'w-28 shrink-0 font-medium',
                            e.type.includes('completed') && 'text-success',
                            e.type.includes('failed') && 'text-destructive',
                            e.type.includes('started') && 'text-info',
                            e.type.includes('progress') && 'text-muted-foreground/60',
                          )}>
                            {e.type}
                          </span>
                          <span className="text-foreground/60 break-all">
                            {typeof e.payload === 'object' ? JSON.stringify(e.payload) : String(e.payload)}
                          </span>
                        </motion.div>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="output" className="mt-4">
            <Card>
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-sm capitalize">{activeStage} — output</CardTitle>
                {activeStageData?.output_payload && (
                  <Button variant="ghost" size="sm" onClick={handleCopy} className="h-7 text-xs gap-1.5">
                    {copied ? <><Check className="size-3" />Copied</> : <><Copy className="size-3" />Copy</>}
                  </Button>
                )}
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[400px]">
                  <pre className="font-mono text-xs whitespace-pre-wrap p-4 bg-muted/20 rounded-lg border border-border/50">
                    {activeStageData?.output_payload ? JSON.stringify(activeStageData.output_payload, null, 2) : 'No output available.'}
                  </pre>
                </ScrollArea>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="artifacts" className="mt-4">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="text-sm capitalize">{activeStage} — artifacts</CardTitle></CardHeader>
              <CardContent>
                {activeStageData?.status === 'succeeded' ? (
                  <div className="bg-muted/20 rounded-lg p-4 border border-border/50">
                    <p className="text-sm text-muted-foreground">Artifacts saved to run directory.</p>
                    <code className="text-xs font-mono mt-2 block text-muted-foreground/60">GET /api/v1/runs/{run.id}/artifacts/&lt;filename&gt;</code>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-32">
                    <p className="text-sm text-muted-foreground">No artifacts available yet.</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </FadeIn>
    </PageWrapper>
  );
}
