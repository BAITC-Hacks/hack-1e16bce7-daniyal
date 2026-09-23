from contextlib import asynccontextmanager, suppress
import asyncio

from fastapi import FastAPI

from app.api.system import router
from app.api.recommendations import router as recommendation_router
from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.explanations import explanation_provider, OllamaExplanationProvider


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(config.database_url)
        application.state.database = database
        application.state.explanations = explanation_provider()
        application.state.inference_slot = asyncio.Semaphore(1)
        provider = application.state.explanations
        warmup = asyncio.create_task(provider.warmup()) if isinstance(provider, OllamaExplanationProvider) and provider.settings.llm_enabled else None
        try:
            yield
        finally:
            if warmup is not None:
                warmup.cancel()
                with suppress(asyncio.CancelledError):
                    await warmup
            database.close()

    application = FastAPI(title="Career Quest API", version="0.1.0", lifespan=lifespan)
    application.include_router(router)
    application.include_router(recommendation_router)
    return application


app = create_app()
