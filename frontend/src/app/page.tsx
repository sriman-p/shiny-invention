/**
 * page.tsx (Dashboard) — The main landing page of the ReqLens application.
 *
 * Displays three sections as specified in the implementation doc:
 *   1. Summary stats cards — project count, total runs, active runs
 *   2. Recent runs table — last 10 runs across all projects with status badges
 *   3. Projects grid — cards for each registered project with quick-launch actions
 *
 * Data is fetched via React Query from two endpoints:
 *   - GET /api/v1/runs (recent runs)
 *   - GET /api/v1/projects (all projects)
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
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
import { StatusBadge } from '@/components/status-badge';
import { formatDistanceToNow } from 'date-fns';
import {
  ArrowRight,
  Plus,
  FolderOpen,
  Activity,
  FlaskConical,
  Code,
} from 'lucide-react';

export default function DashboardPage() {
  // Fetch the 10 most recent pipeline runs across all projects
  const { data: runs = [] } = useQuery({
    queryKey: ['recent-runs'],
    queryFn: api.getRecentRuns,
  });

  // Fetch all registered projects for the stats + project grid
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  });

  // Compute summary stats for the top cards
  const activeRuns = runs.filter((r) => r.status === 'running').length;
  const completedRuns = runs.filter((r) => r.status === 'succeeded').length;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* ---- Page header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Overview of your projects and recent pipeline activity
          </p>
        </div>
        <Link href="/projects/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        </Link>
      </div>

      {/* ---- Summary stat cards ---- */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Projects"
          value={projects.length}
          description="Registered projects"
          icon={<FolderOpen className="h-4 w-4" />}
        />
        <StatCard
          title="Total Runs"
          value={runs.length}
          description={`${completedRuns} succeeded`}
          icon={<Activity className="h-4 w-4" />}
        />
        <StatCard
          title="Active"
          value={activeRuns}
          description="Currently running"
          icon={<FlaskConical className="h-4 w-4" />}
        />
      </div>

      {/* ---- Main content: runs table + project grid ---- */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Recent runs table — takes up 3 of 5 columns on large screens */}
        <Card className="lg:col-span-3">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Recent Runs</CardTitle>
            <CardDescription>Last 10 pipeline runs across all projects</CardDescription>
          </CardHeader>
          <CardContent>
            {runs.length === 0 ? (
              /* Empty state — plain text with a single action, per spec */
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Activity className="h-8 w-8 text-muted-foreground/30 mb-3" />
                <p className="text-sm text-muted-foreground">No runs yet</p>
                <p className="text-xs text-muted-foreground/60 mt-1">
                  Create a project and run the pipeline to see results here.
                </p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[140px]">Project</TableHead>
                    <TableHead className="w-[120px]">Status</TableHead>
                    <TableHead>Started</TableHead>
                    <TableHead className="w-[40px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => (
                    <TableRow key={run.id} className="group">
                      <TableCell className="font-medium text-sm">{run.project_name}</TableCell>
                      <TableCell>
                        <StatusBadge status={run.status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {run.started_at
                          ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true })
                          : 'Not started'}
                      </TableCell>
                      <TableCell>
                        <Link href={`/projects/${run.project}/runs/${run.id}`}>
                          <ArrowRight className="h-3.5 w-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Projects grid — takes up 2 of 5 columns on large screens */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-medium text-muted-foreground px-1">Projects</h2>
          {projects.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center">
                <FolderOpen className="h-8 w-8 text-muted-foreground/30 mx-auto mb-3" />
                <p className="text-sm text-muted-foreground">No projects yet</p>
                <Link href="/projects/new" className="mt-3 inline-block">
                  <Button variant="outline" size="sm">
                    <Plus className="mr-1.5 h-3.5 w-3.5" />
                    Create your first project
                  </Button>
                </Link>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {projects.map((project) => (
                <Link key={project.id} href={`/projects/${project.id}`} className="block group">
                  <Card className="transition-colors hover:border-foreground/10">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between">
                        <div className="space-y-1 min-w-0">
                          <h3 className="text-sm font-medium truncate group-hover:text-foreground">
                            {project.name}
                          </h3>
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Code className="h-3 w-3 shrink-0" />
                            <span className="truncate font-mono">{project.language}</span>
                            <span className="text-muted-foreground/40">|</span>
                            <span>{project.test_framework}</span>
                          </div>
                        </div>
                        <ArrowRight className="h-4 w-4 text-muted-foreground/30 group-hover:text-muted-foreground transition-colors shrink-0 mt-0.5" />
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper Components
// ---------------------------------------------------------------------------

/**
 * StatCard — A compact card showing a single metric with an icon.
 * Used in the top summary row of the dashboard.
 */
function StatCard({
  title,
  value,
  description,
  icon,
}: {
  title: string;
  value: number;
  description: string;
  icon: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">{title}</p>
          <div className="h-8 w-8 rounded-md bg-muted flex items-center justify-center text-muted-foreground">
            {icon}
          </div>
        </div>
        <p className="text-2xl font-semibold mt-2">{value}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </CardContent>
    </Card>
  );
}
