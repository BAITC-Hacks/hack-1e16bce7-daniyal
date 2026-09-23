'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

export default function Home() {
  const [status, setStatus] = useState('Проверяем подключение…');
  useEffect(() => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 7000);
    let active = true;
    fetch('/api/v1/ready', { signal: controller.signal, cache: 'no-store' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Service unavailable');
        const data = await response.json();
        if (data.status !== 'ready' || data.database !== 'ok') throw new Error('Service not ready');
        if (active) setStatus('Сервис подключён и готов к работе');
      })
      .catch(() => { if (active) setStatus('Сервис временно недоступен. Попробуйте обновить страницу.'); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, []);

  return (
    <main className="mx-auto max-w-5xl px-6 py-16 sm:py-24">
      <header className="flex items-center justify-between gap-4 border-b border-emerald-900/15 pb-6">
        <Link href="/" aria-label="Career Quest — к заданиям" className="flex min-h-11 items-center text-sm font-bold tracking-wide">CAREER QUEST</Link>
        <span className="rounded-full bg-white px-4 py-2 text-sm">HR Dashboard</span>
      </header>
      <p className="mt-16 text-xs font-semibold tracking-widest text-emerald-800">РАЗВИТИЕ КОМАНДЫ</p>
      <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight sm:text-6xl">Рост сотрудников начинается с ясного пути.</h1>
      <p className="mt-6 max-w-2xl text-lg leading-relaxed text-emerald-950/70">Здесь появятся навыки команды, карьерные траектории и результаты развития.</p>
      <section className="mt-12 rounded-3xl border border-emerald-900/10 bg-white p-8">
        <h2 className="text-xl font-semibold">Рабочее пространство готовится</h2>
        <p className="mt-3 text-emerald-950/70">Профили сотрудников и аналитика появятся на следующем этапе.</p>
        <p role="status" aria-live="polite" className="mt-6 text-sm text-emerald-800">{status}</p>
      </section>
    </main>
  );
}
