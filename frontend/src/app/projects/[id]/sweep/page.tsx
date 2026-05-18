/**
 * Sweep Evaluation page — multi-provider matrix builder, live reasoning, baseline diff.
 *
 * Three modes:
 *   1. Configure: pick (agent, model) rows × strategies × contexts. Server
 *      returns the expanded matrix via /sweeps/preview before submission.
 *   2. Active sweep: live progress card, embedded <ReasoningStream> for the
 *      currently-running run's most-active stage, run queue with stage dots.
 *   3. Completed sweep: rankings + "Lift vs Baseline" card + ANOVA report.
 *
 * Auto-reconnecting SSE keeps the page in sync with the server's replay buffer.
 */
'use client';

import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  BarChart3,
  Clock,
  ExternalLink,
  FileText,
  Play,
  Plus,
  Square,
  Trophy,
  TrendingUp,
  X,
  Wifi,
  WifiOff,
} from 'lucide-react';

import { BackButton } from '@/components/back-button';
import { PageWrapper, FadeIn, motion, AnimatePresence, springSmooth, springQuick } from '@/components/motion';
import { StatusBadge } from '@/components/status-badge';
import { ReasoningStream } from '@/components/reasoning-stream';
import { AgentModelPicker } from '@/components/agent-model-picker';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Spinner } from '@/components/ui/spinner';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { useEventStream } from '@/lib/sse';
import { cn } from '@/lib/utils';
import type {
  BaselineLift,
  BaselineSummary,
  ReasoningChunk,
  Run,
  StageName,
  StreamEvent,
  Sweep,
  SweepMetric,
} from '@/lib/types';

const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];
const INCLUDE_DIRECT_BASELINE = true;
const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

interface AgentRow {
  id: string;
  agent_id: string;
  model_id: string;
  isCustom: boolean;
}

interface AnovaResult {
  f_statistic?: number;
  p_value?: number;
  eta_squared?: number;
  significant?: boolean;
  significance?: string;
  effect_magnitude?: string;
  groups?: string[];
}

interface PairwiseComparison {
  pair?: string[];
  t_statistic?: number;
  p_value_bonferroni?: number;
  cohens_d?: number;
  significant?: boolean;
  significance?: string;
  cohens_d_magnitude?: string;
}

interface SweepStatsReport {
  anova?: Record<string, AnovaResult>;
  pairwise?: Record<string, PairwiseComparison[]>;
  markdown?: string;
  partial?: boolean;
  completed_configs?: number;
  total_configs?: number;
  [key: string]: unknown;
}

interface MetricChartDef {
  key: keyof SweepMetric;
  label: string;
  description: string;
  formatter: (value: unknown) => string;
  higherIsBetter: boolean;
  max?: number;
}

function metricNumber(value: unknown) {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

function metricPercent(value: unknown) {
  return `${(metricNumber(value) * 100).toFixed(1)}%`;
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

function label(value: string) {
  return value.replace(/_/g, ' ');
}

function configLabel(row: SweepMetric) {
  return `${label(String(row.prompt_strategy ?? 'strategy'))} · ${String(row.context_mode ?? 'context')}`;
}

function metricAgentLabel(row: SweepMetric) {
  return `${row.agent_id || 'agent'}/${row.model_id || 'default'}`;
}

function runConfigLabel(run: Run, fallback: Record<string, unknown> | undefined) {
  const snap = (run.config_snapshot ?? {}) as Record<string, unknown>;
  const strategy = String(snap.prompt_strategy || fallback?.prompt_strategy || '');
  const context = String(snap.context_mode || fallback?.context_mode || '');
  const agentId = String(snap.agent_id || fallback?.agent_id || '');
  const modelId = String(snap.model_id || fallback?.model_id || '');
  return { strategy, context, agentId, modelId };
}

function isActiveStatus(status: string) {
  return status === 'running' || status === 'pending';
}

function rankedMetrics(sweep?: Sweep | null) {
  return [...(sweep?.metrics_summary ?? [])].sort((a, b) => (a.rank ?? 9999) - (b.rank ?? 9999));
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
              status === 'running' && 'bg-info animate-pulse',
              status === 'failed' && 'bg-destructive',
              status === 'cancelled' && 'bg-warning',
              status === 'pending' && 'bg-muted-foreground/25',
              status === 'skipped' && 'border border-muted-foreground/40 bg-transparent',
            )}
          />
        );
      })}
    </div>
  );
}

function EventLine({ event }: { event: StreamEvent }) {
  const nested =
    event.event && typeof event.event === 'object' && !Array.isArray(event.event)
      ? (event.event as StreamEvent)
      : null;
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
                <motion.button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  whileHover={{ y: -2 }}
                  transition={springQuick}
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
                </motion.button>
              );
            })}
          </div>
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

function describeAgentRow(row: AgentRow) {
  const model = row.model_id.trim() || 'agent default';
  return `${row.agent_id} · ${model}`;
}

function LiftBadge({ value, suffix = '%' }: { value: number; suffix?: string }) {
  if (!Number.isFinite(value)) return <span className="text-muted-foreground">—</span>;
  const sign = value >= 0 ? '+' : '';
  return (
    <span className={cn('tabular-nums font-medium', value >= 0 ? 'text-success' : 'text-destructive')}>
      {sign}
      {value.toFixed(1)}
      {suffix}
    </span>
  );
}

function asStatsReport(value: Sweep['stats_report']): SweepStatsReport | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as SweepStatsReport;
}

function statsReportMarkdown(value: Sweep['stats_report']) {
  const report = asStatsReport(value);
  if (typeof report?.markdown === 'string' && report.markdown.trim()) return report.markdown;

  return `# Statistical Analysis Report\n\n\`\`\`json\n${JSON.stringify(value, null, 2)}\n\`\`\``;
}

function magnitudeClass(magnitude: string | undefined) {
  switch (magnitude) {
    case 'large':
      return 'border-success/40 bg-success/10 text-success';
    case 'medium':
      return 'border-info/40 bg-info/10 text-info';
    case 'small':
      return 'border-warning/40 bg-warning/10 text-warning';
    default:
      return 'border-muted bg-muted/40 text-muted-foreground';
  }
}

function metricBarClass(value: number, max: number, higherIsBetter: boolean) {
  const ratio = max > 0 ? value / max : 0;
  const normalized = higherIsBetter ? ratio : 1 - ratio;
  if (normalized >= 0.75) return 'bg-success';
  if (normalized >= 0.45) return 'bg-warning';
  return 'bg-destructive';
}

const COMPARISON_METRICS: MetricChartDef[] = [
  {
    key: 'quality_score',
    label: 'Quality',
    description: 'Static artifact score; generated tests are not executed yet',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'traceability_score',
    label: 'Traceability',
    description: 'Requirements covered or partially covered',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'strict_coverage_score',
    label: 'Strict coverage',
    description: 'Requirements fully covered',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'critique_accept_rate',
    label: 'Critique accept',
    description: 'Model-review decisions marked accept',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'generation_coverage_rate',
    label: 'Generated coverage',
    description: 'Parsed requirements with at least one generated test',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'mapped_requirements_rate',
    label: 'Mapped requirements',
    description: 'Parsed requirements linked to implementation symbols',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'mapping_confidence_avg',
    label: 'Map confidence',
    description: 'Average requirement-to-symbol confidence',
    formatter: metricPercent,
    higherIsBetter: true,
    max: 1,
  },
  {
    key: 'faiss_evidence_per_mapping',
    label: 'FAISS evidence',
    description: 'Evidence snippets attached per mapping',
    formatter: (value: unknown) => metricNumber(value).toFixed(1),
    higherIsBetter: true,
  },
  {
    key: 'latency_total_ms',
    label: 'Latency',
    description: 'Lower is better',
    formatter: (value: unknown) => formatElapsed(metricNumber(value)),
    higherIsBetter: false,
  },
];

const MARKDOWN_COMPONENTS: Components = {
  h1: ({ children }) => <h1 className="mb-4 text-xl font-semibold tracking-tight">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-6 mb-3 border-b pb-2 text-lg font-semibold">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-5 mb-2 text-base font-semibold">{children}</h3>,
  p: ({ children }) => <p className="my-3 text-sm leading-6">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
  ul: ({ children }) => <ul className="my-3 list-disc space-y-1 pl-5 text-sm">{children}</ul>,
  ol: ({ children }) => <ol className="my-3 list-decimal space-y-1 pl-5 text-sm">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  table: ({ children }) => (
    <div className="my-4 overflow-x-auto rounded-md border">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-muted/50">{children}</thead>,
  th: ({ children }) => <th className="border-b px-3 py-2 text-left font-medium text-muted-foreground">{children}</th>,
  td: ({ children }) => <td className="border-b px-3 py-2 align-top">{children}</td>,
  code: ({ children, className }) => (
    <code className={cn('rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]', className)}>{children}</code>
  ),
  pre: ({ children }) => <pre className="my-3 overflow-auto rounded-md border bg-muted/30 p-3 text-xs">{children}</pre>,
};

function StatisticalReportFile({ report }: { report: Sweep['stats_report'] }) {
  const markdown = statsReportMarkdown(report);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-base">Statistical Report</CardTitle>
            <CardDescription className="mt-1">
              Rendered as a Markdown file with Preview selected by default.
            </CardDescription>
          </div>
          <div className="inline-flex items-center gap-2 rounded-md border bg-muted/20 px-2.5 py-1 text-xs text-muted-foreground">
            <FileText className="size-3.5" />
            <span className="font-mono">statistical-report.md</span>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="preview" className="gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <TabsList>
              <TabsTrigger value="preview">Preview</TabsTrigger>
              <TabsTrigger value="source">Markdown</TabsTrigger>
            </TabsList>
            <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">.md</span>
          </div>
          <TabsContent value="preview" className="mt-0">
            <ScrollArea className="max-h-[560px] rounded-md border bg-background">
              <div className="p-5">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>
                  {markdown}
                </ReactMarkdown>
              </div>
            </ScrollArea>
          </TabsContent>
          <TabsContent value="source" className="mt-0">
            <pre className="max-h-[560px] overflow-auto rounded-md border bg-muted/20 p-4 font-mono text-xs whitespace-pre-wrap">
              {markdown}
            </pre>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}

function MetricComparisonCharts({ metrics }: { metrics: SweepMetric[] }) {
  return (
    <Card className="lg:col-span-2">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <BarChart3 className="size-4" />
          All Configuration Graphs
        </CardTitle>
        <CardDescription>
          Color-coded comparison across stored sweep rows. Green is stronger, yellow is middle, red needs attention.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4 lg:grid-cols-2">
          {COMPARISON_METRICS.map((metric) => {
            const values = metrics.map((row) => metricNumber(row[metric.key]));
            const max = metric.max ?? Math.max(...values, 1);
            return (
              <div key={metric.key} className="rounded-md border p-3">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{metric.label}</p>
                    <p className="text-xs text-muted-foreground">{metric.description}</p>
                  </div>
                  <span className="rounded-full border px-2 py-0.5 text-[11px] text-muted-foreground">
                    {metric.higherIsBetter ? 'higher wins' : 'lower wins'}
                  </span>
                </div>
                <div className="space-y-3">
                  {metrics.map((row) => {
                    const value = metricNumber(row[metric.key]);
                    const width = max > 0 ? Math.max(2, Math.min(100, (value / max) * 100)) : 2;
                    return (
                      <div key={`${metric.key}-${row.run_id ?? configLabel(row)}`}>
                        <div className="mb-1 flex justify-between gap-3 text-xs">
                          <span className="truncate">
                            #{row.rank ?? '-'} {configLabel(row)}
                          </span>
                          <span className="tabular-nums">{metric.formatter(value)}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-muted">
                          <motion.div
                            className={cn('h-full rounded-full', metricBarClass(value, max, metric.higherIsBetter))}
                            initial={{ width: 0 }}
                            animate={{ width: `${width}%` }}
                            transition={springSmooth}
                          />
                        </div>
                        <div className="mt-0.5 truncate text-[10px] text-muted-foreground">
                          {row.agent_id || 'agent'}/{row.model_id || 'default'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function StatisticalInsightsCard({ stats }: { stats: SweepStatsReport | null }) {
  const anovaEntries = Object.entries(stats?.anova ?? {});
  const largePairs = Object.entries(stats?.pairwise ?? {}).flatMap(([metric, pairs]) =>
    pairs
      .filter((pair) => pair.cohens_d_magnitude === 'large')
      .map((pair) => ({ metric, ...pair })),
  );
  const isPartial = Boolean(stats?.partial);

  if (anovaEntries.length === 0 && largePairs.length === 0 && !isPartial) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Statistical Significance</CardTitle>
        <CardDescription>
          ANOVA shows whether an axis matters; eta-squared and Cohen&apos;s d show practical effect magnitude.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isPartial && (
          <div className="rounded-md border border-warning/40 bg-warning/5 p-3 text-xs text-warning">
            Statistical results are partial: {formatInteger(stats?.completed_configs)} of{' '}
            {formatInteger(stats?.total_configs)} configurations produced reliable metrics.
          </div>
        )}

        {anovaEntries.length > 0 && (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {anovaEntries.map(([key, result]) => (
              <div
                key={key}
                className={cn(
                  'rounded-md border p-3',
                  result.significant ? magnitudeClass(result.effect_magnitude) : 'bg-muted/20',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="truncate text-sm font-medium">{label(key)}</p>
                  <span className="rounded-full border px-2 py-0.5 text-[11px]">{result.significance ?? 'ns'}</span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <span>
                    <span className="text-muted-foreground">p</span> {metricNumber(result.p_value).toFixed(4)}
                  </span>
                  <span>
                    <span className="text-muted-foreground">η²</span> {metricNumber(result.eta_squared).toFixed(3)}
                  </span>
                  <span className="capitalize">{result.effect_magnitude ?? 'n/a'}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {largePairs.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm font-medium">Large Cohen&apos;s d comparisons</p>
            <div className="grid gap-2 lg:grid-cols-2">
              {largePairs.slice(0, 8).map((pair, index) => (
                <div key={`${pair.metric}-${index}`} className="rounded-md border border-success/40 bg-success/5 p-3">
                  <div className="text-xs font-medium">{label(pair.metric)}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {(pair.pair ?? []).join(' vs ') || 'pairwise comparison'}
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span>Bonferroni p {metricNumber(pair.p_value_bonferroni).toFixed(4)}</span>
                    <span className="font-medium text-success">d={metricNumber(pair.cohens_d).toFixed(2)} large</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function BaselineSummaryCard({ summary }: { summary: BaselineSummary | null | undefined }) {
  if (!summary?.baseline || !summary.lifts || summary.lifts.length === 0) return null;
  const winner = summary.lifts[0]; // already ordered by rank in the API.
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="size-4" />
          Lift vs Baseline Configuration
        </CardTitle>
        <CardDescription>
          Baseline: <span className="font-mono">{summary.baseline.label}</span>
          {' · quality '}
          {metricPercent(summary.baseline.metrics?.quality_score ?? 0)}, latency{' '}
          {Math.round(summary.baseline.metrics?.latency_total_ms ?? 0)}ms, tokens{' '}
          {Math.round(summary.baseline.metrics?.tokens_total ?? 0)}.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-5">
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">Winner</p>
            <p className="mt-1 truncate text-sm font-medium font-mono">{winner.label ?? '—'}</p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">Δ Quality</p>
            <p className="mt-1 text-sm">
              <LiftBadge value={metricNumber(winner.lift?.quality_score)} />
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">Δ Traceability</p>
            <p className="mt-1 text-sm">
              <LiftBadge value={metricNumber(winner.lift?.traceability_score)} />
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">Δ Latency</p>
            <p className="mt-1 text-sm">
              <LiftBadge value={metricNumber(winner.lift?.latency_total_ms)} />
            </p>
          </div>
          <div className="rounded-md border p-3">
            <p className="text-xs text-muted-foreground">Δ Tokens</p>
            <p className="mt-1 text-sm">
              <LiftBadge value={metricNumber(winner.lift?.tokens_total)} />
            </p>
          </div>
        </div>
        <div className="overflow-hidden rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Configuration</TableHead>
                <TableHead className="text-right">Δ Quality</TableHead>
                <TableHead className="text-right">Δ Trace</TableHead>
                <TableHead className="text-right">Δ Accept</TableHead>
                <TableHead className="text-right">Δ Latency</TableHead>
                <TableHead className="text-right">Δ Tokens</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {summary.lifts.map((lift: BaselineLift, index: number) => (
                <TableRow key={lift.run_id ?? lift.label ?? `lift-${index}`}>
                  <TableCell className="font-mono text-xs">#{lift.rank ?? '-'}</TableCell>
                  <TableCell className="font-mono text-xs">{lift.label}</TableCell>
                  <TableCell className="text-right">
                    <LiftBadge value={metricNumber(lift.lift?.quality_score)} />
                  </TableCell>
                  <TableCell className="text-right">
                    <LiftBadge value={metricNumber(lift.lift?.traceability_score)} />
                  </TableCell>
                  <TableCell className="text-right">
                    <LiftBadge value={metricNumber(lift.lift?.critique_accept_rate)} />
                  </TableCell>
                  <TableCell className="text-right">
                    <LiftBadge value={metricNumber(lift.lift?.latency_total_ms)} />
                  </TableCell>
                  <TableCell className="text-right">
                    <LiftBadge value={metricNumber(lift.lift?.tokens_total)} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
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
  const [strategyEnabled, setStrategyEnabled] = useState<boolean[]>(Array(16).fill(true));
  // Default to a single Codex/GPT-5.5 row. Once project data loads, the user
  // can pick a different default; we deliberately don't auto-overwrite their
  // edits, so initialisation happens once via lazy useState.
  const [agentRows, setAgentRows] = useState<AgentRow[]>(() => [
    { id: 'row-0', agent_id: 'codex', model_id: '', isCustom: false },
  ]);

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
  const activeRun =
    activeSweep?.runs?.find((r) => r.status === 'running') ?? activeSweep?.runs?.find((r) => r.status === 'pending');
  const { data: activeRunDetail } = useQuery({
    queryKey: ['run', activeRun?.id],
    queryFn: () => api.getRun(activeRun!.id),
    enabled: !!activeRun?.id,
    refetchInterval: activeRun ? 1200 : false,
  });

  const eventsUrl =
    activeSweep && isActiveStatus(activeSweep.status) ? api.getSweepEventsUrl(activeSweep.id) : null;
  const { events, connectionState } = useEventStream(eventsUrl);

  const enabledStrategyContextPairs = useMemo(
    () =>
      STRATEGIES.flatMap((strategy, sIdx) =>
        CONTEXT_MODES.flatMap((context, cIdx) =>
          strategyEnabled[sIdx * CONTEXT_MODES.length + cIdx]
            ? [{ prompt_strategy: strategy, context_mode: context }]
            : [],
        ),
      ),
    [strategyEnabled],
  );

  const baselineCells = INCLUDE_DIRECT_BASELINE ? agentRows.length : 0;
  const totalCells = agentRows.length * enabledStrategyContextPairs.length + baselineCells;

  const startSweepMutation = useMutation({
    mutationFn: () =>
      // Use the `pairs` axes so each enabled strategy/context cell becomes
      // exactly one run per agent (instead of the legacy cartesian product
      // which multiplied 16 enabled cells into 256 runs).
      api.createSweepFromAxes(projectId, {
        agents: agentRows.map((row) => ({ agent_id: row.agent_id, model_id: row.model_id.trim() })),
        include_direct_baseline: INCLUDE_DIRECT_BASELINE,
        pairs: enabledStrategyContextPairs,
      }),
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

  const totalConfigs = activeSweep?.matrix.length || totalCells;
  const finishedRuns =
    activeSweep?.runs?.filter((r) => ['succeeded', 'failed', 'cancelled'].includes(r.status)).length ?? 0;
  const progress = totalConfigs ? Math.round((finishedRuns / totalConfigs) * 100) : 0;
  const elapsed = useElapsed(activeSweep?.created_at ?? null, activeSweep?.status === 'running');
  const metrics = rankedMetrics(activeSweep);
  const statsReport = asStatsReport(activeSweep?.stats_report ?? null);
  const orderedRuns = useMemo(
    () =>
      [...(activeSweep?.runs ?? [])].sort(
        (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      ),
    [activeSweep?.runs],
  );
  const bestMetric = metrics.find((row) => row.is_winner) ?? metrics[0];
  const degenerateMetrics = metrics.filter(
    (row) => metricNumber(row.total_requirements) === 0 || metricNumber(row.generated_tests_count) === 0,
  ).length;
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

  // Build the live reasoning stream for the active run by collecting nested
  // sweep_run_event entries that carry a stage_reasoning subevent.
  const liveReasoningChunks: ReasoningChunk[] = useMemo(() => {
    if (!activeRun) return [];
    const out: ReasoningChunk[] = [];
    for (const evt of events) {
      const inner = (evt.event && typeof evt.event === 'object' ? evt.event : evt) as StreamEvent;
      if (
        inner.type === 'stage_reasoning' &&
        evt.run_id === activeRun.id &&
        inner.payload &&
        typeof inner.payload === 'object'
      ) {
        const chunk = inner.payload as unknown as ReasoningChunk;
        if (chunk && typeof chunk.kind === 'string') {
          out.push(chunk);
        }
      }
    }
    return out;
  }, [events, activeRun]);

  const addAgentRow = () => {
    const last = agentRows[agentRows.length - 1];
    setAgentRows((prev) => [
      ...prev,
      {
        id: `row-${Date.now()}`,
        agent_id: last?.agent_id || 'codex',
        model_id: '',
        isCustom: false,
      },
    ]);
  };

  const removeAgentRow = (id: string) => {
    setAgentRows((prev) => (prev.length === 1 ? prev : prev.filter((row) => row.id !== id)));
  };

  const updateAgentRow = (id: string, patch: Partial<AgentRow>) => {
    setAgentRows((prev) => prev.map((row) => (row.id === id ? { ...row, ...patch } : row)));
  };

  return (
    <PageWrapper className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <FadeIn>
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-3">
            <BackButton fallbackHref={`/projects/${projectId}`} />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">Sweep Evaluation</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {project?.name ?? 'Project'} · compare any provider, model, prompt strategy, and context mode in one matrix.
                {connectionState === 'open' && eventsUrl && (
                  <span className="ml-2 inline-flex items-center gap-1 text-success">
                    <Wifi className="size-3" /> live
                  </span>
                )}
                {connectionState === 'reconnecting' && (
                  <span className="ml-2 inline-flex items-center gap-1 text-warning">
                    <Spinner className="size-3" /> reconnecting
                  </span>
                )}
                {connectionState === 'closed' && (
                  <span className="ml-2 inline-flex items-center gap-1 text-warning">
                    <WifiOff className="size-3" /> stream closed
                  </span>
                )}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {activeSweep && isActiveStatus(activeSweep.status) && (
              <Button variant="destructive" onClick={() => cancelSweepMutation.mutate()} disabled={cancelSweepMutation.isPending}>
                {cancelSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <Square data-icon="inline-start" />}
                {cancelSweepMutation.isPending ? 'Cancelling…' : 'Stop'}
              </Button>
            )}
            {activeSweep && !isActiveStatus(activeSweep.status) && (
              <Button variant="outline" onClick={() => setShowConfig(true)}>
                <Plus data-icon="inline-start" />
                New sweep
              </Button>
            )}
            {!activeSweep && (
              <Button
                onClick={() => startSweepMutation.mutate()}
                disabled={startSweepMutation.isPending || totalCells === 0 || agentRows.length === 0}
              >
                {startSweepMutation.isPending ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
                Start {totalCells} runs
              </Button>
            )}
          </div>
        </div>
      </FadeIn>

      <FadeIn>
        <SweepHistory sweeps={projectSweeps} activeSweepId={activeSweep?.id ?? sweepId} onSelect={selectSweep} />
      </FadeIn>

      {!activeSweep && sweepId && (
        <FadeIn>
          <Card>
            <CardContent className="flex h-32 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Spinner data-icon="inline-start" />
              Loading saved sweep
            </CardContent>
          </Card>
        </FadeIn>
      )}

      {!activeSweep && !sweepId && (
        <FadeIn>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Configuration Matrix</CardTitle>
              <CardDescription>
                Add one or more (provider, model) rows. Then tick the strategy×context cells to compare. The total
                number of runs is the product of all three axes — keep an eye on the cost summary.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-medium">Providers &amp; models</h3>
                  <Button variant="outline" size="sm" onClick={addAgentRow}>
                    <Plus data-icon="inline-start" />
                    Add row
                  </Button>
                </div>
                <div className="space-y-2">
                  <AnimatePresence initial={false}>
                    {agentRows.map((row) => (
                      <motion.div
                        key={row.id}
                        layout
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -6 }}
                        transition={springSmooth}
                        className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-start"
                      >
                        <div className="flex-1 min-w-0">
                          <AgentModelPicker
                            agents={agents}
                            agentId={row.agent_id}
                            modelId={row.model_id}
                            isCustom={row.isCustom}
                            onAgentChange={(agentId) =>
                              updateAgentRow(row.id, { agent_id: agentId, model_id: '', isCustom: false })
                            }
                            onModelChange={({ modelId, isCustom }) => updateAgentRow(row.id, { model_id: modelId, isCustom })}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="size-8"
                          onClick={() => removeAgentRow(row.id)}
                          disabled={agentRows.length === 1}
                          aria-label="Remove row"
                        >
                          <X className="size-4" />
                        </Button>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              </section>

              <section className="space-y-3">
                <h3 className="text-sm font-medium">Prompt strategy × context mode</h3>
                <div className="overflow-hidden rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Prompt strategy</TableHead>
                        {CONTEXT_MODES.map((mode) => (
                          <TableHead key={mode} className="text-center capitalize">
                            {mode}
                          </TableHead>
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
                                  checked={strategyEnabled[index]}
                                  onCheckedChange={(checked) => {
                                    const next = [...strategyEnabled];
                                    next[index] = checked;
                                    setStrategyEnabled(next);
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
              </section>

              <section className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Providers × models</p>
                  <p className="mt-1 text-sm font-medium">{agentRows.length}</p>
                </div>
                <div className="rounded-md border p-3">
                  <p className="text-xs text-muted-foreground">Strategy × context cells</p>
                  <p className="mt-1 text-sm font-medium">
                    {enabledStrategyContextPairs.length}/16
                    {INCLUDE_DIRECT_BASELINE && (
                      <span className="ml-2 text-[11px] text-muted-foreground">+ direct ACP baseline</span>
                    )}
                  </p>
                </div>
                <div className={cn('rounded-md border p-3', totalCells > 32 && 'border-warning/40 bg-warning/5')}>
                  <p className="text-xs text-muted-foreground">Total runs</p>
                  <p className="mt-1 text-sm font-medium tabular-nums">
                    {totalCells}
                    {totalCells > 32 && (
                      <span className="ml-2 text-[11px] text-warning">large sweep — expect long wall time</span>
                    )}
                  </p>
                </div>
              </section>

              {agentRows.length > 0 && (
                <p className="text-xs text-muted-foreground">
                  Will run: {agentRows.map(describeAgentRow).join(', ')}.
                </p>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      )}

      {activeSweep && (
        <>
          <FadeIn>
            <div className="grid gap-3 md:grid-cols-5">
              {[
                ['Status', <StatusBadge key="status" status={activeSweep.status} />],
                ['Progress', `${finishedRuns}/${totalConfigs}`],
                ['Elapsed', formatElapsed(elapsed)],
                ['ETA', activeSweep.status === 'running' ? eta : 'complete'],
                [
                  'Winner',
                  bestMetric ? `${configLabel(bestMetric)} · ${metricAgentLabel(bestMetric)}` : 'pending',
                ],
              ].map(([title, value]) => (
                <Card key={String(title)}>
                  <CardContent className="p-4">
                    <p className="text-xs text-muted-foreground">{title}</p>
                    <div className="mt-2 truncate text-sm font-medium tabular-nums">{value}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </FadeIn>

          <FadeIn>
            <Card>
              <CardContent className="p-4">
                <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                  <span>Overall progress</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <motion.div
                    className="h-full rounded-full bg-foreground"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={springSmooth}
                  />
                </div>
              </CardContent>
            </Card>
          </FadeIn>

          {activeSweep.baseline_summary && (
            <FadeIn>
              <BaselineSummaryCard summary={activeSweep.baseline_summary} />
            </FadeIn>
          )}

          {bestMetric && !activeSweep.baseline_summary && (
            <FadeIn>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Trophy className="size-4" />
                    Best Performer
                  </CardTitle>
                  <CardDescription>
                    Ranked by quality score first, then traceability, lower latency, and token cost.
                  </CardDescription>
                </CardHeader>
                <CardContent className="grid gap-3 md:grid-cols-6">
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Configuration</p>
                    <p className="mt-1 truncate text-sm font-medium">
                      {label(String(bestMetric.prompt_strategy))} / {bestMetric.context_mode}
                      {' · '}
                      {metricAgentLabel(bestMetric)}
                    </p>
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
                    <p className="text-xs text-muted-foreground">Tests / reqs</p>
                    <p className="mt-1 text-sm font-medium">
                      {formatInteger(bestMetric.generated_tests_count)} / {formatInteger(bestMetric.total_requirements)}
                    </p>
                  </div>
                  <div className="rounded-md border p-3">
                    <p className="text-xs text-muted-foreground">Latency</p>
                    <p className="mt-1 text-sm font-medium">{formatElapsed(metricNumber(bestMetric.latency_total_ms))}</p>
                  </div>
                </CardContent>
              </Card>
            </FadeIn>
          )}

          <FadeIn>
            <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Run Queue</CardTitle>
                  <CardDescription>{orderedRuns.length} runs created. Each row links to the run detail page.</CardDescription>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[460px]">
                    <div className="space-y-2 pr-3">
                      {orderedRuns.map((run, index) => {
                        const cell = activeSweep.matrix[index] ?? {};
                        const { strategy, context, agentId, modelId } = runConfigLabel(run, cell);
                        return (
                          <div
                            key={run.id}
                            className="grid grid-cols-[36px_1fr_auto_auto] items-center gap-3 rounded-md border p-3"
                          >
                            <span className="text-right text-xs text-muted-foreground">{index + 1}</span>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium">
                                {label(strategy)} · {context}
                              </div>
                              <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted-foreground">
                                <span className="font-mono truncate">{agentId}/{modelId || 'default'}</span>
                              </div>
                              <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
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
                  <CardTitle className="text-base">Live Reasoning</CardTitle>
                  <CardDescription>
                    {activeRunDetail ? (
                      <>
                        <span className="font-mono">{activeRunDetail.id.slice(0, 8)}</span> ·
                        {' '}
                        {STAGES.find((stage) => activeRunDetail.stages?.find((s) => s.stage === stage)?.status === 'running') ||
                          'finishing'}
                      </>
                    ) : (
                      'Waiting for the next run.'
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {activeRunDetail ? (
                    <div className="flex flex-col gap-3">
                      <ReasoningStream
                        chunks={
                          STAGES.flatMap(
                            (stage) =>
                              activeRunDetail.stages?.find((s) => s.stage === stage)?.reasoning ?? [],
                          ).concat(liveReasoningChunks)
                        }
                        isLive={isActiveStatus(activeSweep.status)}
                        maxHeight="380px"
                        emptyMessage="No reasoning yet for this run."
                      />
                      <Link
                        href={`/projects/${projectId}/runs/${activeRunDetail.id}`}
                        className="text-xs text-info hover:underline self-end"
                      >
                        Open full run detail →
                      </Link>
                    </div>
                  ) : (
                    <div className="flex h-[300px] items-center justify-center text-sm text-muted-foreground">
                      No active run yet.
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </FadeIn>

          <FadeIn>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Event Log</CardTitle>
                <CardDescription>Last 80 SSE events from this sweep (auto-reconnects on transient errors).</CardDescription>
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
          </FadeIn>

          {metrics.length > 0 && (
            <FadeIn>
              <div className="grid gap-4 lg:grid-cols-2">
                <MetricComparisonCharts metrics={metrics} />

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
                    {degenerateMetrics > 0 && (
                      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive">
                        {degenerateMetrics} completed metric row(s) have zero parsed requirements or zero generated tests, so quality is degraded.
                      </div>
                    )}
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
                              <TableCell>
                                {configLabel(row)}
                                <div className="text-[11px] text-muted-foreground">{metricAgentLabel(row)}</div>
                              </TableCell>
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
            </FadeIn>
          )}

          {metrics.length > 0 && (
            <FadeIn>
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
                          <TableHead className="text-right">Reqs</TableHead>
                          <TableHead>Provider</TableHead>
                          <TableHead>Model</TableHead>
                          <TableHead className="text-right">Tests</TableHead>
                          <TableHead className="text-right">Gen cov.</TableHead>
                          <TableHead className="text-right">Mapped</TableHead>
                          <TableHead className="text-right">Strict</TableHead>
                          <TableHead className="text-right">FAISS</TableHead>
                          <TableHead className="text-right">Map conf.</TableHead>
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
                                <Link
                                  href={`/projects/${projectId}/runs/${row.run_id}`}
                                  className="font-mono text-xs hover:underline"
                                >
                                  {row.run_id.slice(0, 8)}
                                </Link>
                              ) : (
                                <span className="text-muted-foreground">n/a</span>
                              )}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">{formatInteger(row.total_requirements)}</TableCell>
                            <TableCell>{row.agent_id || 'agent'}</TableCell>
                            <TableCell className="max-w-[180px] truncate font-mono text-xs">
                              {row.model_id || 'agent default'}
                            </TableCell>
                            <TableCell className="text-right tabular-nums">{formatInteger(row.generated_tests_count)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.generation_coverage_rate)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.mapped_requirements_rate)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.strict_coverage_score)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricNumber(row.faiss_evidence_per_mapping).toFixed(1)}</TableCell>
                            <TableCell className="text-right tabular-nums">{metricPercent(row.mapping_confidence_avg)}</TableCell>
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
            </FadeIn>
          )}

          {statsReport && (
            <FadeIn>
              <StatisticalInsightsCard stats={statsReport} />
            </FadeIn>
          )}

          {activeSweep.stats_report && (
            <FadeIn>
              <StatisticalReportFile report={activeSweep.stats_report} />
            </FadeIn>
          )}
        </>
      )}
    </PageWrapper>
  );
}
