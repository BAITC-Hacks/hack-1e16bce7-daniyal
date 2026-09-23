from dataclasses import replace
from datetime import date, datetime

import pytest

from app.domain.models import Employee, Event, GradeRequirement, Participation, RecommendationContext, SkillEffect
from app.domain.ranking import DeterministicRecommendationEngine, career_readiness, skill_gaps


@pytest.fixture
def context():
    return RecommendationContext(
        Employee("judge-new", "Engineer", "Middle", 20, {"design": 2, "speaking": 0}),
        GradeRequirement("Engineer", "Senior", "Lead", {"design": 4, "speaking": 1}, ("design",)),
        (), (
            Event("design", "Design", "workshop", ("Engineer",), ("Middle",), (SkillEffect("design", 1, 4),)),
            Event("speaking", "Speaking", "meetup", ("Engineer",), ("Middle",), (SkillEffect("speaking", 1, 3),)),
        ), "ru", date(2026, 10, 1),
    )


def test_critical_grade_gap_beats_lowest_skill(context):
    ranked = DeterministicRecommendationEngine().rank(context)
    assert ranked[0].event_id == "design"
    assert ranked[0].expected_gains == {"design": 1}
    assert ranked[0].readiness_before == 44.44
    assert ranked[0].readiness_after == 66.67
    assert context.employee.skills == {"design": 2, "speaking": 0}


def test_history_penalty_is_bounded_and_never_excludes_critical_event(context):
    history = tuple(Participation(str(i), "judge-new", "design", "no_show", datetime(2026, 9, i + 1)) for i in range(3))
    ranked = DeterministicRecommendationEngine().rank(replace(context, history=history))
    assert ranked[0].event_id == "design"
    assert ranked[0].history_summary == {"no_show": 3}


@pytest.mark.parametrize("change", [
    {"mandatory": True}, {"event_type": "onboarding"}, {"audience_roles": ("Other",)},
    {"audience_grades": ("Lead",)}, {"prerequisites": {"missing": 1}},
    {"format": "online", "upcoming_sessions": (date(2026, 9, 1),)},
    {"effects": (SkillEffect("design", 1, 2),)},
])
def test_unavailable_or_useless_events_filtered(context, change):
    event = replace(context.candidates[0], **change)
    assert DeterministicRecommendationEngine().rank(replace(context, candidates=(event,))) == ()


@pytest.mark.parametrize("status", ["completed", "in_progress", "registered"])
def test_previous_completion_or_active_enrollment_excluded(context, status):
    history = (Participation("r", "judge-new", "design", status, datetime(2026, 9, 1)),)
    assert all(item.event_id != "design" for item in DeterministicRecommendationEngine().rank(replace(context, history=history)))


def test_repeatable_club_and_future_session(context):
    event = replace(context.candidates[0], repeatable=True, format="online", upcoming_sessions=(context.as_of,))
    history = (Participation("r", "judge-new", "design", "completed", datetime(2026, 9, 1)),)
    assert DeterministicRecommendationEngine().rank(replace(context, history=history, candidates=(event,)))


def test_stable_ties_and_top_three(context):
    events = tuple(replace(context.candidates[0], event_id=key) for key in ("d", "c", "b", "a"))
    engine = DeterministicRecommendationEngine()
    first = engine.rank(replace(context, candidates=events))
    assert [item.event_id for item in first] == ["a", "b", "c"]
    assert first == engine.rank(replace(context, candidates=tuple(reversed(events))))


def test_actual_gain_capped_and_missing_skills_zero(context):
    event = replace(context.candidates[0], effects=(SkillEffect("design", 3, 3),))
    ranked = DeterministicRecommendationEngine().rank(replace(context, candidates=(event,)))
    assert ranked[0].expected_gains == {"design": 1}
    assert skill_gaps({}, {"new": 3}) == {"new": 3}
    assert career_readiness({}, context.target) == 0


def test_no_target_no_requirements_and_fully_ready(context):
    engine = DeterministicRecommendationEngine()
    assert engine.rank(replace(context, target=None)) == ()
    assert career_readiness({}, None) is None
    assert career_readiness({}, replace(context.target, required_skills={}, critical_skills=())) is None
    assert engine.rank(replace(context, employee=replace(context.employee, skills={"design": 5, "speaking": 3}))) == ()


def test_bad_inputs_fail_instead_of_being_hidden(context):
    with pytest.raises(ValueError):
        skill_gaps({"x": True}, {"x": 2})
    with pytest.raises(ValueError):
        DeterministicRecommendationEngine().rank(replace(context, candidates=context.candidates * 2))
    with pytest.raises(ValueError):
        DeterministicRecommendationEngine().rank(replace(context, history=(Participation("r", "other", "design", "completed", datetime(2026, 1, 1)),)))
