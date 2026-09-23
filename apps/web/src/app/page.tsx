'use client';

import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

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
  const heading = useRef<HTMLHeadingElement>(null);

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

  return (
    <main className="employee-shell">
      <header className="employee-header">
        <Link href="/" className="brand">CAREER QUEST</Link>
        <Link href="/recommendations" className="hr-link">Подобрать обучение</Link>
        <Link href="/hr" className="hr-link">Для HR ↗</Link>
      </header>

      <section className="employee-intro">
        <p className="eyebrow">ВАША КАРЬЕРНАЯ ТРАЕКТОРИЯ</p>
        <h1>Каждый шаг —<br />ближе к цели.</h1>
        <p>Развивайте навыки в своём темпе. Один небольшой шаг уже сегодня.</p>
      </section>

      <section className="quest-card" aria-label="Прогресс задания">
        <div className="progress-label"><span>Ваш прогресс</span><span>{answers.length} из {questions.length}</span></div>
        <progress value={answers.length} max={questions.length} aria-label="Пройдено вопросов" />
        <p className="muted">Прогресс сохраняется в этом браузере на этом устройстве.</p>
        {storageError && <p role="status">Сохранение недоступно. После закрытия страницы прогресс может потеряться.</p>}
      </section>

      <section className="quest-card" aria-labelledby="quest-heading">
        {!started ? (
          <>
            <span className="quest-tag">КОММУНИКАЦИЯ · 3 МИНУТЫ</span>
            <h2 id="quest-heading">Договориться и действовать</h2>
            <p>Три рабочих ситуации, которые помогут потренировать общение с командой.</p>
            <button className="primary-button" disabled={!loaded} onClick={() => setStarted(true)}>
              {!loaded ? 'Загружаем прогресс…' : complete ? 'Посмотреть результат' : answers.length ? 'Продолжить задание →' : 'Начать задание →'}
            </button>
          </>
        ) : complete ? (
          <>
            <span className="quest-tag">ЗАДАНИЕ ЗАВЕРШЕНО</span>
            <h2 id="quest-heading" tabIndex={-1} ref={heading}>Ещё один шаг сделан!</h2>
            <p>Верных ответов: <strong>{score} из {questions.length}</strong>. Вы разобрали, как уточнять задачи, давать обратную связь и фиксировать договорённости.</p>
            <button className="primary-button" onClick={() => { save([]); setSelected(null); setFeedback(false); }}>Пройти ещё раз</button>
            <button className="text-button" onClick={() => setStarted(false)}>К обзору</button>
          </>
        ) : (
          <>
            <span className="quest-tag">ВОПРОС {answers.length + 1} ИЗ {questions.length}</span>
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
            }}>{!feedback ? 'Проверить ответ' : answers.length === questions.length - 1 ? 'Посмотреть результат →' : 'Следующий вопрос →'}</button>
            <button className="text-button" onClick={() => { setStarted(false); setSelected(null); setFeedback(false); }}>Продолжить позже</button>
          </>
        )}
      </section>
      <footer className="employee-footer">Пробное задание · Результат не влияет на оценку сотрудника.</footer>
    </main>
  );
}
