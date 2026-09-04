/**
 * The authenticated-page shell: `NavBar` plus a centered `main` (E2-S3).
 */
import type { ReactNode } from 'react';

import { NavBar } from './NavBar';

interface LayoutProps {
  children: ReactNode;
}

export function Layout({ children }: LayoutProps) {
  return (
    <>
      <NavBar />
      <main>{children}</main>
    </>
  );
}
