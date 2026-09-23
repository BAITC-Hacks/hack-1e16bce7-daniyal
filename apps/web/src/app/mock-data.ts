export const skills = ['System Design', 'API Design', 'Communication', 'Analytics'] as const;
export type Skill = typeof skills[number];
export type Employee = { id: string; name: string; role: string; department: string; grade: string; target: number; levels: Record<Skill, number> };
export type Change = { id: string; employeeId: string; skill: Skill; from: number; to: number; date: string; reason: string };
export type Assignment = { id: string; employeeId: string; courseId: string; date: string; status: 'assigned' | 'completed' };
export type State = { version: 1; employees: Employee[]; changes: Change[]; assignments: Assignment[] };
export const courses: { id: string; title: string; skill: Skill; duration: string; description: string }[] = [
  { id: 'architecture', title: 'Designing High-Load Systems', skill: 'System Design', duration: '3 недели', description: 'Проектирование сервисов, отказоустойчивость и защита архитектурного решения.' },
  { id: 'api', title: 'API Design Workshop', skill: 'API Design', duration: '2 недели', description: 'Спроектировать API, обработать ошибки и пройти ревью контракта.' },
  { id: 'speaking', title: 'Communication Lab', skill: 'Communication', duration: '1 неделя', description: 'Презентация решения, обратная связь и практическая работа в команде.' },
  { id: 'analytics', title: 'Product Analytics Lab', skill: 'Analytics', duration: '2 недели', description: 'Метрики продукта, анализ эксперимента и выводы на основе данных.' },
];
export function seed(): State {
  const date = (days: number) => new Date(Date.now() - days * 86400000).toISOString();
  return { version: 1, employees: [
    { id: 'arman', name: 'Arman Zhaksylykov', role: 'Backend Engineer', department: 'Разработка', grade: 'Middle', target: 4, levels: { 'System Design': 3, 'API Design': 4, Communication: 3, Analytics: 2 } },
    { id: 'nikita', name: 'Nikita Smirnov', role: 'Data Analyst', department: 'Аналитика', grade: 'Middle', target: 4, levels: { 'System Design': 2, 'API Design': 2, Communication: 3, Analytics: 3 } },
    { id: 'elena', name: 'Elena Orlova', role: 'QA Engineer', department: 'Разработка', grade: 'Senior', target: 5, levels: { 'System Design': 3, 'API Design': 4, Communication: 4, Analytics: 3 } },
    { id: 'aliya', name: 'Aliya Sarsenova', role: 'Product Designer', department: 'Дизайн', grade: 'Middle', target: 4, levels: { 'System Design': 2, 'API Design': 2, Communication: 4, Analytics: 3 } },
    { id: 'daniyar', name: 'Daniyar Omarov', role: 'Frontend Engineer', department: 'Разработка', grade: 'Junior', target: 3, levels: { 'System Design': 1, 'API Design': 2, Communication: 3, Analytics: 1 } },
    { id: 'aigerim', name: 'Aigerim Bekova', role: 'Business Analyst', department: 'Аналитика', grade: 'Senior', target: 5, levels: { 'System Design': 3, 'API Design': 3, Communication: 5, Analytics: 4 } },
  ], changes: [
    { id: 'c1', employeeId: 'arman', skill: 'System Design', from: 2, to: 3, date: date(5), reason: 'Защита архитектуры: выполнены 4 из 5 критериев.' },
    { id: 'c2', employeeId: 'elena', skill: 'Analytics', from: 4, to: 3, date: date(42), reason: 'Повторная оценка: требуется практика в анализе экспериментов.' },
    { id: 'c3', employeeId: 'nikita', skill: 'Analytics', from: 2, to: 3, date: date(75), reason: 'Практический кейс: корректно выбраны метрики продукта.' },
    { id: 'c4', employeeId: 'aliya', skill: 'Communication', from: 3, to: 4, date: date(140), reason: 'Успешная презентация исследования команде.' },
  ], assignments: [{ id: 'a1', employeeId: 'daniyar', courseId: 'api', status: 'assigned', date: date(3) }] };
}
export const coverage = (e: Employee) => Math.round(skills.reduce((sum, s) => sum + Math.min(e.levels[s], e.target), 0) / (skills.length * e.target) * 100);
export const initials = (name: string) => name.split(' ').map(n => n[0]).slice(0, 2).join('');
export const formatDate = (value: string) => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
export function isState(value: unknown): value is State {
  if (!value || typeof value !== 'object') return false;
  const s = value as State;
  return s.version === 1 && Array.isArray(s.employees) && s.employees.length > 0 && s.employees.every(e => typeof e.id === 'string' && typeof e.name === 'string' && typeof e.role === 'string' && typeof e.department === 'string' && typeof e.grade === 'string' && Number.isInteger(e.target) && e.target >= 1 && e.target <= 5 && e.levels && skills.every(k => Number.isInteger(e.levels[k]) && e.levels[k] >= 0 && e.levels[k] <= 5)) && Array.isArray(s.changes) && s.changes.every(c => typeof c.id === 'string' && s.employees.some(e => e.id === c.employeeId) && skills.includes(c.skill) && Number.isInteger(c.from) && c.from >= 0 && c.from <= 5 && Number.isInteger(c.to) && c.to >= 0 && c.to <= 5 && typeof c.reason === 'string' && Number.isFinite(Date.parse(c.date))) && Array.isArray(s.assignments) && s.assignments.every(a => typeof a.id === 'string' && s.employees.some(e => e.id === a.employeeId) && courses.some(c => c.id === a.courseId) && ['assigned', 'completed'].includes(a.status) && Number.isFinite(Date.parse(a.date)));
}
