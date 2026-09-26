import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from core.config import settings
from core.database import engine
from core.errors import success_response
from core.handler import register_exception_handlers
from models import *  # noqa: F401,F403  (register all tables on metadata)
from tasks.scheduler import start_scheduler

_STATIC_DIR = Path(__file__).resolve().parent / "static"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="HR Attendance + Payroll Management SaaS with eSSL eTimeTrackLite + AI-FACE-ORCUS integration.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from api.v1.router import api_router  # noqa: E402

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
register_exception_handlers(app)

if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root():
    return {"app": settings.APP_NAME, "docs": "/api/docs", "status": "ok"}


@app.get(f"{settings.API_V1_PREFIX}/health", tags=["System"])
def health():
    return JSONResponse(
        content=success_response(
            {
                "status": "ok",
                "time": datetime.now(timezone.utc).isoformat(),
                "environment": settings.APP_ENV,
                "mock_mode": settings.ESSL_MOCK_MODE,
            }
        )
    )


@app.on_event("startup")
def on_startup() -> None:
    from core.migrations import run_migrations

    run_migrations(engine)
    logger.info("Database is ready (tables ensured).")
    if settings.SCHEDULER_ENABLED:
        start_scheduler()
    else:
        logger.info("Background scheduler disabled by configuration.")


@app.on_event("shutdown")
def on_shutdown() -> None:
    from tasks.scheduler import get_scheduler

    scheduler = get_scheduler()
    if scheduler is not None and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Background scheduler stopped.")