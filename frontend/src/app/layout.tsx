/**
 * layout.tsx — Root layout for the entire ReqLens application.
 *
 * This is the top-level Next.js App Router layout that wraps every page.
 * It sets up:
 *   1. Geist font family (sans + mono) via CSS variables
 *   2. Client-side providers (React Query, theme, toast notifications)
 *   3. The persistent sidebar + main content area layout
 *
 * The layout uses a flex container to create a sidebar-on-the-left pattern.
 * The sidebar stays fixed while the main content area scrolls independently.
 */
import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';
import { Providers } from './providers';
import { AppSidebar } from '@/components/app-sidebar';
import { Breadcrumbs } from '@/components/breadcrumbs';

/** Page metadata — shown in the browser tab and search engine results */
export const metadata: Metadata = {
  title: 'ReqLens',
  description: 'Requirement-traced test generation',
};

/**
 * RootLayout — The outermost shell of every page in the application.
 *
 * Structure:
 *   <html>            — Geist font CSS variables applied here
 *     <body>          — Base font + antialiasing
 *       <Providers>   — React Query, ThemeProvider, Toaster
 *         <sidebar>   — Fixed navigation sidebar (left side)
 *         <main>      — Scrollable content area (right side, fills remaining space)
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>
          <div className="flex h-screen">
            {/* Persistent sidebar — always visible on desktop */}
            <AppSidebar />
            {/* Main content area — scrolls independently of sidebar */}
            <div className="flex-1 flex flex-col overflow-hidden bg-background">
              <Breadcrumbs />
              <main className="flex-1 overflow-auto">{children}</main>
            </div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
