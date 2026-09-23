"""Database adapter for the existing ranking engine and career workspace."""
from collections import Counter, defaultdict
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.dataset import GRADES
from app.domain import models as domain
from app.domain.progress import apply_skill_effects
from app.domain.ranking import DeterministicRecommendationEngine, career_readiness, skill_gaps
from app.infrastructure import models as db


class CareerSnapshot:
    """Bulk-load shared facts once per request, avoiding an employee N+1 loop."""
    def __init__(self, session: Session, employee_ids: list[str] | None = None):
        state = session.get(db.DatasetState, 1)
        self.as_of = state.as_of_date if state else date.today()
        self.names = {row.skill_id: row.name for row in session.scalars(select(db.Skill))}
        self.events = {row.event_id: row for row in session.scalars(select(db.Event).order_by(db.Event.event_id))}
        self.effects = defaultdict(list)
        for row in session.scalars(select(db.EventSkill)):
            self.effects[row.event_id].append(domain.SkillEffect(row.skill_id, row.gain, row.max_level))
        prerequisites = defaultdict(dict)
        for row in session.scalars(select(db.EventPrerequisite)):
            prerequisites[row.event_id][row.skill_id] = row.required_level
        self.candidates = tuple(domain.Event(row.event_id, row.title, row.type,
            tuple(row.target_roles), tuple(row.target_grades), tuple(self.effects[row.event_id]),
            row.mandatory, prerequisites[row.event_id], row.format,
            tuple(date.fromisoformat(day) for day in row.upcoming_sessions), row.repeatable)
            for row in self.events.values())
        self.grades = {(row.role, row.grade): row.next_grade for row in session.scalars(select(db.RoleGrade))}
        requirements, critical = defaultdict(dict), defaultdict(list)
        for row in session.scalars(select(db.GradeRequirement)):
            requirements[(row.role, row.grade)][row.skill_id] = row.required_level
            if row.critical:
                critical[(row.role, row.grade)].append(row.skill_id)
        self.targets = {key: domain.GradeRequirement(key[0], key[1], successor,
            requirements[key], tuple(critical[key])) for key, successor in self.grades.items()}
        def rows(model):
            query = select(model)
            if employee_ids is not None:
                query = query.where(model.employee_id.in_(employee_ids))
            return session.scalars(query).all()
        self.employees = {row.employee_id: row for row in rows(db.Employee)}
        self.levels = defaultdict(dict)
        for row in rows(db.EmployeeSkill):
            self.levels[row.employee_id][row.skill_id] = row.level
        self.histories = defaultdict(list)
        self.history_rows = rows(db.ActivityHistory)
        for row in self.history_rows:
            self.histories[row.employee_id].append(domain.Participation(row.record_id, row.employee_id,
                row.event_id, row.status, datetime.combine(row.completed_on or row.date, time.min)))

    def context(self, employee_id, locale='ru'):
        row = self.employees[employee_id]
        target_key = ((row.career_goal['target_role'], row.career_goal['target_grade']) if row.career_goal
                      else (row.role, self.grades.get((row.role, row.grade))))
        levels = {key: self.levels[employee_id].get(key, 0) for key in self.names}
        return domain.RecommendationContext(domain.Employee(row.employee_id, row.role, row.grade,
            row.tenure_months, levels), self.targets.get(target_key), tuple(self.histories[employee_id]),
            self.candidates, locale, self.as_of)

    def employee(self, employee_id):
        row = self.employees[employee_id]
        context = self.context(employee_id)
        return {field: getattr(row, field) for field in ('employee_id', 'full_name', 'role', 'grade',
            'tenure_months', 'department')} | {'career_readiness': career_readiness(context.employee.skills, context.target)}

    def trajectory(self, employee_id):
        context = self.context(employee_id)
        target = context.target
        return {'current_grade': context.employee.grade, 'target_grade': target.grade if target else None,
            'target_role': target.role if target else None,
            'grades': [grade for grade in GRADES if (context.employee.role, grade) in self.grades],
            'career_readiness': career_readiness(context.employee.skills, target),
            'requirements': [{'skill_id': key, 'name': self.names[key],
                'current_level': context.employee.skills.get(key, 0), 'required_level': level,
                'critical': key in target.critical_skills} for key, level in (target.required_skills.items() if target else [])]}

    def event(self, event_id, employee_id=None):
        row = self.events[event_id]
        result = {field: getattr(row, field) for field in ('event_id', 'title', 'description', 'type', 'duration_hours')}
        result['develops_skills'] = [{'skill_id': effect.skill_id, 'name': self.names[effect.skill_id],
            'gain': effect.gain, 'max_level': effect.max_level} for effect in self.effects[event_id]]
        if employee_id:
            context = self.context(employee_id)
            before = context.employee.skills
            already_completed = not row.repeatable and any(item.event_id == event_id and item.status == 'completed' for item in context.history)
            after = dict(before) if already_completed else apply_skill_effects(before, self.effects[event_id])
            result['preview'] = {'skills': [{'skill_id': effect.skill_id, 'name': self.names[effect.skill_id],
                'current_level': before[effect.skill_id], 'predicted_level': after[effect.skill_id],
                'required_level': context.target.required_skills.get(effect.skill_id) if context.target else None}
                for effect in self.effects[event_id]],
                'career_readiness_before': career_readiness(before, context.target),
                'career_readiness_after': career_readiness(after, context.target)}
        return result

    def eligible(self, employee_id, event_id):
        context = self.context(employee_id)
        event = next(event for event in self.candidates if event.event_id == event_id)
        return (context.employee.role in event.audience_roles and context.employee.grade in event.audience_grades
                and all(context.employee.skills.get(key, 0) >= value for key, value in event.prerequisites.items()))

    def analytics(self):
        engine = DeterministicRecommendationEngine()
        profiles, coverage, gaps, readiness = [], [], Counter(), []
        for key in sorted(self.employees):
            context = self.context(key)
            profile = self.employee(key)
            profiles.append(profile)
            if profile['career_readiness'] is not None:
                readiness.append(profile['career_readiness'])
            if not engine.rank(context):
                coverage.append(profile)
            if context.target:
                gaps.update(skill_gaps(context.employee.skills, context.target.required_skills).keys())
        month = self.as_of.replace(day=1)
        active = {row.employee_id for row in self.history_rows
            if month <= (row.completed_on or row.date) <= self.as_of and row.status in ('in_progress', 'completed')}
        stats, participants = defaultdict(Counter), defaultdict(set)
        for row in self.history_rows:
            stats[row.event_id][row.status] += 1
            participants[row.event_id].add(row.employee_id)
        return {'dashboard': {'employee_count': len(profiles),
            'average_readiness': round(sum(readiness) / len(readiness), 2) if readiness else None,
            'without_recommendations': len(coverage), 'active_this_month': len(active),
            'completed_activities': sum(row.status == 'completed' for row in self.history_rows),
            'as_of_date': self.as_of}, 'employees': profiles, 'recommendation-coverage': coverage,
            'skill-gaps': [{'skill_id': key, 'name': self.names[key], 'employee_count': value}
                          for key, value in gaps.most_common()],
            'activity-stats': [{'event_id': key, 'title': self.events[key].title,
                'participant_count': len(participants[key]), 'statuses': {status: stats[key][status]
                    for status in ('completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue')}}
                for key in sorted(stats)]}
