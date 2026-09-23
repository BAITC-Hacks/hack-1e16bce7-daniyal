from fastapi import APIRouter, HTTPException

from app.api.access import PrincipalDependency, SessionDependency
from app.api.catalog_schemas import CatalogEvent, HREmployee
from app.application import catalog
from app.auth.models import Role

router = APIRouter(prefix="/api/v1")


@router.get("/hr/employees", response_model=list[HREmployee], tags=["hr"])
def hr_employees(principal: PrincipalDependency, db: SessionDependency, include_readiness: bool = False):
    if principal.role != Role.HR:
        raise HTTPException(403, "Access denied")
    if include_readiness:
        from app.application.career import CareerSnapshot
        snapshot = CareerSnapshot(db)
        return [snapshot.employee(key) for key in sorted(snapshot.employees)]
    return catalog.hr_employees(db)


@router.get("/events", response_model=list[CatalogEvent], response_model_exclude_unset=True, tags=["events"])
def events(principal: PrincipalDependency, db: SessionDependency):
    return catalog.catalog_events(db)


@router.get("/events/{event_id}", response_model=CatalogEvent, response_model_exclude_unset=True, tags=["events"])
def event(event_id: str, principal: PrincipalDependency, db: SessionDependency, employee_id: str | None = None):
    results = catalog.catalog_events(db, event_id)
    if not results:
        raise HTTPException(404, "Event not found")
    if employee_id:
        if principal.role != Role.HR and principal.employee_id != employee_id:
            raise HTTPException(403, 'Access denied')
        from app.application.career import CareerSnapshot
        snapshot = CareerSnapshot(db, [employee_id])
        if employee_id not in snapshot.employees:
            raise HTTPException(404, 'Employee not found')
        results[0]['preview'] = snapshot.event(event_id, employee_id)['preview']
    return results[0]
