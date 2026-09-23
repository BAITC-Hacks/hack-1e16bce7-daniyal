import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Career Quest · HR',
  description: 'Развитие сотрудников и карьерные траектории',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ru"><body>{children}</body></html>;
}
