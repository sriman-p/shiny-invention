/**
 * breadcrumbs.tsx — pathname-driven breadcrumb trail.
 *
 * Renders nothing on the dashboard (where the sidebar is enough) and on the
 * "/projects/new" wizard. On project / run / sweep pages it parses the URL
 * into a sequence of links, hydrating the project name from the projects
 * list query so the user sees a friendly label instead of a UUID.
 */
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { ChevronRight, Home } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Crumb {
  label: string;
  href?: string;
}

function useCrumbs(pathname: string): Crumb[] {
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
    staleTime: 60_000,
  });

  if (pathname === '/' || pathname === '') return [];
  const segments = pathname.split('/').filter(Boolean);
  const crumbs: Crumb[] = [{ label: 'Home', href: '/' }];

  if (segments[0] === 'projects' && segments[1] === 'new') {
    crumbs.push({ label: 'New project' });
    return crumbs;
  }
  if (segments[0] === 'settings' && segments[1] === 'agents') {
    crumbs.push({ label: 'Agent registry' });
    return crumbs;
  }

  if (segments[0] === 'projects' && segments[1]) {
    const project = projects.find((p) => p.id === segments[1]);
    const projectLabel = project?.name ?? `${segments[1].slice(0, 8)}…`;
    crumbs.push({ label: projectLabel, href: `/projects/${segments[1]}` });

    if (segments[2] === 'sweep') {
      crumbs.push({ label: 'Sweep' });
    } else if (segments[2] === 'runs' && segments[3]) {
      crumbs.push({ label: 'Runs', href: `/projects/${segments[1]}` });
      crumbs.push({ label: `Run ${segments[3].slice(0, 8)}` });
    }
  }

  return crumbs;
}

export function Breadcrumbs({ className }: { className?: string }) {
  const pathname = usePathname();
  const crumbs = useCrumbs(pathname);

  if (crumbs.length === 0) return null;

  return (
    <nav
      aria-label="Breadcrumb"
      className={cn(
        'flex items-center gap-1.5 px-8 py-2 text-xs text-muted-foreground border-b border-border/60 bg-card/40',
        className,
      )}
    >
      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={`${crumb.label}-${i}`} className="flex items-center gap-1.5">
            {i > 0 && <ChevronRight className="size-3 text-muted-foreground/40" />}
            {i === 0 && <Home className="size-3 text-muted-foreground/60" />}
            {crumb.href && !isLast ? (
              <Link
                href={crumb.href}
                className="hover:text-foreground transition-colors truncate max-w-[180px]"
              >
                {crumb.label}
              </Link>
            ) : (
              <span className={cn('truncate max-w-[220px]', isLast && 'text-foreground font-medium')}>
                {crumb.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
