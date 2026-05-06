/**
 * status-badge.tsx — Animated status indicators using semantic color tokens.
 */
'use client';

import { Badge } from '@/components/ui/badge';
import { CircleCheck, CircleDashed, CircleX, Ban } from 'lucide-react';
import { Spinner } from '@/components/ui/spinner';
import type { RunStatus, StageStatus } from '@/lib/types';
import { cn } from '@/lib/utils';
import { motion } from 'motion/react';

const STATUS_STYLES: Record<string, string> = {
  succeeded: 'bg-success/10 text-success border-success/20',
  failed: 'bg-destructive/10 text-destructive border-destructive/20',
  running: 'bg-info/10 text-info border-info/20',
  pending: 'bg-muted text-muted-foreground border-border',
  cancelled: 'bg-warning/10 text-warning border-warning/20',
  skipped: 'bg-muted text-muted-foreground/60 border-border',
};

export function StatusBadge({ status, className }: { status: RunStatus | StageStatus; className?: string }) {
  const Icon = { succeeded: CircleCheck, failed: CircleX, running: Spinner, pending: CircleDashed, cancelled: Ban, skipped: CircleDashed }[status] || CircleDashed;

  return (
    <motion.div initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ type: 'spring', stiffness: 400, damping: 25 }}>
      <Badge variant="outline" className={cn('gap-1.5 font-medium', STATUS_STYLES[status] || STATUS_STYLES.pending, className)}>
        <Icon />
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
        <div className="absolute inset-0 rounded-full bg-info/20 animate-pulse-ring" />
        <Spinner className="size-5 text-info relative" />
      </div>
    );
  }
  if (status === 'succeeded') {
    return (
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15, delay: 0.1 }}>
        <CircleCheck className="size-5 text-success" />
      </motion.div>
    );
  }
  if (status === 'failed') {
    return (
      <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', stiffness: 500, damping: 15 }}>
        <CircleX className="size-5 text-destructive" />
      </motion.div>
    );
  }
  return <CircleDashed className="size-5 text-muted-foreground/40" />;
}
