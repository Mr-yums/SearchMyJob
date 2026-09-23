"""Application composition and resource lifetime."""

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from searchmyjob import config
from searchmyjob.api.routes import (
    agents,
    ai,
    assistant,
    connections,
    conversations,
    documents,
    mail,
    onboarding,
    opportunities,
    profile,
    workspace,
)
from searchmyjob.api.security import boundary
from searchmyjob.runtime import Engine


def create_app(state_path: Path | None = None, engine_factory=Engine):
    @asynccontextmanager
    async def lifespan(app):
        engine = engine_factory(state_path if state_path is not None else config.STATE)
        app.state.engine = engine
        scheduler = asyncio.create_task(engine.scheduler())
        try:
            yield
        finally:
            scheduler.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await scheduler
            if engine.task and not engine.task.done():
                engine.task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await engine.task
            engine.db.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    app.middleware("http")(boundary)
    from fastapi.responses import JSONResponse

    from searchmyjob.domain.errors import WorkspaceError

    @app.exception_handler(WorkspaceError)
    async def workspace_error(request, exc):
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, exc):
        return JSONResponse(
            {
                "detail": "Champs invalides : vérifie le fournisseur, le modèle et les valeurs saisies."
            },
            status_code=422,
        )

    app.include_router(ai.router)
    app.include_router(workspace.router)
    app.include_router(conversations.router)
    app.include_router(onboarding.router)
    app.include_router(opportunities.router)
    app.include_router(profile.router)
    app.include_router(connections.router)
    app.include_router(agents.router)
    app.include_router(assistant.router)
    app.include_router(documents.router)
    app.include_router(mail.router)
    app.mount(
        "/",
        StaticFiles(directory=config.PROJECT_ROOT / "ui/dist", html=True, check_dir=False),
        name="ui",
    )
    return app
