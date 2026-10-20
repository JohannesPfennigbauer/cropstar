from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from importlib.metadata import version

from fastapi import FastAPI

from cropstar_api.auth.mailer import Mailer, mailer_from_settings
from cropstar_api.auth.provider import PasswordAuthProvider
from cropstar_api.db import create_db_engine
from cropstar_api.routes import areas, auth, status, tasks
from cropstar_api.settings import Settings


def create_app(settings: Settings | None = None, mailer: Mailer | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_db_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    # Every route lives under /api, so paths are identical behind the web proxy and here.
    app = FastAPI(
        title="Cropstar API",
        version=version("cropstar-api"),
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.auth = PasswordAuthProvider(timedelta(days=settings.session_lifetime_days))
    app.state.mailer = mailer or mailer_from_settings(settings)
    app.include_router(status.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(areas.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    return app
