'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { courses, coverage, formatDate, isState, seed, skills, type State } from './mock-data';
import './employee.css';

function EmployeeIcon({ name, size = 22 }: { name: 'arrow' | 'book' | 'check' | 'clock' | 'telegram' | 'target'; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === 'arrow' && <path d="M4 12h15m-6-6 6 6-6 6" />}
    {name === 'book' && <><path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1ZM12 5v15" /></>}
    {name === 'check' && <path d="m5 12 4 4L19 6" />}
    {name === 'clock' && <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>}
    {name === 'telegram' && <><path d="m3 10 18-7-4 18-6-6-4 3v-6l10-6-6 9M3 10l4 2" /></>}
    {name === 'target' && <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></>}
  </svg>;
}

const questions = [
  {
    title: 'Сначала — понять задачу',
    text: 'Коллега просит срочно подготовить отчёт, но не уточняет, какие данные нужны. С чего начать?',
    options: ['Сразу собрать все доступные данные', 'Уточнить цель, формат и срок отчёта', 'Отложить задачу до напоминания'],
    correct: 1,
    explanation: 'Уточните, какое решение поможет принять отчёт. Цель, формат и срок позволяют согласовать ожидания и избежать лишней работы.',
  },
  {
    title: 'Обратная связь, которая помогает',
    text: 'В презентации коллеги вы заметили ошибку. Как лучше дать обратную связь?',
    options: ['Обсудить конкретную ошибку лично и предложить исправление', 'Написать в общий чат, что презентация плохая', 'Исправить молча и больше не обсуждать'],
    correct: 0,
    explanation: 'Конкретный пример и предложение решения помогают улучшить результат. Личный разговор оставляет пространство для спокойного обсуждения.',
  },
  {
    title: 'Договорённости — в действие',
    text: 'Встреча завершена, команда выбрала решение. Что поможет довести его до результата?',
    options: ['Назначить ещё одну встречу без повестки', 'Рассчитывать, что каждый запомнил свою часть', 'Зафиксировать шаги, ответственных и сроки'],
    correct: 2,
    explanation: 'Когда у каждого шага есть ответственный и срок, участники понимают, что делать дальше и когда сверять результат.',
  },
];

const storageKey = 'career-quest:communication:v1';

export default function Home() {
  const [answers, setAnswers] = useState<number[]>([]);
  const [started, setStarted] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [feedback, setFeedback] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [storageError, setStorageError] = useState(false);
  const [hrData, setHrData] = useState<State | null>(null);
  const [employeeId, setEmployeeId] = useState('daniyar');
  const heading = useRef<HTMLHeadingElement>(null);
  const practice = useRef<HTMLElement>(null);

  useEffect(() => {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(storageKey) || '[]');
      if (Array.isArray(saved) && saved.length <= questions.length && saved.every(
        (value, index) => Number.isInteger(value) && value >= 0 && value < questions[index].options.length,
      )) setAnswers(saved);
    } catch { setStorageError(true); }
    setLoaded(true);
  }, []);

  useEffect(() => {
    const hrKey = 'career-quest-demo-v1';
    const read = () => {
      try {
        const saved: unknown = JSON.parse(localStorage.getItem(hrKey) || 'null');
        setHrData(isState(saved) ? saved : seed());
      } catch { setHrData(seed()); }
    };
    read();
    const sync = (event: StorageEvent) => { if (event.key === hrKey) read(); };
    window.addEventListener('storage', sync);
    return () => window.removeEventListener('storage', sync);
  }, []);

  useEffect(() => {
    if (started) heading.current?.focus();
  }, [started, answers.length]);

  function save(next: number[]) {
    setAnswers(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
      setStorageError(false);
    } catch { setStorageError(true); }
  }

  const complete = answers.length === questions.length;
  const question = questions[answers.length];
  const score = answers.filter((answer, index) => answer === questions[index].correct).length;
  const employee = hrData?.employees.find(item => item.id === employeeId) || hrData?.employees[0];
  const employeeChanges = hrData?.changes.filter(item => item.employeeId === employee?.id).sort((a, b) => Date.parse(b.date) - Date.parse(a.date)) || [];
  const employeeAssignments = hrData?.assignments.filter(item => item.employeeId === employee?.id) || [];
  const assignedCourses = employeeAssignments.map(item => ({ assignment: item, course: courses.find(course => course.id === item.courseId)! }));
  const nextCourse = employee ? courses.filter(course => employee.levels[course.skill] < employee.target && !employeeAssignments.some(item => item.status === 'assigned' && item.courseId === course.id)).sort((a, b) => (employee.target - employee.levels[b.skill]) - (employee.target - employee.levels[a.skill]))[0] : undefined;
  function openPractice() {
    setStarted(true);
    practice.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  return (
    <main className="employee-app" id="employee-top">
      <header className="site-header">
        <div className="header-inner">
          <Link href="/" className="brand" aria-label="Halyk Career Quest — главная"><img className="brand-logo" src="/brand/halyk-logo.svg" alt="" /></Link>
          <div className="top-links"><span className="top-link active">Career Quest</span><span className="top-link">Кабинет сотрудника</span></div>
          <div className="header-actions"><span className="ep-demo">Демо</span><Link href="/hr" className="ep-hr-link">Кабинет HR <EmployeeIcon name="arrow" size={17} /></Link></div>
        </div>
        <nav className="section-nav" aria-label="Навигация сотрудника"><div className="header-inner section-nav-inner"><a href="#employee-top" aria-current="page">Мой путь</a><a href="#practice">Практика</a><a href="#my-development">Мои навыки</a><a href="#my-progress">Мой прогресс</a><a href="#employee-help">Помощь</a></div></nav>
      </header>
      <div className="page-shell ep-shell">
      <div className="ep-breadcrumbs"><span>Halyk</span><span>/</span><strong>Career Quest</strong></div>
      <section className="ep-hero">
        <div className="ep-hero-copy"><h1>Твой следующий шаг.<br /><strong>Ближе, чем кажется.</strong></h1><p>Развивай навыки в своём темпе.<br />Начни с одного небольшого задания сегодня.</p><div className="ep-hero-actions"><button className="primary-button" disabled={!loaded} onClick={openPractice}>{complete ? 'Мой результат' : answers.length ? 'Продолжить путь' : 'Начать мой путь'}<EmployeeIcon name="arrow" size={19} /></button><span><EmployeeIcon name="clock" size={16} />Всего 3 минуты</span></div></div>
        <div className="ep-hero-route"><div className="ep-route-title"><EmployeeIcon name="target" size={24} /><span>Маленькие шаги.<br /><strong>Полезные привычки.</strong></span></div><ol>{['Понять задачу', 'Дать обратную связь', 'Договориться о результате'].map((title, index) => <li key={title} className={index < answers.length ? 'is-done' : ''}><span className="ep-step">{index < answers.length ? <EmployeeIcon name="check" size={17} /> : index + 1}</span><span>{title}</span></li>)}</ol></div>
      </section>
      <div className="ep-section-heading"><div><h2>Развитие начинается с практики</h2><p>Один навык. Три ситуации из рабочего дня.</p></div><span className="ep-available"><span /> Доступно сейчас</span></div>
      <div className="ep-workspace">
      <section className="quest-card ep-practice" id="practice" ref={practice} aria-labelledby="quest-heading">
        <div className="ep-practice-top"><span className="ep-topic-icon"><EmployeeIcon name="book" size={26} /></span><div><strong>Коммуникация</strong><span>Практическое задание</span></div><span className="ep-lesson-state">{complete ? 'Завершено' : answers.length || started ? 'В процессе' : 'Можно начинать'}</span></div>
        {!started ? (
          <>
            <h2 id="quest-heading">Договориться и действовать</h2>
            <p>Три рабочих ситуации, которые помогут потренировать общение с командой.</p>
            <ul className="ep-outcomes"><li><EmployeeIcon name="check" size={17} />Уточнять задачу до начала работы</li><li><EmployeeIcon name="check" size={17} />Давать полезную обратную связь</li><li><EmployeeIcon name="check" size={17} />Превращать обсуждение в конкретные шаги</li></ul>
            <div className="ep-lesson-meta"><span><EmployeeIcon name="clock" size={16} />3 минуты</span><span>3 вопроса</span><span>С разбором ответов</span></div>
            <button className="primary-button" disabled={!loaded} onClick={openPractice}>
              {!loaded ? 'Загружаем прогресс…' : complete ? 'Посмотреть результат' : answers.length ? 'Продолжить задание' : 'Начать задание'}<EmployeeIcon name="arrow" size={18} />
            </button>
          </>
        ) : complete ? (
          <>
            <h2 id="quest-heading" tabIndex={-1} ref={heading}>Ещё один шаг сделан!</h2>
            <div className="ep-result"><span className="ep-result-icon"><EmployeeIcon name="check" size={32} /></span><span><strong>{score} / {questions.length}</strong><small>верных ответов</small></span></div>
            <p>Верных ответов: <strong>{score} из {questions.length}</strong>. Вы разобрали, как уточнять задачи, давать обратную связь и фиксировать договорённости.</p>
            <button className="primary-button" onClick={() => { save([]); setSelected(null); setFeedback(false); }}>Пройти ещё раз</button>
            <button className="text-button" onClick={() => setStarted(false)}>К обзору</button>
          </>
        ) : (
          <>
            <div className="ep-question-progress" aria-label={`Вопрос ${answers.length + 1} из ${questions.length}`}>{questions.map((_, i) => <span key={i} className={i <= answers.length ? 'filled' : ''} />)}<small>{answers.length + 1} из {questions.length}</small></div>
            <h2 id="quest-heading" tabIndex={-1} ref={heading}>{question.title}</h2>
            <fieldset disabled={feedback}>
              <legend>{question.text}</legend>
              <div className="answer-list">
                {question.options.map((option, index) => (
                  <label key={option} className={`answer-option ${selected === index ? 'selected' : ''}`}>
                    <input type="radio" name="answer" value={index} checked={selected === index} onChange={() => setSelected(index)} />
                    <span>{option}</span>
                  </label>
                ))}
              </div>
            </fieldset>
            {feedback && <div className="answer-feedback" role="status"><strong>{selected === question.correct ? 'Верно!' : 'Разберём ситуацию'}</strong><p>{question.explanation}</p></div>}
            <button className="primary-button" disabled={selected === null} onClick={() => {
              if (selected === null) return;
              if (!feedback) { setFeedback(true); return; }
              save([...answers, selected]); setSelected(null); setFeedback(false);
            }}>{!feedback ? 'Проверить ответ' : answers.length === questions.length - 1 ? 'Посмотреть результат' : 'Следующий вопрос'}<EmployeeIcon name="arrow" size={18} /></button>
            <button className="text-button" onClick={() => { setStarted(false); setSelected(null); setFeedback(false); }}>Продолжить позже</button>
          </>
        )}
      </section>
      <aside className="ep-sidebar">
        <section className="ep-progress-panel" id="my-progress" aria-label="Прогресс задания"><div className="ep-panel-heading"><h2>Твой прогресс</h2><EmployeeIcon name="target" /></div><div className="ep-progress-number"><strong>{Math.round(answers.length / questions.length * 100)}<span>%</span></strong><span>{complete ? 'Практика завершена' : 'Шаг за шагом к результату'}</span></div><progress value={answers.length} max={questions.length} aria-label="Пройдено вопросов" /><div className="ep-progress-caption"><span>Пройдено вопросов</span><strong>{answers.length} из {questions.length}</strong></div><ol className="ep-progress-list">{questions.map((item, index) => <li key={item.title}><span className={`ep-step ${index < answers.length ? 'done' : ''}`}>{index < answers.length ? <EmployeeIcon name="check" size={15} /> : index + 1}</span><span>{item.title}</span></li>)}</ol><p className="ep-storage-note">Прогресс сохраняется в этом браузере. Можно вернуться в удобный момент.</p>{storageError && <p className="ep-storage-error" role="alert">Сохранение недоступно. После закрытия страницы прогресс может потеряться.</p>}</section>
        <section className="ep-telegram"><span className="ep-topic-icon"><EmployeeIcon name="telegram" size={24} /></span><div><h2>Небольшое напоминание</h2><p>Бот Career Quest поможет не забыть о мероприятиях и дедлайнах.</p><a href="https://t.me/CareerQuuestBot" target="_blank" rel="noopener noreferrer">Открыть Telegram <EmployeeIcon name="arrow" size={16} /></a><small>Для уведомлений нужна ссылка привязки профиля.</small></div></section>
      </aside>
      </div>
      <section className="ep-development" id="my-development" aria-labelledby="development-title">
        <div className="ep-development-heading"><div><span className="ep-eyebrow">ТВОЙ ПРОФИЛЬ РАЗВИТИЯ</span><h2 id="development-title">Что уже получается — и куда расти дальше</h2><p>Навыки, план и обратная связь из кабинета HR. Обновляются после оценки с обоснованием.</p></div><label className="ep-profile-select"><span>Демо-профиль</span><select value={employee?.id || ''} onChange={event => setEmployeeId(event.target.value)} aria-label="Выбрать демо-профиль сотрудника">{hrData?.employees.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label></div>
        {employee && <>
          <div className="ep-profile-card"><div className="ep-profile-person"><span className="ep-avatar">{employee.name.split(' ').map(part => part[0]).slice(0, 2).join('')}</span><div><h3>{employee.name}</h3><p>{employee.role} · {employee.department} · {employee.grade}</p></div><Link href="/hr#Сотрудники">Открыть HR-профиль <EmployeeIcon name="arrow" size={16} /></Link></div><div className="ep-profile-summary"><div><strong>{coverage(employee)}%</strong><span>покрытие цели</span></div><div><strong>{employee.target}/5</strong><span>целевой уровень</span></div><div><strong>{employeeChanges.length}</strong><span>оценок в истории</span></div></div></div>
          <div className="ep-development-grid"><section className="ep-development-card"><div className="ep-card-title"><div><h3>Карта моих навыков</h3><p>Оценки подтверждает HR по результатам работы.</p></div><Link href="/hr#Карта%20навыков" aria-label="Открыть карту навыков в HR"><EmployeeIcon name="arrow" /></Link></div><div className="ep-skill-list">{skills.map(skill => { const level = employee.levels[skill]; const delta = employeeChanges.filter(change => change.skill === skill).reduce((sum, change) => sum + change.to - change.from, 0); return <div className="ep-skill-row" key={skill}><div className="ep-skill-label"><strong>{skill}</strong><span>{level} из {employee.target}{delta ? <em className={delta > 0 ? 'up' : 'down'}>{delta > 0 ? '+' : ''}{delta} за историю</em> : <em>цель {employee.target}</em>}</span></div><div className="ep-skill-track" role="img" aria-label={`${skill}: ${level} из ${employee.target}`}><span style={{ width: `${Math.min(level / employee.target * 100, 100)}%` }} /></div></div>; })}</div><p className="ep-trust-note"><EmployeeIcon name="check" size={16} />Практика помогает учиться, но сама по себе не меняет оценку навыка.</p></section>
            <section className="ep-development-card ep-learning-card"><div className="ep-card-title"><div><h3>Мой план развития</h3><p>Назначения и рекомендации HR</p></div><Link href="/hr#Обучение" aria-label="Открыть обучение в HR"><EmployeeIcon name="arrow" /></Link></div>{assignedCourses.length ? <div className="ep-assignment-list">{assignedCourses.map(({ assignment, course }) => <article className="ep-assignment" key={assignment.id}><span className="ep-assignment-icon"><EmployeeIcon name="book" size={20} /></span><div><small>{course.skill} · {course.duration}</small><h4>{course.title}</h4><p>{assignment.status === 'completed' ? 'Завершено · результат сохранён в профиле' : `Назначено ${formatDate(assignment.date)} · ожидает прохождения`}</p></div><span className={`ep-status ${assignment.status}`}>{assignment.status === 'completed' ? 'Завершено' : 'Назначено'}</span></article>)}</div> : <p className="ep-no-assignment">Пока нет назначенного обучения. Следующий шаг можно выбрать вместе с HR.</p>}{nextCourse && <div className="ep-next-step"><span>СЛЕДУЮЩИЙ ШАГ</span><strong>{nextCourse.title}</strong><p>{nextCourse.skill}: до цели осталось {employee.target - employee.levels[nextCourse.skill]} {employee.target - employee.levels[nextCourse.skill] === 1 ? 'уровень' : 'уровня'}.</p><Link href="/hr#Рекомендации">Посмотреть рекомендацию HR <EmployeeIcon name="arrow" size={15} /></Link></div>}</section></div>
          <section className="ep-development-card ep-history-card"><div className="ep-card-title"><div><h3>История обратной связи</h3><p>Почему оценка навыка менялась</p></div><Link href="/hr#Обзор">Все изменения в HR <EmployeeIcon name="arrow" size={16} /></Link></div>{employeeChanges.length ? <div className="ep-history-list">{employeeChanges.slice(0, 3).map(change => <article key={change.id}><span className={`ep-change-mark ${change.to >= change.from ? 'up' : 'down'}`}>{change.to >= change.from ? '↑' : '↓'}</span><div><strong>{change.skill} <span>{change.from} → {change.to}</span></strong><p>{change.reason}</p></div><time>{formatDate(change.date)}</time></article>)}</div> : <p className="ep-no-assignment">Оценки появятся здесь после обратной связи от HR или завершённой практической оценки.</p>}</section>
        </>}
      </section>
      <section className="ep-help" id="employee-help"><h2>Всё просто</h2><div><details><summary>Как сохраняется мой результат?</summary><p>Ответы сохраняются на этом устройстве после перехода к следующему вопросу или результату. Если закроешь страницу, можно будет продолжить с последнего сохранённого шага.</p></details><details><summary>Как практика влияет на оценку навыка?</summary><p>Практика помогает развивать навык, но не меняет оценку автоматически. HR фиксирует новый уровень после подтверждения результата; история и карта навыков затем обновляются в этом кабинете.</p></details><details><summary>Можно пройти ещё раз?</summary><p>Да. После завершения открой результат и нажми «Пройти ещё раз». Предыдущие ответы заменятся результатом новой попытки.</p></details></div></section>
      <footer className="employee-footer"><span>Career Quest · Halyk</span><span>Демо-данные · оценка навыка меняется после подтверждения HR.</span><Link href="/hr">Перейти в HR-панель <EmployeeIcon name="arrow" size={15} /></Link></footer>
      </div>
    </main>
  );
}
