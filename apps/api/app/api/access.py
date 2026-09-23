from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.application.employees import get_employee
from app.auth.models import Role
from app.auth.tokens import Principal, read_token
from app.config import Settings

bearer = HTTPBearer(auto_error=False)


def settings(request: Request) -> Settings:
    return request.app.state.settings


def demo_enabled(config: Annotated[Settings, Depends(settings)]) -> None:
    if not config.demo_auth_enabled:
        raise HTTPException(404, "Not found")


def session(request: Request):
    with request.app.state.database.sessions() as db_session:
        yield db_session


SessionDependency = Annotated[Session, Depends(session)]
ConfigDependency = Annotated[Settings, Depends(settings)]


def current_principal(config: ConfigDependency, db: SessionDependency,
                      credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
    denied = HTTPException(401, "Invalid or missing access token", headers={"WWW-Authenticate": "Bearer"})
    if not config.demo_auth_enabled or credentials is None:
        raise denied
    try:
        principal = read_token(config, credentials.credentials)
    except InvalidTokenError:
        raise denied from None
    if principal.role == Role.EMPLOYEE and get_employee(db, principal.employee_id) is None:
        raise denied
    return principal


PrincipalDependency = Annotated[Principal, Depends(current_principal)]


def accessible_employee(employee_id: str, principal: PrincipalDependency, db: SessionDependency):
    if principal.role != Role.HR and principal.employee_id != employee_id:
        raise HTTPException(403, "Access denied")
    employee = get_employee(db, employee_id)
    if employee is None:
        raise HTTPException(404, "Employee not found")
    return employee
