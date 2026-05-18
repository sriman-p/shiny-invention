/**
 * Run detail page — Cursor/opencode-grade vertical accordion of pipeline stages.
 *
 * Each stage card collapses to a header (status, name, agent/model, duration,
 * tokens) and expands to reveal:
 *   - Live <ReasoningStream> of normalized thought / tool-call / text chunks
 *   - Output JSON viewer (collapsible)
 *   - Artifact links
 *
 * Progress bar advances continuously: completed stages count as 1.0 each, the
 * currently-running stage adds a fractional progress derived from the streamed
 * reasoning event count vs a rolling average. A 1s heartbeat keeps the bar
 * nudging forward so the user never feels stuck.
 */
'use client';

import { useParams } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useMemo, useState } from 'react';
import { Clock, Copy, Check, Square, ChevronDown, Wifi, WifiOff, ShieldCheck, ShieldQuestion } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { StatusBadge, StageStatusIcon } from '@/components/status-badge';
import { ReasoningStream } from '@/components/reasoning-stream';
import { PageWrapper, FadeIn, motion, AnimatePresence, springSmooth } from '@/components/motion';
import { cn } from '@/lib/utils';
import type { ReasoningChunk, ReasoningKind, StageExecution, StageName, StageStatus } from '@/lib/types';
import { Button } from '@/components/ui/button';
import { BackButton } from '@/components/back-button';
import { toast } from 'sonner';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];
const ROLLING_AVG_FALLBACK = 30;

interface PermissionPrompt {
  prompt_id: string;
  session_id?: string;
  tool_call?: Record<string, unknown>;
  options?: { option_id?: string | null; kind?: string | null; label?: string | null }[];
  acted?: boolean;
}

function sumTokenUsage(usage: Record<string, number> | undefined): number {
  if (!usage) return 0;
  return Object.values(usage).reduce((sum, value) => (typeof value === 'number' ? sum + value : sum), 0);
}

function formatLatency(ms: number | null | undefined): string {
  if (!ms || ms < 0) return '—';
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(ms < 10000 ? 2 : 1)}s`;
}

function formatTokens(value: number): string {
  if (value <= 0) return '—';
  if (value < 1000) return value.toLocaleString();
  return `${(value / 1000).toFixed(value < 10_000 ? 1 : 0)}k`;
}

interface StreamedReasoning {
  byStage: Record<StageName, ReasoningChunk[]>;
  permissions: PermissionPrompt[];
  resolvedPrompts: Set<string>;
}

function useStreamedReasoning(events: ReturnType<typeof useEventStream>['events']): StreamedReasoning {
  return useMemo(() => {
    const byStage: Record<StageName, ReasoningChunk[]> = {
      parse: [],
      analyze: [],
      map: [],
      generate: [],
      critique: [],
      trace: [],
    };
    const permissionsByPrompt = new Map<string, PermissionPrompt>();
    const resolved = new Set<string>();

    for (const event of events) {
      if (event.type === 'stage_reasoning' && event.stage && event.payload && typeof event.payload === 'object') {
        const stage = event.stage as StageName;
        const chunk = event.payload as unknown as ReasoningChunk;
        if (chunk && typeof chunk.kind === 'string' && typeof chunk.content === 'string') {
          byStage[stage]?.push(chunk);
        }
      } else if (event.type === 'permission_required' && event.payload && typeof event.payload === 'object') {
        const payload = event.payload as unknown as PermissionPrompt;
        if (payload.prompt_id && !permissionsByPrompt.has(payload.prompt_id)) {
          permissionsByPrompt.set(payload.prompt_id, payload);
        }
      } else if (event.type === 'permission_resolved' && event.payload && typeof event.payload === 'object') {
        const payload = event.payload as unknown as { prompt_id?: string };
        if (payload.prompt_id) resolved.add(payload.prompt_id);
      }
    }

    return {
      byStage,
      permissions: Array.from(permissionsByPrompt.values()).filter((p) => !resolved.has(p.prompt_id)),
      resolvedPrompts: resolved,
    };
  }, [events]);
}

function PermissionPromptCard({
  runId,
  prompt,
  onResolved,
}: {
  runId: string;
  prompt: PermissionPrompt;
  onResolved: () => void;
}) {
  const [pending, setPending] = useState<'allowed_once' | 'cancelled' | null>(null);

  const respond = async (outcome: 'allowed_once' | 'cancelled') => {
    setPending(outcome);
    try {
      await api.resolveRunPermission(runId, prompt.prompt_id, outcome);
      toast.success(outcome === 'allowed_once' ? 'Permission granted' : 'Permission denied');
      onResolved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to resolve permission');
    } finally {
      setPending(null);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springSmooth}
      className="rounded-lg border border-warning/30 bg-warning/5 p-4"
    >
      <div className="flex items-center gap-2 text-sm font-medium text-warning">
        <ShieldQuestion className="size-4" />
        Permission requested
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        The agent paused for approval to run a tool. Allow it once to continue, or cancel to skip.
      </p>
      {prompt.tool_call && (
        <pre className="mt-3 overflow-auto rounded-md border border-warning/20 bg-background/40 p-2 text-[11px]">
          {JSON.stringify(prompt.tool_call, null, 2)}
        </pre>
      )}
      <div className="mt-3 flex gap-2">
        <Button
          size="sm"
          onClick={() => respond('allowed_once')}
          disabled={pending !== null}
          className="gap-1.5"
        >
          {pending === 'allowed_once' ? <Spinner /> : <ShieldCheck className="size-3.5" />}
          Allow once
        </Button>
        <Button
          size="sm"
          variant="outline"
          onClick={() => respond('cancelled')}
          disabled={pending !== null}
        >
          Cancel
        </Button>
      </div>
    </motion.div>
  );
}

interface StageCardProps {
  stage: StageName;
  stageExecution: StageExecution | undefined;
  liveReasoning: ReasoningChunk[];
  liveTokens: number;
  expanded: boolean;
  onToggle: () => void;
  isLive: boolean;
  fallbackAgent?: string;
  fallbackModel?: string;
}

const STAGE_DESC: Record<StageName, string> = {
  parse: 'Extract requirements from the document',
  analyze: 'Walk the codebase and inventory symbols',
  map: 'Link requirements to code symbols',
  generate: 'Generate pytest tests for each mapping',
  critique: 'Score the generated tests',
  trace: 'Build the traceability matrix and gap report',
};

function reasoningKindCounts(chunks: ReasoningChunk[]): Partial<Record<ReasoningKind, number>> {
  const counts: Partial<Record<ReasoningKind, number>> = {};
  for (const chunk of chunks) {
    counts[chunk.kind] = (counts[chunk.kind] ?? 0) + 1;
  }
  return counts;
}

/**
 * Pulls a "Try --model to switch to <id>" hint out of an adapter error.
 * The Claude Code adapter and a few others embed a recommended model id in
 * their 4xx responses; surfacing it as a one-click action saves the user a
 * trip to the docs.
 */
function extractSuggestedModel(error: string): string | null {
  const match = error.match(/Try\s+--model\s+to\s+switch\s+to\s+([^\s.]+)/i);
  return match ? match[1].replace(/[.,)]+$/, '') : null;
}

function StageErrorCard({ error }: { error: string }) {
  const suggested = extractSuggestedModel(error);
  const [copied, setCopied] = useState(false);

  const onCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
      <p className="leading-relaxed">{error}</p>
      {suggested && (
        <div className="mt-2 flex items-center gap-2 rounded border border-destructive/30 bg-background/40 px-2 py-1.5 text-foreground/80">
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">Try this model</span>
          <code className="font-mono text-[11px] truncate">{suggested}</code>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="ml-auto h-6 gap-1 px-2 text-[11px]"
            onClick={() => onCopy(suggested)}
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
            {copied ? 'Copied' : 'Copy id'}
          </Button>
        </div>
      )}
    </div>
  );
}

function StageCard({
  stage,
  stageExecution,
  liveReasoning,
  liveTokens,
  expanded,
  onToggle,
  isLive,
  fallbackAgent,
  fallbackModel,
}: StageCardProps) {
  const status: StageStatus = (stageExecution?.status as StageStatus) ?? 'pending';
  const persisted = stageExecution?.reasoning ?? [];
  const chunks = persisted.length >= liveReasoning.length ? persisted : liveReasoning;
  const tokens = sumTokenUsage(stageExecution?.token_usage) || liveTokens;
  const counts = reasoningKindCounts(chunks);
  const [outputCopied, setOutputCopied] = useState(false);
  const stageRunning = status === 'running';

  return (
    <motion.div layout className="rounded-xl border bg-card overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        className="relative w-full grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 px-4 py-3 text-left hover:bg-muted/30 transition-colors"
      >
        {stageRunning && (
          <span className="pointer-events-none absolute inset-x-0 bottom-0 h-px overflow-hidden">
            <span className="absolute inset-0 animate-beam bg-gradient-to-r from-transparent via-info/60 to-transparent" />
          </span>
        )}
        <StageStatusIcon status={status} />
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium capitalize">{stage}</span>
            <StatusBadge status={status} className="hidden sm:inline-flex" />
          </div>
          <p className="mt-0.5 text-[11px] text-muted-foreground/80 truncate">
            {STAGE_DESC[stage]}
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
          <span className="hidden md:inline-flex flex-col items-end leading-tight">
            <span>{stageExecution?.agent_id || fallbackAgent || '—'}</span>
            <span className="text-muted-foreground/60">
              {stageExecution?.model_id || fallbackModel || 'default'}
            </span>
          </span>
          <span className="hidden lg:inline-flex flex-col items-end leading-tight">
            <span>{formatLatency(stageExecution?.latency_ms)}</span>
            <span className="text-muted-foreground/60">{formatTokens(tokens)} tok</span>
          </span>
          <ChevronDown
            className={cn('size-4 text-muted-foreground/60 transition-transform', expanded && 'rotate-180')}
          />
        </div>
      </button>
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            key="body"
            layout
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden border-t bg-background/40"
          >
            <div className="grid gap-4 p-4 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Reasoning
                  </h4>
                  <div className="flex gap-2 text-[10px] text-muted-foreground">
                    {Object.entries(counts).map(([kind, count]) => (
                      <span key={kind} className="rounded border border-border/60 px-1.5 py-0.5 capitalize">
                        {kind.replace('_', ' ')}: {count}
                      </span>
                    ))}
                  </div>
                </div>
                <ReasoningStream chunks={chunks} isLive={stageRunning && isLive} maxHeight="360px" />
                {stageExecution?.error && <StageErrorCard error={stageExecution.error} />}
              </div>
              <div className="flex flex-col gap-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Output
                  </h4>
                  {stageExecution?.output_payload && (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-7 gap-1.5 text-xs"
                      onClick={() => {
                        navigator.clipboard.writeText(JSON.stringify(stageExecution.output_payload, null, 2));
                        setOutputCopied(true);
                        setTimeout(() => setOutputCopied(false), 1500);
                      }}
                    >
                      {outputCopied ? <Check className="size-3" /> : <Copy className="size-3" />}
                      Copy
                    </Button>
                  )}
                </div>
                <ScrollArea className="h-[360px] rounded-md border border-border/60 bg-muted/20 p-3">
                  <pre className="font-mono text-[11px] whitespace-pre-wrap leading-snug">
                    {stageExecution?.output_payload
                      ? JSON.stringify(stageExecution.output_payload, null, 2)
                      : status === 'pending'
                        ? 'Waiting for upstream stage to finish.'
                        : status === 'running'
                          ? 'Stage is still running. Output will appear when complete.'
                          : 'No output captured.'}
                  </pre>
                </ScrollArea>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;
  const queryClient = useQueryClient();
  // Tracks user-driven open/close intent. The currently-running stage is
  // ALWAYS auto-expanded (computed in `effectiveExpanded` below) without
  // mutating this state, so we don't trigger render cascades from effects.
  const [userExpanded, setUserExpanded] = useState<Record<StageName, boolean | undefined>>({
    parse: true,
    analyze: undefined,
    map: undefined,
    generate: undefined,
    critique: undefined,
    trace: undefined,
  });
  const [heartbeatTick, setHeartbeatTick] = useState(0);

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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['run', runId] }),
  });

  const isLive = run?.status === 'running' || run?.status === 'pending';
  const eventsUrl = isLive ? api.getRunEventsUrl(runId) : null;
  const { events, connectionState } = useEventStream(eventsUrl);

  // Heartbeat tick: every 1s while running, advance a counter so the
  // sub-stage progress bar nudges forward even if no events have arrived.
  useEffect(() => {
    if (!isLive) return;
    const id = setInterval(() => setHeartbeatTick((tick) => tick + 1), 1000);
    return () => clearInterval(id);
  }, [isLive]);

  const reasoning = useStreamedReasoning(events);

  const stagesByName = useMemo(() => {
    const map: Partial<Record<StageName, StageExecution>> = {};
    for (const stage of run?.stages ?? []) map[stage.stage as StageName] = stage;
    return map;
  }, [run?.stages]);

  const completedStages = STAGES.filter((stage) => stagesByName[stage]?.status === 'succeeded').length;
  const failedStages = STAGES.filter((stage) => stagesByName[stage]?.status === 'failed').length;
  const runningStage = STAGES.find((stage) => stagesByName[stage]?.status === 'running');

  // Effective expanded = explicit user choice OR the currently running stage.
  // Computing this in render keeps us out of effect-driven setState territory.
  const effectiveExpanded = useMemo<Record<StageName, boolean>>(() => {
    const result: Record<StageName, boolean> = {
      parse: false,
      analyze: false,
      map: false,
      generate: false,
      critique: false,
      trace: false,
    };
    for (const stage of STAGES) {
      const explicit = userExpanded[stage];
      if (typeof explicit === 'boolean') {
        result[stage] = explicit;
      } else if (runningStage === stage) {
        result[stage] = true;
      } else {
        result[stage] = false;
      }
    }
    return result;
  }, [userExpanded, runningStage]);

  // Sub-stage progress: combine event count and time elapsed since the stage
  // started so the bar always moves while a stage is alive.
  const subProgress = useMemo(() => {
    if (!runningStage) return 0;
    const reasoningCount =
      (stagesByName[runningStage]?.reasoning?.length ?? 0) +
      (reasoning.byStage[runningStage]?.length ?? 0);
    const reasoningProgress = Math.min(reasoningCount / ROLLING_AVG_FALLBACK, 0.85);
    // Heartbeat nudges add a slow ceiling-bound bump so the bar never freezes.
    const ticks = heartbeatTick % 30;
    const heartbeatProgress = Math.min(0.05 + ticks / 240, 0.15);
    return Math.min(reasoningProgress + heartbeatProgress, 0.92);
  }, [runningStage, stagesByName, reasoning.byStage, heartbeatTick]);

  const progressPct = ((completedStages + (runningStage ? subProgress : 0)) / STAGES.length) * 100;

  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-2 w-full" />
        <div className="flex flex-col gap-3">
          {STAGES.map((stage) => (
            <Skeleton key={stage} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (!run) {
    return (
      <div className="p-8">
        <p className="text-muted-foreground">Run not found.</p>
      </div>
    );
  }

  const canCancel = run.status === 'running' || run.status === 'pending';
  const tokensTotal = STAGES.reduce(
    (acc, stage) => acc + sumTokenUsage(stagesByName[stage]?.token_usage),
    0,
  );

  return (
    <PageWrapper className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
      <FadeIn>
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-3">
            <BackButton fallbackHref={`/projects/${run.project}`} />
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-xl font-semibold tracking-tight font-mono">Run {run.id.slice(0, 8)}</h1>
              <StatusBadge status={run.status} />
              <span className="hidden md:inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
                {connectionState === 'open' && <Wifi className="size-3 text-success" />}
                {connectionState === 'reconnecting' && <Spinner className="size-3" />}
                {connectionState === 'closed' && <WifiOff className="size-3 text-warning" />}
                {connectionState !== 'idle' && (
                  <span>
                    stream {connectionState}
                  </span>
                )}
              </span>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5">
                <Clock className="size-3.5" />
                {run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'pending'}
              </span>
              <Separator orientation="vertical" className="h-4" />
              <span>{run.project_name}</span>
              <Separator orientation="vertical" className="h-4" />
              <span className="tabular-nums">{formatTokens(tokensTotal)} tokens · {formatLatency(STAGES.reduce((acc, stage) => acc + (stagesByName[stage]?.latency_ms ?? 0), 0))}</span>
            </div>
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
      </FadeIn>

      <FadeIn>
        <div className="relative">
          <div className="h-1 bg-muted rounded-full overflow-hidden">
            <motion.div
              className={cn(
                'h-full rounded-full',
                failedStages > 0
                  ? 'bg-destructive'
                  : 'bg-gradient-to-r from-info via-success to-success',
              )}
              initial={{ width: 0 }}
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
            />
          </div>
          <div className="mt-1.5 flex items-center justify-between text-[11px] text-muted-foreground tabular-nums">
            <span>
              {completedStages} of {STAGES.length} complete
              {runningStage && ` · ${runningStage} streaming`}
            </span>
            <span>{Math.round(progressPct)}%</span>
          </div>
        </div>
      </FadeIn>

      {reasoning.permissions.length > 0 && (
        <FadeIn>
          <div className="flex flex-col gap-3">
            {reasoning.permissions.map((prompt) => (
              <PermissionPromptCard
                key={prompt.prompt_id}
                runId={runId}
                prompt={prompt}
                onResolved={() => queryClient.invalidateQueries({ queryKey: ['run', runId] })}
              />
            ))}
          </div>
        </FadeIn>
      )}

      <FadeIn>
        <div className="flex flex-col gap-3">
          {STAGES.map((stage) => {
            const stageExecution = stagesByName[stage];
            const liveReasoning = reasoning.byStage[stage] ?? [];
            return (
              <StageCard
                key={stage}
                stage={stage}
                stageExecution={stageExecution}
                liveReasoning={liveReasoning}
                liveTokens={0}
                expanded={effectiveExpanded[stage]}
                onToggle={() =>
                  setUserExpanded((prev) => ({
                    ...prev,
                    [stage]: !effectiveExpanded[stage],
                  }))
                }
                isLive={isLive}
                fallbackAgent={(run.config_snapshot?.agents as Array<Record<string, unknown>> | undefined)?.find(
                  (entry) => entry?.stage === stage,
                )?.agent_id as string | undefined}
                fallbackModel={(run.config_snapshot?.agents as Array<Record<string, unknown>> | undefined)?.find(
                  (entry) => entry?.stage === stage,
                )?.model_id as string | undefined}
              />
            );
          })}
        </div>
      </FadeIn>

      <FadeIn>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm">Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">
              Stage outputs are saved to{' '}
              <code className="font-mono text-[10px] bg-muted/40 px-1.5 py-0.5 rounded">
                {run.artifacts_path || `data/runs/${run.id}`}
              </code>
              . Fetch any stage output as JSON via{' '}
              <code className="font-mono text-[10px] bg-muted/40 px-1.5 py-0.5 rounded">
                GET /api/v1/runs/{run.id}/artifacts/&lt;stage&gt;.json
              </code>
              .
            </p>
          </CardContent>
        </Card>
      </FadeIn>
    </PageWrapper>
  );
}
