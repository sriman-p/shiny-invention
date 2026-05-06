/**
 * motion.tsx — Shared animation primitives for consistent Linear/Vercel-style UX.
 *
 * Provides reusable motion components that wrap framer-motion (now "motion" lib)
 * to give every page and component consistent enter/exit animations, staggered
 * children, and smooth layout transitions.
 */
'use client';

import { motion, AnimatePresence, type Variants } from 'motion/react';

// Re-export motion primitives for convenience
export { motion, AnimatePresence };

// ---------------------------------------------------------------------------
// Animation Variants — reusable presets for consistent timing
// ---------------------------------------------------------------------------

/** Fade up from below — the primary page/card entrance animation */
export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 12, filter: 'blur(4px)' },
  visible: { opacity: 1, y: 0, filter: 'blur(0px)' },
};

/** Fade in from left — for sidebar items and list entries */
export const fadeInLeft: Variants = {
  hidden: { opacity: 0, x: -8 },
  visible: { opacity: 1, x: 0 },
};

/** Scale up from slightly smaller — for cards and interactive elements */
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.95 },
  visible: { opacity: 1, scale: 1 },
};

/** Stagger children container — wrap around a list of animated items */
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.06,
      delayChildren: 0.04,
    },
  },
};

/** Stagger with slower timing for larger items like cards */
export const staggerContainerSlow: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.08,
    },
  },
};

// ---------------------------------------------------------------------------
// Spring Configs — physics-based easing for that Linear feel
// ---------------------------------------------------------------------------

/** Quick, snappy spring — for micro-interactions */
export const springQuick = { type: 'spring' as const, stiffness: 500, damping: 30 };

/** Smooth spring — for page transitions and layout changes */
export const springSmooth = { type: 'spring' as const, stiffness: 300, damping: 25 };

/** Gentle spring — for large layout shifts */
export const springGentle = { type: 'spring' as const, stiffness: 200, damping: 20 };

// ---------------------------------------------------------------------------
// Wrapper Components
// ---------------------------------------------------------------------------

/**
 * PageWrapper — Wraps page content with a smooth fade-up entrance animation.
 * Every page should use this as its outermost container.
 */
export function PageWrapper({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={staggerContainerSlow}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * FadeIn — Animate a single element into view with fade+translate.
 * Use inside a PageWrapper or stagger container.
 */
export function FadeIn({
  children,
  className,
  delay = 0,
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  return (
    <motion.div
      variants={fadeInUp}
      transition={{ ...springSmooth, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/**
 * StaggerList — Container that staggers children entrance.
 * Each direct child should be wrapped in a motion element with fadeInUp variants.
 */
export function StaggerList({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={staggerContainer}
      className={className}
    >
      {children}
    </motion.div>
  );
}
