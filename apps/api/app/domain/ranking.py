"""Deterministic AI calculations. Versioned policy documented in docs/ai-integration.md."""
from collections import Counter
from collections.abc import Mapping

from app.domain.models import GradeRequirement, RankedRecommendation, RecommendationContext
from app.domain.progress import apply_skill_effects


def _levels(values: Mapping[str, int]) -> None:
    if any(not key or type(value) is not int or not 0 <= value <= 5 for key, value in values.items()):
        raise ValueError("skills must have nonempty IDs and integer levels in 0..5")


def skill_gaps(skills: Mapping[str, int], requirements: Mapping[str, int]) -> dict[str, int]:
    """Dataset policy: a missing skill is level zero; preserve only positive gaps."""
    _levels(skills)
    _levels(requirements)
    return {key: required - skills.get(key, 0) for key, required in sorted(requirements.items())
            if required > skills.get(key, 0)}


def career_readiness(skills: Mapping[str, int], target: GradeRequirement | None) -> float | None:
    _levels(skills)
    if target is None:
        return None
    _levels(target.required_skills)
    if not set(target.critical_skills) <= target.required_skills.keys():
        raise ValueError("critical skills must be present in grade requirements")
    weights = {key: 2 if key in target.critical_skills else 1 for key in target.required_skills}
    total = sum(required * weights[key] for key, required in target.required_skills.items())
    if not total:
        return None
    reached = sum(min(skills.get(key, 0), required) * weights[key]
                  for key, required in target.required_skills.items())
    return round(100 * reached / total, 2)


class DeterministicRecommendationEngine:
    def rank(self, context: RecommendationContext) -> tuple[RankedRecommendation, ...]:
        employee, target = context.employee, context.target
        before = career_readiness(employee.skills, target)
        if target is None or before is None:
            return ()
        gaps = skill_gaps(employee.skills, target.required_skills)
        if not gaps:
            return ()
        if context.locale not in ("ru", "kk", "en"):
            raise ValueError("unsupported locale")
        events = {event.event_id: event for event in context.candidates}
        if len(events) != len(context.candidates):
            raise ValueError("duplicate event IDs")
        history_ids = [row.participation_id for row in context.history]
        if len(set(history_ids)) != len(history_ids):
            raise ValueError("duplicate participation IDs")
        if any(row.employee_id != employee.employee_id for row in context.history):
            raise ValueError("history belongs to another employee")
        history = [row for row in context.history
                   if context.as_of is None or row.occurred_at.date() <= context.as_of]
        completed = {row.event_id for row in history if row.status == "completed"}
        active = {row.event_id for row in history if row.status in ("in_progress", "registered")}
        total_gap = sum(gap * (2 if key in target.critical_skills else 1) for key, gap in gaps.items())
        ranked = []
        for event in context.candidates:
            _levels(event.prerequisites)
            if event.mandatory or event.event_type in ("compliance", "onboarding"):
                continue
            if employee.role not in event.audience_roles or employee.grade not in event.audience_grades:
                continue
            if event.event_id in active or (event.event_id in completed and not event.repeatable):
                continue
            if any(employee.skills.get(key, 0) < value for key, value in event.prerequisites.items()):
                continue
            if event.format != "self_paced":
                if context.as_of is None:
                    raise ValueError("as_of is required for scheduled events")
                if not any(day >= context.as_of for day in event.upcoming_sessions):
                    continue
            normalized = dict(employee.skills)
            for effect in event.effects:
                normalized.setdefault(effect.skill_id, 0)
            after = apply_skill_effects(normalized, event.effects)
            gains = {key: value - normalized[key] for key, value in after.items() if value > normalized[key]}
            relevant = {key: gaps[key] for key in gains if key in gaps}
            if not relevant:
                continue
            reduction = sum(min(gains[key], gap) * (2 if key in target.critical_skills else 1)
                            for key, gap in relevant.items())
            counts = Counter(row.status for row in history
                             if row.event_id in events and events[row.event_id].event_type == event.event_type)
            failures = sum(counts[key] for key in ("missed", "no_show", "dropped", "declined"))
            fit = max(.25, (counts["completed"] + 1) / (counts["completed"] + failures + 2))
            score = round(.85 * reduction / total_gap + .15 * fit, 6)
            reasons = ["closes_target_grade_gap", "positive_skill_gain"]
            if any(key in target.critical_skills for key in relevant):
                reasons.append("critical_skill_gap")
            if counts:
                reasons.append("participation_history_considered")
            ranked.append(RankedRecommendation(
                event_id=event.event_id, score=score, target_grade=target.grade,
                skill_gaps=relevant, expected_gains=gains, reason_codes=tuple(reasons),
                current_grade=employee.grade,
                current_levels={key: normalized[key] for key in relevant},
                required_levels={key: target.required_skills[key] for key in relevant},
                history_summary=dict(sorted(counts.items())), readiness_before=before,
                readiness_after=career_readiness(after, target),
            ))
        return tuple(sorted(ranked, key=lambda item: (-item.score, item.event_id))[:3])
