/**
 * status-badge.tsx — Reusable status indicator badge used across the app.
 *
 * Provides consistent, semantic color coding for run/stage statuses:
 *   - emerald for success
 *   - rose for failure
 *   - blue for running/active
 *   - zinc for pending/idle
 *   - amber for cancelled/warning
 *
 * Following the spec's "non-AI aesthetic" rule: uses Lucide icons instead of
 * emoji, and semantic colors only (no saturated brand colors).
 */
import { Badge } from '@/components/ui/badge';
import { CircleCheck, CircleDashed, CircleX, Loader2, Ban } from 'lucide-react';
import type { RunStatus, StageStatus } from '@/lib/types';
import { cn } from '@/lib/utils';

/**
 * Color mapping for each status — applied as Tailwind classes to the Badge.
 * Uses low-opacity backgrounds with higher-opacity text for a subtle look.
 */
const STATUS_STYLES: Record<string, string> = {
  succeeded: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  failed: 'bg-rose-500/10 text-rose-600 border-rose-500/20',
  running: 'bg-blue-500/10 text-blue-600 border-blue-500/20',
  pending: 'bg-zinc-500/10 text-zinc-500 border-zinc-500/20',
  cancelled: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  skipped: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
};

/** Icon mapping — each status gets a distinct Lucide icon */
const STATUS_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  succeeded: CircleCheck,
  failed: CircleX,
  running: Loader2,
  pending: CircleDashed,
  cancelled: Ban,
  skipped: CircleDashed,
};

/**
 * StatusBadge — Renders a pill-shaped badge with an icon and label
 * indicating the current status of a run or stage.
 */
export function StatusBadge({ status, className }: { status: RunStatus | StageStatus; className?: string }) {
  const Icon = STATUS_ICONS[status] || CircleDashed;
  const isSpinning = status === 'running';

  return (
    <Badge variant="outline" className={cn('gap-1.5 font-medium', STATUS_STYLES[status] || STATUS_STYLES.pending, className)}>
      <Icon className={cn('h-3 w-3', isSpinning && 'animate-spin')} />
      {status}
    </Badge>
  );
}

/**
 * StageStatusIcon — Renders just the icon for a pipeline stage status.
 * Used in the pipeline graph where space is limited.
 */
export function StageStatusIcon({ status }: { status: StageStatus }) {
  switch (status) {
    case 'succeeded':
      return <CircleCheck className="h-4 w-4 text-emerald-600" />;
    case 'running':
      return <Loader2 className="h-4 w-4 text-blue-600 animate-spin" />;
    case 'failed':
      return <CircleX className="h-4 w-4 text-rose-600" />;
    default:
      return <CircleDashed className="h-4 w-4 text-zinc-400" />;
  }
}
