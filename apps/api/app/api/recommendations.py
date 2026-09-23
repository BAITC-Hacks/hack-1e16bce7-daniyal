"""Read-only recommendation UI for the local development deployment."""
import asyncio
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.domain.models import ExplanationContext
from app.domain.ranking import DeterministicRecommendationEngine, career_readiness
from app.infrastructure.models import Employee
from app.infrastructure.recommendation_context import load_context

router = APIRouter(prefix="/api/v1", tags=["recommendations"])


class RecommendationRequest(BaseModel):
    employee_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    locale: Literal["ru", "kk", "en"] = "ru"


@router.get("/employees")
def employees(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        with request.app.state.database.sessions() as session:
            rows = session.scalars(select(Employee).order_by(Employee.employee_id).limit(500))
            return {"employees": [{"employee_id": row.employee_id, "full_name": row.full_name,
                                    "role": row.role, "grade": row.grade} for row in rows]}
    except SQLAlchemyError:
        raise HTTPException(503, "База данных временно недоступна.") from None


def prepare(request: Request, body: RecommendationRequest):
    try:
        with request.app.state.database.sessions() as session:
            context, names = load_context(session, body.employee_id, body.locale)
    except KeyError:
        raise HTTPException(404, "Сотрудник не найден.") from None
    except (SQLAlchemyError, ValueError):
        raise HTTPException(503, "Данные для рекомендаций недоступны. Проверьте импорт датасета.") from None
    ranked = DeterministicRecommendationEngine().rank(context)
    return context, names, ranked


@router.post("/recommendations")
async def recommendations(body: RecommendationRequest, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    # Bound GPU demand. Reject excess requests instead of growing an unbounded queue.
    try:
        await asyncio.wait_for(request.app.state.inference_slot.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        raise HTTPException(429, "Модель занята. Повторите запрос немного позже.", headers={"Retry-After": "10"}) from None
    try:
        context, names, ranked = await run_in_threadpool(prepare, request, body)
        explained = await request.app.state.explanations.explain_with_metadata(
            ExplanationContext(context.locale, ranked, names))
        events = {event.event_id: event for event in context.candidates}
        return {
            "employee_id": body.employee_id,
            "locale": context.locale,
            "as_of": context.as_of,
            "target_grade": context.target.grade if context.target else None,
            "readiness": career_readiness(context.employee.skills, context.target),
            "explanation_source": explained.source,
            "fallback_reason": explained.fallback_reason,
            "skill_names": names,
            "recommendations": [{**asdict(item), "title": events[item.event_id].title,
                                 "explanation": explained.texts[item.event_id]} for item in ranked],
        }
    finally:
        request.app.state.inference_slot.release()
