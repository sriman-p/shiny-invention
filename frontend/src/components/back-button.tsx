'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

import { Button } from '@/components/ui/button';

/**
 * BackButton — robust SPA back navigation.
 *
 * Detects whether the user actually navigated within our app at click time
 * by inspecting `document.referrer` and the navigation API. If the user
 * opened the page directly (no in-app referrer), `router.back()` would
 * jump out of the app, so we fall back to `fallbackHref` instead. We do
 * the check inside the click handler instead of an effect so that we never
 * trigger an extra render when the component mounts.
 */
export function BackButton({ fallbackHref = '/', label = 'Back' }: { fallbackHref?: string; label?: string }) {
  const router = useRouter();

  const handleClick = () => {
    if (typeof window === 'undefined') {
      router.push(fallbackHref);
      return;
    }
    const sameOriginReferrer =
      document.referrer && new URL(document.referrer, window.location.origin).origin === window.location.origin;
    const hasHistory = window.history.length > 1;
    if (sameOriginReferrer && hasHistory) {
      router.back();
    } else {
      router.push(fallbackHref);
    }
  };

  return (
    <Button variant="ghost" size="sm" type="button" onClick={handleClick} className="w-fit">
      <ArrowLeft data-icon="inline-start" />
      {label}
    </Button>
  );
}
