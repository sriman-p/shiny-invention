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
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusBadge } from '@/components/status-badge';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import { Play, BarChart3, Save, Code, FileText, Loader2, FolderOpen, ArrowRight, CheckCircle2 } from 'lucide-react';
import type { AgentSpec, StageName } from '@/lib/types';
import { toast } from 'sonner';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];
const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];
const DEFAULT_MODEL_VALUE = '__agent_default__';
const CUSTOM_MODEL_VALUE = '__custom_model__';
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

  const getModelOptions = (agentId: string) => {
    const agent = getAgent(agentId);
    return Array.from(new Set([agent?.model, ...(agent?.model_options ?? [])].filter(Boolean))) as string[];
  };

  const getStageConfig = (stage: StageName): StageConfig => {
    const existing = project?.agents?.find((a) => a.stage === stage);
    const override = agentConfigs[stage];
    return {
      agent_id: override?.agent_id || existing?.agent_id || 'claude-code',
      model_id: override?.model_id ?? existing?.model_id ?? '',
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
      <div className="p-8 max-w-6xl mx-auto space-y-6">
        <Skeleton className="h-8 w-48" /><Skeleton className="h-4 w-32" /><Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (!project) return <div className="p-8"><p className="text-muted-foreground">Project not found.</p></div>;

  return (
    <PageWrapper className="p-8 max-w-7xl mx-auto space-y-6">
      <FadeIn>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
            <div className="flex items-center gap-2 mt-1.5 text-sm text-muted-foreground">
              <Code className="h-3.5 w-3.5" /><span>{project.language}</span>
              <span className="text-muted-foreground/30">|</span><span>{project.test_framework}</span>
            </div>
          </div>
          <div className="flex gap-2">
            <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}>
              <Button onClick={() => runPipelineMutation.mutate()} disabled={runPipelineMutation.isPending}>
                {runPipelineMutation.isPending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Play className="mr-2 h-4 w-4" />}
                Run pipeline
              </Button>
            </motion.div>
            <Link href={`/projects/${projectId}/sweep`}>
              <Button variant="outline"><BarChart3 className="mr-2 h-4 w-4" />Start sweep</Button>
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
                        <item.icon className="h-4 w-4" />{item.label}
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
                      {saveAgentsMutation.isPending ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : hasUnsavedChanges ? <Save className="mr-1.5 h-3.5 w-3.5" /> : <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />}
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
                        <TableHead className="w-[200px]">Stage</TableHead>
                        <TableHead>Agent</TableHead>
                        <TableHead>Model</TableHead>
                        <TableHead>Strategy</TableHead>
                        <TableHead>Context</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {STAGES.map((stage, i) => {
                        const config = getStageConfig(stage);
                        const modelOptions = getModelOptions(config.agent_id);
                        const hasCustomModel = customModelStages[stage] || Boolean(config.model_id && !modelOptions.includes(config.model_id));
                        const modelSelectValue = hasCustomModel ? CUSTOM_MODEL_VALUE : config.model_id || DEFAULT_MODEL_VALUE;
                        const defaultModel = getAgent(config.agent_id)?.model;
                        return (
                          <motion.tr key={stage} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06, ...springSmooth }} className="border-b border-border last:border-0">
                            <TableCell>
                              <div><span className="font-medium capitalize text-sm">{stage}</span><p className="text-[11px] text-muted-foreground/70 mt-0.5">{STAGE_DESC[stage]}</p></div>
                            </TableCell>
                            <TableCell>
                              <Select value={config.agent_id} onValueChange={(v) => updateStageConfig(stage, 'agent_id', v)}>
                                <SelectTrigger className="w-[155px] h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>{agents.map((a: AgentSpec) => (<SelectItem key={a.id} value={a.id} disabled={!a.available}>{a.display_name}</SelectItem>))}</SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <div className="flex w-[190px] flex-col gap-1">
                                <Select
                                  value={modelSelectValue}
                                  onValueChange={(v) => {
                                    if (v === DEFAULT_MODEL_VALUE) {
                                      setCustomModelStages((custom) => ({ ...custom, [stage]: false }));
                                      updateStageConfig(stage, 'model_id', '');
                                    } else if (v === CUSTOM_MODEL_VALUE) {
                                      setCustomModelStages((custom) => ({ ...custom, [stage]: true }));
                                      updateStageConfig(stage, 'model_id', config.model_id || '');
                                    } else {
                                      setCustomModelStages((custom) => ({ ...custom, [stage]: false }));
                                      updateStageConfig(stage, 'model_id', v);
                                    }
                                  }}
                                >
                                  <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value={DEFAULT_MODEL_VALUE}>{defaultModel ? `Default (${defaultModel})` : 'Agent default'}</SelectItem>
                                    {modelOptions.map((model) => (<SelectItem key={model} value={model}>{model}</SelectItem>))}
                                    <SelectItem value={CUSTOM_MODEL_VALUE}>Custom model...</SelectItem>
                                  </SelectContent>
                                </Select>
                                {modelSelectValue === CUSTOM_MODEL_VALUE && (
                                  <Input
                                    value={config.model_id}
                                    onChange={(event) => updateStageConfig(stage, 'model_id', event.target.value)}
                                    placeholder="model id"
                                    className="h-8 text-xs font-mono"
                                  />
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              <Select value={config.prompt_strategy} onValueChange={(v) => updateStageConfig(stage, 'prompt_strategy', v)}>
                                <SelectTrigger className="w-[155px] h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>{STRATEGIES.map((s) => (<SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>))}</SelectContent>
                              </Select>
                            </TableCell>
                            <TableCell>
                              <Select value={config.context_mode} onValueChange={(v) => updateStageConfig(stage, 'context_mode', v)}>
                                <SelectTrigger className="w-[115px] h-8 text-xs"><SelectValue /></SelectTrigger>
                                <SelectContent>{CONTEXT_MODES.map((m) => (<SelectItem key={m} value={m}>{m}</SelectItem>))}</SelectContent>
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
      <Card><CardContent className="py-16 text-center">
        <motion.div animate={{ y: [0, -4, 0] }} transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}>
          <FolderOpen className="h-10 w-10 text-muted-foreground/20 mx-auto mb-4" />
        </motion.div>
        <p className="text-sm text-muted-foreground">No runs yet</p>
        <p className="text-xs text-muted-foreground/50 mt-1">Click &ldquo;Run pipeline&rdquo; above to start.</p>
      </CardContent></Card>
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
              <TableCell><Link href={`/projects/${projectId}/runs/${run.id}`}><ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-0.5" /></Link></TableCell>
            </motion.tr>
          ))}
        </TableBody>
      </Table>
    </CardContent></Card>
  );
}
