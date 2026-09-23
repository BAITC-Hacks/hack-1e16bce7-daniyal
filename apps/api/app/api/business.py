import hashlib
import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.access import (ConfigDependency, PrincipalDependency, SessionDependency,
                            accessible_employee, demo_enabled)
from app.api.schemas import (ActivityPage, EmployeeLogin, EmployeePage, EmployeeProfile,
                             EmployeeSkills, HRLogin, IdentityResponse, TokenResponse)
from app.application import employees
from app.auth.models import Role
from app.auth.tokens import Principal, issue_token

router = APIRouter(prefix="/api/v1")
demo = APIRouter(prefix="/auth/demo", tags=["demo-auth"], dependencies=[Depends(demo_enabled)])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@demo.get("/employees", response_model=EmployeePage)
def demo_employees(db: SessionDependency, limit: Limit = 50, offset: Offset = 0):
    return employees.list_employees(db, limit, offset)


@demo.post("/employee", response_model=TokenResponse)
def employee_login(body: EmployeeLogin, db: SessionDependency, config: ConfigDependency):
    if employees.get_employee(db, body.employee_id) is None:
        raise HTTPException(404, "Employee not found")
    return TokenResponse(access_token=issue_token(config, Principal(Role.EMPLOYEE, body.employee_id)))


@demo.post("/hr", response_model=TokenResponse)
def hr_login(body: HRLogin, config: ConfigDependency):
    # Compare fixed-length digests, including for non-ASCII passwords.
    actual = hashlib.sha256(body.password.get_secret_value().encode()).digest()
    expected = hashlib.sha256(config.demo_hr_password.get_secret_value().encode()).digest()
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(401, "Invalid credentials", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=issue_token(config, Principal(Role.HR)))


@router.get("/auth/me", response_model=IdentityResponse, tags=["auth"])
def identity(principal: PrincipalDependency):
    return principal


@router.get("/employees/{employee_id}", response_model=EmployeeProfile, tags=["employees"])
def profile(employee=Depends(accessible_employee)):
    return employee


@router.get("/employees/{employee_id}/skills", response_model=EmployeeSkills, tags=["employees"])
def skills(db: SessionDependency, employee=Depends(accessible_employee)):
    return employees.employee_skills(db, employee.employee_id)


@router.get("/employees/{employee_id}/activities", response_model=ActivityPage, tags=["employees"])
def activities(db: SessionDependency, employee=Depends(accessible_employee),
               limit: Limit = 50, offset: Offset = 0):
    return employees.employee_history(db, employee.employee_id, limit, offset)


router.include_router(demo)
