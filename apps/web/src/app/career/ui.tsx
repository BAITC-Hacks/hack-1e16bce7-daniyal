'use client';
import Link from 'next/link';
import { useEffect, useRef, type ReactNode } from 'react';

export function Icon({ name = 'arrow', size = 20 }: { name?: 'arrow' | 'book' | 'chart' | 'people' | 'target' | 'check' | 'clock' | 'search' | 'close' | 'upload' | 'download' | 'calendar' | 'leaf'; size?: number }) {
  const paths = { arrow: 'M5 12h14m-6-6 6 6-6 6', book: 'M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15', chart: 'M4 20h17M7 16v-5m5 5V5m5 11V8', people: 'M15 20v-2a5 5 0 0 0-10 0v2m14 0v-2a4 4 0 0 0-3-4M10 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6m6 0a3 3 0 0 1 0 6', target: 'M21 11a9 9 0 1 1-8-8M16 8a5 5 0 1 0 1 5m-5-1 9-9m-5 0h5v5', check: 'm5 12 4 4L19 6', clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18m0 4v5l3 2', search: 'M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15m6 13 5 5', close: 'm6 6 12 12M6 18 18 6', upload: 'M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5', download: 'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4', calendar: 'M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1m3-2v4m8-4v4M4 10h16', leaf: 'M5 19C-1 8 10 2 21 3c0 11-6 22-16 16Zm0 0L16 8' };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}
export function Shell({ hr, section, tabs, onSection, children }: { hr: boolean; section: string; tabs: string[]; onSection(s: string): void; children: ReactNode }) {
  return <div className="cq"><a className="cq-skip" href="#cq-content">К содержимому</a><header className="cq-header"><div className="cq-headrow"><Link className="cq-logo" href="/" aria-label="Halyk Career Quest — главная"><img src="/brand/halyk-logo.svg" alt="Halyk" width="145" height="48" /></Link><span className="cq-product">Career Quest<span>Развитие начинается с тебя</span></span><div className="cq-mode" aria-label="Демонстрация кабинетов"><Link href="/" aria-current={!hr ? 'page' : undefined}>Сотрудник</Link><Link href="/hr" aria-current={hr ? 'page' : undefined}>HR</Link></div><span className="cq-demo">Демо</span></div><nav className="cq-nav" aria-label={hr ? 'Разделы HR' : 'Разделы сотрудника'}>{tabs.map((tab, i) => <button key={tab} aria-current={section === tab ? 'page' : undefined} onClick={() => onSection(tab)}><Icon name={(hr ? ['chart', 'people', 'target', 'upload'] : ['target', 'book', 'calendar', 'chart'])[i] as 'target'} size={18} />{tab}</button>)}</nav></header><main id="cq-content" className="cq-main">{children}</main><footer className="cq-footer"><span>Halyk · Career Quest</span><span>Синтетические данные · демо кабинетов без авторизации</span><a href="/hr#Данные">Данные и методика</a></footer></div>;
}
export function Modal({ title, close, children }: { title: string; close(): void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const opener = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => {
      dialog.close();
      // Restore after React removes the dialog and any completed plan row.
      requestAnimationFrame(() => {
        if (document.querySelector('dialog[open]')) return;
        const fallback = document.querySelector<HTMLElement>('.cq-nav [aria-current="page"]');
        const target = opener?.isConnected && opener !== document.body && !opener.closest('dialog') ? opener : fallback;
        target?.focus({ preventScroll: true });
      });
    };
  }, []);
  return <dialog className="cq-dialog-new" ref={ref} onCancel={e => { e.preventDefault(); close(); }} aria-labelledby="cq-modal-title"><div className="cq-modal-head"><h2 id="cq-modal-title">{title}</h2><button className="cq-icon-button" aria-label="Закрыть окно" onClick={close}><Icon name="close" /></button></div>{children}</dialog>;
}
export function Empty({ title, children }: { title: string; children?: ReactNode }) { return <div className="cq-empty"><Icon name="leaf" size={32} /><h3>{title}</h3>{children}</div>; }
export function Meter({ value, label }: { value: number; label: string }) { return <progress className="cq-meter" value={value} max={100} aria-label={label} />; }
export function download(name: string, contents: string, type = 'application/json') { const url = URL.createObjectURL(new Blob([contents], { type })); const a = document.createElement('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
