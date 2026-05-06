/**
 * api/health/route.ts — Frontend health check endpoint.
 *
 * Returns a simple JSON response confirming the Next.js frontend service
 * is running. Used for monitoring and deployment verification.
 *
 * This is a Next.js Route Handler (App Router API route), not a React page.
 * It runs on the server side and responds to GET requests at /api/health.
 */
import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    status: 'ok',
    service: 'reqlens-frontend',
  });
}
