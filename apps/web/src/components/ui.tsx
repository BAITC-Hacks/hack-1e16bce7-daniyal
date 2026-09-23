import type { CSSProperties } from 'react';
import { percent } from '../lib/api';
import type { Skill } from '../lib/contracts';

export type IconName = 'dashboard' | 'path' | 'spark' | 'activity' | 'history' | 'people' | 'chart' | 'upload' | 'arrow' | 'check' | 'logout';
const paths: Record<IconName, string> = {
  dashboard: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',
  path: 'M5 4v12a4 4 0 0 0 4 4h10 M15 16l4 4-4 4 M5 4h14 M19 4l-4-4 M19 4l-4 4',
  spark: 'm12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z M20 2v4 M18 4h4',
  activity: 'M3 6h7l2 2h9v12H3z M3 6V4h7l2 2',
  history: 'M3 10a9 9 0 1 1 1 7 M3 4v6h6 M12 7v5l3 2',
  people: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M16 3a4 4 0 0 1 0 8 M22 21v-2a4 4 0 0 0-3-3.9 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
  chart: 'M4 3v18h17 M8 17v-5 M13 17V7 M18 17V4',
  upload: 'M12 16V3 M7 8l5-5 5 5 M3 16v5h18v-5',
  arrow: 'M4 12h16 M14 6l6 6-6 6',
  check: 'm5 12 4 4L19 6',
  logout: 'M9 4H3v16h6 M9 12h12 M17 8l4 4-4 4',
};
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name]} /></svg>;
}

export function Readiness({ value, target }: { value: number | null; target?: string | null }) {
  return <div className="cq-readiness"><div className="cq-ring" style={{ '--readiness': `${Math.min(100, Math.max(0, value ?? 0))}%` } as CSSProperties}><div><strong>{value === null ? '—' : percent(value)}</strong><span>Career readiness</span></div></div><p>{target ? `На пути к ${target}` : 'Готовность к следующему грейду'}</p></div>;
}

export function SkillTable({ skills, compact = false }: { skills: Skill[]; compact?: boolean }) {
  const rows = compact ? skills.slice(0, 4) : skills;
  return rows.length ? <div className="cq-skill-list">{rows.map(skill => {
    const met = skill.required_level !== null && skill.current_level >= skill.required_level;
    const max = skill.required_level ?? 5;
    return <div className={`cq-skill ${met ? 'is-met' : ''}`} key={skill.skill_id}><div className="cq-skill-heading"><span><strong>{skill.name}</strong>{skill.critical && <small>Ключевой навык</small>}</span><span className="cq-skill-level">{skill.current_level} <span>/ {max}</span>{met && <Icon name="check" size={16} />}</span></div><progress max={Math.max(1, max)} value={Math.min(skill.current_level, max)} aria-label={`${skill.name}: текущий уровень ${skill.current_level}, ${skill.required_level === null ? 'максимум 5' : `требуется ${max}`}`} /></div>;
  })}</div> : <p className="cq-empty">Навыков для отображения пока нет.</p>;
}
