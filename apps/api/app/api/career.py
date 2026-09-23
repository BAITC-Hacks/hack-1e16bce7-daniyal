"""Authenticated endpoints for the employee and HR career workspace."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.access import PrincipalDependency, SessionDependency, accessible_employee
from app.application.career import CareerSnapshot
from app.auth.models import Role
from app.domain.models import ExplanationContext
from app.domain.ranking import DeterministicRecommendationEngine
from app.infrastructure.explanations import OpenAIExplanationProvider

router = APIRouter(prefix='/api/v1', tags=['career'])


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    language: Literal['ru', 'kk', 'en'] = 'ru'


def hr_only(principal: PrincipalDependency):
    if principal.role != Role.HR:
        raise HTTPException(403, 'HR access required')


@router.get('/employees/{employee_id}/trajectory')
def trajectory(db: SessionDependency, employee=Depends(accessible_employee)):
    return CareerSnapshot(db, [employee.employee_id]).trajectory(employee.employee_id)


@router.post('/employees/{employee_id}/recommendations')
async def recommendations(body: RecommendationRequest, db: SessionDependency, employee=Depends(accessible_employee)):
    snapshot = CareerSnapshot(db, [employee.employee_id])
    ranked = DeterministicRecommendationEngine().rank(snapshot.context(employee.employee_id, body.language))
    explanations = await OpenAIExplanationProvider().explain_with_metadata(ExplanationContext(body.language, ranked, snapshot.names))
    result = []
    for priority, item in enumerate(ranked, 1):
        preview = snapshot.event(item.event_id, employee.employee_id)['preview']
        effects = {effect.skill_id: effect for effect in snapshot.effects[item.event_id]}
        result.append({'event_id': item.event_id, 'title': snapshot.events[item.event_id].title,
            'priority': priority, 'score': item.score, 'skills': [skill | {'gain': effects[skill['skill_id']].gain}
                for skill in preview['skills']], 'career_readiness_before': item.readiness_before,
            'career_readiness_after': item.readiness_after, 'reason': explanations.texts[item.event_id],
            'explanation_source': 'ai' if explanations.source == 'openai' else 'fallback'})
    return result


@router.get('/hr/dashboard', dependencies=[Depends(hr_only)])
def dashboard(db: SessionDependency):
    return CareerSnapshot(db).analytics()['dashboard']


@router.get('/hr/skill-gaps', dependencies=[Depends(hr_only)])
def skill_gaps(db: SessionDependency):
    return CareerSnapshot(db).analytics()['skill-gaps']


@router.get('/hr/activity-stats', dependencies=[Depends(hr_only)])
def activity_stats(db: SessionDependency):
    return CareerSnapshot(db).analytics()['activity-stats']


@router.get('/hr/recommendation-coverage', dependencies=[Depends(hr_only)])
def coverage(db: SessionDependency):
    return CareerSnapshot(db).analytics()['recommendation-coverage']
