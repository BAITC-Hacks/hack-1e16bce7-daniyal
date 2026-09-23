'use client';

import { useRef, useState, type FormEvent } from 'react';
import { api, dateLabel, message, percent } from '../lib/api';
import { statusLabels, type ActivityStat, type Dashboard, type Employee, type ImportResult, type SkillGap } from '../lib/contracts';
import { EmployeeProfile } from './employee-profile';
import { ErrorNotice, Loading, useResource } from './workspace';

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
  return <section className="surface-card"><span className="cq-kicker">ДАННЫЕ КОМАНДЫ</span><h2>Загрузить датасет</h2><p className="cq-muted">JSON-профили, события, справочник навыков с требованиями грейдов и CSV-история. Проверка связей и сохранение выполняются на сервере.</p><form className="cq-form" onSubmit={submit}><fieldset disabled={busy}><legend>Режим загрузки</legend><div className="cq-radio-group"><label><input type="radio" name="import-mode" checked={mode === 'initial'} onChange={() => { setMode('initial'); setFiles({}); setResult(null); setError(''); }} />Первоначальный набор</label><label><input type="radio" name="import-mode" checked={mode === 'append'} onChange={() => { setMode('append'); setFiles({}); setResult(null); setError(''); }} />Добавить проверочные профили</label></div></fieldset><p className="cq-caption">{mode === 'initial' ? 'Четыре файла исходного датасета. Импорт не должен перезаписывать существующий прогресс.' : 'Новые сотрудники и их история с использованием уже загруженных навыков и событий.'}</p><div className="cq-upload-grid">{requiredFiles.map(name => <label key={`${mode}:${name}`} className="cq-upload"><strong>{name}</strong><input type="file" required disabled={busy} accept={name.endsWith('.json') ? '.json,application/json' : '.csv,text/csv'} onChange={event => { setFiles(previous => ({ ...previous, [name]: event.target.files?.[0] })); setResult(null); setError(''); }} /><small>{files[name] ? `${files[name]!.name} · ${(files[name]!.size / 1024).toFixed(1)} КБ` : 'До 10 МБ'}</small></label>)}</div>{error && <ErrorNotice error={error} />}<button className="primary-button" disabled={busy || requiredFiles.some(name => !files[name])}>{busy ? 'Проверяем и загружаем…' : 'Загрузить датасет'}</button></form>{result && <div className="cq-notice success" role="status"><h3>{result.status === 'unchanged' ? 'Этот набор уже загружен' : 'Датасет загружен'}</h3><ul><li>Сотрудников: {result.employees}</li><li>Событий: {result.events}</li><li>Навыков: {result.skills}</li><li>Записей истории: {result.history_records}</li></ul></div>}</section>;
}

function Overview({ revision }: { revision: number }) {
  const dashboard = useResource<Dashboard>('hr/dashboard', revision);
  const gaps = useResource<SkillGap[]>('hr/skill-gaps', revision);
  const activities = useResource<ActivityStat[]>('hr/activity-stats', revision);
  const coverage = useResource<Employee[]>('hr/recommendation-coverage', revision);
  const [selected, setSelected] = useState<string | null>(null);
  if (selected) return <div className="cq-stack"><button className="outline-button cq-back" onClick={() => setSelected(null)}>← К обзору</button><EmployeeProfile key={selected} employeeId={selected} readOnly /></div>;
  return <div className="cq-stack">{dashboard.loading ? <Loading /> : dashboard.error ? <ErrorNotice error={dashboard.error} retry={dashboard.retry} /> : dashboard.data && <><p className="cq-caption">Срез на {dateLabel(dashboard.data.as_of_date)} · показатели по всему загруженному набору</p><section className="metric-grid" aria-label="Показатели команды">{[{ label: 'Сотрудников', value: dashboard.data.employee_count }, { label: 'Средняя готовность', value: percent(dashboard.data.average_readiness) }, { label: 'Без следующего шага', value: dashboard.data.without_recommendations }, { label: 'Завершённых участий', value: dashboard.data.completed_activities }].map(metric => <article className="metric-card cq-metric" key={metric.label}><strong>{metric.value}</strong><span>{metric.label}</span></article>)}</section></>}
    <div className="cq-profile-grid"><section className="surface-card"><span className="cq-kicker">КОМПЕТЕНЦИИ</span><h2>Где нужна поддержка</h2><p className="cq-muted">Количество сотрудников с разрывом до целевого уровня.</p>{gaps.loading ? <Loading /> : gaps.error ? <ErrorNotice error={gaps.error} retry={gaps.retry} /> : gaps.data && (gaps.data.length ? gaps.data.map(gap => <div className="cq-gap" key={gap.skill_id}><strong>{gap.name}</strong><span>{gap.employee_count} чел.</span></div>) : <p className="cq-empty">Разрывов по навыкам нет.</p>)}</section><section className="surface-card"><span className="cq-kicker">В ФОКУСЕ HR</span><h2>Без рекомендованного шага</h2>{coverage.loading ? <Loading /> : coverage.error ? <ErrorNotice error={coverage.error} retry={coverage.retry} /> : coverage.data && (coverage.data.length ? coverage.data.map(employee => <div className="cq-gap" key={employee.employee_id}><div><button className="cq-link" onClick={() => setSelected(employee.employee_id)}>{employee.full_name || employee.employee_id} ↗</button><small>{employee.role} · {employee.grade}</small></div><span>{employee.employee_id}</span></div>) : <p className="cq-empty">Нет сотрудников без рекомендаций.</p>)}</section></div>
    <section className="surface-card"><h2>Участие в активностях</h2><p className="cq-muted">Участники и число записей каждого статуса за всю историю датасета.</p>{activities.loading ? <Loading /> : activities.error ? <ErrorNotice error={activities.error} retry={activities.retry} /> : activities.data && (activities.data.length ? <div className="cq-table-scroll"><table><caption className="sr-only">Статистика активностей</caption><thead><tr><th>Активность</th><th>Участников</th>{Object.entries(statusLabels).map(([status, label]) => <th key={status}>{label}</th>)}</tr></thead><tbody>{activities.data.map(activity => <tr key={activity.event_id}><td>{activity.title}</td><td>{activity.participant_count}</td>{Object.keys(statusLabels).map(status => <td key={status}>{activity.statuses[status as keyof typeof statusLabels]}</td>)}</tr>)}</tbody></table></div> : <p className="cq-empty">Участий пока нет.</p>)}</section>
  </div>;
}

function Employees({ revision }: { revision: number }) {
  const employees = useResource<Employee[]>('hr/employees', revision);
  const [query, setQuery] = useState('');
  const [role, setRole] = useState('');
  const [grade, setGrade] = useState('');
  const [selected, setSelected] = useState<string | null>(null);
  const [directId, setDirectId] = useState('');
  const rows = employees.data?.filter(employee => (!role || employee.role === role) && (!grade || employee.grade === grade) && `${employee.employee_id} ${employee.full_name || ''} ${employee.role}`.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru')));
  if (selected) return <div className="cq-stack"><button className="outline-button cq-back" onClick={() => setSelected(null)}>← К сотрудникам</button><EmployeeProfile key={selected} employeeId={selected} readOnly /></div>;
  return <section className="surface-card"><h2>Сотрудники</h2><form className="cq-direct" onSubmit={event => { event.preventDefault(); if (directId.trim()) setSelected(directId.trim()); }}><label>Открыть по ID<input maxLength={200} required placeholder="Произвольный employee ID" value={directId} onChange={event => setDirectId(event.target.value)} /></label><button className="outline-button" disabled={!directId.trim()}>Открыть профиль →</button></form><div className="cq-filters"><label>Поиск<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Имя, ID или роль" /></label><label>Роль<select value={role} onChange={event => setRole(event.target.value)}><option value="">Все роли</option>{[...new Set(employees.data?.map(employee => employee.role))].map(role => <option key={role}>{role}</option>)}</select></label><label>Грейд<select value={grade} onChange={event => setGrade(event.target.value)}><option value="">Все грейды</option>{[...new Set(employees.data?.map(employee => employee.grade))].map(grade => <option key={grade}>{grade}</option>)}</select></label><button className="outline-button" onClick={() => { setQuery(''); setRole(''); setGrade(''); }}>Сбросить</button></div>{employees.loading ? <Loading /> : employees.error ? <ErrorNotice error={employees.error} retry={employees.retry} /> : rows && (rows.length ? <div className="cq-table-scroll"><table><caption className="sr-only">Профили сотрудников</caption><thead><tr><th>Сотрудник</th><th>Роль</th><th>Грейд</th><th>Готовность</th></tr></thead><tbody>{rows.map(employee => <tr key={employee.employee_id}><td><button className="cq-link" onClick={() => setSelected(employee.employee_id)}>{employee.full_name || employee.employee_id} ↗</button>{employee.full_name && <small>{employee.employee_id}</small>}</td><td>{employee.role}</td><td>{employee.grade}</td><td>{percent(employee.career_readiness)}</td></tr>)}</tbody></table></div> : <p className="cq-empty">{employees.data?.length ? 'По вашему запросу сотрудников не найдено.' : 'Сотрудников пока нет. Загрузите датасет.'}</p>)}</section>;
}

export function HrDashboard() {
  const [tab, setTab] = useState('overview');
  const [revision, setRevision] = useState(0);
  return <div className="cq-stack"><section className="cq-hr-hero"><span className="cq-kicker">ПРОСТРАНСТВО HR</span><h1>Развитие начинается<br />с внимания к людям.</h1><p>Навыки команды, следующие шаги и участие в обучении.</p></section><nav className="cq-tabs" aria-label="Разделы HR">{[{ id: 'overview', label: 'Обзор команды' }, { id: 'employees', label: 'Сотрудники' }, { id: 'import', label: 'Загрузка данных' }].map(item => <button key={item.id} aria-current={tab === item.id ? 'page' : undefined} onClick={() => setTab(item.id)}>{item.label}</button>)}</nav>{tab === 'overview' ? <Overview revision={revision} /> : tab === 'employees' ? <Employees revision={revision} /> : <DatasetImport onImported={() => setRevision(value => value + 1)} />}</div>;
}
