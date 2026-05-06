'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

import { Button } from '@/components/ui/button';

export function BackButton({ fallbackHref = '/', label = 'Back' }: { fallbackHref?: string; label?: string }) {
  const router = useRouter();

  return (
    <Button
      variant="ghost"
      size="sm"
      type="button"
      onClick={() => {
        if (window.history.length > 1) {
          router.back();
        } else {
          router.push(fallbackHref);
        }
      }}
      className="w-fit"
    >
      <ArrowLeft data-icon="inline-start" />
      {label}
    </Button>
  );
}
