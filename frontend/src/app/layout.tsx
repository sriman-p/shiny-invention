import type { Metadata } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import './globals.css';
import { Providers } from './providers';
import { AppSidebar } from '@/components/app-sidebar';

export const metadata: Metadata = {
  title: 'ReqLens',
  description: 'Requirement-traced test generation',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>
          <div className="flex h-screen">
            <AppSidebar />
            <main className="flex-1 overflow-auto bg-background">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
