'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useContext, useEffect, useState, type ReactNode, type FormEvent } from 'react';
import { api, jsonPost, message } from '../lib/api';
import { DEVELOPMENT_NOTICE, isPlannedRoute } from '../lib/features';
import type { User, Page } from '../lib/contracts';
import { Icon, type IconName } from './ui';

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
  if (error === DEVELOPMENT_NOTICE) return <div className="cq-notice" role="status"><p>{error}</p></div>;
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

const employeeMenu: { href: string; label: string; icon: IconName }[] = [
  { href: '/', label: 'Dashboard', icon: 'dashboard' },
  { href: '/career', label: 'My Career', icon: 'path' },
  { href: '/recommendations', label: 'Recommendations', icon: 'spark' },
  { href: '/activities', label: 'Activities', icon: 'activity' },
  { href: '/history', label: 'History', icon: 'history' },
];
const hrMenu: typeof employeeMenu = [
  { href: '/hr', label: 'Dashboard', icon: 'dashboard' },
  { href: '/hr/employees', label: 'Employees', icon: 'people' },
  { href: '/hr/skill-gaps', label: 'Skill Gaps', icon: 'chart' },
  { href: '/hr/activities', label: 'Activities', icon: 'activity' },
  { href: '/hr/import', label: 'Data Import', icon: 'upload' },
];

export function Workspace({ hr = false, children }: { hr?: boolean; children: ReactNode }) {
  const session = useSession();
  const pathname = usePathname();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isHr = session.user?.role === 'hr';
  const menu = isHr ? hrMenu : employeeMenu;
  const active = menu.find(item => item.href === pathname);
  useEffect(() => {
    if (session.user && hr !== isHr) router.replace(isHr ? '/hr' : '/');
  }, [session.user, hr, isHr, router]);
  async function logout() {
    setBusy(true); setError('');
    try { await api('auth/logout', jsonPost({})); session.setUser(null); }
    catch (error) { setError(message(error)); }
    finally { setBusy(false); }
  }
  return <div className={`cq-app ${session.user ? 'cq-authenticated' : ''}`}>
    <a className="cq-skip" href="#main">К содержимому</a>
    {session.user && <aside className="cq-sidebar">
      <Link href={isHr ? '/hr' : '/'} className="brand"><span className="cq-logo"><Icon name="path" size={23} /></span>Career Quest<span className="cq-brand-dot">.</span></Link>
      <p className="cq-nav-label">{isHr ? 'ПРОСТРАНСТВО HR' : 'ВАШЕ РАЗВИТИЕ'}</p>
      <nav aria-label={isHr ? 'Меню HR' : 'Меню сотрудника'}>{menu.map(item => <Link key={item.href} href={item.href} aria-current={pathname === item.href ? 'page' : undefined}><Icon name={item.icon} /><span>{item.label}</span>{pathname === item.href && <span className="cq-nav-dot" />}</Link>)}</nav>
      <div className="cq-sidebar-note"><Icon name="spark" /><strong>Маленькие шаги.<br />Большие возможности.</strong><p>Ваш следующий уровень начинается сегодня.</p></div>
      <div className="cq-account"><span className="cq-avatar">{isHr ? 'HR' : 'CQ'}</span><div><strong>{isHr ? 'HR Workspace' : session.user.employee_id}</strong><small>{isHr ? 'Управление развитием' : 'Личный кабинет'}</small></div><button className="cq-icon-button" aria-label="Выйти" title="Выйти" disabled={busy} onClick={logout}><Icon name="logout" size={18} /></button></div>
    </aside>}
    <div className="cq-content"><header className="cq-topbar">{session.user ? <><span>Workspace <span className="cq-slash">/</span> <strong>{active?.label || 'Career Quest'}</strong></span><span className="cq-topbar-role"><span className="cq-status-dot" />{isHr ? 'HR workspace' : 'Employee workspace'}</span></> : <><Link href="/" className="brand">Career Quest<span className="cq-brand-dot">✳</span></Link><span className="cq-caption">Ваш путь к следующему уровню</span></>}</header>
      <main id="main" className="cq-main">
        {error && <ErrorNotice error={error} />}
        {session.loading ? <Loading text="Проверяем сессию…" /> : !session.user ? <>{session.error && <ErrorNotice error={session.error} retry={session.retry} />}<Login hr={hr} /></> : hr !== isHr ? <Loading text="Открываем рабочее пространство…" /> : children}
        <footer className="cq-footer"><span>Career Quest <span>·</span> Каждый шаг имеет значение</span><span>Развитие в вашем темпе</span></footer>
      </main>
    </div>
  </div>;
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
      if (!controller.signal.aborted) setState({ key, data: null, error: error.status === 404 && isPlannedRoute(path) ? DEVELOPMENT_NOTICE : message(error), loading: false });
    });
    return () => controller.abort();
  }, [path, key, post]);
  return { ...(state.key === key ? state : { data: null, error: '', loading: true }), retry: () => setRetryCount(value => value + 1) };
}
