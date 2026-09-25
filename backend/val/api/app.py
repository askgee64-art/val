"""FastAPI Application for VAL — Document 04 §4 & Document 22."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from val import __version__
from val.api.routes_approvals import router as approvals_router
from val.api.routes_audit import router as audit_router
from val.api.routes_chat import router as chat_router
from val.api.routes_control import router as control_router
from val.api.routes_memory import router as memory_router
from val.api.routes_status import router as status_router
from val.api.routes_tasks import router as tasks_router
from val.api.routes_tools import router as tools_router
from val.api.routes_agents import router as agents_router
from val.api.routes_learning import router as learning_router
from val.config import get_settings
from val.db.session import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Bootstrap DB schema and seed entities on startup
    await init_db()
    yield
    # Shutdown hooks if any


def create_app() -> FastAPI:
    app = FastAPI(
        title="VAL — Autonomous AI Core",
        description=(
            "Executive autonomous system for AI workforce management. "
            "Enforces permission checks outside the model, sandboxed execution, "
            "and hardened founder emergency controls."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API Routes under /api/v1
    api_prefix = settings.api_prefix
    app.include_router(status_router, prefix=api_prefix)
    app.include_router(chat_router, prefix=api_prefix)
    app.include_router(tasks_router, prefix=api_prefix)
    app.include_router(approvals_router, prefix=api_prefix)
    app.include_router(tools_router, prefix=api_prefix)
    app.include_router(memory_router, prefix=api_prefix)
    app.include_router(audit_router, prefix=api_prefix)
    app.include_router(control_router, prefix=api_prefix)
    app.include_router(agents_router, prefix=api_prefix)
    app.include_router(learning_router, prefix=api_prefix)

    # Mount static assets if frontend directory exists
    frontend_dir = settings.project_root / "frontend"
    if frontend_dir.exists():
        index_file = frontend_dir / "index.html"
        if index_file.exists():
            @app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse, include_in_schema=False)
            async def serve_index() -> FileResponse:
                return FileResponse(index_file)

        css_file = frontend_dir / "styles.css"
        if css_file.exists():
            @app.api_route("/styles.css", methods=["GET", "HEAD"], include_in_schema=False)
            async def serve_css() -> FileResponse:
                return FileResponse(css_file, media_type="text/css")

        js_file = frontend_dir / "app.js"
        if js_file.exists():
            @app.api_route("/app.js", methods=["GET", "HEAD"], include_in_schema=False)
            async def serve_js() -> FileResponse:
                return FileResponse(js_file, media_type="application/javascript")

        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    return app


app = create_app()
