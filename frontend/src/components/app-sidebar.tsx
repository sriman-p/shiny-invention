/**
 * app-sidebar.tsx — Animated navigation sidebar with Linear-style transitions.
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
import { motion, AnimatePresence, fadeInLeft, staggerContainer, springQuick } from '@/components/motion';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/projects/new', label: 'New Project', icon: FolderPlus },
  { href: '/settings/agents', label: 'Agent Registry', icon: Settings },
];

export function AppSidebar() {
  const pathname = usePathname();
  const { data: projects = [] } = useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  });

  return (
    <aside className="w-60 border-r border-border bg-card/50 flex flex-col shrink-0">
      {/* Logo */}
      <div className="h-14 px-4 flex items-center border-b border-border">
        <Link href="/" className="flex items-center gap-2.5 text-sm font-semibold tracking-tight group">
          <motion.div
            whileHover={{ scale: 1.05, rotate: 3 }}
            whileTap={{ scale: 0.95 }}
            transition={springQuick}
            className="h-7 w-7 rounded-md bg-foreground/[0.04] border border-border flex items-center justify-center"
          >
            <FlaskConical className="h-4 w-4 text-foreground/70" />
          </motion.div>
          <span className="text-foreground">ReqLens</span>
        </Link>
      </div>

      {/* Primary nav */}
      <motion.nav
        initial="hidden"
        animate="visible"
        variants={staggerContainer}
        className="p-2 space-y-0.5"
      >
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href;
          return (
            <motion.div key={item.href} variants={fadeInLeft} transition={springQuick}>
              <Link
                href={item.href}
                className={cn(
                  'flex items-center gap-2.5 px-3 py-2 text-[13px] rounded-md transition-all duration-150 relative',
                  active
                    ? 'text-foreground font-medium'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                {active && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 bg-accent rounded-md"
                    transition={{ type: 'spring', stiffness: 350, damping: 30 }}
                  />
                )}
                <span className="relative flex items-center gap-2.5">
                  <Icon className="h-4 w-4 shrink-0" />
                  {item.label}
                </span>
              </Link>
            </motion.div>
          );
        })}
      </motion.nav>

      <Separator className="mx-3" />

      {/* Projects */}
      <div className="flex-1 overflow-auto p-2">
        <p className="px-3 py-1.5 text-[11px] font-medium text-muted-foreground/70 uppercase tracking-wider">
          Projects
        </p>
        <motion.div
          initial="hidden"
          animate="visible"
          variants={staggerContainer}
          className="space-y-0.5 mt-1"
        >
          <AnimatePresence mode="popLayout">
            {projects.length === 0 ? (
              <motion.p
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-3 py-2 text-xs text-muted-foreground/40"
              >
                No projects yet
              </motion.p>
            ) : (
              projects.map((project) => {
                const isActive = pathname.startsWith(`/projects/${project.id}`);
                return (
                  <motion.div
                    key={project.id}
                    variants={fadeInLeft}
                    transition={springQuick}
                    layout
                  >
                    <Link
                      href={`/projects/${project.id}`}
                      className={cn(
                        'flex items-center gap-2 px-3 py-1.5 text-[13px] rounded-md transition-all duration-150 group relative',
                        isActive
                          ? 'text-foreground font-medium bg-accent'
                          : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                      )}
                    >
                      <FolderOpen className="h-3.5 w-3.5 shrink-0 opacity-50" />
                      <span className="truncate">{project.name}</span>
                      <ChevronRight className="h-3 w-3 ml-auto opacity-0 group-hover:opacity-50 transition-opacity shrink-0" />
                    </Link>
                  </motion.div>
                );
              })
            )}
          </AnimatePresence>
        </motion.div>
      </div>

      {/* Footer */}
      <div className="px-4 py-3 border-t border-border">
        <p className="text-[11px] text-muted-foreground/40">ReqLens v0.1.0</p>
      </div>
    </aside>
  );
}
