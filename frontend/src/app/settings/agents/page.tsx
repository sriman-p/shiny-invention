/**
 * Agent Registry — animated agent list with staggered entrance.
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { CircleCheck, CircleX, Settings, Terminal, Key, ShieldCheck } from 'lucide-react';
import { PageWrapper, FadeIn, motion, springSmooth } from '@/components/motion';

export default function AgentsSettingsPage() {
  const { data: agents = [] } = useQuery({ queryKey: ['agents'], queryFn: api.getAgents });
  const availableCount = agents.filter((a) => a.available).length;

  return (
    <PageWrapper className="p-8 max-w-5xl mx-auto space-y-6">
      <FadeIn>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <Settings className="h-5 w-5" />Agent Registry
          </h1>
          <p className="text-sm text-muted-foreground mt-1">ACP agents for pipeline execution. Install agents and set env vars to enable.</p>
        </div>
      </FadeIn>

      <FadeIn>
        <div className="flex items-center gap-4 text-sm">
          <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.2, ...springSmooth }} className="flex items-center gap-1.5 bg-muted/50 rounded-full px-3 py-1">
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
            <span><strong className="tabular-nums">{availableCount}</strong> of <strong className="tabular-nums">{agents.length}</strong> agents available</span>
          </motion.div>
        </div>
      </FadeIn>

      <FadeIn>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Registered agents</CardTitle>
            <CardDescription>CLI command must be on PATH and required env vars must be set.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-lg border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[200px]">Agent</TableHead>
                    <TableHead className="w-[130px]">Command</TableHead>
                    <TableHead className="w-[80px] text-center">On PATH</TableHead>
                    <TableHead>Required Env Vars</TableHead>
                    <TableHead className="w-[100px] text-center">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agents.map((agent, i) => (
                    <motion.tr
                      key={agent.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05, ...springSmooth }}
                      className="border-b border-border last:border-0 group"
                    >
                      <TableCell>
                        <div>
                          <span className="font-medium text-sm group-hover:text-foreground transition-colors">{agent.display_name}</span>
                          {agent.notes && <p className="text-[11px] text-muted-foreground/60 mt-0.5 leading-tight">{agent.notes}</p>}
                        </div>
                      </TableCell>
                      <TableCell>
                        <code className="font-mono text-xs bg-muted/60 px-2 py-1 rounded inline-flex items-center gap-1.5 border border-border/50">
                          <Terminal className="h-3 w-3 text-muted-foreground/60" />{agent.command}
                        </code>
                      </TableCell>
                      <TableCell className="text-center">
                        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ delay: 0.3 + i * 0.05, type: 'spring', stiffness: 500, damping: 15 }}>
                          {agent.command_on_path
                            ? <CircleCheck className="h-4 w-4 text-emerald-500 mx-auto" />
                            : <CircleX className="h-4 w-4 text-rose-400 mx-auto" />}
                        </motion.div>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1 flex-wrap">
                          {agent.env_required.length === 0
                            ? <span className="text-xs text-muted-foreground/40">None required</span>
                            : agent.env_required.map((env) => (
                                <Badge key={env} variant="outline" className="text-[10px] font-mono gap-1 bg-muted/30">
                                  <Key className="h-2.5 w-2.5" />{env}
                                </Badge>
                              ))
                          }
                        </div>
                      </TableCell>
                      <TableCell className="text-center">
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 + i * 0.05 }}>
                          <Badge variant="outline" className={agent.available ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' : 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'}>
                            {agent.available ? 'Available' : 'Missing'}
                          </Badge>
                        </motion.div>
                      </TableCell>
                    </motion.tr>
                  ))}
                </TableBody>
              </Table>
            </div>
          </CardContent>
        </Card>
      </FadeIn>
    </PageWrapper>
  );
}
