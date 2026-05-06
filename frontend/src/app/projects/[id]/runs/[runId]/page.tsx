/**
 * projects/[id]/runs/[runId]/page.tsx — Pipeline run detail page.
 *
 * The "flagship page" of the application. Displays:
 *
 *   1. Run header — Run ID (monospace), status badge, timing, project name
 *
 *   2. Pipeline graph — 6 stage cards in a horizontal row with arrows between
 *      them. Each card shows the stage name, status icon, agent name, and
 *      elapsed time. The active/running stage has a pulsing border. Clicking
 *      a stage selects it for the detail tabs below.
 *
 *   3. Stage detail tabs:
 *      - Stream: Real-time log of SSE events (session updates, tool calls)
 *      - Output: Pretty-printed JSON of the stage's Pydantic output
 *      - Artifacts: List of files saved to the run's artifacts directory
 *
 * The page polls the run endpoint every 2 seconds while the run is active,
 * and subscribes to the SSE stream for real-time event updates.
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
import { StatusBadge, StageStatusIcon } from '@/components/status-badge';
import { formatDistanceToNow } from 'date-fns';
import { Clock, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { StageName, StageStatus } from '@/lib/types';

/** All 6 pipeline stages in execution order */
const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;

  // Which stage the user has selected to view details for
  const [activeStage, setActiveStage] = useState<StageName>('parse');

  /**
   * Fetch the run with all stage execution details.
   * Polls every 2 seconds while the run is active (running/pending),
   * stops polling once the run reaches a terminal state.
   */
  const { data: run, isLoading } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => {
      const r = query.state.data;
      return r && (r.status === 'running' || r.status === 'pending') ? 2000 : false;
    },
  });

  /**
   * SSE connection — only active while the run is executing.
   * Events are accumulated in state and displayed in the Stream tab.
   */
  const eventsUrl = run?.status === 'running' ? api.getRunEventsUrl(runId) : null;
  const { events } = useEventStream(eventsUrl);

  // Helper: get the execution status of a specific stage
  const getStageStatus = (stage: StageName): StageStatus => {
    const se = run?.stages?.find((s) => s.stage === stage);
    if (se) return se.status as StageStatus;
    return 'pending';
  };

  // Helper: get the agent name for a specific stage
  const getStageAgent = (stage: StageName): string => {
    const se = run?.stages?.find((s) => s.stage === stage);
    return se?.agent_id || '—';
  };

  // Helper: get elapsed time for a specific stage in human-readable format
  const getStageLatency = (stage: StageName): string | null => {
    const se = run?.stages?.find((s) => s.stage === stage);
    if (se?.latency_ms) return `${(se.latency_ms / 1000).toFixed(1)}s`;
    return null;
  };

  // The selected stage's full execution data (for output/artifacts tabs)
  const activeStageData = run?.stages?.find((s) => s.stage === activeStage);

  // Filter SSE events to only show those relevant to the selected stage
  const stageEvents = events.filter((e) => !e.stage || e.stage === activeStage);

  // Loading state
  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <p className="text-muted-foreground">Run not found.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* ---- Run header ---- */}
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight font-mono">
            Run {run.id.slice(0, 8)}
          </h1>
          <StatusBadge status={run.status} />
        </div>
        <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            {run.started_at
              ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
              : 'pending'}
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span>{run.project_name}</span>
        </div>
      </div>

      {/* ---- Pipeline graph: 6 stage cards in a row ---- */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2">
        {STAGES.map((stage, i) => {
          const stageStatus = getStageStatus(stage);
          const isActive = activeStage === stage;
          const latency = getStageLatency(stage);

          return (
            <div key={stage} className="flex items-center gap-1.5">
              {/* Stage card — clickable to select for detail view */}
              <button
                onClick={() => setActiveStage(stage)}
                className={cn(
                  'flex flex-col items-center px-4 py-3 rounded-lg border transition-all min-w-[110px]',
                  isActive && 'border-foreground/20 bg-accent ring-1 ring-foreground/5',
                  !isActive && stageStatus === 'running' && 'border-blue-500/30 animate-pulse',
                  !isActive && stageStatus !== 'running' && 'border-border hover:border-foreground/10 hover:bg-accent/30'
                )}
              >
                <span className="text-xs font-medium capitalize mb-1.5">{stage}</span>
                <StageStatusIcon status={stageStatus} />
                <span className="text-[10px] text-muted-foreground mt-1.5 font-mono truncate max-w-[90px]">
                  {getStageAgent(stage)}
                </span>
                {latency && (
                  <span className="text-[10px] text-muted-foreground/60 mt-0.5">{latency}</span>
                )}
              </button>
              {/* Arrow between stages */}
              {i < STAGES.length - 1 && (
                <ArrowRight className="h-3 w-3 text-muted-foreground/30 shrink-0" />
              )}
            </div>
          );
        })}
      </div>

      {/* ---- Stage detail tabs ---- */}
      <Tabs defaultValue="stream">
        <TabsList>
          <TabsTrigger value="stream">Stream</TabsTrigger>
          <TabsTrigger value="output">Output</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
        </TabsList>

        {/* Stream tab: real-time event log from SSE */}
        <TabsContent value="stream" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm capitalize flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                {activeStage} — stream log
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                {stageEvents.length === 0 ? (
                  <div className="flex items-center justify-center h-32">
                    <p className="text-sm text-muted-foreground">
                      {run.status === 'running' ? 'Waiting for events...' : 'No events recorded.'}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-0.5 font-mono text-xs">
                    {stageEvents.map((e, i) => (
                      <div
                        key={i}
                        className="flex gap-3 py-1 px-2 rounded hover:bg-muted/50"
                      >
                        {/* Event type label with semantic coloring */}
                        <span
                          className={cn(
                            'w-28 shrink-0 font-medium',
                            e.type.includes('completed') && 'text-emerald-600',
                            e.type.includes('failed') && 'text-rose-600',
                            e.type.includes('started') && 'text-blue-600',
                            e.type.includes('progress') && 'text-muted-foreground'
                          )}
                        >
                          {e.type}
                        </span>
                        {/* Event payload */}
                        <span className="text-foreground/70 break-all">
                          {typeof e.payload === 'object'
                            ? JSON.stringify(e.payload)
                            : String(e.payload)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Output tab: pretty-printed JSON of the stage's Pydantic model output */}
        <TabsContent value="output" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm capitalize">{activeStage} — output</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <pre className="font-mono text-xs whitespace-pre-wrap p-3 bg-muted/30 rounded-md">
                  {activeStageData?.output_payload
                    ? JSON.stringify(activeStageData.output_payload, null, 2)
                    : 'No output available.'}
                </pre>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Artifacts tab: files saved to the run's artifacts directory */}
        <TabsContent value="artifacts" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm capitalize">{activeStage} — artifacts</CardTitle>
            </CardHeader>
            <CardContent>
              {activeStageData?.status === 'succeeded' ? (
                <div className="bg-muted/30 rounded-md p-4">
                  <p className="text-sm text-muted-foreground">
                    Artifacts saved to run directory. Use the API to retrieve specific files.
                  </p>
                  <code className="text-xs font-mono mt-2 block text-muted-foreground/70">
                    GET /api/v1/runs/{run.id}/artifacts/&lt;filename&gt;
                  </code>
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
    </div>
  );
}
