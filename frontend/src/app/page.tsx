'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatDistanceToNow } from 'date-fns';
import { ArrowRight, Plus } from 'lucide-react';
import type { RunStatus } from '@/lib/types';

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

export default function DashboardPage() {
  const { data: runs = [] } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: api.getRecentRuns,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  });

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      </div>

      <div className="grid gap-6 md:grid-cols-3">
        <Card className="md:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Recent Runs</CardTitle>
            <CardDescription>Last 10 pipeline runs across all projects</CardDescription>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground py-8 text-center">
                No runs yet. Create a project and run the pipeline.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Project</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Started</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="font-medium">{run.project_name}</TableCell>
                      <TableCell>
                        <StatusBadge status={run.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {run.started_at
                          ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
                          : 'Not started'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quick Start</CardTitle>
            </CardHeader>
            <CardContent>
              <Link href="/projects/new">
                <Button className="w-full" variant="outline">
                  <Plus className="mr-2 h-4 w-4" />
                  New Project
                </Button>
              </Link>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Projects</CardTitle>
              <CardDescription>{projects.length} total</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {projects.map((project) => (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="flex items-center justify-between p-2 rounded-md hover:bg-accent text-sm group"
                >
                  <span>{project.name}</span>
                  <ArrowRight className="h-3 w-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                </Link>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
