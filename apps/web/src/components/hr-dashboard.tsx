'use client';

import Link from 'next/link';
import { useRef, useState, type FormEvent } from 'react';
import { api, dateLabel, message, percent } from '../lib/api';
import { statusLabels, type ActivityStat, type Dashboard, type Employee, type ImportResult, type SkillGap } from '../lib/contracts';
import { EmployeeProfile } from './employee-profile';
import { ErrorNotice, Loading, useResource } from './workspace';
import { Icon } from './ui';

const fileNames = ['employees.json', 'events.json', 'skills.json', 'activity_history.csv'] as const;
type FileName = typeof fileNames[number];

function DatasetImport({ onImported }: { onImported: () => void }) {
  const [mode, setMode] = useState<'initial' | 'append'>('initial');
  const [files, setFiles] = useState<Partial<Record<FileName, File>>>({});
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ImportResult | null>(null);
  const requiredFiles = mode === 'initial' ? fileNames : (['employees.json', 'activity_history.csv'] as const);
  async function submit(event: FormEvent) {
    event.preventDefault(); if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError(''); setResult(null);
    try {
      const payload = new FormData();
      payload.set('mode', mode);
      for (const name of requiredFiles) {
        const file = files[name];
        if (!file) throw new Error(`Выберите ${name}.`);
        if (file.size > 10 * 1024 * 1024) throw new Error(`${name}: размер файла не должен превышать 10 МБ.`);
        if (name.endsWith('.json')) {
          try { JSON.parse(await file.text()); } catch { throw new Error(`${name}: некорректный JSON. Проверьте синтаксис файла.`); }
        }
        payload.set(name, file, name);
      }
      const response = await api<ImportResult>('datasets/import', { method: 'POST', body: payload });
      setResult(response); onImported();
    } catch (error) { setError(message(error)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  return <section className="surface-card"><span className="cq-kicker">ДАННЫЕ КОМАНДЫ</span><h2>Upload Dataset</h2><p className="cq-muted">JSON-профили, события, справочник навыков с требованиями грейдов и CSV-история. Выберите файлы тестового набора для загрузки профилей и рекомендаций.</p><form className="cq-form" onSubmit={submit}><fieldset disabled={busy}><legend>Режим загрузки</legend><div className="cq-radio-group"><label><input type="radio" name="import-mode" checked={mode === 'initial'} onChange={() => { setMode('initial'); setFiles({}); setResult(null); setError(''); }} />Первоначальный набор</label><label><input type="radio" name="import-mode" checked={mode === 'append'} onChange={() => { setMode('append'); setFiles({}); setResult(null); setError(''); }} />Добавить проверочные профили</label></div></fieldset><p className="cq-caption">{mode === 'initial' ? 'Четыре файла исходного датасета. Существующий прогресс сохраняется.' : 'Новые сотрудники и их история с использованием уже загруженных навыков и событий.'}</p><div className="cq-upload-grid">{requiredFiles.map(name => <label key={`${mode}:${name}`} className="cq-upload"><strong><Icon name={files[name] ? 'check' : 'upload'} size={20} />{name}{files[name] && <span className="cq-tag">Выбран</span>}</strong><input type="file" required disabled={busy} accept={name.endsWith('.json') ? '.json,application/json' : '.csv,text/csv'} onChange={event => { setFiles(previous => ({ ...previous, [name]: event.target.files?.[0] })); setResult(null); setError(''); }} /><small>{files[name] ? `${files[name]!.name} · ${(files[name]!.size / 1024).toFixed(1)} КБ` : 'До 10 МБ'}</small></label>)}</div>{error && <ErrorNotice error={error} />}<button className="primary-button" disabled={busy || requiredFiles.some(name => !files[name])}>{busy ? 'Проверяем и загружаем…' : 'Import Dataset →'}</button></form>{result && <div className="cq-notice success" role="status"><h3>{result.status === 'unchanged' ? 'Этот набор уже загружен' : 'Датасет загружен'}</h3><ul><li>Сотрудников: {result.employees}</li><li>Событий: {result.events}</li><li>Навыков: {result.skills}</li><li>Записей истории: {result.history_records}</li></ul></div>}</section>;
}

export type HrView = 'dashboard' | 'employees' | 'skill-gaps' | 'activities' | 'import';
const titles: Record<HrView, [string, string]> = {
  dashboard: ['Рост команды начинается здесь.', 'Общая картина развития и возможности для следующего шага.'],
  employees: ['Люди и их возможности', 'Карьерные траектории, навыки и персональные рекомендации команды.'],
  'skill-gaps': ['Навыки, которым нужно внимание', 'Разрывы между текущим уровнем команды и требованиями целевых грейдов.'],
  activities: ['Как команда учится', 'Участие в активностях и результаты обучения.'],
  import: ['Данные для нового старта', 'Загрузите датасет, чтобы построить персональные траектории развития.'],
};

function SkillGaps({ revision, compact = false }: { revision: number; compact?: boolean }) {
  const gaps = useResource<SkillGap[]>('hr/skill-gaps', revision);
  const sorted = [...(gaps.data ?? [])].sort((a, b) => b.employee_count - a.employee_count || a.name.localeCompare(b.name));
  const rows = compact ? sorted.slice(0, 5) : sorted;
  const max = Math.max(1, ...sorted.map(gap => gap.employee_count));
  return <section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">КОМПЕТЕНЦИИ</span><h2>Top Skill Gaps</h2></div><span className="cq-stat-icon amber"><Icon name="chart" /></span></div><p className="cq-muted">Количество сотрудников с разрывом до целевого уровня.</p>{gaps.loading ? <Loading /> : gaps.error ? <ErrorNotice error={gaps.error} retry={gaps.retry} /> : rows.length ? <div className="cq-bar-chart">{rows.map((gap, index) => <div className="cq-chart-row" key={gap.skill_id}><div><span>{gap.name}</span><strong>{gap.employee_count}<small> чел.</small></strong></div><div className="cq-chart-track" role="img" aria-label={`${gap.name}: ${gap.employee_count} сотрудников`}><span style={{ width: `${gap.employee_count / max * 100}%`, opacity: 1 - Math.min(index, 5) * .1 }} /></div></div>)}</div> : <p className="cq-empty">Разрывов по навыкам нет.</p>}{compact && <Link className="cq-link" href="/hr/skill-gaps">Все навыки →</Link>}</section>;
}

function ActivityPerformance({ revision, compact = false }: { revision: number; compact?: boolean }) {
  const activities = useResource<ActivityStat[]>('hr/activity-stats', revision);
  const rows = compact ? activities.data?.slice(0, 3) : activities.data;
  return <section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">РЕЗУЛЬТАТЫ ОБУЧЕНИЯ</span><h2>Activity Performance</h2></div><Icon name="activity" /></div><p className="cq-muted">Доля статусов среди всех записей участия в активности.</p>{activities.loading ? <Loading /> : activities.error ? <ErrorNotice error={activities.error} retry={activities.retry} /> : rows?.length ? <><div className="cq-performance">{rows.map(activity => {
    const total = Object.values(activity.statuses).reduce((sum, value) => sum + value, 0);
    const completed = total ? activity.statuses.completed / total * 100 : 0;
    const skipped = total ? (activity.statuses.dropped + activity.statuses.no_show) / total * 100 : 0;
    const other = total ? 100 - completed - skipped : 0;
    return <article key={activity.event_id}><div className="cq-section-heading"><strong>{activity.title}</strong><span className="cq-caption">{activity.participant_count} участников</span></div><div className="cq-stacked-bar" role="img" aria-label={`Завершено ${Math.round(completed)}%, пропущено ${Math.round(skipped)}%, остальные статусы ${Math.round(other)}%`}><span className="completed" style={{ width: `${completed}%` }} /><span className="skipped" style={{ width: `${skipped}%` }} /><span className="other" style={{ width: `${other}%` }} /></div><div className="cq-chart-legend"><span><i className="completed" />Completed <strong>{Math.round(completed)}%</strong></span><span><i className="skipped" />Skipped <strong>{Math.round(skipped)}%</strong></span>{other > 0 && <span><i className="other" />Остальные <strong>{Math.round(other)}%</strong></span>}</div></article>;
  })}</div>{!compact && <><p className="cq-caption">Skipped = прервано + неявка. Остальные = в процессе + отказ + просрочено. Участники считаются уникально; повторные участия входят в распределение статусов.</p><div className="cq-table-scroll"><table><caption className="sr-only">Число записей каждого статуса</caption><thead><tr><th>Активность</th>{Object.entries(statusLabels).map(([status, label]) => <th key={status}>{label}</th>)}</tr></thead><tbody>{rows.map(activity => <tr key={activity.event_id}><td>{activity.title}</td>{Object.keys(statusLabels).map(status => <td key={status}>{activity.statuses[status as keyof typeof statusLabels]}</td>)}</tr>)}</tbody></table></div></>}</> : <p className="cq-empty">Участий пока нет.</p>}{compact && <Link className="cq-link" href="/hr/activities">Все активности →</Link>}</section>;
}

function Employees({ revision, compact = false, onSelect }: { revision: number; compact?: boolean; onSelect: (id: string) => void }) {
  const employees = useResource<Employee[]>('hr/employees?include_readiness=true', revision);
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [grade, setGrade] = useState('');
  const [page, setPage] = useState(0);
  const rows = employees.data?.filter(employee => (!role || employee.role === role) && (!grade || employee.grade === grade) && `${employee.employee_id} ${employee.full_name || ''} ${employee.role}`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru')));
  const visible = compact ? rows?.slice(0, 5) : rows?.slice(page * 15, page * 15 + 15);
  return <section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">КОМАНДА</span><h2>Сотрудники <span className="cq-count">{employees.data?.length ?? '—'}</span></h2></div>{compact && <Link className="cq-link" href="/hr/employees">Все сотрудники →</Link>}</div>{!compact && <div className="cq-filters"><label>Поиск<input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(0); }} placeholder="Имя, ID или роль" /></label><label>Роль<select value={role} onChange={event => { setRole(event.target.value); setPage(0); }}><option value="">Все роли</option>{[...new Set(employees.data?.map(employee => employee.role))].sort().map(role => <option key={role}>{role}</option>)}</select></label><label>Грейд<select value={grade} onChange={event => { setGrade(event.target.value); setPage(0); }}><option value="">Все грейды</option>{[...new Set(employees.data?.map(employee => employee.grade))].map(grade => <option key={grade}>{grade}</option>)}</select></label><button className="outline-button" onClick={() => { setQuery(''); setRole(''); setGrade(''); setPage(0); }}>Сбросить</button></div>}
    {employees.loading ? <Loading /> : employees.error ? <ErrorNotice error={employees.error} retry={employees.retry} /> : visible?.length ? <><div className="cq-table-scroll"><table><caption className="sr-only">Профили сотрудников</caption><thead><tr><th>Сотрудник</th><th>Роль</th><th>Грейд</th><th>Career readiness</th><th><span className="sr-only">Открыть</span></th></tr></thead><tbody>{visible.map(employee => <tr key={employee.employee_id}><td><button className="cq-employee-link" onClick={() => onSelect(employee.employee_id)}><span className="cq-avatar">{(employee.full_name || employee.employee_id).split(' ').map(part => part[0]).slice(0, 2).join('')}</span><span><strong>{employee.full_name || employee.employee_id}</strong><small>{employee.employee_id}</small></span></button></td><td>{employee.role}</td><td><span className="cq-tag neutral">{employee.grade}</span></td><td><div className="cq-table-progress"><strong>{percent(employee.career_readiness)}</strong>{employee.career_readiness !== null && <progress max={100} value={employee.career_readiness} aria-label={`${employee.employee_id}: ${percent(employee.career_readiness)}`} />}</div></td><td><button className="cq-icon-button" aria-label={`Открыть профиль ${employee.employee_id}`} onClick={() => onSelect(employee.employee_id)}><Icon name="arrow" size={18} /></button></td></tr>)}</tbody></table></div>{!compact && rows && rows.length > 15 && <div className="cq-pagination"><button className="outline-button" disabled={!page} onClick={() => setPage(value => value - 1)}>← Назад</button><span>{page * 15 + 1}–{Math.min((page + 1) * 15, rows.length)} из {rows.length}</span><button className="outline-button" disabled={(page + 1) * 15 >= rows.length} onClick={() => setPage(value => value + 1)}>Далее →</button></div>}</> : <p className="cq-empty">{employees.data?.length ? 'По вашему запросу сотрудников не найдено.' : 'Сотрудников пока нет. Загрузите датасет.'}</p>}
  </section>;
}

function Overview({ revision, onSelect }: { revision: number; onSelect: (id: string) => void }) {
  const dashboard = useResource<Dashboard>('hr/dashboard', revision);
  const coverage = useResource<Employee[]>('hr/recommendation-coverage', revision);
  return <div className="cq-stack">{dashboard.loading ? <Loading /> : dashboard.error ? <ErrorNotice error={dashboard.error} retry={dashboard.retry} /> : dashboard.data && <><section className="cq-metrics" aria-label="Показатели команды">{[
    { label: 'Сотрудников', value: dashboard.data.employee_count, icon: 'people' as const, note: 'В загруженном наборе' },
    { label: 'Средняя готовность', value: percent(dashboard.data.average_readiness), icon: 'chart' as const, note: 'К целевому грейду' },
    { label: 'Без рекомендации', value: dashboard.data.without_recommendations, icon: 'spark' as const, note: 'Нуждается во внимании' },
    { label: 'Активны в этом месяце', value: dashboard.data.active_this_month ?? '—', icon: 'activity' as const, note: `На ${dateLabel(dashboard.data.as_of_date)}` },
  ].map(metric => <article className="surface-card cq-metric" key={metric.label}><div><span>{metric.label}</span><Icon name={metric.icon} /></div><strong>{metric.value}</strong><small>{metric.note}</small></article>)}</section><p className="cq-caption cq-metric-note">Срез на {dateLabel(dashboard.data.as_of_date)}. Активность за месяц — участие со статусом «в процессе» или «завершено» в месяце среза.</p></>}
    <div className="cq-profile-grid"><SkillGaps revision={revision} compact /><ActivityPerformance revision={revision} compact /></div>
    <Employees revision={revision} compact onSelect={onSelect} />
    <section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">В ФОКУСЕ HR</span><h2>Без рекомендованного шага</h2></div><Icon name="spark" /></div>{coverage.loading ? <Loading /> : coverage.error ? <ErrorNotice error={coverage.error} retry={coverage.retry} /> : coverage.data?.length ? <div className="cq-coverage">{coverage.data.map(employee => <button className="cq-coverage-card" key={employee.employee_id} onClick={() => onSelect(employee.employee_id)}><span><strong>{employee.full_name || employee.employee_id}</strong><small>{employee.role} · {employee.grade}</small></span><Icon name="arrow" size={18} /></button>)}</div> : <p className="cq-empty">У каждого сотрудника есть следующий шаг.</p>}</section>
  </div>;
}

export function HrDashboard({ view = 'dashboard' }: { view?: HrView }) {
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const openProfile = (id: string) => { setSelected(id); window.scrollTo({ top: 0, behavior: 'smooth' }); };
  if (selected) return <div className="cq-stack"><button className="outline-button cq-back" onClick={() => setSelected(null)}>← К {view === 'employees' ? 'сотрудникам' : 'обзору команды'}</button><EmployeeProfile key={selected} employeeId={selected} readOnly /></div>;
  return <div className="cq-stack"><div className="cq-page-heading"><span className="cq-kicker">CAREER QUEST / HR WORKSPACE</span><h1>{titles[view][0]}</h1><p className="cq-muted">{titles[view][1]}</p></div>{view === 'dashboard' ? <Overview revision={revision} onSelect={openProfile} /> : view === 'employees' ? <Employees revision={revision} onSelect={openProfile} /> : view === 'skill-gaps' ? <SkillGaps revision={revision} /> : view === 'activities' ? <ActivityPerformance revision={revision} /> : <DatasetImport onImported={() => setRevision(value => value + 1)} />}</div>;
}
