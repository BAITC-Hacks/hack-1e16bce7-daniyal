from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import SQLAlchemyError

from app.api.system import router
from app.api.business import router as business_router
from app.config import Settings
from app.infrastructure.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config.validate_auth()
        database = Database(config.database_url)
        application.state.database = database
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
    return application


app = create_app()
