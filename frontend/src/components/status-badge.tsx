/**
 * status-badge.tsx — Animated status indicators with Linear-style micro-interactions.
 */
'use client';

import { Badge } from '@/components/ui/badge';
import { CircleCheck, CircleDashed, CircleX, Loader2, Ban } from 'lucide-react';
import type { RunStatus, StageStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { motion } from 'motion/react';

const STATUS_STYLES: Record<string, string> = {
  succeeded: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  failed: 'bg-rose-500/10 text-rose-600 border-rose-500/20',
  running: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  pending: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
  cancelled: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  skipped: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

export function StatusBadge({ status, className }: { status: RunStatus | StageStatus; className?: string }) {
  const Icon = { succeeded: CircleCheck, failed: CircleX, running: Loader2, pending: CircleDashed, cancelled: Ban, skipped: CircleDashed }[status] || CircleDashed;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: 'spring', stiffness: 400, damping: 25 }}>
      <Badge variant="outline" className={cn('gap-1.5 font-medium', STATUS_STYLES[status] || STATUS_STYLES.pending, className)}>
        <Icon className={cn('h-3 w-3', status === 'running' && 'animate-spin')} />
        {status}
      </Badge>
    </motion.div>
  );
}

/** Animated stage icon with a pulsing ring when running */
export function StageStatusIcon({ status }: { status: StageStatus }) {
  if (status === 'running') {
    return (
      <div className="relative">
        <div className="absolute inset-0 rounded-full bg-blue-500/20 animate-pulse-ring" />
        <Loader2 className="h-5 w-5 text-blue-500 animate-spin relative" />
      </div>
    );
  }
  if (status === 'succeeded') {
    return (
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15, delay: 0.1 }}>
        <CircleCheck className="h-5 w-5 text-emerald-500" />
      </motion.div>
    );
  }
  if (status === 'failed') {
    return (
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15 }}>
        <CircleX className="h-5 w-5 text-rose-500" />
      </motion.div>
    );
  }
  return <CircleDashed className="h-5 w-5 text-zinc-500/40" />;
}
