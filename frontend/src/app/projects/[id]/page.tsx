'use client';

import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';
import type { AgentSpec, StageName, RunStatus } from '@/lib/types';

const STAGES: StageName[] = ['parse', 'analyze', 'map', 'generate', 'critique', 'trace'];
const STRATEGIES = ['zero_shot', 'chain_of_thought', 'few_shot_static', 'few_shot_dynamic'];
const CONTEXT_MODES = ['minimal', 'local', 'module', 'full'];

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

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = params.id as string;

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.getProject(projectId),
  });

  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });

  const [agentConfigs, setAgentConfigs] = useState<Record<string, { agent_id: string; prompt_strategy: string; context_mode: string }>>({});

  const saveAgentsMutation = useMutation({
    mutationFn: (configs: Record<string, unknown>[]) => api.updateProjectAgents(projectId, configs),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['project', projectId] }),
  });

  const runPipelineMutation = useMutation({
    mutationFn: () => api.createRun(projectId),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ['recent-runs'] });
      router.push(`/projects/${projectId}/runs/${run.id}`);
    },
  });

  const getStageConfig = (stage: StageName) => {
    const existing = project?.agents?.find((a) => a.stage === stage);
    const override = agentConfigs[stage];
    return {
      agent_id: override?.agent_id || existing?.agent_id || 'claude-code',
      prompt_strategy: override?.prompt_strategy || existing?.prompt_strategy || 'zero_shot',
      context_mode: override?.context_mode || existing?.context_mode || 'full',
    };
  };

  const updateStageConfig = (stage: StageName, field: string, value: string | null) => {
    if (!value) return;
    setAgentConfigs((prev) => ({
      ...prev,
      [stage]: { ...getStageConfig(stage), [field]: value },
    }));
  };

  const handleSaveAgents = () => {
    const configs = STAGES.map((stage) => ({
      stage,
      ...getStageConfig(stage),
      enabled: true,
    }));
    saveAgentsMutation.mutate(configs);
  };

  if (!project) return <div className="p-6">Loading...</div>;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {project.language} &middot; {project.test_framework}
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => runPipelineMutation.mutate()} disabled={runPipelineMutation.isPending}>
            {runPipelineMutation.isPending ? 'Starting...' : 'Run pipeline'}
          </Button>
          <Link href={`/projects/${projectId}/sweep`}>
            <Button variant="outline">Start sweep</Button>
          </Link>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="runs">Runs</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Project details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Code path</span>
                <code className="font-mono text-xs bg-muted px-2 py-1 rounded">{project.code_path}</code>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Requirements</span>
                <code className="font-mono text-xs bg-muted px-2 py-1 rounded">{project.requirements_path}</code>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="agents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Agent configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Stage</TableHead>
                    <TableHead>Agent</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Context</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {STAGES.map((stage) => {
                    const config = getStageConfig(stage);
                    return (
                      <TableRow key={stage}>
                        <TableCell className="font-medium capitalize">{stage}</TableCell>
                        <TableCell>
                          <Select value={config.agent_id} onValueChange={(v) => updateStageConfig(stage, 'agent_id', v)}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {agents.map((a: AgentSpec) => (
                                <SelectItem key={a.id} value={a.id} disabled={!a.available}>
                                  {a.display_name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Select value={config.prompt_strategy} onValueChange={(v) => updateStageConfig(stage, 'prompt_strategy', v)}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {STRATEGIES.map((s) => (
                                <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <Select value={config.context_mode} onValueChange={(v) => updateStageConfig(stage, 'context_mode', v)}>
                            <SelectTrigger className="w-28">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {CONTEXT_MODES.map((m) => (
                                <SelectItem key={m} value={m}>{m}</SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
              <div className="mt-4">
                <Button onClick={handleSaveAgents} disabled={saveAgentsMutation.isPending}>
                  {saveAgentsMutation.isPending ? 'Saving...' : 'Save agent config'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="runs" className="space-y-4">
          <RunsList projectId={projectId} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function RunsList({ projectId }: { projectId: string }) {
  const { data: runs = [] } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: api.getRecentRuns,
    select: (data) => data.filter((r) => r.project === projectId),
  });

  if (runs.length === 0) {
    return <p className="text-sm text-muted-foreground py-4">No runs yet.</p>;
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run ID</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Started</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((run) => (
          <TableRow key={run.id}>
            <TableCell>
              <Link href={`/projects/${projectId}/runs/${run.id}`} className="text-blue-600 hover:underline font-mono text-xs">
                {run.id.slice(0, 8)}
              </Link>
            </TableCell>
            <TableCell>
              <StatusBadge status={run.status} />
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'Pending'}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
