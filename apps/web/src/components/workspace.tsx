'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState, type ReactNode, type FormEvent } from 'react';
import { api, jsonPost, message } from '../lib/api';
import type { User, Page } from '../lib/contracts';

const Session = createContext<{ user: User | null; setUser: (user: User | null) => void; loading: boolean; error: string; retry: () => void } | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api<{ user: User }>('auth/me', { signal: controller.signal }).then(result => setUser(result.user)).catch(error => {
      if (!controller.signal.aborted && error.status !== 401) setError(message(error));
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    const expire = () => setUser(null);
    window.addEventListener('cq:unauthorized', expire);
    return () => window.removeEventListener('cq:unauthorized', expire);
  }, []);
  return <Session.Provider value={{ user, setUser, loading, error, retry: () => setRevision(value => value + 1) }}>{children}</Session.Provider>;
}

export function useSession() { const session = useContext(Session); if (!session) throw new Error('Missing session provider'); return session; }

export function ErrorNotice({ error, retry }: { error: string; retry?: () => void }) {
  return <div className="cq-notice error" role="alert"><p>{error}</p>{retry && <button className="outline-button" onClick={retry}>Повторить</button>}</div>;
}

export function Loading({ text = 'Загружаем данные…' }: { text?: string }) {
  return <div className="cq-loading" role="status"><span className="cq-spinner" />{text}</div>;
}

function Login({ hr }: { hr: boolean }) {
  const { setUser } = useSession();
  const router = useRouter();
  const [employees, setEmployees] = useState<{ employee_id: string; full_name: string; role: string; grade: string }[]>([]);
  const [listError, setListError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const all: typeof employees = [];
        let offset = 0;
        while (!controller.signal.aborted) {
          const page = await api<Page<(typeof employees)[number]>>(`auth/demo/employees?limit=100&offset=${offset}`, { signal: controller.signal });
          all.push(...page.items);
          offset += page.items.length;
          if (offset >= page.total || !page.items.length) break;
        }
        if (!controller.signal.aborted) setEmployees(all);
      } catch (error) { if (!controller.signal.aborted) setListError(message(error)); }
    }
    void load();
    return () => controller.abort();
  }, []);
  const [role, setRole] = useState<'employee' | 'hr'>(hr ? 'hr' : 'employee');
  const [employeeId, setEmployeeId] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError('');
    try { const result = await api<{ user: User }>(`auth/demo/${role}`, jsonPost(role === 'employee' ? { employee_id: employeeId.trim() } : { password })); setPassword(''); setUser(result.user); router.push(result.user.role === 'hr' ? '/hr' : '/'); }
    catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <section className="cq-login surface-card"><span className="cq-kicker">ДЕМО-ДОСТУП</span><h1>Ваш следующий<br />карьерный шаг.</h1><p className="cq-muted">Войдите, чтобы увидеть траекторию развития или обзор команды.</p><form onSubmit={submit} className="cq-form"><div className="cq-section-heading" aria-label="Роль для входа">{(['employee', 'hr'] as const).map(value => <button type="button" key={value} className={role === value ? 'primary-button' : 'outline-button'} aria-pressed={role === value} disabled={busy} onClick={() => { setRole(value); setPassword(''); setError(''); }}>{value === 'employee' ? 'Сотрудник' : 'HR'}</button>)}</div>{role === 'employee' && <label>Сотрудник<input list="demo-employees" required maxLength={200} autoComplete="username" value={employeeId} disabled={busy} onChange={event => setEmployeeId(event.target.value)} placeholder="Выберите сотрудника или введите ID" /><datalist id="demo-employees">{employees.map(employee => <option key={employee.employee_id} value={employee.employee_id}>{employee.full_name} · {employee.role} · {employee.grade}</option>)}</datalist>{listError && <span className="cq-caption">Список недоступен. Можно ввести ID вручную.</span>}</label>}{role === 'hr' && <label>Пароль HR<input type="password" required maxLength={1024} autoComplete="current-password" disabled={busy} value={password} onChange={event => setPassword(event.target.value)} /></label>}{error && <ErrorNotice error={error} />}<button className="primary-button" disabled={busy || (role === 'employee' ? !employeeId.trim() : !password)}>{busy ? 'Входим…' : 'Войти →'}</button></form><p className="cq-caption">Демо-вход предназначен для синтетических профилей хакатона.</p></section>;
}

export function Workspace({ hr = false, children }: { hr?: boolean; children: ReactNode }) {
  const session = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function logout() {
    setBusy(true); setError('');
    try { await api('auth/logout', jsonPost({})); session.setUser(null); }
    catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <div className="cq-app"><a className="cq-skip" href="#main">К содержимому</a><header className="site-header"><div className="header-inner cq-header"><Link href="/" className="brand">career quest<span className="cq-brand-dot">✳</span></Link><nav aria-label="Основная навигация"><Link href="/" aria-current={!hr ? 'page' : undefined}>Моё развитие</Link><Link href="/hr" aria-current={hr ? 'page' : undefined}>HR-обзор</Link></nav>{session.user && <button className="outline-button" disabled={busy} onClick={logout}>{busy ? 'Выходим…' : 'Выйти'}</button>}</div></header><main id="main" className="page-shell cq-main">{error && <ErrorNotice error={error} />}{session.loading ? <Loading text="Проверяем сессию…" /> : !session.user ? <>{session.error && <ErrorNotice error={session.error} retry={session.retry} />}<Login hr={hr} /></> : hr && session.user.role !== 'hr' ? <section className="surface-card"><h1>Доступ для HR</h1><p>Ваша текущая сессия — сотрудник. Для обзора команды войдите с ролью HR.</p><Link href="/">Вернуться к своему развитию →</Link></section> : !hr && session.user.role === 'hr' ? <section className="surface-card"><h1>Вы вошли как HR</h1><p>Профили сотрудников доступны в обзоре команды.</p><Link href="/hr">Открыть HR-обзор →</Link></section> : children}<footer className="cq-footer"><span>Career Quest</span><span>Развитие в вашем темпе · RU</span></footer></main></div>;
}

export function useResource<T>(path: string, revision = 0, post = false) {
  const [state, setState] = useState<{ key: string; data: T | null; error: string; loading: boolean }>({ key: '', data: null, error: '', loading: true });
  const [retryCount, setRetryCount] = useState(0);
  const key = `${path}:${revision}:${retryCount}:${post}`;
  useEffect(() => {
    const controller = new AbortController();
    setState({ key, data: null, error: '', loading: true });
    api<T>(path, { ...(post ? jsonPost({ language: 'ru' }) : {}), signal: controller.signal }).then(data => {
      if (!controller.signal.aborted) setState({ key, data, error: '', loading: false });
    }).catch(error => {
      if (!controller.signal.aborted) setState({ key, data: null, error: message(error), loading: false });
    });
    return () => controller.abort();
  }, [path, key, post]);
  return { ...(state.key === key ? state : { data: null, error: '', loading: true }), retry: () => setRetryCount(value => value + 1) };
}
