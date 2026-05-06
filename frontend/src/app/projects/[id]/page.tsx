/**
 * projects/[id]/page.tsx — Project detail page with tabbed navigation.
 *
 * This is the main hub for managing a project. It displays three tabs:
 *
 *   1. Overview — Project metadata (paths, language, framework), quick
 *      stats, and action buttons for running the pipeline or starting a sweep.
 *
 *   2. Agents — Configuration table for all 6 pipeline stages. Each row lets
 *      the user select which ACP agent to use, which prompt strategy to apply,
 *      and what level of context to include. Changes are saved via PATCH.
 *
 *   3. Runs — Paginated table of all pipeline runs for this project, with
 *      status badges and links to the run detail page.
 *
 * Design: dense information layout with subtle borders, matching the
 * "Linear/Vercel/GitHub Primer" aesthetic specified in the implementation doc.
 */
'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/components/status-badge';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import {
  Play,
  BarChart3,
  Save,
  Code,
  FileText,
  Loader2,
  FolderOpen,
  ArrowRight,
} from 'lucide-react';
import type { AgentSpec, StageName } from '@/lib/types';

// ---------------------------------------------------------------------------
// Constants — the 6 pipeline stages and their configuration options
// ---------------------------------------------------------------------------

/** All pipeline stages in execution order */
const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];

/** The four prompt engineering strategies available for each stage */
const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];

/** The four context inclusion levels — from minimal to full project context */
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];

/** Human-readable descriptions for each pipeline stage */
const STAGE_DESCRIPTIONS: Record<string, string> = {
  parse: 'Extract requirements from the document',
  analyze: 'Walk the codebase and build symbol inventory',
  map: 'Map requirements to implementing code symbols',
  generate: 'Generate pytest tests for each mapping',
  critique: 'Score tests on relevance, completeness, correctness',
  trace: 'Build traceability matrix and gap report',
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = params.id as string;

  // Fetch project details (including agent configs) from the API
  const { data: project, isLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId),
  });

  // Fetch the global list of available ACP agents for the agent picker dropdowns
  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });

  /**
   * Local state for unsaved agent config changes.
   * Maps stage name -> { agent_id, prompt_strategy, context_mode }.
   * Only populated when the user makes changes; empty means "use server values".
   */
  const [agentConfigs, setAgentConfigs] = useState<
    Record<string, { agent_id: string; prompt_strategy: string; context_mode: string }>
  >({});

  // Mutation: save the agent configuration for all 6 stages via PATCH
  const saveAgentsMutation = useMutation({
    mutationFn: (configs: Record<string, unknown>[]) =>
      api.updateProjectAgents(projectId, configs),
    onSuccess: () => {
      // Refetch the project to get updated agent configs
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      setAgentConfigs({}); // Clear local overrides since they're now saved
    },
  });

  // Mutation: start a new pipeline run and navigate to its detail page
  const runPipelineMutation = useMutation({
    mutationFn: () => api.createRun(projectId),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
      router.push(`/projects/${projectId}/runs/${run.id}`);
    },
  });

  /**
   * Get the effective config for a stage: local override > server value > default.
   * This allows the user to make changes without immediately saving.
   */
  const getStageConfig = (stage: StageName) => {
    const existing = project?.agents?.find((a) => a.stage === stage);
    const override = agentConfigs[stage];
    return {
      agent_id: override?.agent_id || existing?.agent_id || 'claude-code',
      prompt_strategy: override?.prompt_strategy || existing?.prompt_strategy || 'zero_shot',
      context_mode: override?.context_mode || existing?.context_mode || 'full',
    };
  };

  /** Update a single field of a stage's config in local state */
  const updateStageConfig = (stage: StageName, field: string, value: string | null) => {
    if (!value) return;
    setAgentConfigs((prev) => ({
      ...prev,
      [stage]: { ...getStageConfig(stage), [field]: value },
    }));
  };

  /** Collect all 6 stages' configs and send them to the API */
  const handleSaveAgents = () => {
    const configs = STAGES.map((stage) => ({
      stage,
      ...getStageConfig(stage),
      enabled: true,
    }));
    saveAgentsMutation.mutate(configs);
  };

  // Check if user has unsaved changes to highlight the save button
  const hasUnsavedChanges = Object.keys(agentConfigs).length > 0;

  // Loading skeleton while project data is being fetched
  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="p-8 max-w-6xl mx-auto">
        <p className="text-muted-foreground">Project not found.</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      {/* ---- Page header with project name and action buttons ---- */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
          <div className="flex items-center gap-2 mt-1.5 text-sm text-muted-foreground">
            <Code className="h-3.5 w-3.5" />
            <span>{project.language}</span>
            <span className="text-muted-foreground/40">|</span>
            <span>{project.test_framework}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => runPipelineMutation.mutate()}
            disabled={runPipelineMutation.isPending}
          >
            {runPipelineMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Run pipeline
          </Button>
          <Link href={`/projects/${projectId}/sweep`}>
            <Button variant="outline">
              <BarChart3 className="mr-2 h-4 w-4" />
              Start sweep
            </Button>
          </Link>
        </div>
      </div>

      {/* ---- Tabbed content area ---- */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>

        {/* ---- OVERVIEW TAB ---- */}
        <TabsContent value="overview" className="space-y-4 mt-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Code path card */}
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <Code className="h-4 w-4" />
                  Code directory
                </div>
                <code className="text-sm font-mono bg-muted px-3 py-1.5 rounded-md block truncate">
                  {project.code_path}
                </code>
              </CardContent>
            </Card>
            {/* Requirements path card */}
            <Card>
              <CardContent className="p-5">
                <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                  <FileText className="h-4 w-4" />
                  Requirements document
                </div>
                <code className="text-sm font-mono bg-muted px-3 py-1.5 rounded-md block truncate">
                  {project.requirements_path}
                </code>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ---- AGENTS TAB ---- */}
        <TabsContent value="agents" className="space-y-4 mt-4">
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base">Agent configuration</CardTitle>
                  <CardDescription>
                    Select an ACP agent, prompt strategy, and context level for each pipeline stage.
                  </CardDescription>
                </div>
                <Button
                  onClick={handleSaveAgents}
                  disabled={saveAgentsMutation.isPending || !hasUnsavedChanges}
                  variant={hasUnsavedChanges ? 'default' : 'outline'}
                  size="sm"
                >
                  {saveAgentsMutation.isPending ? (
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Save className="mr-1.5 h-3.5 w-3.5" />
                  )}
                  Save agent config
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[180px]">Stage</TableHead>
                      <TableHead>Agent</TableHead>
                      <TableHead>Prompt Strategy</TableHead>
                      <TableHead>Context Mode</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {STAGES.map((stage) => {
                      const config = getStageConfig(stage);
                      return (
                        <TableRow key={stage}>
                          {/* Stage name + description */}
                          <TableCell>
                            <div>
                              <span className="font-medium capitalize text-sm">{stage}</span>
                              <p className="text-[11px] text-muted-foreground mt-0.5">
                                {STAGE_DESCRIPTIONS[stage]}
                              </p>
                            </div>
                          </TableCell>
                          {/* Agent picker — disabled agents show tooltip */}
                          <TableCell>
                            <Select
                              value={config.agent_id}
                              onValueChange={(v) => updateStageConfig(stage, 'agent_id', v)}
                            >
                              <SelectTrigger className="w-[160px] h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {agents.map((a: AgentSpec) => (
                                  <SelectItem key={a.id} value={a.id} disabled={!a.available}>
                                    {a.display_name}
                                    {!a.available && ' (unavailable)'}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          {/* Prompt strategy picker */}
                          <TableCell>
                            <Select
                              value={config.prompt_strategy}
                              onValueChange={(v) => updateStageConfig(stage, 'prompt_strategy', v)}
                            >
                              <SelectTrigger className="w-[160px] h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {STRATEGIES.map((s) => (
                                  <SelectItem key={s} value={s}>
                                    {s.replace(/_/g, ' ')}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          {/* Context mode picker */}
                          <TableCell>
                            <Select
                              value={config.context_mode}
                              onValueChange={(v) => updateStageConfig(stage, 'context_mode', v)}
                            >
                              <SelectTrigger className="w-[120px] h-8 text-xs">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {CONTEXT_MODES.map((m) => (
                                  <SelectItem key={m} value={m}>
                                    {m}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ---- RUNS TAB ---- */}
        <TabsContent value="runs" className="mt-4">
          <RunsList projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-Components
// ---------------------------------------------------------------------------

/**
 * RunsList — Table of pipeline runs for this project.
 * Fetches from the recent runs endpoint and filters by project ID.
 */
function RunsList({ projectId }: { projectId: string }) {
  const { data: runs = [] } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: api.getRecentRuns,
    // Client-side filter to show only this project's runs
    select: (data) => data.filter((r) => r.project === projectId),
  });

  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="py-12 text-center">
          <FolderOpen className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">No runs yet</p>
          <p className="text-xs text-muted-foreground/60 mt-1">
            Click &ldquo;Run pipeline&rdquo; above to start your first run.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Run ID</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Started</TableHead>
              <TableHead className="w-[40px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runs.map((run) => (
              <TableRow key={run.id} className="group">
                <TableCell>
                  <Link
                    href={`/projects/${projectId}/runs/${run.id}`}
                    className="font-mono text-xs hover:underline"
                  >
                    {run.id.slice(0, 8)}...
                  </Link>
                </TableCell>
                <TableCell>
                  <StatusBadge status={run.status} />
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {run.started_at
                    ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
                    : 'Pending'}
                </TableCell>
                <TableCell>
                  <Link href={`/projects/${projectId}/runs/${run.id}`}>
                    <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
