// Test-only API with fixed responses. Never imported by the application.
import { createServer } from 'node:http';
import { pathToFileURL } from 'node:url';

export function fixtureApi() {
  let completed = false;
  let imported = false;
  const sessions = new Map();
  return createServer(async (request, response) => {
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const raw = Buffer.concat(chunks).toString();
    const path = decodeURIComponent(new URL(request.url, 'http://localhost').pathname).replace('/api/v1/', '');
    const send = (value, status = 200) => { response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(value)); };
    if (path === 'health' || path === 'ready') return send({ status: 'ok' });
    if (path === 'auth/demo/employee' || path === 'auth/demo/hr') {
      const credentials = JSON.parse(raw);
      if (path.endsWith('/hr') && credentials.password !== 'fixture-hr') return send({ detail: 'Invalid credentials' }, 401);
      const user = path.endsWith('/hr') ? { role: 'hr', employee_id: null } : { role: 'employee', employee_id: credentials.employee_id };
      if (user.employee_id === 'missing') return send({ detail: 'Not found' }, 404);
      const token = `fixture-${sessions.size}`;
      sessions.set(token, user);
      return send({ access_token: token, token_type: 'bearer', expires_in: 3600 });
    }
    const user = sessions.get(request.headers.authorization?.replace('Bearer ', ''));
    if (!user) return send({ detail: 'Unauthorized' }, 401);
    if (path === 'auth/me') return send(user);
    if ((path.startsWith('hr/') || path === 'datasets/import') && user.role !== 'hr') return send({ detail: 'Forbidden' }, 403);
    const employeeId = path.startsWith('employees/') ? path.split('/')[1] : user.employee_id || 'JURY-42';
    if (user.role === 'employee' && employeeId !== user.employee_id) return send({ detail: 'Forbidden' }, 403);
    const employee = { employee_id: employeeId, full_name: 'Айдана Садыкова', role: 'Backend Engineer', grade: 'Middle', tenure_months: 36, career_readiness: completed ? 76 : 68, department: 'Разработка' };
    const skill = { skill_id: 'SK_SYSTEM_DESIGN', name: 'System Design', current_level: completed ? 3 : 2, required_level: 4, critical: true };
    if (/^employees\/[^/]+$/.test(path)) return send(employee);
    if (path.endsWith('/skills')) return send({ employee_id: employeeId, items: [{ skill_id: skill.skill_id, name: skill.name, level: skill.current_level, assessed_level: 2, type: 'hard', category: 'Engineering', description: 'Architecture' }] });
    if (path.endsWith('/trajectory')) return send({ current_grade: 'Middle', target_grade: 'Senior', target_role: 'Backend Engineer', grades: ['Junior', 'Middle', 'Senior', 'Lead'], career_readiness: completed ? 76 : 68, requirements: [skill] });
    if (path.endsWith('/recommendations')) return send(completed ? [] : [{ event_id: 'EV_014', title: 'System Design Workshop', priority: 1, score: 0.87, skills: [{ ...skill, gain: 1, predicted_level: 3 }], career_readiness_before: 68, career_readiness_after: 76, reason: 'Для перехода с Middle на Senior требуется System Design 4, текущий уровень — 2. Практикум повышает его до 3. Две предыдущие технические активности завершены в срок; похожие выступления вы пропускали.', explanation_source: 'fallback' }]);
    if (path === 'events/EV_014') return send({ event_id: 'EV_014', title: 'System Design Workshop', description: 'Практикум по архитектуре высоконагруженных систем с разбором решения и обратной связью.', type: 'workshop', duration_hours: 4, develops_skills: [{ skill_id: skill.skill_id, name: skill.name, gain: 1, max_level: 4 }] });
    if (path.endsWith('/complete')) {
      if (user.role !== 'employee') return send({ detail: 'Forbidden' }, 403);
      const before = completed;
      completed = true;
      return send({ event_id: 'EV_014', already_completed: before, changes: before ? [] : [{ skill_id: skill.skill_id, name: skill.name, before: 2, after: 3 }], career_readiness_before: before ? 76 : 68, career_readiness_after: 76 });
    }
    if (path.endsWith('/activities')) {
      const items = ['completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue'].map((status, index) => ({ record_id: `R${index}`, event_id: `EV${index}`, event_title: `Активность ${index + 1}`, status, date: '2026-09-01' })).concat(completed ? [{ record_id: 'new', event_id: 'EV_014', event_title: 'System Design Workshop', status: 'completed', date: '2026-10-01' }] : []);
      return send({ items, total: items.length, offset: 0, limit: 50 });
    }
    if (path === 'hr/dashboard') return send({ employee_count: 200, average_readiness: 62, without_recommendations: 1, completed_activities: 1400, as_of_date: '2026-10-01' });
    if (path === 'hr/employees' || path === 'hr/recommendation-coverage') return send([employee]);
    if (path === 'hr/skill-gaps') return send([{ skill_id: skill.skill_id, name: skill.name, employee_count: 42 }]);
    if (path === 'hr/activity-stats') return send([{ event_id: 'EV_014', title: 'System Design Workshop', participant_count: 30, statuses: { completed: 20, in_progress: 3, dropped: 1, no_show: 2, declined: 2, overdue: 2 } }]);
    if (path === 'datasets/import') {
      if (!raw.includes('name="employees.json"')) return send({ detail: [{ loc: ['body', 'employees.json'], msg: 'Файл обязателен' }] }, 422);
      const status = imported ? 'unchanged' : 'imported'; imported = true;
      return send({ status, employees: 200, events: 40, skills: 60, history_records: 2743 });
    }
    send({ detail: 'Not found' }, 404);
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  fixtureApi().listen(18001, '127.0.0.1', () => console.log('Test fixture API: http://127.0.0.1:18001'));
}
