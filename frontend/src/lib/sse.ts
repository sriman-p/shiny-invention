'use client';

import { useEffect, useState } from 'react';

import type { StreamEvent } from './types';

export function useEventStream(url: string | null) {
  const [events, setEvents] = useState<StreamEvent[]>([]);

  useEffect(() => {
    if (!url) return;

    const source = new EventSource(url);
    source.onmessage = (event) => {
      try {
        setEvents((prev) => [...prev, JSON.parse(event.data) as StreamEvent]);
      } catch {
        setEvents((prev) => [...prev, { type: 'message', payload: event.data }]);
      }
    };
    source.onerror = () => source.close();

    return () => source.close();
  }, [url]);

  return { events };
}
