'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { Workspace, useSession } from '../../components/workspace';
import './recommendations.css';

type Employee = { employee_id: string; full_name: string; role: string; grade: string };
type Recommendation = {
  event_id: string; title: string; explanation: string; skill_gaps: Record<string, number>;
  expected_gains: Record<string, number>; readiness_before: number | null; readiness_after: number | null;
};
type Result = {
  employee_id: string; locale: string; as_of: string; target_grade: string | null; readiness: number | null;
  explanation_source: 'ollama' | 'openai' | 'template'; fallback_reason: string | null;
  skill_names: Record<string, string>; recommendations: Recommendation[];
};

export default function Recommendations() {
  const { user } = useSession();
  return <Workspace hr={user?.role === 'hr'}><RecommendationsContent key={user?.employee_id || user?.role} /></Workspace>;
}

function RecommendationsContent() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [employeeId, setEmployeeId] = useState('');
  const [locale, setLocale] = useState('ru');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Result | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    fetch('/api/v1/employees', { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        if (!response.ok) throw new Error('Не удалось загрузить сотрудников. Проверьте доступность сервера.');
        const data = await response.json();
        if (!Array.isArray(data.employees)) throw new Error('Сервер вернул некорректный список сотрудников.');
        setEmployees(data.employees);
        setEmployeeId(data.employees.find((e: Employee) => e.employee_id === 'E0028')?.employee_id
          || data.employees[0]?.employee_id || '');
      })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [reload]);

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !employeeId) return;
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const response = await fetch('/api/v1/recommendations', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ employee_id: employeeId, locale }), signal: AbortSignal.timeout(10000),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Не удалось получить рекомендации.');
      setResult(data);
    } catch (e) {
      setError(e instanceof Error && e.name !== 'TimeoutError' ? e.message : 'Ответ занял слишком много времени. Попробуйте ещё раз.');
    } finally { setBusy(false); }
  }

  return <div className="ai-page">
    <header className="ai-nav"><Link href="/">CAREER QUEST</Link><Link href="/hr">HR-панель ↗</Link></header>
    <section className="ai-intro"><p className="ai-eyebrow">ВАШ СЛЕДУЮЩИЙ ШАГ</p>
      <h1>Обучение, которое<br />приближает к цели.</h1>
      <p>Выберите профиль из загруженного набора. Мы учтём текущие навыки, карьерную цель и историю обучения, а AI поможет объяснить подбор.</p>
    </section>
    <form className="ai-controls" onSubmit={generate} aria-busy={busy}>
      <label>Сотрудник<select value={employeeId} disabled={loading || busy || !employees.length}
        onChange={e => { setEmployeeId(e.target.value); setResult(null); }}>
        {loading && <option value="">Загружаем профили…</option>}
        {!loading && !employees.length && <option value="">Нет загруженных профилей</option>}
        {employees.map(employee => <option key={employee.employee_id} value={employee.employee_id}>
          {employee.full_name} · {employee.role} · {employee.grade}
        </option>)}
      </select></label>
      <label>Язык объяснения<select value={locale} disabled={busy} onChange={e => { setLocale(e.target.value); setResult(null); }}>
        <option value="ru">Русский</option><option value="kk">Қазақша</option><option value="en">English</option>
      </select></label>
      <button className="ai-button" disabled={loading || busy || !employeeId}>{busy ? 'Готовим объяснения…' : 'Подобрать обучение'}</button>
    </form>
    {busy && <p className="ai-notice" role="status">Готовим рекомендации. Если AI задержится, покажем объяснения по правилам.</p>}
    {error && <div className="ai-error" role="alert"><p>{error}</p>{!employees.length && <button className="ai-button" onClick={() => setReload(v => v + 1)}>Повторить загрузку</button>}</div>}
    {!loading && !error && !employees.length && <p className="ai-notice">Сначала загрузите датасет сотрудников в базу.</p>}
    {result && <section className="ai-results" aria-label="Результаты подбора" aria-live="polite">
      <div className="ai-summary"><div><p className="ai-eyebrow">КАРЬЕРНАЯ ЦЕЛЬ</p><h2>{result.target_grade || 'Следующий грейд не задан'}</h2>
        <p>Данные на {result.as_of}. {result.readiness !== null && `Покрытие требований: ${Math.round(result.readiness)}%.`}</p></div>
        {result.recommendations.length > 0 && <span className="ai-badge">{result.explanation_source === 'template' ? 'Объяснения по правилам' : 'Объяснения с AI'}</span>}
      </div>
      {result.explanation_source === 'template' && result.recommendations.length > 0 && <p className="ai-notice" role="status">
        AI сейчас недоступен или не вернул корректный ответ. Показаны проверенные объяснения по правилам; подбор курсов сохранён.
      </p>}
      {!result.recommendations.length && <p className="ai-empty">Подходящих курсов сейчас нет: доступные мероприятия не закрывают оставшиеся требования или уже пройдены. Можно выбрать другой профиль.</p>}
      {result.recommendations.map((item, index) => <article className="ai-card" key={item.event_id}>
        <span className="ai-number">0{index + 1}</span><div><h3>{item.title}</h3><p className="ai-explanation" lang={result.locale}>{item.explanation}</p>
          <div className="ai-skills">{Object.entries(item.skill_gaps).map(([skill, gap]) => <span key={skill}>
            {result.skill_names[skill] || skill}: до цели {gap}, прирост +{item.expected_gains[skill] || 0}
          </span>)}</div>
          {item.readiness_before !== null && item.readiness_after !== null && <p className="ai-progress">Покрытие требований после курса: {Math.round(item.readiness_before)}% → {Math.round(item.readiness_after)}%</p>}
        </div>
      </article>)}
    </section>}
    <p className="ai-footnote">Рекомендации помогают планировать развитие. Покрытие навыков не гарантирует повышение.</p>
  </div>;
}
