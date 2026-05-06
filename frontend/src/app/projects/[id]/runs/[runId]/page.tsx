'use client';

import { useParams } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { formatDistanceToNow } from 'date-fns';
import { CircleCheck, CircleDashed, CircleX, Loader2 } from 'lucide-react';
import type { StageName, StageStatus, RunStatus } from '@/lib/types';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

function StageIcon({ status }: { status: StageStatus }) {
  switch (status) {
    case 'succeeded':
      return <CircleCheck className="h-4 w-4 text-emerald-600" />;
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
    case 'failed':
      return <CircleX className="h-4 w-4 text-rose-600" />;
    default:
      return <CircleDashed className="h-4 w-4 text-zinc-400" />;
  }
}

function StatusBadge({ status }: { status: RunStatus }) {
  const variants: Record<string, string> = {
    succeeded: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
    failed: 'bg-rose-500/10 text-rose-600 border-rose-500/20',
    running: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
    pending: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
    cancelled: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  };
  return (
    <Badge variant="outline" className={variants[status] || variants.pending}>
      {status}
    </Badge>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;
  const [activeStage, setActiveStage] = useState<StageName>('parse');

  const { data: run } = useQuery({
    queryKey: ['run', runId],
    queryFn: () => api.getRun(runId),
    refetchInterval: (query) => {
      const r = query.state.data;
      return r && (r.status === 'running' || r.status === 'pending') ? 2000 : false;
    },
  });

  const eventsUrl = run?.status === 'running' ? api.getRunEventsUrl(runId) : null;
  const { events } = useEventStream(eventsUrl);

  const getStageStatus = (stage: StageName): StageStatus => {
    const se = run?.stages?.find((s) => s.stage === stage);
    if (se) return se.status as StageStatus;
    return 'pending';
  };

  const getStageAgent = (stage: StageName): string => {
    const se = run?.stages?.find((s) => s.stage === stage);
    return se?.agent_id || '—';
  };

  const activeStageData = run?.stages?.find((s) => s.stage === activeStage);

  if (!run) return <div className="p-6">Loading...</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight font-mono">
            Run {run.id.slice(0, 8)}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <StatusBadge status={run.status} />
            <span className="text-sm text-muted-foreground">
              {run.started_at
                ? `started ${formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}`
                : 'pending'}
            </span>
            <span className="text-sm text-muted-foreground">on {run.project_name}</span>
          </div>
        </div>
      </div>

      {/* Pipeline graph */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {STAGES.map((stage, i) => {
          const stageStatus = getStageStatus(stage);
          const isActive = activeStage === stage;
          return (
            <div key={stage} className="flex items-center gap-2">
              <button
                onClick={() => setActiveStage(stage)}
                className={`flex flex-col items-center px-4 py-3 rounded-lg border transition-all min-w-[100px] ${
                  isActive
                    ? 'border-foreground/20 bg-accent'
                    : stageStatus === 'running'
                    ? 'border-blue-500/30 animate-pulse'
                    : 'border-border hover:border-foreground/10'
                }`}
              >
                <span className="text-xs font-medium capitalize">{stage}</span>
                <StageIcon status={stageStatus} />
                <span className="text-[10px] text-muted-foreground mt-1 font-mono">
                  {getStageAgent(stage)}
                </span>
              </button>
              {i < STAGES.length - 1 && (
                <span className="text-muted-foreground text-xs">&rarr;</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Stage detail tabs */}
      <Tabs defaultValue="stream">
        <TabsList>
          <TabsTrigger value="stream">Stream</TabsTrigger>
          <TabsTrigger value="output">Output</TabsTrigger>
          <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
        </TabsList>

        <TabsContent value="stream">
          <Card>
            <CardHeader>
              <CardTitle className="text-base capitalize">{activeStage} — stream log</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-80">
                <div className="space-y-1 font-mono text-xs">
                  {events.filter((e) => !e.stage || e.stage === activeStage).length === 0 ? (
                    <p className="text-muted-foreground">No events yet.</p>
                  ) : (
                    events
                      .filter((e) => !e.stage || e.stage === activeStage)
                      .map((e, i) => (
                        <div key={i} className="flex gap-2 py-0.5">
                          <span className="text-muted-foreground w-20 flex-shrink-0">{e.type}</span>
                          <span className="text-foreground/80 break-all">
                            {typeof e.payload === 'object' ? JSON.stringify(e.payload) : String(e.payload)}
                          </span>
                        </div>
                      ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="output">
          <Card>
            <CardHeader>
              <CardTitle className="text-base capitalize">{activeStage} — output</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-80">
                <pre className="font-mono text-xs whitespace-pre-wrap">
                  {activeStageData?.output_payload
                    ? JSON.stringify(activeStageData.output_payload, null, 2)
                    : 'No output available.'}
                </pre>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="artifacts">
          <Card>
            <CardHeader>
              <CardTitle className="text-base capitalize">{activeStage} — artifacts</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">
                {activeStageData?.status === 'succeeded'
                  ? 'Artifacts saved to run directory.'
                  : 'No artifacts available yet.'}
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
