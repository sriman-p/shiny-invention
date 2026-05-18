/**
 * reasoning-stream.tsx — Cursor/opencode-grade live reasoning view.
 *
 * Renders a normalized stream of `ReasoningChunk` items with kind-aware icons,
 * collapsible JSON tool-call payloads, and a typing-cursor when the last chunk
 * is text and the stage is still running. Auto-scrolls to the bottom while the
 * stage streams; pauses scroll if the user manually scrolls up.
 *
 * Used in:
 *   - Run detail page (one stream per stage card, expanded on demand)
 *   - Sweep page (live tile mirrors the active sweep run)
 */
'use client';

import { useEffect, useRef, useState } from 'react';
import { Brain, Wrench, ArrowRight, FileText, Sparkles, Activity, ChevronRight, Copy, Check } from 'lucide-react';

import { cn } from '@/lib/utils';
import { motion, AnimatePresence, springQuick } from '@/components/motion';
import type { ReasoningChunk, ReasoningKind } from '@/lib/types';

const KIND_META: Record<ReasoningKind, { icon: typeof Brain; label: string; tone: string }> = {
  thought: { icon: Brain, label: 'Thinking', tone: 'text-info' },
  text: { icon: FileText, label: 'Output', tone: 'text-foreground' },
  tool_call: { icon: Wrench, label: 'Tool call', tone: 'text-warning' },
  tool_result: { icon: ArrowRight, label: 'Tool result', tone: 'text-success' },
  model_message: { icon: Sparkles, label: 'Model', tone: 'text-info' },
  status: { icon: Activity, label: 'Status', tone: 'text-muted-foreground' },
};

function MetadataBlock({ metadata }: { metadata: Record<string, unknown> | undefined }) {
  const [open, setOpen] = useState(false);
  if (!metadata || Object.keys(metadata).length === 0) return null;

  return (
    <div className="mt-1.5">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-1 text-[10px] text-muted-foreground/70 hover:text-foreground transition-colors"
      >
        <ChevronRight
          className={cn('size-3 transition-transform', open && 'rotate-90')}
        />
        {open ? 'hide details' : `${Object.keys(metadata).length} field${Object.keys(metadata).length === 1 ? '' : 's'}`}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.pre
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.15 }}
            className="mt-1 overflow-hidden rounded-md border border-border/60 bg-muted/30 px-2 py-1.5 font-mono text-[10px] text-muted-foreground"
          >
            {JSON.stringify(metadata, null, 2)}
          </motion.pre>
        )}
      </AnimatePresence>
    </div>
  );
}

function ChunkRow({ chunk, isLastText, isLive }: { chunk: ReasoningChunk; isLastText: boolean; isLive: boolean }) {
  const meta = KIND_META[chunk.kind] ?? KIND_META.status;
  const Icon = meta.icon;
  const [copied, setCopied] = useState(false);

  const onCopy = () => {
    navigator.clipboard.writeText(chunk.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  };

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={springQuick}
      className="group flex gap-3 rounded-md px-2 py-1.5 hover:bg-muted/30 transition-colors"
    >
      <div className={cn('mt-0.5 flex size-5 shrink-0 items-center justify-center', meta.tone)}>
        <Icon className="size-3.5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <span className={cn('text-[10px] uppercase tracking-wider font-medium', meta.tone)}>
            {meta.label}
          </span>
          <button
            type="button"
            onClick={onCopy}
            className="opacity-0 group-hover:opacity-100 transition-opacity text-muted-foreground hover:text-foreground"
            aria-label="Copy"
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          </button>
        </div>
        <div
          className={cn(
            'mt-0.5 break-words text-xs leading-relaxed',
            chunk.kind === 'thought' && 'italic text-foreground/80',
            chunk.kind === 'tool_call' && 'font-mono text-foreground/90',
            chunk.kind === 'tool_result' && 'font-mono text-foreground/85',
          )}
        >
          {chunk.content}
          {isLastText && isLive && (
            <span className="ml-0.5 inline-block h-3 w-[2px] translate-y-0.5 animate-pulse bg-foreground/70" />
          )}
        </div>
        <MetadataBlock metadata={chunk.metadata as Record<string, unknown> | undefined} />
      </div>
    </motion.div>
  );
}

export function ReasoningStream({
  chunks,
  isLive = false,
  emptyMessage = 'No reasoning captured yet.',
  className,
  maxHeight = '420px',
}: {
  chunks: ReasoningChunk[];
  isLive?: boolean;
  emptyMessage?: string;
  className?: string;
  maxHeight?: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [stickToBottom, setStickToBottom] = useState(true);

  useEffect(() => {
    const node = containerRef.current;
    if (!node || !stickToBottom) return;
    node.scrollTop = node.scrollHeight;
  }, [chunks.length, stickToBottom]);

  // Pause auto-scroll if the user manually scrolls up.
  const onScroll = (event: React.UIEvent<HTMLDivElement>) => {
    const el = event.currentTarget;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setStickToBottom(distanceFromBottom < 24);
  };

  if (chunks.length === 0) {
    return (
      <div
        className={cn(
          'flex items-center justify-center rounded-md border border-dashed border-border/60 px-3 py-6 text-xs text-muted-foreground',
          className,
        )}
      >
        {isLive ? (
          <span className="flex items-center gap-2">
            <span className="relative inline-flex size-2">
              <span className="absolute inline-flex size-full animate-ping rounded-full bg-info opacity-60" />
              <span className="relative inline-flex size-2 rounded-full bg-info" />
            </span>
            Waiting for first reasoning chunk…
          </span>
        ) : (
          emptyMessage
        )}
      </div>
    );
  }

  // Find the index of the last text chunk for the typing cursor effect.
  const lastTextIdx = (() => {
    for (let i = chunks.length - 1; i >= 0; i -= 1) {
      if (chunks[i].kind === 'text') return i;
    }
    return -1;
  })();

  return (
    <div
      ref={containerRef}
      onScroll={onScroll}
      className={cn('overflow-auto pr-1', className)}
      style={{ maxHeight }}
    >
      <div className="flex flex-col gap-0.5">
        {chunks.map((chunk, i) => (
          <ChunkRow
            key={`${chunk.ts ?? i}-${i}`}
            chunk={chunk}
            isLastText={i === lastTextIdx}
            isLive={isLive}
          />
        ))}
      </div>
    </div>
  );
}
