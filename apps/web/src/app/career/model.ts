export type Person = { employee_id: string; full_name: string; department: string; role: string; grade: string; tenure_months: number; last_review_date: string; hire_date: string; career_goal: { target_role: string; target_grade: string } | null; skills: Record<string, number> };
export type EventItem = { event_id: string; title: string; description: string; type: string; format: string; duration_hours: number; mandatory: boolean; target_roles: string[]; target_grades: string[]; develops_skills: { skill_id: string; gain: number; max_level: number }[]; prerequisites: Record<string, number>; upcoming_sessions: string[] };
export type Skill = { skill_id: string; name: string; type: string; category: string; description: string };
export type Profile = { role: string; grade: string; required_skills: Record<string, number>; critical_skills: string[] };
export type Activity = { record_id: string; employee_id: string; event_id: string; date: string; due_date: string; status: string; completion_pct: number; score: number | null; feedback_rating: number | null; assigned_by: string; session_date?: string; simulation?: boolean };
export type Dataset = { meta: { dataset: string; version: string; as_of_date: string }; employees: Person[]; events: EventItem[]; skills: Skill[]; role_profiles: Profile[]; history: Activity[] };
export type Gain = { id: string; name: string; before: number; after: number; target: number; critical: boolean };
export type Recommendation = { event: EventItem; points: number; reasons: string[]; gains: Gain[]; session: string; improvement: number };
export const grades = ['Junior', 'Middle', 'Senior', 'Lead'];
export const statusLabels: Record<string, string> = { completed: 'Завершено', in_progress: 'В плане', dropped: 'Прервано', no_show: 'Пропущено', declined: 'Отказ', overdue: 'Просрочено' };
export const formatLabels: Record<string, string> = { online: 'Онлайн', offline: 'Очно', self_paced: 'В своём темпе' };
export const typeLabels: Record<string, string> = { course: 'Курс', workshop: 'Практикум', meetup: 'Встреча', mentoring: 'Менторство', certification: 'Сертификация', compliance: 'Обязательное обучение', onboarding: 'Онбординг' };
export const dayDiff = (a: string, b: string) => Math.floor((Date.parse(a) - Date.parse(b)) / 86400000);
export const dateLabel = (value: string) => value ? new Date(value + 'T12:00:00').toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) : 'Без даты';
export const nameOf = (data: Dataset, id: string) => data.skills.find(s => s.skill_id === id)?.name || id;
export function targetFor(data: Dataset, person: Person) {
  const goal = person.career_goal || { target_role: person.role, target_grade: grades[Math.min(grades.indexOf(person.grade) + 1, 3)] };
  return data.role_profiles.find(p => p.role === goal.target_role && p.grade === goal.target_grade)!;
}
export function historyFor(data: Dataset, id: string) { return data.history.filter(h => h.employee_id === id && h.date <= data.meta.as_of_date).sort((a, b) => b.date.localeCompare(a.date) || b.record_id.localeCompare(a.record_id)); }
export function applyEffects(levels: Record<string, number>, event: EventItem) {
  const result = { ...levels };
  for (const effect of event.develops_skills) { const before = result[effect.skill_id] || 0; result[effect.skill_id] = Math.max(before, Math.min(before + effect.gain, effect.max_level, 5)); }
  return result;
}
// The profile is a review snapshot. Replay subsequent completions exactly once;
// never write calculated levels back into that snapshot.
export function levelsFor(data: Dataset, person: Person) {
  let levels = { ...person.skills };
  for (const row of historyFor(data, person.employee_id).filter(h => h.status === 'completed' && (h.date > person.last_review_date || h.simulation)).reverse()) {
    const event = data.events.find(e => e.event_id === row.event_id);
    if (event) levels = applyEffects(levels, event);
  }
  return levels;
}
export function coverage(levels: Record<string, number>, profile: Profile) {
  const entries = Object.entries(profile.required_skills), total = entries.reduce((s, [, v]) => s + v, 0);
  return total ? Math.round(entries.reduce((s, [id, v]) => s + Math.min(levels[id] || 0, v), 0) / total * 100) : 100;
}
export function gapsFor(data: Dataset, person: Person) {
  const target = targetFor(data, person), levels = levelsFor(data, person);
  return Object.entries(target.required_skills).map(([id, required]) => ({ id, name: nameOf(data, id), level: levels[id] || 0, required, critical: target.critical_skills.includes(id), gap: Math.max(0, required - (levels[id] || 0)) })).sort((a, b) => Number(b.critical) - Number(a.critical) || b.gap - a.gap || a.name.localeCompare(b.name));
}
export function idleDays(data: Dataset, person: Person) {
  const voluntary = new Set(data.events.filter(e => !e.mandatory).map(e => e.event_id));
  const last = historyFor(data, person.employee_id).find(h => h.status === 'completed' && voluntary.has(h.event_id));
  return Math.max(0, dayDiff(data.meta.as_of_date, last?.date || person.hire_date));
}
export function availability(data: Dataset, person: Person, event: EventItem): string | null {
  const levels = levelsFor(data, person), history = historyFor(data, person.employee_id);
  if (!event.target_roles.includes(person.role) || !event.target_grades.includes(person.grade)) return 'Для другой роли или грейда';
  if (history.some(h => h.event_id === event.event_id && h.status === 'in_progress')) return 'Уже в плане';
  if (history.some(h => h.event_id === event.event_id && h.status === 'completed' && (event.event_id !== 'EV_036' || h.date === data.meta.as_of_date))) return 'Уже завершено';
  const prerequisite = Object.entries(event.prerequisites).find(([id, v]) => (levels[id] || 0) < v);
  if (prerequisite) return nameOf(data, prerequisite[0]) + ': нужен уровень ' + prerequisite[1];
  if (event.format !== 'self_paced' && !event.upcoming_sessions.some(d => d >= data.meta.as_of_date)) return 'Новых сессий пока нет';
  return null;
}
export function recommend(data: Dataset, person: Person): Recommendation[] {
  const levels = levelsFor(data, person), profile = targetFor(data, person), history = historyFor(data, person.employee_id), baseline = coverage(levels, profile);
  const completed = history.filter(h => h.status === 'completed').length;
  return data.events.filter(e => !e.mandatory && !availability(data, person, e)).map(event => {
    const after = applyEffects(levels, event);
    const gains = event.develops_skills.map(e => ({ id: e.skill_id, name: nameOf(data, e.skill_id), before: levels[e.skill_id] || 0, after: after[e.skill_id], target: profile.required_skills[e.skill_id] || 0, critical: profile.critical_skills.includes(e.skill_id) })).filter(g => g.after > g.before);
    const useful = gains.filter(g => g.target > g.before);
    // Related activity types and overlapping skills matter even when IDs differ.
    const related = history.filter(h => { const past = data.events.find(e => e.event_id === h.event_id); return past && past.type === event.type && past.develops_skills.some(a => event.develops_skills.some(b => b.skill_id === a.skill_id)); });
    const skipped = related.filter(h => ['no_show', 'declined', 'dropped'].includes(h.status)).length;
    const finished = related.filter(h => h.status === 'completed').length;
    const points = useful.reduce((sum, g) => sum + Math.min(g.after - g.before, g.target - g.before) * (g.critical ? 30 : 10), 0) + Math.min(finished, 3) * 2 - Math.min(skipped, 4) * 8 - event.duration_hours * .15;
    const reasons = [profile.role + ' · ' + profile.grade + ': ' + useful.map(g => g.name + ' ' + g.before + '/' + g.target + (g.critical ? ' (критичный)' : '')).join(', '), skipped ? 'В похожих активностях ' + skipped + ' пропусков или отказов. Учли это при выборе приоритета.' : finished ? 'Вы завершили ' + finished + ' похожих активностей — формат вам знаком.' : 'Подобных активностей в истории завершения нет. Всего завершено: ' + completed + '.', 'Доступно для вашей роли и грейда; начальные требования выполнены. Нагрузка: ' + event.duration_hours + ' ч.'];
    return { event, points, reasons, gains, session: [...event.upcoming_sessions].sort().find(d => d >= data.meta.as_of_date) || '', improvement: coverage(after, profile) - baseline, useful: useful.length };
  }).filter(r => r.useful > 0).sort((a, b) => b.points - a.points || a.event.event_id.localeCompare(b.event.event_id)).slice(0, 3);
}
export function enroll(data: Dataset, employeeId: string, eventId: string, by = 'self'): Dataset {
  const person = data.employees.find(e => e.employee_id === employeeId), event = data.events.find(e => e.event_id === eventId);
  if (!person || !event) throw Error('Профиль или мероприятие не найдено.');
  const reason = availability(data, person, event); if (reason) throw Error(reason);
  if (event.mandatory) throw Error('Обязательные активности уже отражены в истории назначений.');
  return { ...data, history: [...data.history, { record_id: 'LOCAL_' + crypto.randomUUID(), employee_id: employeeId, event_id: eventId, date: data.meta.as_of_date, due_date: '', status: 'in_progress', completion_pct: 0, score: null, feedback_rating: null, assigned_by: by, session_date: [...event.upcoming_sessions].sort().find(d => d >= data.meta.as_of_date), simulation: true }] };
}
export function finish(data: Dataset, recordId: string, status: 'completed' | 'declined'): Dataset {
  const row = data.history.find(h => h.record_id === recordId);
  if (!row || row.status !== 'in_progress') throw Error('Эта активность уже обработана. Обновите план.');
  const event = data.events.find(e => e.event_id === row.event_id)!;
  if (status === 'declined' && event.mandatory) throw Error('Отменить обязательное обучение в этом демо нельзя.');
  return { ...data, history: data.history.map(h => h.record_id === recordId ? { ...h, status, date: data.meta.as_of_date, completion_pct: status === 'completed' ? 100 : 0, simulation: true } : h) };
}

function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
function text(value: unknown): value is string { return typeof value === 'string' && value.trim().length > 0; }
function date(value: unknown): value is string { return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value; }
function level(value: unknown) { return Number.isInteger(value) && Number(value) >= 0 && Number(value) <= 5; }
function strings(value: unknown): value is string[] { return Array.isArray(value) && value.every(text); }
function ensure(condition: unknown, message: string): asserts condition { if (!condition) throw Error(message); }
export function validate(value: unknown): asserts value is Dataset {
  ensure(object(value) && object(value.meta) && date(value.meta.as_of_date), 'Нужна корректная дата среза meta.as_of_date.');
  for (const key of ['employees', 'events', 'skills', 'role_profiles', 'history']) ensure(Array.isArray(value[key]), 'Ожидается массив ' + key + '.');
  const d = value as unknown as Dataset;
  ensure(d.employees.length && d.events.length && d.skills.length && d.role_profiles.length, 'Профили, мероприятия, навыки и требования не должны быть пустыми.');
  for (const [rows, key] of [[d.employees, 'employee_id'], [d.events, 'event_id'], [d.skills, 'skill_id'], [d.history, 'record_id']] as const) {
    const ids = rows.map(r => (r as unknown as Record<string, unknown>)?.[key]);
    ensure(ids.every(text) && new Set(ids).size === ids.length, 'Пустой или повторяющийся идентификатор ' + key + '.');
  }
  const skillIds = new Set(d.skills.map(s => s.skill_id)), employees = new Set(d.employees.map(p => p.employee_id)), events = new Set(d.events.map(e => e.event_id));
  const skillMap = (map: unknown) => object(map) && Object.entries(map).every(([id, n]) => skillIds.has(id) && level(n));
  for (const s of d.skills) ensure(text(s.name) && ['hard', 'soft'].includes(s.type), 'Некорректное описание навыка ' + s.skill_id);
  for (const p of d.role_profiles) ensure(text(p.role) && grades.includes(p.grade) && skillMap(p.required_skills) && strings(p.critical_skills) && p.critical_skills.every(id => id in p.required_skills), 'Некорректные требования роли или критичные навыки.');
  ensure(new Set(d.role_profiles.map(p => p.role + '/' + p.grade)).size === d.role_profiles.length, 'Требования роли и грейда повторяются.');
  for (const p of d.employees) {
    ensure(text(p.full_name) && text(p.department) && text(p.role) && grades.includes(p.grade) && skillMap(p.skills) && date(p.last_review_date) && date(p.hire_date) && Number.isInteger(p.tenure_months) && p.tenure_months >= 0, 'Некорректный профиль ' + p.employee_id + ': проверьте поля, даты и уровни 0–5.');
    ensure(p.last_review_date <= d.meta.as_of_date && p.hire_date <= d.meta.as_of_date, 'Дата профиля позже даты среза: ' + p.employee_id);
    ensure(p.career_goal === null || object(p.career_goal) && text(p.career_goal.target_role) && grades.includes(p.career_goal.target_grade), 'Некорректная карьерная цель ' + p.employee_id);
    ensure(targetFor(d, p) && d.role_profiles.some(r => r.role === p.role && r.grade === p.grade), 'Нет требований для роли или цели ' + p.employee_id);
  }
  for (const e of d.events) {
    ensure(text(e.title) && text(e.description) && text(e.type) && ['online', 'offline', 'self_paced'].includes(e.format) && typeof e.mandatory === 'boolean' && Number.isFinite(e.duration_hours) && e.duration_hours > 0 && strings(e.target_roles) && strings(e.target_grades) && e.target_grades.every(g => grades.includes(g)) && skillMap(e.prerequisites) && Array.isArray(e.upcoming_sessions) && e.upcoming_sessions.every(date) && Array.isArray(e.develops_skills), 'Некорректное мероприятие ' + e.event_id);
    ensure(e.develops_skills.every(x => object(x) && skillIds.has(x.skill_id) && level(x.gain) && x.gain > 0 && level(x.max_level)) && new Set(e.develops_skills.map(x => x.skill_id)).size === e.develops_skills.length, 'Некорректный прирост навыков ' + e.event_id);
  }
  for (const h of d.history) ensure(employees.has(h.employee_id) && events.has(h.event_id) && date(h.date) && h.date <= d.meta.as_of_date && (!h.due_date || date(h.due_date)) && h.status in statusLabels && Number.isInteger(h.completion_pct) && h.completion_pct >= 0 && h.completion_pct <= 100 && (h.status !== 'completed' || h.completion_pct === 100) && (h.score === null || Number.isInteger(h.score) && h.score >= 0 && h.score <= 100) && (h.feedback_rating === null || Number.isInteger(h.feedback_rating) && h.feedback_rating >= 1 && h.feedback_rating <= 5) && ['self', 'manager', 'hr'].includes(h.assigned_by), 'Некорректная строка истории ' + h.record_id + ': проверьте ссылки, дату, статус и числа.');
}
export function parseHistory(csv: string): Activity[] {
  const rows: string[][] = []; let row: string[] = [], cell = '', quoted = false;
  for (let i = 0; i < csv.length; i++) {
    const c = csv[i];
    if (c === '"') { if (quoted && csv[i + 1] === '"') { cell += '"'; i++; } else quoted = !quoted; }
    else if (!quoted && c === ',') { row.push(cell); cell = ''; }
    else if (!quoted && (c === '\n' || c === '\r')) { if (c === '\r' && csv[i + 1] === '\n') i++; row.push(cell); if (row.some(Boolean)) rows.push(row); row = []; cell = ''; }
    else cell += c;
  }
  ensure(!quoted, 'В CSV не закрыта кавычка.'); if (cell || row.length) { row.push(cell); rows.push(row); }
  const [headers, ...body] = rows; ensure(headers, 'CSV пуст.');
  const at = Object.fromEntries(headers.map((h, i) => [h.trim().replace(/^\uFEFF/, ''), i]));
  const columns = ['record_id', 'employee_id', 'event_id', 'date', 'due_date', 'status', 'completion_pct', 'score', 'feedback_rating', 'assigned_by'];
  ensure(columns.every(k => k in at), 'CSV должен содержать все 10 столбцов исходной истории.');
  return body.map(cells => { ensure(cells.length === headers.length, 'Число полей CSV не совпадает с заголовком.'); const h = Object.fromEntries(columns.map(k => [k, cells[at[k]].trim()])); return { ...h, completion_pct: h.completion_pct === '' ? NaN : Number(h.completion_pct), score: h.score === '' ? null : Number(h.score), feedback_rating: h.feedback_rating === '' ? null : Number(h.feedback_rating) } as Activity; });
}
export async function loadStarter(): Promise<Dataset> {
  const files = await Promise.all(['employees.json', 'events.json', 'skills.json', 'activity_history.csv'].map(async path => { const r = await fetch('/demo-data/' + path); if (!r.ok) throw Error('Не удалось загрузить ' + path); return r.text(); }));
  const [people, events, skills] = files.slice(0, 3).map(x => JSON.parse(x.replace(/^\uFEFF/, '')));
  const data = { meta: people.meta, employees: people.employees, events: events.events, skills: skills.skills, role_profiles: skills.role_profiles, history: parseHistory(files[3]) }; validate(data); return data;
}
export async function importDataset(base: Dataset, files: { name: string; text(): Promise<string>; size: number }[], mode: 'merge' | 'replace'): Promise<Dataset> {
  const next = structuredClone(base), seen = new Set<string>();
  const merge = <T,>(old: T[], incoming: T[], key: keyof T) => mode === 'replace' ? incoming : [...new Map([...old, ...incoming].map(x => [x[key], x])).values()];
  for (const file of files) {
    ensure(file.size < 10_000_000, 'Файл слишком большой: предел 10 МБ.'); const source = (await file.text()).replace(/^\uFEFF/, '');
    if (file.name.toLowerCase().endsWith('.csv')) { ensure(!seen.has('history'), 'Выберите один CSV истории.'); seen.add('history'); const incoming = parseHistory(source); ensure(new Set(incoming.map(h => h.record_id)).size === incoming.length, 'Повторяющиеся record_id в CSV.'); next.history = merge(next.history, incoming, 'record_id'); continue; }
    const value: unknown = JSON.parse(source); ensure(object(value), 'Ожидается JSON-объект датасета.');
    const key = Array.isArray(value.employees) ? 'employees' : Array.isArray(value.events) ? 'events' : Array.isArray(value.skills) ? 'skills' : '';
    ensure(key && !seen.has(key), 'Неизвестный или повторный JSON-файл: ' + file.name); seen.add(key);
    if (object(value.meta) && value.meta.as_of_date) { ensure(value.meta.as_of_date === base.meta.as_of_date, 'Дата импортируемого набора должна совпадать с датой среза ' + base.meta.as_of_date); }
    // Validate incoming duplicates before merging so bad rows cannot disappear.
    const rows = value[key] as Record<string, unknown>[], idKey = key === 'employees' ? 'employee_id' : key === 'events' ? 'event_id' : 'skill_id';
    ensure(rows.every(object) && new Set(rows.map(r => r[idKey])).size === rows.length, 'Повторяющиеся ID в ' + file.name);
    if (key === 'employees') next.employees = merge(next.employees, rows as unknown as Person[], 'employee_id');
    if (key === 'events') next.events = merge(next.events, rows as unknown as EventItem[], 'event_id');
    if (key === 'skills') { next.skills = merge(next.skills, rows as unknown as Skill[], 'skill_id'); ensure(Array.isArray(value.role_profiles), 'В skills.json нужны role_profiles.'); next.role_profiles = value.role_profiles as Profile[]; }
  }
  ensure(files.length, 'Выберите файлы.'); validate(next); return next;
}
