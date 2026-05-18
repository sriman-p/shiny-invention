import path from 'node:path';
import { defineConfig } from 'vitest/config';

/**
 * Minimal vitest setup — Node environment for pure-logic tests.
 *
 * The repo doesn't ship a JSDOM environment by design: the run/sweep page
 * UIs are integration-tested via the backend SSE flow, while the pure
 * formatters and matrix helpers are unit-tested here. Adding JSDOM later
 * is a one-line `environment: 'jsdom'` change once we need it.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'node',
    globals: false,
    include: ['src/**/*.test.ts'],
    reporters: 'default',
  },
});
