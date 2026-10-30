"""Application factory: middlewares, routers, exception handlers, metrics."""

import contextlib
import time
from pathlib import Path
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api.v1.router import api_router
from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.exceptions import DomainError, domain_error_handler
from app.core.logging import setup_logging
from app.db.session import engine
from app.web.router import router as web_router

BASE_DIR = Path(__file__).resolve().parent
logger = structlog.get_logger(__name__)


@contextlib.asynccontextmanager
async def _lifespan(_: FastAPI):
    yield
    await engine.dispose()
    with contextlib.suppress(Exception):
        await get_redis().aclose()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()

    app = FastAPI(
        title="FinTrack API",
        version=__version__,
        description=(
            "Personal finance tracker: categories, transactions, budgets, analytics.\n\n"
            "Authentication: `POST /api/v1/auth/login` (OAuth2 password flow), "
            "then `Authorization: Bearer <token>`."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", uuid4().hex[:12])
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - started) * 1000, 1)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    app.include_router(api_router, prefix="/api/v1")
    app.include_router(web_router)
    app.add_exception_handler(DomainError, domain_error_handler)

    app.mount(
        "/static",
        StaticFiles(directory=BASE_DIR / "web" / "static"),
        name="static",
    )

    # Prometheus metrics: GET /metrics
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
