'use client';

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { CircleCheck, CircleX } from 'lucide-react';

export default function AgentsSettingsPage() {
  const { data: agents = [] } = useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
  });

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Agent Registry</h1>
      <p className="text-sm text-muted-foreground">
        Available ACP agents and their status. Install agents and set environment variables to enable them.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Registered agents</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Command</TableHead>
                <TableHead>On PATH</TableHead>
                <TableHead>Env vars</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow key={agent.id}>
                  <TableCell>
                    <div>
                      <span className="font-medium">{agent.display_name}</span>
                      {agent.notes && (
                        <p className="text-xs text-muted-foreground mt-0.5">{agent.notes}</p>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">
                      {agent.command}
                    </code>
                  </TableCell>
                  <TableCell>
                    {agent.command_on_path ? (
                      <CircleCheck className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <CircleX className="h-4 w-4 text-rose-500" />
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 flex-wrap">
                      {agent.env_required.length === 0 ? (
                        <span className="text-xs text-muted-foreground">None</span>
                      ) : (
                        agent.env_required.map((env) => (
                          <Badge key={env} variant="outline" className="text-[10px] font-mono">
                            {env}
                          </Badge>
                        ))
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
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
        </CardContent>
      </Card>
    </div>
  );
}
