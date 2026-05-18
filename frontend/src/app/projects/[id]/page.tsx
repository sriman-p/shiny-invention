/**
 * Project detail page — animated tabs with motion layout transitions.
 */
'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Spinner } from '@/components/ui/spinner';
import { StatusBadge } from '@/components/status-badge';
import { AgentModelPicker, getFlatModelOptions } from '@/components/agent-model-picker';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import { Play, BarChart3, Save, Code, FileText, FolderOpen, ArrowRight, CheckCircle2 } from 'lucide-react';
import type { StageName } from '@/lib/types';
import { toast } from 'sonner';
import { BackButton } from '@/components/back-button';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];
const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];
type StageConfig = { agent_id: string; model_id: string; prompt_strategy: string; context_mode: string };
const STAGE_DESC: Record<string, string> = {
  parse: 'Extract requirements from document',
  analyze: 'Walk codebase, build symbol inventory',
  map: 'Map requirements to code symbols',
  generate: 'Generate pytest tests for mappings',
  critique: 'Score tests 1-5, accept/revise/reject',
  trace: 'Build traceability matrix + gap report',
};

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = params.id as string;

  const { data: project, isLoading } = useQuery({ queryKey: ['project', projectId], queryFn: () => api.getProject(projectId) });
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });
  const [agentConfigs, setAgentConfigs] = useState<Record<string, StageConfig>>({});
  const [customModelStages, setCustomModelStages] = useState<Record<string, boolean>>({});

  const getAgent = (agentId: string) => agents.find((agent) => agent.id === agentId);

  const getStageConfig = (stage: StageName): StageConfig => {
    const existing = project?.agents?.find((a) => a.stage === stage);
    const override = agentConfigs[stage];
    return {
      agent_id: override?.agent_id || existing?.agent_id || 'codex',
      model_id: override?.model_id ?? existing?.model_id ?? 'gpt-5.5/low',
      prompt_strategy: override?.prompt_strategy || existing?.prompt_strategy || 'zero_shot',
      context_mode: override?.context_mode || existing?.context_mode || 'full',
    };
  };

  const buildAgentConfigs = () => STAGES.map((stage) => ({ stage, ...getStageConfig(stage), enabled: true }));

  const updateStageConfig = (stage: StageName, field: keyof StageConfig, value: string | null) => {
    if (value === null) return;
    setAgentConfigs((prev) => {
      const next = { ...getStageConfig(stage), [field]: value };
      if (field === 'agent_id') {
        next.model_id = '';
        setCustomModelStages((custom) => ({ ...custom, [stage]: false }));
      }
      return { ...prev, [stage]: next };
    });
  };

  const hasUnsavedChanges = Object.keys(agentConfigs).length > 0;

  const saveAgentsMutation = useMutation({
    mutationFn: () => api.updateProjectAgents(projectId, buildAgentConfigs()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      setAgentConfigs({});
      setCustomModelStages({});
      toast.success('Agent configuration saved');
    },
  });

  const runPipelineMutation = useMutation({
    mutationFn: async () => {
      if (hasUnsavedChanges) {
        await api.updateProjectAgents(projectId, buildAgentConfigs());
      }
      return api.createRun(projectId);
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
      setAgentConfigs({});
      setCustomModelStages({});
      router.push(`/projects/${projectId}/runs/${run.id}`);
    },
  });

  const handleSaveAgents = () => {
    saveAgentsMutation.mutate();
  };

  if (isLoading) {
    return (
      <div className="p-8 max-w-6xl mx-auto flex flex-col gap-6">
        <Skeleton className="h-8 w-48" /><Skeleton className="h-4 w-32" /><Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (!project) return <div className="p-8"><p className="text-muted-foreground">Project not found.</p></div>;

  return (
    <PageWrapper className="p-8 max-w-7xl mx-auto flex flex-col gap-6">
      <FadeIn>
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-3">
            <BackButton fallbackHref="/" />
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
              <div className="flex items-center gap-2 mt-1.5 text-sm text-muted-foreground">
                <Code className="size-3.5" /><span>{project.language}</span>
                <span className="text-muted-foreground/30">|</span><span>{project.test_framework}</span>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Button onClick={() => runPipelineMutation.mutate()} disabled={runPipelineMutation.isPending}>
                {runPipelineMutation.isPending ? <Spinner data-icon="inline-start" /> : <Play data-icon="inline-start" />}
                Run pipeline
              </Button>
            </motion.div>
            <Link href={`/projects/${projectId}/sweep`}>
              <Button variant="outline">
                <BarChart3 data-icon="inline-start" />
                Start sweep
              </Button>
            </Link>
          </div>
        </div>
      </FadeIn>

      <FadeIn>
        <Tabs defaultValue="overview">
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="agents">Agents</TabsTrigger>
            <TabsTrigger value="runs">Runs</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="mt-4">
            <div className="grid gap-4 md:grid-cols-2">
              {[
                { icon: Code, label: 'Code directory', value: project.code_path },
                { icon: FileText, label: 'Requirements document', value: project.requirements_path },
              ].map((item, i) => (
                <motion.div key={item.label} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1, ...springSmooth }}>
                  <Card className="group hover:border-foreground/10 transition-colors">
                    <CardContent className="p-5">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
                        <item.icon className="size-4" />{item.label}
                      </div>
                      <code className="text-sm font-mono bg-muted/50 px-3 py-2 rounded-md block truncate">{item.value}</code>
                    </CardContent>
                  </Card>
                </motion.div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="agents" className="mt-4">
            <Card>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">Agent configuration</CardTitle>
                    <CardDescription>Select an agent, model, strategy, and context for each stage.</CardDescription>
                  </div>
                  <motion.div whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                    <Button onClick={handleSaveAgents} disabled={saveAgentsMutation.isPending || !hasUnsavedChanges} variant={hasUnsavedChanges ? 'default' : 'outline'} size="sm">
                      {saveAgentsMutation.isPending ? <Spinner data-icon="inline-start" /> : hasUnsavedChanges ? <Save data-icon="inline-start" /> : <CheckCircle2 data-icon="inline-start" />}
                      {hasUnsavedChanges ? 'Save config' : 'Saved'}
                    </Button>
                  </motion.div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg border overflow-hidden">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[180px]">Stage</TableHead>
                        <TableHead>Provider &amp; Model</TableHead>
                        <TableHead className="w-[170px]">Strategy</TableHead>
                        <TableHead className="w-[130px]">Context</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {STAGES.map((stage, i) => {
                        const config = getStageConfig(stage);
                        const modelOptions = getFlatModelOptions(getAgent(config.agent_id));
                        const isCustom =
                          customModelStages[stage] ||
                          Boolean(config.model_id && !modelOptions.includes(config.model_id));
                        return (
                          <motion.tr
                            key={stage}
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.06, ...springSmooth }}
                            className="border-b border-border last:border-0 align-top"
                          >
                            <TableCell className="py-3">
                              <div>
                                <span className="font-medium capitalize text-sm">{stage}</span>
                                <p className="text-[11px] text-muted-foreground/70 mt-0.5">{STAGE_DESC[stage]}</p>
                              </div>
                            </TableCell>
                            <TableCell className="py-3">
                              <AgentModelPicker
                                agents={agents}
                                agentId={config.agent_id}
                                modelId={config.model_id}
                                isCustom={isCustom}
                                onAgentChange={(value) => updateStageConfig(stage, 'agent_id', value)}
                                onModelChange={({ modelId, isCustom: nextCustom }) => {
                                  setCustomModelStages((custom) => ({ ...custom, [stage]: nextCustom }));
                                  updateStageConfig(stage, 'model_id', modelId);
                                }}
                              />
                            </TableCell>
                            <TableCell className="py-3">
                              <Select value={config.prompt_strategy} onValueChange={(v) => updateStageConfig(stage, 'prompt_strategy', v)}>
                                <SelectTrigger className="w-[160px] h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectGroup>
                                    {STRATEGIES.map((s) => (<SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>))}
                                  </SelectGroup>
                                </SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell className="py-3">
                              <Select value={config.context_mode} onValueChange={(v) => updateStageConfig(stage, 'context_mode', v)}>
                                <SelectTrigger className="w-[120px] h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>
                                  <SelectGroup>
                                    {CONTEXT_MODES.map((m) => (<SelectItem key={m} value={m}>{m}</SelectItem>))}
                                  </SelectGroup>
                                </SelectContent>
                              </Select>
                            </TableCell>
                          </motion.tr>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="runs" className="mt-4">
            <RunsList projectId={projectId} />
          </TabsContent>
        </Tabs>
      </FadeIn>
    </PageWrapper>
  );
}

function RunsList({ projectId }: { projectId: string }) {
  const { data: runs = [] } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: api.getRecentRuns,
    select: (data) => data.filter((r) => r.project === projectId),
  });

  if (runs.length === 0) {
    return (
      <Card>
        <CardContent className="py-16">
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon"><FolderOpen /></EmptyMedia>
              <EmptyTitle>No runs yet</EmptyTitle>
              <EmptyDescription>Click &ldquo;Run pipeline&rdquo; above to start.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card><CardContent className="p-0">
      <Table>
        <TableHeader><TableRow><TableHead>Run ID</TableHead><TableHead>Status</TableHead><TableHead>Started</TableHead><TableHead className="w-[40px]" /></TableRow></TableHeader>
        <TableBody>
          {runs.map((run, i) => (
            <motion.tr key={run.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05, ...springSmooth }} className="group border-b border-border last:border-0">
              <TableCell><Link href={`/projects/${projectId}/runs/${run.id}`} className="font-mono text-xs hover:underline">{run.id.slice(0, 8)}...</Link></TableCell>
              <TableCell><StatusBadge status={run.status} /></TableCell>
              <TableCell className="text-sm text-muted-foreground">{run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'Pending'}</TableCell>
              <TableCell><Link href={`/projects/${projectId}/runs/${run.id}`}><ArrowRight className="size-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-0.5" /></Link></TableCell>
            </motion.tr>
          ))}
        </TableBody>
      </Table>
    </CardContent></Card>
  );
}
