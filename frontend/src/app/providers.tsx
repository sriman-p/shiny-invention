/**
 * providers.tsx — Client-side context providers for the ReqLens application.
 *
 * Wraps the entire app with:
 *   1. ThemeProvider (next-themes) — Manages dark/light mode with class-based
 *      toggling on <html>. Default theme is "dark" per the spec.
 *   2. QueryClientProvider (TanStack React Query) — Manages all server state
 *      (API data fetching, caching, background refetching). Configured with
 *      30s staleTime so data isn't re-fetched on every component mount.
 *   3. Toaster (sonner) — Global toast notification container for success/error
 *      messages triggered by mutations throughout the app.
 *
 * This file is marked 'use client' because all three providers require
 * browser-side React context, which is not available in Server Components.
 */
'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ThemeProvider } from 'next-themes';
import { useState } from 'react';
import { Toaster } from '@/components/ui/sonner';

export function Providers({ children }: { children: React.ReactNode }) {
  /**
   * Create the React Query client inside useState to ensure it's only
   * created once per app lifecycle (not on every render). This prevents
   * cache loss on re-renders.
   */
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Data is considered fresh for 30 seconds — prevents excessive API calls
            staleTime: 30 * 1000,
            // Don't refetch when the user tabs back to the app
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  return (
    <ThemeProvider attribute="class" defaultTheme="dark" enableSystem>
      <QueryClientProvider client={queryClient}>
        {children}
        {/* Global toast notification container — positioned at bottom-right */}
        <Toaster />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
