/**
 * settings/agents/page.tsx — Agent Registry page.
 *
 * Displays all ACP agents registered in the backend's agent registry.
 * For each agent, shows:
 *   - Display name and description
 *   - CLI command used to spawn the agent
 *   - Whether the command is found on the system PATH (green check / red X)
 *   - Required environment variables (with badges)
 *   - Overall availability status (available = command on PATH + env vars set)
 *
 * This page is read-only — there's no install flow in the MVP.
 * Users must install agents and set environment variables manually.
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  CircleCheck,
  CircleX,
  Settings,
  Terminal,
  Key,
  ShieldCheck,
} from 'lucide-react';

export default function AgentsSettingsPage() {
  // Fetch the list of all registered ACP agents from the backend
  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });

  // Count how many agents are fully available vs total
  const availableCount = agents.filter((a) => a.available).length;

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* ---- Page header ---- */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Settings className="h-5 w-5" />
          Agent Registry
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          ACP agents available for pipeline execution. Install agents and set environment
          variables to enable them.
        </p>
      </div>

      {/* ---- Summary stat ---- */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1.5">
          <ShieldCheck className="h-4 w-4 text-emerald-600" />
          <span>
            <strong>{availableCount}</strong> of{' '}
            <strong>{agents.length}</strong> agents available
          </span>
        </div>
      </div>

      {/* ---- Agents table ---- */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Registered agents</CardTitle>
          <CardDescription>
            Each agent must have its CLI command on the system PATH and required
            environment variables set to be usable.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[200px]">Agent</TableHead>
                  <TableHead className="w-[120px]">Command</TableHead>
                  <TableHead className="w-[80px] text-center">On PATH</TableHead>
                  <TableHead>Required Env Vars</TableHead>
                  <TableHead className="w-[100px] text-center">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow key={agent.id}>
                    {/* Agent name and description */}
                    <TableCell>
                      <div>
                        <span className="font-medium text-sm">{agent.display_name}</span>
                        {agent.notes && (
                          <p className="text-[11px] text-muted-foreground mt-0.5 leading-tight">
                            {agent.notes}
                          </p>
                        )}
                      </div>
                    </TableCell>

                    {/* CLI command with monospace styling */}
                    <TableCell>
                      <code className="font-mono text-xs bg-muted px-2 py-1 rounded inline-flex items-center gap-1.5">
                        <Terminal className="h-3 w-3 text-muted-foreground" />
                        {agent.command}
                      </code>
                    </TableCell>

                    {/* PATH availability indicator */}
                    <TableCell className="text-center">
                      {agent.command_on_path ? (
                        <CircleCheck className="h-4 w-4 text-emerald-600 mx-auto" />
                      ) : (
                        <CircleX className="h-4 w-4 text-rose-500 mx-auto" />
                      )}
                    </TableCell>

                    {/* Required environment variables */}
                    <TableCell>
                      <div className="flex gap-1 flex-wrap">
                        {agent.env_required.length === 0 ? (
                          <span className="text-xs text-muted-foreground/60">None required</span>
                        ) : (
                          agent.env_required.map((env) => (
                            <Badge
                              key={env}
                              variant="outline"
                              className="text-[10px] font-mono gap-1"
                            >
                              <Key className="h-2.5 w-2.5" />
                              {env}
                            </Badge>
                          ))
                        )}
                      </div>
                    </TableCell>

                    {/* Overall availability status badge */}
                    <TableCell className="text-center">
                      <Badge
                        variant="outline"
                        className={
                          agent.available
                            ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20'
                            : 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20'
                        }
                      >
                        {agent.available ? 'Available' : 'Missing'}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
