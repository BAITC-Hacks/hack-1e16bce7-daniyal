'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';
import './interactive.css';
import { courses, coverage, formatDate, initials, isState, seed, skills, type Employee, type Skill, type State } from './mock-data';

const tabs = ['Обзор', 'Сотрудники', 'Карта навыков', 'Рекомендации', 'Обучение'] as const;
type Tab = typeof tabs[number];
const storageKey = 'career-quest-demo-v1';

function Arrow() { return <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M4 12h15m-6-6 6 6-6 6" /></svg>; }
function Modal({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; const previous = document.activeElement as HTMLElement | null; dialog?.showModal(); return () => { dialog?.close(); previous?.focus(); }; }, []);
  return <dialog ref={ref} className="cq-dialog" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose(); }} aria-labelledby="dialog-title"><div className="dialog-body"><div className="card-heading"><h2 id="dialog-title">{title}</h2><button className="outline-button" onClick={onClose} aria-label="Закрыть окно">Закрыть</button></div>{children}</div></dialog>;
}

export default function Home() {
  const [data, setData] = useState<State | null>(null);
  const [tab, setTab] = useState<Tab>('Обзор');
  const [query, setQuery] = useState('');
  const [department, setDepartment] = useState('Все отделы');
  const [grade, setGrade] = useState('Все грейды');
  const [period, setPeriod] = useState(90);
  const [sort, setSort] = useState('name');
  const [activityFilter, setActivityFilter] = useState('all');
  const [trainingFilter, setTrainingFilter] = useState('all');
  const [employeeId, setEmployeeId] = useState<string | null>(null);
  const [review, setReview] = useState<{ employeeId: string; skill: Skill; assignmentId?: string } | null>(null);
  const [level, setLevel] = useState(0);
  const [reason, setReason] = useState('');
  const [help, setHelp] = useState(false);
  const [reset, setReset] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const workspaceRef = useRef<HTMLElement>(null);

  useEffect(() => {
    try { const saved = localStorage.getItem(storageKey); const parsed = saved ? JSON.parse(saved) : null; if (parsed && !isState(parsed)) throw new Error(); setData(parsed || seed()); }
    catch { setData(seed()); setError('Не удалось прочитать сохранённые данные. Загружен исходный демо-набор.'); }
    const hash = decodeURIComponent(location.hash.slice(1));
    if (tabs.includes(hash as Tab)) setTab(hash as Tab);
    const navigate = () => { const next = decodeURIComponent(location.hash.slice(1)); if (tabs.includes(next as Tab)) { setTab(next as Tab); setEmployeeId(null); } };
    window.addEventListener('hashchange', navigate);
    const sync = (event: StorageEvent) => { if (event.key !== storageKey || !event.newValue) return; try { const next = JSON.parse(event.newValue); if (isState(next)) { setData(next); setNotice('Данные обновлены из другой вкладки.'); } } catch { /* Keep the current valid state. */ } };
    window.addEventListener('storage', sync);
    return () => { window.removeEventListener('hashchange', navigate); window.removeEventListener('storage', sync); };
  }, []);

  function go(next: Tab) { setTab(next); setEmployeeId(null); location.hash = encodeURIComponent(next); workspaceRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  function commit(next: State, message: string) {
    try { localStorage.setItem(storageKey, JSON.stringify(next)); setError(''); setNotice(message); }
    catch { setError('Изменение применено только в этой вкладке: браузер не разрешил сохранение. Не закрывайте страницу.'); setNotice(message); }
    setData(next);
  }
  function openReview(id: string, skill: Skill, assignmentId?: string) { const e = data?.employees.find(e => e.id === id); if (!e) return; setReview({ employeeId: id, skill, assignmentId }); setLevel(e.levels[skill]); setReason(''); }
  function saveReview() {
    if (!data || !review || reason.trim().length < 10) return;
    const employee = data.employees.find(e => e.id === review.employeeId)!;
    if (review.assignmentId && data.assignments.find(a => a.id === review.assignmentId)?.status !== 'assigned') { setReview(null); return; }
    const date = new Date().toISOString();
    commit({ ...data, employees: data.employees.map(e => e.id === employee.id ? { ...e, levels: { ...e.levels, [review.skill]: level } } : e), changes: [{ id: crypto.randomUUID(), employeeId: employee.id, skill: review.skill, from: employee.levels[review.skill], to: level, date, reason: reason.trim() }, ...data.changes], assignments: data.assignments.map(a => a.id === review.assignmentId ? { ...a, status: 'completed', date } : a) }, 'Оценка сохранена. Карта навыков и отчёт обновлены.');
    setReview(null);
  }
  function assign(e: Employee, courseId: string) {
    if (!data || data.assignments.some(a => a.employeeId === e.id && a.courseId === courseId && a.status === 'assigned')) return;
    commit({ ...data, assignments: [{ id: crypto.randomUUID(), employeeId: e.id, courseId, date: new Date().toISOString(), status: 'assigned' }, ...data.assignments] }, `Обучение назначено: ${e.name}. Оно доступно во вкладке «Обучение».`);
  }
  function clearFilters() { setQuery(''); setDepartment('Все отделы'); setGrade('Все грейды'); setActivityFilter('all'); setTrainingFilter('all'); }

  if (!data) return <main className="page-shell"><h1>Career Quest</h1><p role="status">Загружаем демо-профили…</p></main>;
  const employees = data.employees.filter(e => (department === 'Все отделы' || e.department === department) && (grade === 'Все грейды' || e.grade === grade) && `${e.name} ${e.role} ${e.department}`.toLowerCase().includes(query.toLowerCase().trim())).sort((a, b) => sort === 'coverage' ? coverage(a) - coverage(b) : a.name.localeCompare(b.name));
  const ids = new Set(employees.map(e => e.id));
  const changes = data.changes.filter(c => ids.has(c.employeeId) && Date.now() - Date.parse(c.date) <= period * 86400000).sort((a, b) => Date.parse(b.date) - Date.parse(a.date));
  const average = employees.length ? Math.round(employees.reduce((s, e) => s + coverage(e), 0) / employees.length) : 0;
  const selected = data.employees.find(e => e.id === employeeId);
  const attention = employees.filter(e => coverage(e) < 75);
  const filteredAssignments = data.assignments.filter(a => ids.has(a.employeeId) && (trainingFilter === 'all' || a.status === trainingFilter));
  const visibleChanges = changes.filter(c => activityFilter === 'all' || (activityFilter === 'up' ? c.to > c.from : activityFilter === 'down' ? c.to < c.from : c.to === c.from));

  function exportReport() {
    const rows: (string | number)[][] = [['Демо-отчёт Career Quest', `Период: ${period} дней`], ['Сотрудник', 'Отдел', 'Роль', 'Грейд', 'Навык', 'Уровень', 'Целевой уровень', 'Покрытие цели (%)', 'Изменение за период']];
    employees.forEach(e => skills.forEach(s => rows.push([e.name, e.department, e.role, e.grade, s, e.levels[s], e.target, coverage(e), changes.filter(c => c.employeeId === e.id && c.skill === s).reduce((sum, c) => sum + c.to - c.from, 0)])));
    const csv = '\uFEFF' + rows.map(r => r.map(v => { const text = String(v); return '"' + (/^[=+@\-]/.test(text) ? "'" + text : text).replaceAll('"', '""') + '"'; }).join(';')).join('\r\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
    const link = document.createElement('a'); link.href = url; link.download = 'career-quest-demo.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); setNotice('CSV-отчёт выгружен с учётом поиска, отдела, грейда и периода.');
  }
  const empty = <div className="empty-state"><h3>Ничего не найдено</h3><p>Попробуйте другой запрос или снимите ограничения.</p><button className="outline-button" onClick={clearFilters}>Сбросить фильтры</button></div>;
  function employeeButton(e: Employee) { return <button className="person-button" onClick={() => { setEmployeeId(e.id); setTab('Сотрудники'); }}><span className="avatar">{initials(e.name)}</span><span><strong>{e.name}</strong><small>{e.role} · {e.grade}</small></span><Arrow /></button>; }
  function recommendations(list: Employee[]) { return list.flatMap(e => courses.filter(c => e.levels[c.skill] < e.target).sort((a, b) => e.levels[a.skill] - e.levels[b.skill]).map(course => {
    const assigned = data!.assignments.some(a => a.employeeId === e.id && a.courseId === course.id && a.status === 'assigned');
    return <article className="recommendation-row" key={`${e.id}-${course.id}`}><div><span className="muted-text">{e.name} · {course.duration}</span><h3>{course.title}</h3><p>{course.description}</p><p className="recommendation-reason">{course.skill}: {e.levels[course.skill]} из {e.target}. До цели не хватает {e.target - e.levels[course.skill]} ур.</p></div><button className={assigned ? 'outline-button' : 'primary-button'} disabled={assigned} onClick={() => assign(e, course.id)}>{assigned ? 'Уже назначено' : 'Назначить обучение'}</button></article>;
  })); }

  return <main className="halyk-app">
    <header className="site-header"><div className="header-inner"><a className="brand" href="#Обзор" onClick={() => go('Обзор')} aria-label="Halyk Career Quest, главная"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><span>Halyk</span></a><nav className="top-links" aria-label="Приложение"><span className="top-link active">Career Quest</span><span className="top-link">Кабинет HR</span></nav><div className="header-actions"><button className="outline-button" onClick={() => { workspaceRef.current?.scrollIntoView(); searchRef.current?.focus(); }}>Поиск</button><button className="header-cta" onClick={() => setHelp(true)}>Как это работает</button></div></div><nav className="section-nav" aria-label="Разделы"><div className="header-inner section-nav-inner">{tabs.map(t => <a key={t} href={`#${encodeURIComponent(t)}`} aria-current={tab === t ? 'page' : undefined} onClick={() => go(t)}>{t}</a>)}</div></nav></header>
    <div className="page-shell">
      <div className="breadcrumbs"><span>Halyk</span><span>/</span><strong>Career Quest</strong><span> / Демо</span></div>
      <section className="hero-panel cq-hero"><div className="hero-copy"><h1>Развитие команды,<br /><strong>которое видно.</strong></h1><p>От навыков сегодня — к следующему карьерному шагу. Все изменения собраны в одном месте.</p><div className="hero-actions"><button className="primary-button" onClick={() => go('Рекомендации')}>Подобрать обучение <Arrow /></button><span className="hero-note">{data.employees.length} демонстрационных профилей</span></div></div><div className="hero-summary"><span>Готовность к целевому уровню</span><strong>{average}%</strong><progress max="100" value={average} aria-label="Средняя готовность команды" /><span>По текущей выборке · {employees.length} сотрудников</span></div></section>
      <section ref={workspaceRef} className="workspace-heading" id="workspace"><div><h2>{selected ? 'Профиль сотрудника' : tab}</h2><p>Демо-данные · изменения сохраняются в этом браузере</p></div><button className="ghost-button" onClick={exportReport} disabled={!employees.length}>Экспорт CSV <Arrow /></button></section>
      {error && <div className="notice error" role="alert">{error}<button onClick={() => setError('')} aria-label="Скрыть ошибку">Закрыть</button></div>}
      {notice && <div className="notice" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Скрыть сообщение">Закрыть</button></div>}
      <div className="tabs" aria-label="Вкладки">{tabs.map(t => <button key={t} className={tab === t ? 'tab active' : 'tab'} aria-pressed={tab === t} onClick={() => go(t)}>{t}</button>)}</div>
      <div className="filter-row cq-filters"><label className="search-field"><span className="sr-only">Поиск сотрудника</span><input ref={searchRef} value={query} onChange={e => { setQuery(e.target.value); setEmployeeId(null); }} placeholder="Имя, роль или отдел" /></label><label><span className="sr-only">Отдел</span><select className="filter-select" value={department} onChange={e => { setDepartment(e.target.value); setEmployeeId(null); }}>{['Все отделы', ...new Set(data.employees.map(e => e.department))].map(d => <option key={d}>{d}</option>)}</select></label><label><span className="sr-only">Грейд</span><select className="filter-select" value={grade} onChange={e => { setGrade(e.target.value); setEmployeeId(null); }}>{['Все грейды', 'Junior', 'Middle', 'Senior'].map(g => <option key={g}>{g}</option>)}</select></label><div className="period-tabs" aria-label="Период изменений">{[30, 90, 365].map(p => <button key={p} className={period === p ? 'period active' : 'period'} aria-pressed={period === p} onClick={() => setPeriod(p)}>{p === 365 ? 'Год' : `${p} дней`}</button>)}</div><button className="ghost-button" onClick={clearFilters}>Сбросить</button></div>

      {selected ? <section className="surface-card profile"><button className="ghost-button" onClick={() => setEmployeeId(null)}>Назад к сотрудникам</button><div className="profile-heading"><span className="avatar big-avatar">{initials(selected.name)}</span><div><h2>{selected.name}</h2><p>{selected.role} · {selected.grade} · {selected.department}</p></div><strong>{coverage(selected)}%<small>покрытие цели</small></strong></div><h3>Навыки и подтверждения</h3><p className="muted-text">Целевой уровень: {selected.target} из 5. Изменение оценки требует обоснования.</p><div className="profile-skills">{skills.map(s => <div className="profile-skill" key={s}><strong>{s}</strong><span>{selected.levels[s]} / {selected.target}</span><progress value={Math.min(selected.levels[s], selected.target)} max={selected.target} aria-label={s} /><button className="outline-button" onClick={() => openReview(selected.id, s)}>Оценить навык</button></div>)}</div><h3>История оценки за {period} дней</h3>{changes.filter(c => c.employeeId === selected.id).map(c => <div className="history-row" key={c.id}><strong>{c.skill} · {c.from} → {c.to}</strong><p>{c.reason}</p><small>{formatDate(c.date)}</small></div>)}{!changes.some(c => c.employeeId === selected.id) && <p className="muted-text">За этот период оценок нет.</p>}<h3>Рекомендованное обучение</h3>{recommendations([selected])}</section> : <>
      {tab === 'Обзор' && <><section className="metric-grid">{[{ value: employees.length, label: 'сотрудников в выборке', action: () => go('Сотрудники') }, { value: `${average}%`, label: 'среднее покрытие цели', action: () => go('Карта навыков') }, { value: changes.filter(c => c.from !== c.to).length, label: `изменений за ${period} дней`, action: () => document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' }) }, { value: attention.length, label: 'с покрытием ниже 75%', action: () => { setSort('coverage'); go('Сотрудники'); } }].map(m => <button className="metric-card clickable-metric" key={m.label} onClick={m.action}><strong>{m.value}</strong><span>{m.label}</span><Arrow /></button>)}</section><section className="content-grid"><article className="surface-card"><div className="card-heading"><div><h3>Карта навыков команды</h3><p>Средний уровень по выбранным сотрудникам</p></div><button className="round-button" aria-label="Открыть карту навыков" onClick={() => go('Карта навыков')}><Arrow /></button></div><div className="skill-list">{employees.length ? skills.map(s => { const value = employees.reduce((sum, e) => sum + e.levels[s], 0) / employees.length; const delta = changes.filter(c => c.skill === s).reduce((sum, c) => sum + c.to - c.from, 0); return <div className="skill-row" key={s}><strong>{s}</strong><div className="skill-progress"><progress max={5} value={value} aria-label={s} /><span>{value.toFixed(1)}</span><span className={delta < 0 ? 'negative' : 'positive'}>{delta > 0 ? '+' : ''}{delta}</span></div></div>; }) : empty}</div></article><article className="surface-card"><div className="card-heading"><div><h3>В фокусе HR</h3><p>Сотрудники с покрытием цели ниже 75%</p></div></div>{attention.map(e => <div className="attention-item" key={e.id}>{employeeButton(e)}<small>{coverage(e)}% покрытия цели</small></div>)}{!attention.length && <p className="empty-state">В текущей выборке нет сотрудников с покрытием ниже 75%.</p>}</article></section><section className="surface-card activity-card" id="history"><div className="card-heading"><div><h3>История навыков</h3><p>Изменения с обоснованием за {period} дней</p></div><select className="filter-select" aria-label="Тип изменения" value={activityFilter} onChange={e => setActivityFilter(e.target.value)}><option value="all">Все оценки</option><option value="up">Рост</option><option value="down">Снижение</option><option value="same">Без изменения</option></select></div>{visibleChanges.map(c => <div className="history-row history-grid" key={c.id}><div><button className="text-button" onClick={() => { setEmployeeId(c.employeeId); setTab('Сотрудники'); }}>{data.employees.find(e => e.id === c.employeeId)?.name}</button><p>{c.skill} · {c.reason}</p></div><strong className={c.to < c.from ? 'negative' : 'positive'}>{c.from} → {c.to}</strong><small>{formatDate(c.date)}</small></div>)}{!visibleChanges.length && <p className="empty-state">За выбранный период нет таких оценок.</p>}</section></>}

      {tab === 'Сотрудники' && <section className="surface-card"><div className="card-heading"><h3>Команда · {employees.length}</h3><select className="filter-select" aria-label="Сортировка сотрудников" value={sort} onChange={e => setSort(e.target.value)}><option value="name">По имени</option><option value="coverage">Сначала пробелы в навыках</option></select></div>{employees.length ? <div className="table-scroll"><table><thead><tr><th>Сотрудник</th><th>Отдел</th><th>Покрытие цели</th><th>Обучение</th></tr></thead><tbody>{employees.map(e => <tr key={e.id}><td>{employeeButton(e)}</td><td>{e.department}</td><td><progress max={100} value={coverage(e)} aria-label={`Покрытие цели ${e.name}`} /> {coverage(e)}%</td><td>{data.assignments.filter(a => a.employeeId === e.id && a.status === 'assigned').length} назначено</td></tr>)}</tbody></table></div> : empty}</section>}

      {tab === 'Карта навыков' && <section className="surface-card"><div className="card-heading"><div><h3>Матрица компетенций</h3><p>Нажмите на уровень, чтобы зафиксировать оценку. Шкала 0–5.</p></div></div>{employees.length ? <div className="table-scroll"><table><thead><tr><th>Сотрудник</th>{skills.map(s => <th key={s}>{s}</th>)}<th>Цель</th></tr></thead><tbody>{employees.map(e => <tr key={e.id}><td>{employeeButton(e)}</td>{skills.map(s => <td key={s}><button className={`level-cell ${e.levels[s] >= e.target ? 'met' : 'gap'}`} aria-label={`Оценить ${s}: ${e.name}, уровень ${e.levels[s]}`} onClick={() => openReview(e.id, s)}>{e.levels[s]} <small>/ {e.target}</small></button></td>)}<td>{coverage(e)}%</td></tr>)}</tbody></table></div> : empty}<p className="muted-text">Зелёный — цель достигнута. Светлый — есть пространство для роста. Требования упрощены для демо.</p></section>}

      {tab === 'Рекомендации' && <section className="surface-card"><div className="card-heading"><div><h3>Следующий шаг для каждого</h3><p>Подбор по разнице между текущим и целевым уровнем. Без внешнего AI.</p></div><button className="ghost-button" onClick={() => go('Обучение')}>Назначенное обучение <Arrow /></button></div>{employees.length ? recommendations(employees).length ? recommendations(employees) : <p className="empty-state">Все цели достигнуты. Сейчас дополнительное обучение не требуется.</p> : empty}</section>}

      {tab === 'Обучение' && <section className="surface-card"><div className="card-heading"><div><h3>План развития</h3><p>Завершение обучения требует итоговой оценки и обоснования.</p></div><select className="filter-select" aria-label="Статус обучения" value={trainingFilter} onChange={e => setTrainingFilter(e.target.value)}><option value="all">Все статусы</option><option value="assigned">Назначено</option><option value="completed">Завершено</option></select></div>{filteredAssignments.map(a => { const course = courses.find(c => c.id === a.courseId)!; const e = data.employees.find(e => e.id === a.employeeId)!; return <article className="recommendation-row" key={a.id}><div><span className="muted-text">{e.name} · {formatDate(a.date)}</span><h3>{course.title}</h3><p>{course.skill} · {a.status === 'completed' ? 'Завершено, результат зафиксирован' : 'Назначено, ожидает результата'}</p></div>{a.status === 'assigned' ? <div className="button-group"><button className="primary-button" onClick={() => openReview(e.id, course.skill, a.id)}>Зафиксировать результат</button><button className="outline-button" onClick={() => commit({ ...data, assignments: data.assignments.filter(x => x.id !== a.id) }, 'Назначение отменено. Уровень навыка не изменён.')}>Отменить назначение</button></div> : <button className="outline-button" onClick={() => { setEmployeeId(e.id); setTab('Сотрудники'); }}>Профиль сотрудника</button>}</article>; })}{!filteredAssignments.length && <div className="empty-state"><h3>Здесь пока нет обучения</h3><p>Измените фильтры или выберите подходящий курс.</p><button className="primary-button" onClick={() => go('Рекомендации')}>Подобрать обучение</button></div>}</section>}
      </>}
      <footer className="page-footer"><span>Career Quest · Frontend demo · Русский</span><button className="text-button" onClick={() => setReset(true)}>Сбросить демо-данные</button></footer>
    </div>
    {review && <Modal title="Оценка навыка" onClose={() => setReview(null)}><form className="review-form" onSubmit={e => { e.preventDefault(); saveReview(); }}><p>{data.employees.find(e => e.id === review.employeeId)?.name} · <strong>{review.skill}</strong></p><p className="muted-text">{review.assignmentId ? 'Укажите результат обучения. Само завершение курса не повышает навык автоматически.' : 'Оценка обновит профиль, историю и рекомендации.'}</p><label>Подтверждённый уровень<select autoFocus value={level} onChange={e => setLevel(Number(e.target.value))}>{[0, 1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n} из 5</option>)}</select></label><label>Обоснование<textarea required minLength={10} maxLength={1000} rows={4} value={reason} onChange={e => setReason(e.target.value)} placeholder="Какой результат подтверждает эту оценку? Минимум 10 символов." /></label><span className="muted-text">{reason.trim().length} / 1000 символов</span><button className="primary-button" disabled={reason.trim().length < 10}>Сохранить оценку</button></form></Modal>}
    {help && <Modal title="Как работает демо" onClose={() => setHelp(false)}><ol className="help-list"><li>Найдите сотрудника через поиск или фильтр отдела.</li><li>Откройте профиль и изучите разницу между навыками и целью.</li><li>В рекомендациях назначьте курс, затем откройте «Обучение».</li><li>Зафиксируйте итоговую оценку с обоснованием. Она появится в истории и изменит показатели.</li><li>Выгрузите CSV-отчёт по выбранным сотрудникам.</li></ol><p>Все имена, оценки и курсы — mock-данные. Данные хранятся в этом браузере. Интеграция с Halyk, общий backend и авторизация здесь не подключены.</p></Modal>}
    {reset && <Modal title="Сбросить демо?" onClose={() => setReset(false)}><p>Локальные назначения и оценки будут заменены исходным набором из шести сотрудников.</p><div className="button-group"><button className="outline-button" onClick={() => setReset(false)}>Оставить данные</button><button className="primary-button" onClick={() => { commit(seed(), 'Демо-данные восстановлены.'); clearFilters(); setEmployeeId(null); setReset(false); }}>Восстановить исходные данные</button></div></Modal>}
  </main>;
}
