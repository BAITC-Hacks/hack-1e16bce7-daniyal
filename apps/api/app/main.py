from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError

from app.api.system import router
from app.api.business import router as business_router
from app.api.career import router as career_router
from app.api.catalog import router as catalog_router
from app.api.completion import router as completion_router
from app.api.datasets import router as datasets_router
from app.api.upload_limit import ImportBodyLimit
from app.api.recommendations import router as recommendation_router
from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.explanations import explanation_provider


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config.validate_auth()
        database = Database(config.database_url)
        application.state.database = database
        application.state.explanations = explanation_provider()
        application.state.inference_slot = asyncio.Semaphore(1)
        try:
            yield
        finally:
            database.close()

    application = FastAPI(title="Career Quest API", version="0.1.0", lifespan=lifespan)
    application.state.settings = config

    @application.middleware("http")
    async def no_store(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # FastAPI normally echoes invalid input; credentials must never be echoed.
        details = [{key: value for key, value in item.items() if key in {"loc", "msg", "type"}}
                   for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(details)})

    application.include_router(router)
    application.include_router(business_router)
    application.include_router(career_router)
    application.include_router(catalog_router)
    application.include_router(completion_router)
    application.include_router(datasets_router)
    application.add_middleware(ImportBodyLimit)
    application.include_router(recommendation_router)
    return application


app = create_app()
