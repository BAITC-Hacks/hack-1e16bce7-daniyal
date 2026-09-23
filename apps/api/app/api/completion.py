from typing import Annotated

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.access import PrincipalDependency, SessionDependency
from app.api.completion_schemas import CompletionRequest, CompletionResponse
from app.application.completion import CompletionError, complete_activity
from app.auth.models import Role

router = APIRouter(prefix="/api/v1", tags=["activities"])


@router.post("/employees/{employee_id}/activities/{event_id}/complete", response_model=CompletionResponse)
def complete(employee_id: str, event_id: str, body: CompletionRequest,
             principal: PrincipalDependency, db: SessionDependency,
             idempotency_key: Annotated[str, Header(min_length=1, max_length=128)]):
    if principal.role != Role.EMPLOYEE or principal.employee_id != employee_id:
        raise HTTPException(403, "Only the employee can complete their activity")
    # Auth already began a read transaction. The command owns a separate unit of work.
    with Session(bind=db.get_bind()) as write_session:
        try:
            return complete_activity(write_session, employee_id, event_id,
                                     body.model_dump(mode="json"), idempotency_key, include_readiness=True)
        except CompletionError as error:
            raise HTTPException(error.status, str(error)) from None
