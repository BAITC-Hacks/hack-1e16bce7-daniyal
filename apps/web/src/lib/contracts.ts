// Proposed integration contract; see docs/frontend-api.md. All computed values come from API.
export type User = { role: 'employee' | 'hr'; employee_id: string | null };
export type Employee = { employee_id: string; full_name?: string | null; role: string; grade: string; tenure_months: number; department?: string; career_readiness: number | null };
export type Skill = { skill_id: string; name: string; current_level: number; required_level: number | null; critical?: boolean };
export type Trajectory = { current_grade: string; target_grade: string | null; target_role: string | null; grades: string[]; career_readiness: number | null; requirements: Skill[] };
export type Effect = { skill_id: string; name: string; gain: number; max_level: number };
export type Recommendation = { event_id: string; title: string; priority: number; score: number; skills: (Skill & { gain: number; predicted_level: number })[]; career_readiness_before: number | null; career_readiness_after: number | null; reason: string; explanation_source: 'ai' | 'fallback' };
export type Event = { repeatable?: boolean; mandatory?: boolean; format?: string; upcoming_sessions?: string[]; event_id: string; title: string; description: string; type: string; duration_hours?: number | null; develops_skills: Effect[]; preview?: { skills: (Skill & { predicted_level: number })[]; career_readiness_before: number | null; career_readiness_after: number | null } };
export const statusLabels = { completed: 'Завершено', in_progress: 'В процессе', dropped: 'Прервано', no_show: 'Неявка', declined: 'Отказ', overdue: 'Просрочено' } as const;
export type ActivityStatus = keyof typeof statusLabels;
export type Activity = { record_id: string; event_id: string; title: string; status: ActivityStatus; date: string; completed_on?: string | null; session_date?: string | null; simulated?: boolean };
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type Completion = { record_id?: string; event_id: string; already_completed: boolean; changes: { skill_id: string; name: string; before: number; after: number }[]; career_readiness_before: number | null; career_readiness_after: number | null };
export type Dashboard = { employee_count: number; average_readiness: number | null; without_recommendations: number; completed_activities: number; active_this_month: number; as_of_date: string };
export type SkillGap = { skill_id: string; name: string; employee_count: number };
export type ActivityStat = { event_id: string; title: string; participant_count: number; statuses: Record<ActivityStatus, number> };
export type ImportResult = { status: 'imported' | 'unchanged'; employees: number; events: number; skills: number; history_records: number };
