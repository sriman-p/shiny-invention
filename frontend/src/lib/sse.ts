/**
 * useEventStream — resilient SSE hook with exponential-backoff reconnect and
 * a bounded event buffer so long-running pipelines don't grow memory unbounded.
 *
 * The native EventSource auto-reconnects on transport errors, but it doesn't
 * give us a way to skip events the server already sent. We append a
 * `last_event_id` query parameter on each retry so the backend's per-key
 * replay buffer (see `core.views._broadcast` deque) can resume from where we
 * left off — this is what the server uses to honour the SSE `id:` field.
 *
 * After ~5 retry attempts spaced by exponential backoff (1s → 16s) we close
 * the source and surface a `connectionState` of `"closed"` so the UI can
 * render a small "stream lost" hint.
 */
'use client';

import { useEffect, useRef, useState } from 'react';

import type { StreamEvent } from './types';

const MAX_BUFFER = 500;
const MAX_RETRIES = 5;
const BACKOFF_MS = [1_000, 2_000, 4_000, 8_000, 16_000];

export type SseConnectionState = 'idle' | 'open' | 'reconnecting' | 'closed';

interface SseEvent extends StreamEvent {
  seq?: number;
}

export function useEventStream(url: string | null) {
  // Reset state synchronously when `url` changes — React 19's recommended
  // pattern for "reset on prop change". Mutable refs are reset inside the
  // effect below where it's allowed; only state is touched during render.
  const [events, setEvents] = useState<SseEvent[]>([]);
  const [connectionState, setConnectionState] = useState<SseConnectionState>(url ? 'reconnecting' : 'idle');
  const [seenUrl, setSeenUrl] = useState<string | null>(url);
  const lastSeqRef = useRef(0);
  const sourceRef = useRef<EventSource | null>(null);
  const retryRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  if (url !== seenUrl) {
    setSeenUrl(url);
    setEvents([]);
    setConnectionState(url ? 'reconnecting' : 'idle');
  }

  useEffect(() => {
    // Reset refs whenever the effect re-establishes a connection for a new
    // URL. Refs aren't allowed to be mutated during render, but effects can.
    lastSeqRef.current = 0;
    retryRef.current = 0;

    if (!url) {
      return undefined;
    }

    let cancelled = false;

    const cleanup = () => {
      if (sourceRef.current) {
        sourceRef.current.close();
        sourceRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    const connect = () => {
      if (cancelled) return;
      const join = url.includes('?') ? '&' : '?';
      const target = lastSeqRef.current > 0 ? `${url}${join}last_event_id=${lastSeqRef.current}` : url;
      const source = new EventSource(target);
      sourceRef.current = source;

      source.onopen = () => {
        retryRef.current = 0;
        setConnectionState('open');
      };

      source.onmessage = (event) => {
        let parsed: SseEvent;
        try {
          parsed = JSON.parse(event.data) as SseEvent;
        } catch {
          parsed = { type: 'message', payload: event.data };
        }
        // EventSource forwards the SSE `id:` line via event.lastEventId.
        const lastEventId = Number(event.lastEventId);
        if (Number.isFinite(lastEventId) && lastEventId > 0) {
          lastSeqRef.current = Math.max(lastSeqRef.current, lastEventId);
        } else if (typeof parsed.seq === 'number') {
          lastSeqRef.current = Math.max(lastSeqRef.current, parsed.seq);
        }
        setEvents((prev) => {
          const next = [...prev, parsed];
          if (next.length > MAX_BUFFER) next.splice(0, next.length - MAX_BUFFER);
          return next;
        });
      };

      source.onerror = () => {
        if (cancelled) return;
        source.close();
        sourceRef.current = null;
        if (retryRef.current >= MAX_RETRIES) {
          setConnectionState('closed');
          return;
        }
        const delay = BACKOFF_MS[Math.min(retryRef.current, BACKOFF_MS.length - 1)];
        retryRef.current += 1;
        setConnectionState('reconnecting');
        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      cancelled = true;
      cleanup();
    };
  }, [url]);

  return { events, connectionState };
}
