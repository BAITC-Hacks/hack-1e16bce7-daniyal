from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.system import router
from app.config import Settings
from app.infrastructure.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(config.database_url)
        application.state.database = database
        try:
            yield
        finally:
            database.close()

    application = FastAPI(title="Career Quest API", version="0.1.0", lifespan=lifespan)
    application.include_router(router)
    return application


app = create_app()
