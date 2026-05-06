/**
 * app-sidebar.tsx — Persistent navigation sidebar for the ReqLens application.
 *
 * GitHub-style collapsible sidebar with:
 *   - Logo + app name at the top
 *   - Primary navigation links (Dashboard, New Project, Agents)
 *   - Dynamic project list fetched from the API
 *   - Active state highlighting based on the current URL
 *   - Version badge at the bottom
 *
 * Design: follows the spec's "Linear/Vercel/GitHub Primer aesthetic" —
 * neutral grays, subtle borders, dense information layout. No saturated
 * brand colors or decorative elements.
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard,
  FolderPlus,
  Settings,
  FlaskConical,
  FolderOpen,
  ChevronRight,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { Separator } from '@/components/ui/separator';

/** Primary navigation items — always visible in the sidebar */
const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/projects/new', label: 'New Project', icon: FolderPlus },
  { href: '/settings/agents', label: 'Agent Registry', icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();

  // Fetch projects to display in the sidebar's project list section
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  });

  return (
    <aside className="w-60 border-r border-border bg-muted/20 flex flex-col shrink-0">
      {/* ---- Logo & app name ---- */}
      <div className="h-14 px-4 flex items-center border-b border-border">
        <Link href="/" className="flex items-center gap-2.5 text-sm font-semibold tracking-tight">
          <div className="h-7 w-7 rounded-md bg-foreground/5 border border-border flex items-center justify-center">
            <FlaskConical className="h-4 w-4 text-foreground/80" />
          </div>
          <span className="text-foreground">ReqLens</span>
        </Link>
      </div>

      {/* ---- Primary navigation ---- */}
      <nav className="p-2 space-y-0.5">
        {navItems.map((item) => {
          const Icon = item.icon;
          // Check if the current page matches this nav item
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-2.5 px-3 py-2 text-[13px] rounded-md transition-colors',
                active
                  ? 'bg-accent text-accent-foreground font-medium'
                  : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* ---- Projects section ---- */}
      <Separator className="mx-2" />
      <div className="flex-1 overflow-auto p-2">
        <p className="px-3 py-1.5 text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
          Projects
        </p>
        <div className="space-y-0.5 mt-1">
          {projects.length === 0 ? (
            <p className="px-3 py-2 text-xs text-muted-foreground/60">No projects yet</p>
          ) : (
            projects.map((project) => {
              // Highlight if the user is viewing this project's pages
              const isActive = pathname.startsWith(`/projects/${project.id}`);
              return (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className={cn(
                    'flex items-center gap-2 px-3 py-1.5 text-[13px] rounded-md transition-colors group',
                    isActive
                      ? 'bg-accent text-accent-foreground font-medium'
                      : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                  )}
                >
                  <FolderOpen className="h-3.5 w-3.5 shrink-0 opacity-60" />
                  <span className="truncate">{project.name}</span>
                  <ChevronRight className="h-3 w-3 ml-auto opacity-0 group-hover:opacity-60 transition-opacity shrink-0" />
                </Link>
              );
            })
          )}
        </div>
      </div>

      {/* ---- Footer with version ---- */}
      <div className="px-4 py-3 border-t border-border">
        <p className="text-[11px] text-muted-foreground/50">ReqLens v0.1.0</p>
      </div>
    </aside>
  );
}
