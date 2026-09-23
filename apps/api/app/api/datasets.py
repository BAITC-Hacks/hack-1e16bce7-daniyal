"""HR-only atomic dataset upload endpoint."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException
from python_multipart.exceptions import MultipartParseError

from app.api.access import PrincipalDependency
from app.application.append_dataset import append_dataset
from app.application.dataset import Employees
from app.application.import_dataset import DatasetConflict, import_dataset
from app.auth.models import Role
from app.infrastructure.dataset_loader import dataset_from_files, read_history, read_json

router = APIRouter(prefix="/api/v1", tags=["datasets"])
FILE_LIMIT = 10 * 1024 * 1024


def write_session(request: Request):
    # Independent of the read session used by authentication.
    with request.app.state.database.sessions() as session:
        yield session


def require_hr(principal: PrincipalDependency):
    if principal.role != Role.HR:
        raise HTTPException(403, "Access denied")


@router.post("/datasets/import", dependencies=[Depends(require_hr)])
async def upload_dataset(request: Request, session: Annotated[object, Depends(write_session)]):
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data"):
        raise HTTPException(422, "Expected multipart/form-data")
    try:
        async with request.form(max_files=4, max_fields=1) as form:
            mode = form.get("mode")
            if mode not in ("initial", "append"):
                raise HTTPException(422, "mode must be initial or append")
            names = {"employees.json", "activity_history.csv"}
            if mode == "initial":
                names |= {"events.json", "skills.json"}
            if set(form) != names | {"mode"} or len(form.multi_items()) != len(names) + 1:
                raise HTTPException(422, "Unexpected, duplicate or missing multipart fields")
            files = {}
            for name in names:
                file = form[name]
                if not isinstance(file, UploadFile):
                    raise HTTPException(422, f"{name}: expected file upload")
                content = await file.read(FILE_LIMIT + 1)
                if len(content) > FILE_LIMIT:
                    raise HTTPException(413, f"{name}: file exceeds 10 MiB")
                files[name] = content
    except HTTPException:
        raise
    except (StarletteHTTPException, MultipartParseError):
        raise HTTPException(422, "Invalid multipart form") from None
    try:
        if mode == "initial":
            dataset = await run_in_threadpool(dataset_from_files, files)
            result = await run_in_threadpool(import_dataset, session, dataset)
            result["history_records"] = result.pop("history")
            return result
        employees, history = await run_in_threadpool(parse_append, files)
        return await run_in_threadpool(append_dataset, session, employees, history)
    except DatasetConflict as error:
        raise HTTPException(409, str(error)) from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


def parse_append(files):
    return (Employees.model_validate(read_json(files["employees.json"], "employees.json")),
            read_history(files["activity_history.csv"]))
