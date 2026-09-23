import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'Career Quest · HR' };

export default function HrLayout({ children }: { children: React.ReactNode }) {
  return children;
}
