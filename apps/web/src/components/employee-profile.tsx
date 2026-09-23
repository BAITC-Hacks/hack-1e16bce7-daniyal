'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { api, dateLabel, employeePath, jsonPost, message, percent } from '../lib/api';
import { statusLabels, type Activity, type Page, type Completion, type Employee, type Event, type Recommendation, type Skill, type Trajectory } from '../lib/contracts';
import { ErrorNotice, Loading, useResource } from './workspace';
import { Icon, Readiness, SkillTable } from './ui';

export type EmployeeView = 'dashboard' | 'career' | 'recommendations' | 'activities' | 'history';
const viewTitles: Record<EmployeeView, [string, string]> = {
  dashboard: ['Ваш следующий уровень — ближе.', 'Навыки, возможности и понятный план развития.'],
  career: ['Моя карьерная траектория', 'Ваша цель и конкретные навыки, которые помогут к ней прийти.'],
  recommendations: ['Шаги, подобранные для вас', 'До трёх рекомендаций с учётом цели, навыков и истории участия.'],
  activities: ['Возможности для роста', 'Найдите следующую активность для развития своих навыков.'],
  history: ['История вашего развития', 'Все активности и результаты в одном месте.'],
};
const eventTypes: Record<string, string> = { workshop: 'Workshop', course: 'Курс', meetup: 'Meetup', webinar: 'Вебинар', mentoring: 'Менторство', conference: 'Конференция', hackathon: 'Хакатон' };

function useHistory(employeeId: string, revision: number) {
  const [state, setState] = useState<{ items: Activity[]; error: string; loading: boolean }>({ items: [], error: '', loading: true });
  const [retryCount, setRetryCount] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ items: [], error: '', loading: true });
    async function load() {
      const items: Activity[] = [];
      let offset = 0;
      while (!controller.signal.aborted) {
        const page = await api<Page<Activity>>(`${employeePath(employeeId)}/activities?limit=100&offset=${offset}`, { signal: controller.signal });
        items.push(...page.items);
        offset += page.items.length;
        if (offset >= page.total || !page.items.length) break;
      }
      if (!controller.signal.aborted) setState({ items: items.sort((a, b) => (b.completed_on || b.date).localeCompare(a.completed_on || a.date) || b.record_id.localeCompare(a.record_id)), error: '', loading: false });
    }
    void load().catch(error => { if (!controller.signal.aborted) setState({ items: [], error: message(error), loading: false }); });
    return () => controller.abort();
  }, [employeeId, revision, retryCount]);
  return { ...state, retry: () => setRetryCount(value => value + 1) };
}

function RecommendationCard({ recommendation: rec, onOpen, featured = false }: { recommendation: Recommendation; onOpen: () => void; featured?: boolean }) {
  return <article className={`surface-card cq-recommendation ${featured ? 'cq-featured' : ''}`}>
    <div className="cq-section-heading"><span className="cq-tag amber"><span className="cq-status-dot" />{rec.priority === 1 ? 'Высокий приоритет' : rec.priority === 2 ? 'Средний приоритет' : 'Дополнительный шаг'}</span><span className="cq-caption"><Icon name="spark" size={14} />{rec.explanation_source === 'ai' ? 'AI-рекомендация' : 'На основе вашего профиля'}</span></div>
    <div className="cq-activity-icon"><Icon name="activity" size={26} /></div><h3>{rec.title}</h3>
    <ul className="cq-effects">{rec.skills.map(skill => <li key={skill.skill_id}><strong>{skill.name}<span className="cq-tag">+{skill.predicted_level - skill.current_level}</span></strong><span>Сейчас: {skill.current_level} · Требуется: {skill.required_level ?? '—'} · После: {skill.predicted_level}</span></li>)}</ul>
    <div className="cq-why"><strong><Icon name="spark" size={16} />Почему рекомендуем</strong><ul>{rec.skills.filter(skill => skill.required_level !== null && skill.required_level > skill.current_level).map(skill => <li key={skill.skill_id}>{skill.name}: до цели не хватает {skill.required_level! - skill.current_level}; активность даёт +{skill.predicted_level - skill.current_level}.</li>)}</ul><p>{rec.reason}</p></div>
    <div className="cq-recommendation-bottom"><div><span className="cq-caption">Career readiness</span><strong>{percent(rec.career_readiness_before)} <span>→</span> {percent(rec.career_readiness_after)}</strong></div><button className="primary-button" onClick={onOpen}>Подробнее <Icon name="arrow" size={17} /></button></div>
  </article>;
}

type SelectedActivity = { event_id: string; title: string; recommendation?: Recommendation };
function ActivityDetails({ selected, employeeId, readOnly, onClose, onComplete }: { selected: SelectedActivity; employeeId: string; readOnly: boolean; onClose: () => void; onComplete: (result: Completion) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const event = useResource<Event>(`events/${encodeURIComponent(selected.event_id)}?employee_id=${encodeURIComponent(employeeId)}`);
  const recommendation = selected.recommendation;
  const previewData = recommendation ?? event.data?.preview;
  const history = useHistory(employeeId, 0);
  const [recordId, setRecordId] = useState('');
  const [sessionDate, setSessionDate] = useState('');
  const requestIdentity = useRef<{ payload: string; key: string } | null>(null);
  const participations = history.items.filter(item => item.event_id === selected.event_id && ['in_progress', 'overdue', 'completed'].includes(item.status));
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const element = dialog.current;
    element?.showModal();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { element?.close(); document.body.style.overflow = overflow; previous?.focus(); };
  }, []);
  async function complete() {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(true); setError('');
    const payload = recordId ? { record_id: recordId } : sessionDate ? { session_date: sessionDate } : {};
    const serialized = JSON.stringify(payload);
    if (requestIdentity.current?.payload !== serialized) {
      const bytes = crypto.getRandomValues(new Uint8Array(16));
      requestIdentity.current = { payload: serialized, key: Array.from(bytes, value => value.toString(16).padStart(2, '0')).join('') };
    }
    try { onComplete(await api<Completion>(`${employeePath(employeeId)}/activities/${encodeURIComponent(selected.event_id)}/complete`, {
      ...jsonPost(payload), headers: { 'Content-Type': 'application/json', 'Idempotency-Key': requestIdentity.current.key },
    })); }
    catch (error) { setError(message(error)); }
    finally { busyRef.current = false; setBusy(false); }
  }
  return <dialog className="cq-dialog" ref={dialog} aria-labelledby="activity-title" onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}><div className="cq-dialog-content">
    <div className="cq-section-heading"><span className="cq-kicker">ВАШ СЛЕДУЮЩИЙ ШАГ</span><button className="outline-button" onClick={onClose} disabled={busy} autoFocus>Закрыть ×</button></div>
    <div className="cq-activity-icon"><Icon name="activity" size={28} /></div><h2 id="activity-title">{selected.title}</h2>
    {event.loading ? <Loading /> : event.error ? <ErrorNotice error={event.error} retry={event.retry} /> : event.data && <><div className="cq-event-meta"><span className="cq-tag neutral">{eventTypes[event.data.type] || event.data.type}</span>{event.data.duration_hours != null && <span className="cq-tag neutral">{event.data.duration_hours} ч</span>}</div><p className="cq-muted">{event.data.description}</p><h3>Что развивает активность</h3><ul className="cq-effects">{event.data.develops_skills.map(skill => {
      const preview = previewData?.skills.find(item => item.skill_id === skill.skill_id);
      return <li key={skill.skill_id}><strong>{skill.name}<span className="cq-tag">+{skill.gain}</span></strong><span>{preview && `Текущий уровень: ${preview.current_level} → После завершения: ${preview.predicted_level} · `}Максимум активности: {skill.max_level}</span></li>;
    })}</ul></>}
    {recommendation && <div className="cq-why"><strong><Icon name="spark" size={16} />Почему рекомендуем</strong><p>{recommendation.reason}</p></div>}{previewData && <div className="cq-preview"><span>Career readiness</span><strong>{percent(previewData.career_readiness_before)} <Icon name="arrow" /> {percent(previewData.career_readiness_after)}</strong></div>}
    {error && <ErrorNotice error={error} />}{readOnly ? <p className="cq-caption">Просмотр профиля сотрудника. Завершение доступно в его личном кабинете.</p> : <><p className="cq-caption">Демо-симуляция: завершение сразу обновит навыки, даже если сессия ещё не наступила.</p>{participations.length > 0 && <label>Участие<select disabled={busy} value={recordId} onChange={e => { setRecordId(e.target.value); setSessionDate(''); }}><option value="">Новое участие</option>{participations.map(item => <option key={item.record_id} value={item.record_id}>{dateLabel(item.date)} · {statusLabels[item.status]}</option>)}</select></label>}{!recordId && !!event.data?.upcoming_sessions?.length && <label>Сессия<select disabled={busy} value={sessionDate} onChange={e => setSessionDate(e.target.value)}><option value="">{event.data.repeatable ? 'Выберите сессию' : 'Ближайшая сессия'}</option>{event.data.upcoming_sessions.map(day => <option key={day} value={day}>{dateLabel(day)}</option>)}</select></label>}{event.data?.mandatory && !recordId && <p className="cq-caption">Для обязательной активности выберите существующее назначение.</p>}<button className="primary-button cq-full-width" disabled={busy || !event.data || (!!event.data?.repeatable && !recordId && !sessionDate) || (!!event.data?.mandatory && !recordId)} onClick={complete}><Icon name="check" />{busy ? 'Сохраняем результат…' : 'Завершить в демо'}</button></>}
  </div></dialog>;
}

function ActivityCatalog({ onOpen, revision }: { onOpen: (event: Event) => void; revision: number }) {
  const events = useResource<Event[]>('events', revision);
  const [query, setQuery] = useState('');
  const [type, setType] = useState('');
  const rows = events.data?.filter(event => (!type || event.type === type) && `${event.title} ${event.develops_skills.map(skill => skill.name).join(' ')}`.toLocaleLowerCase('ru').includes(query.toLocaleLowerCase('ru')));
  return <section><div className="cq-section-heading"><h2>Каталог активностей</h2><span className="cq-caption">{rows?.length ?? '—'} доступно</span></div><div className="cq-filters cq-catalog-filters"><label>Поиск<input type="search" placeholder="Название или навык" value={query} onChange={event => setQuery(event.target.value)} /></label><label>Формат активности<select value={type} onChange={event => setType(event.target.value)}><option value="">Все типы</option>{[...new Set(events.data?.map(event => event.type))].map(kind => <option key={kind} value={kind}>{eventTypes[kind] || kind}</option>)}</select></label></div>{events.loading ? <Loading /> : events.error ? <ErrorNotice error={events.error} retry={events.retry} /> : rows?.length ? <div className="cq-catalog-grid">{rows.map(event => <article className="surface-card cq-catalog-card" key={event.event_id}><div className="cq-section-heading"><span className="cq-activity-icon"><Icon name="activity" /></span><span className="cq-tag neutral">{eventTypes[event.type] || event.type}</span></div><h3>{event.title}</h3><p className="cq-muted">{event.description}</p><div className="cq-event-meta">{event.develops_skills.map(skill => <span key={skill.skill_id} className="cq-tag">{skill.name} +{skill.gain}</span>)}</div><div className="cq-catalog-bottom"><span className="cq-caption">{event.duration_hours != null ? `${event.duration_hours} ч` : 'Длительность не указана'}</span><button className="cq-link" onClick={() => onOpen(event)}>Подробнее →</button></div></article>)}</div> : <p className="surface-card cq-empty">{events.data?.length ? 'По вашему запросу активностей не найдено.' : 'В каталоге пока нет активностей.'}</p>}</section>;
}

const historyFilters = [{ id: 'all', label: 'Все' }, { id: 'completed', label: 'Completed' }, { id: 'skipped', label: 'Skipped' }, { id: 'declined', label: 'Declined' }, { id: 'in_progress', label: 'В процессе' }, { id: 'overdue', label: 'Просрочено' }];
function matchesFilter(activity: Activity, filter: string) { return filter === 'all' || (filter === 'skipped' ? ['dropped', 'no_show'].includes(activity.status) : activity.status === filter); }
function History({ history, compact = false }: { history: ReturnType<typeof useHistory>; compact?: boolean }) {
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(0);
  const rows = history.items.filter(activity => matchesFilter(activity, filter));
  const visible = compact ? rows.slice(0, 3) : rows.slice(page * 10, page * 10 + 10);
  return <section className="surface-card"><div className="cq-section-heading"><h2>{compact ? 'Последние активности' : 'История активностей'}</h2>{compact && <Link className="cq-link" href="/history">Вся история →</Link>}</div>{!compact && <><div className="cq-filter-tabs" aria-label="Фильтр истории">{historyFilters.map(item => <button key={item.id} aria-pressed={filter === item.id} onClick={() => { setFilter(item.id); setPage(0); }}>{item.label}<span>{history.items.filter(activity => matchesFilter(activity, item.id)).length}</span></button>)}</div>{filter === 'skipped' && <p className="cq-caption">Skipped объединяет прерванные активности и неявки; исходный статус сохранён в таблице.</p>}</>}
    {history.loading ? <Loading /> : history.error ? <ErrorNotice error={history.error} retry={history.retry} /> : visible.length ? <><div className="cq-table-scroll"><table><caption className="sr-only">История участия сотрудника</caption><thead><tr><th>Активность</th><th>Статус</th><th>Дата</th></tr></thead><tbody>{visible.map(activity => <tr key={activity.record_id}><td><strong>{activity.title}</strong>{activity.simulated && <small>Демо-симуляция</small>}</td><td><span className={`cq-tag ${activity.status === 'completed' ? '' : activity.status === 'in_progress' ? 'amber' : 'neutral'}`}>{activity.status === 'completed' && <Icon name="check" size={13} />}{statusLabels[activity.status] || activity.status}</span></td><td className="cq-nowrap cq-muted">{dateLabel(activity.completed_on || activity.date)}</td></tr>)}</tbody></table></div>{!compact && rows.length > 10 && <div className="cq-pagination"><button className="outline-button" disabled={page === 0} onClick={() => setPage(value => value - 1)}>← Назад</button><span>{page * 10 + 1}–{Math.min((page + 1) * 10, rows.length)} из {rows.length}</span><button className="outline-button" disabled={(page + 1) * 10 >= rows.length} onClick={() => setPage(value => value + 1)}>Далее →</button></div>}</> : <div className="cq-empty"><Icon name="history" size={28} /><p>{history.items.length ? 'В этой категории пока нет активностей.' : 'История пока пуста. Начните с рекомендованного шага.'}</p></div>}
  </section>;
}

export function EmployeeProfile({ employeeId, readOnly = false, view = 'dashboard' }: { employeeId: string; readOnly?: boolean; view?: EmployeeView }) {
  const [revision, setRevision] = useState(0);
  const [selected, setSelected] = useState<SelectedActivity | null>(null);
  const [completed, setCompleted] = useState<Completion | null>(null);
  const [profileView, setProfileView] = useState<EmployeeView>('dashboard');
  const currentView = readOnly ? profileView : view;
  const base = employeePath(employeeId);
  const profile = useResource<Employee>(base, revision);
  const trajectory = useResource<Trajectory>(`${base}/trajectory`, revision);
  const skills = useResource<Skill[]>(`${base}/skills`, revision);
  const recommendations = useResource<Recommendation[]>(`${base}/recommendations`, revision, true);
  const history = useHistory(employeeId, revision);
  const target = trajectory.data?.target_grade;
  const gaps = trajectory.data?.requirements.filter(skill => skill.required_level !== null && skill.current_level < skill.required_level).sort((a, b) => Number(b.critical) - Number(a.critical) || (b.required_level! - b.current_level) - (a.required_level! - a.current_level)) ?? [];
  const openRecommendation = (recommendation: Recommendation) => setSelected({ ...recommendation, recommendation });
  const title = viewTitles[currentView];
  const recommendationSection = (featured = false) => <section><div className="cq-section-heading"><div><span className="cq-kicker"><Icon name="spark" size={14} />ПЕРСОНАЛЬНЫЙ ПЛАН</span><h2>{featured ? 'Рекомендуемый следующий шаг' : 'Ваши рекомендации'}</h2></div>{featured ? (readOnly ? <button className="cq-link" onClick={() => setProfileView('recommendations')}>Все рекомендации →</button> : <Link className="cq-link" href="/recommendations">Все рекомендации →</Link>) : <button className="outline-button" disabled={recommendations.loading} onClick={recommendations.retry}>Обновить</button>}</div>{recommendations.loading ? <Loading text="Подбираем шаги развития…" /> : recommendations.error ? <ErrorNotice error={recommendations.error} retry={recommendations.retry} /> : recommendations.data?.length ? <div className={featured ? '' : 'cq-recommendations'}>{recommendations.data.slice(0, featured ? 1 : 3).map(rec => <RecommendationCard key={rec.event_id} recommendation={rec} featured={featured} onOpen={() => openRecommendation(rec)} />)}</div> : <div className="surface-card cq-empty"><Icon name="check" size={28} /><h3>Подходящих шагов пока нет</h3><p>{target ? 'Сейчас нет доступных активностей, соответствующих вашим навыкам и цели.' : 'Следующий грейд не задан. Продолжайте развивать навыки в своей роли.'}</p></div>}</section>;
  return <div className="cq-stack">
    <div className="cq-page-heading"><span className="cq-kicker">{readOnly ? `ПРОФИЛЬ СОТРУДНИКА · ${employeeId}` : 'CAREER QUEST / YOUR GROWTH'}</span><h1>{title[0]}</h1><p className="cq-muted">{title[1]}</p></div>
    {readOnly && <nav className="cq-tabs" aria-label="Разделы профиля сотрудника">{(['dashboard', 'career', 'recommendations', 'history'] as const).map(item => <button key={item} aria-current={currentView === item ? 'page' : undefined} onClick={() => setProfileView(item)}>{({ dashboard: 'Обзор', career: 'Траектория и навыки', recommendations: 'Рекомендации', history: 'История' })[item]}</button>)}</nav>}
    {completed && <section className="cq-notice success" role="status"><div className="cq-section-heading"><h2><Icon name="check" />{completed.already_completed ? 'Выполнение уже учтено' : 'Активность завершена!'}</h2><button className="outline-button" onClick={() => setCompleted(null)}>Скрыть ×</button></div>{completed.changes.length ? <div className="cq-completion-changes">{completed.changes.map(change => <div key={change.skill_id}><span>{change.name}</span><strong>{change.before} → {change.after}</strong></div>)}<div><span>Career readiness</span><strong>{percent(completed.career_readiness_before)} → {percent(completed.career_readiness_after)}</strong></div></div> : <p>Готовность: {percent(completed.career_readiness_after)}. Уровни навыков не изменились.</p>}<p>Ваш профиль обновлён. Следующие рекомендации учитывают новый уровень навыков.</p></section>}
    {(currentView === 'dashboard' || currentView === 'career') && <>{profile.loading ? <Loading text="Загружаем профиль…" /> : profile.error ? <ErrorNotice error={profile.error} retry={profile.retry} /> : profile.data && <section className="cq-profile-hero"><div><span className="cq-hero-badge">ВАШ КАРЬЕРНЫЙ ПУТЬ</span><h2>{profile.data.full_name || profile.data.employee_id}</h2><p className="cq-role">{profile.data.role}</p><div className="cq-grade-line"><span>{profile.data.grade}</span><Icon name="arrow" /><strong>{target || 'Следующая цель не задана'}</strong></div><div className="cq-hero-meta"><span>ID: {profile.data.employee_id}</span><span>Стаж: {profile.data.tenure_months} мес.</span>{profile.data.department && <span>{profile.data.department}</span>}</div></div><Readiness value={trajectory.data?.career_readiness ?? profile.data.career_readiness} target={target} /></section>}{trajectory.error && <ErrorNotice error={trajectory.error} retry={trajectory.retry} />}</>}
    {currentView === 'dashboard' && <><section className="cq-quick-stats" aria-label="Ваш прогресс"><div><span className="cq-stat-icon"><Icon name="path" /></span><div><span>Следующий грейд</span><strong>{trajectory.loading ? '…' : target || 'Не задан'}</strong></div></div><div><span className="cq-stat-icon amber"><Icon name="chart" /></span><div><span>Навыков в фокусе</span><strong>{trajectory.data ? gaps.length : '—'}</strong></div></div><div><span className="cq-stat-icon"><Icon name="check" /></span><div><span>Активностей завершено</span><strong>{history.loading || history.error ? '—' : history.items.filter(item => item.status === 'completed').length}</strong></div></div></section><div className="cq-dashboard-grid"><section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">ФОКУС РАЗВИТИЯ</span><h2>Основные skill gaps</h2></div><Icon name="chart" /></div><p className="cq-muted">Текущий уровень / требование {target || 'целевого грейда'}.</p>{trajectory.loading ? <Loading /> : trajectory.data && (gaps.length ? <SkillTable skills={gaps} compact /> : <p className="cq-empty">{target ? 'Все заданные требования выполнены ✓' : 'Следующий грейд пока не задан.'}</p>)}{readOnly ? <button className="outline-button cq-full-width" onClick={() => setProfileView('career')}>Посмотреть траекторию →</button> : <Link className="outline-button cq-full-width" href="/career">Посмотреть траекторию →</Link>}</section>{recommendationSection(true)}</div>{!readOnly && <History history={history} compact />}</>}
    {currentView === 'career' && <><section className="surface-card"><div className="cq-section-heading"><div><span className="cq-kicker">ВАША ТРАЕКТОРИЯ</span><h2>Каждый уровень — новая возможность</h2></div></div>{trajectory.loading ? <Loading /> : trajectory.data && <><ol className="cq-path" aria-label="Карьерные грейды">{trajectory.data.grades.map((grade, index) => <li key={grade} className={grade === trajectory.data!.current_grade ? 'current' : grade === target ? 'target' : ''}><span className="cq-path-node">{index < trajectory.data!.grades.indexOf(trajectory.data!.current_grade) ? <Icon name="check" size={17} /> : index + 1}</span><strong>{grade}</strong><small>{grade === trajectory.data!.current_grade ? 'Вы здесь' : grade === target ? 'Следующая цель' : index < trajectory.data!.grades.indexOf(trajectory.data!.current_grade) ? 'Пройдено' : 'Впереди'}</small></li>)}</ol><div className="cq-section-heading"><h3>{target ? `Требования ${trajectory.data.target_role || profile.data?.role || ''} · ${target}` : 'Следующий грейд не задан'}</h3><span className="cq-tag">{trajectory.data.requirements.filter(skill => skill.required_level !== null && skill.current_level >= skill.required_level).length} / {trajectory.data.requirements.length} выполнено</span></div><SkillTable skills={trajectory.data.requirements} /></>}</section><section className="surface-card"><h2>Все навыки</h2>{skills.loading ? <Loading /> : skills.error ? <ErrorNotice error={skills.error} retry={skills.retry} /> : skills.data && <SkillTable skills={skills.data.map(skill => trajectory.data?.requirements.find(item => item.skill_id === skill.skill_id) || skill)} />}</section></>}
    {currentView === 'recommendations' && recommendationSection()}
    {currentView === 'activities' && <>{recommendationSection()}<ActivityCatalog revision={revision} onOpen={event => setSelected({ ...event, recommendation: recommendations.data?.find(rec => rec.event_id === event.event_id) })} /></>}
    {currentView === 'history' && <History history={history} />}
    {selected && <ActivityDetails selected={selected} employeeId={employeeId} readOnly={readOnly} onClose={() => setSelected(null)} onComplete={result => { setCompleted(result); setSelected(null); setRevision(value => value + 1); window.scrollTo({ top: 0, behavior: 'smooth' }); }} />}
  </div>;
}
