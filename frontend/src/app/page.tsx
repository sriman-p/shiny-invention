/**
 * page.tsx (Dashboard) — Animated dashboard with staggered entrance and live counters.
 */
'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from '@/components/ui/empty';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { StatusBadge } from '@/components/status-badge';
import { PageWrapper, FadeIn, StaggerList, motion, fadeInUp, springSmooth } from '@/components/motion';
import { formatDistanceToNow } from 'date-fns';
import { ArrowRight, Plus, FolderOpen, Activity, FlaskConical, Code } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

/** Animated number counter — counts up from 0 to target using requestAnimationFrame */
function AnimatedCount({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  const prevValueRef = useRef(value);
  useEffect(() => {
    prevValueRef.current = value;
  });
  useEffect(() => {
    let raf: number;
    const duration = 600;
    const start = performance.now();
    const from = 0;
    const tick = (now: number) => {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(from + eased * (value - from)));
      if (progress < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // Only re-run when the target value actually changes
  }, [value]);
  return <>{display}</>;
}

export default function DashboardPage() {
  const { data: runs = [] } = useQuery({ queryKey: ['recent-runs'], queryFn: api.getRecentRuns });
  const { data: projects = [] } = useQuery({ queryKey: ['projects'], queryFn: api.getProjects });

  const activeRuns = runs.filter((r) => r.status === 'running').length;
  const completedRuns = runs.filter((r) => r.status === 'succeeded').length;

  return (
    <PageWrapper className="p-8 max-w-7xl mx-auto flex flex-col gap-8">
      {/* Header */}
      <FadeIn>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
            <p className="text-sm text-muted-foreground mt-1">Overview of your projects and pipeline activity</p>
          </div>
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Link href="/projects/new">
              <Button>
                <Plus data-icon="inline-start" />
                New Project
              </Button>
            </Link>
          </motion.div>
        </div>
      </FadeIn>

      {/* Stat cards with animated counters */}
      <div className="grid gap-4 md:grid-cols-3">
        {[
          { title: 'Projects', value: projects.length, desc: 'Registered projects', icon: FolderOpen },
          { title: 'Total Runs', value: runs.length, desc: `${completedRuns} succeeded`, icon: Activity },
          { title: 'Active', value: activeRuns, desc: 'Currently running', icon: FlaskConical },
        ].map((stat, i) => (
          <FadeIn key={stat.title} delay={i * 0.08}>
            <motion.div whileHover={{ y: -2, transition: { duration: 0.2 } }}>
              <Card className="overflow-hidden relative group">
                <CardContent className="p-5">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">{stat.title}</p>
                    <div className="size-8 rounded-md bg-muted flex items-center justify-center text-muted-foreground">
                      <stat.icon className="size-4" />
                    </div>
                  </div>
                  <p className="text-3xl font-semibold mt-2 tabular-nums">
                    <AnimatedCount value={stat.value} />
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">{stat.desc}</p>
                </CardContent>
              </Card>
            </motion.div>
          </FadeIn>
        ))}
      </div>

      {/* Main content */}
      <div className="grid gap-6 lg:grid-cols-5">
        {/* Runs table */}
        <FadeIn className="lg:col-span-3">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Recent Runs</CardTitle>
              <CardDescription>Last 10 pipeline runs across all projects</CardDescription>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyMedia variant="icon"><Activity /></EmptyMedia>
                    <EmptyTitle>No runs yet</EmptyTitle>
                    <EmptyDescription>Create a project and run the pipeline to see results here.</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[140px]">Project</TableHead>
                      <TableHead className="w-[120px]">Status</TableHead>
                      <TableHead>Started</TableHead>
                      <TableHead className="w-[40px]" />
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {runs.map((run, i) => (
                      <motion.tr
                        key={run.id}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: i * 0.05, ...springSmooth }}
                        className="group border-b border-border last:border-0"
                      >
                        <TableCell className="font-medium text-sm">{run.project_name}</TableCell>
                        <TableCell><StatusBadge status={run.status} /></TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {run.started_at ? formatDistanceToNow(new Date(run.started_at), { addSuffix: true }) : 'Not started'}
                        </TableCell>
                        <TableCell>
                          <Link href={`/projects/${run.project}/runs/${run.id}`}>
                            <ArrowRight className="size-3.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-all group-hover:translate-x-0.5" />
                          </Link>
                        </TableCell>
                      </motion.tr>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </FadeIn>

        {/* Projects grid */}
        <FadeIn className="lg:col-span-2">
          <div className="flex flex-col gap-3">
            <h2 className="text-sm font-medium text-muted-foreground px-1">Projects</h2>
            {projects.length === 0 ? (
              <Card>
                <CardContent className="py-12">
                  <Empty>
                    <EmptyHeader>
                      <EmptyMedia variant="icon"><FolderOpen /></EmptyMedia>
                      <EmptyTitle>No projects yet</EmptyTitle>
                      <EmptyDescription>Get started by creating a new project.</EmptyDescription>
                    </EmptyHeader>
                    <EmptyContent>
                      <Link href="/projects/new">
                        <Button variant="outline" size="sm">
                          <Plus data-icon="inline-start" />
                          Create your first project
                        </Button>
                      </Link>
                    </EmptyContent>
                  </Empty>
                </CardContent>
              </Card>
            ) : (
              <StaggerList className="flex flex-col gap-2">
                {projects.map((project) => (
                  <motion.div key={project.id} variants={fadeInUp} transition={springSmooth}>
                    <Link href={`/projects/${project.id}`} className="block group">
                      <motion.div whileHover={{ x: 3, transition: { duration: 0.15 } }}>
                        <Card className="transition-colors duration-150 hover:border-foreground/10 hover:bg-accent/30">
                          <CardContent className="p-4">
                            <div className="flex items-start justify-between">
                              <div className="flex flex-col gap-1 min-w-0">
                                <h3 className="text-sm font-medium truncate">{project.name}</h3>
                                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                  <Code className="size-3 shrink-0" />
                                  <span className="font-mono">{project.language}</span>
                                  <Separator />
                                  <span>{project.test_framework}</span>
                                </div>
                              </div>
                              <ArrowRight className="size-4 text-muted-foreground/20 group-hover:text-muted-foreground/60 transition-all group-hover:translate-x-0.5 shrink-0 mt-0.5" />
                            </div>
                          </CardContent>
                        </Card>
                      </motion.div>
                    </Link>
                  </motion.div>
                ))}
              </StaggerList>
            )}
          </div>
        </FadeIn>
      </div>
    </PageWrapper>
  );
}

function Separator() {
  return <span className="text-muted-foreground/30">|</span>;
}
