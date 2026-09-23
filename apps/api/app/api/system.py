from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/api/v1", tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    stage: Literal["foundation"] = "foundation"


class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    database: Literal["ok", "unavailable"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/ready", response_model=ReadyResponse, responses={503: {"model": ReadyResponse}})
def ready(request: Request) -> ReadyResponse | JSONResponse:
    try:
        request.app.state.database.check()
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content=ReadyResponse(status="unavailable", database="unavailable").model_dump(),
        )
    return ReadyResponse(status="ready", database="ok")
