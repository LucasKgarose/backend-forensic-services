from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.cases import router as cases_router
from app.api.devices import router as devices_router
from app.api.evidence import router as evidence_router
from app.api.reports import router as reports_router
from app.api.health import router as health_router
from app.api.exception_handlers import register_exception_handlers

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        from app.config import get_settings
        settings = get_settings()
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.warning(f"Configuration validation warning: {e}")

    logger.info("Run 'alembic upgrade head' to apply pending database migrations")
    yield
    # Shutdown (nothing to do)


app = FastAPI(title="Forensic Services API", lifespan=lifespan)

# CORS middleware
try:
    from app.config import get_settings
    cors_origins = get_settings().CORS_ORIGINS
except Exception:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# Routers (each already carries its own /api/v1/... prefix)
app.include_router(cases_router)
app.include_router(devices_router)
app.include_router(evidence_router)
app.include_router(reports_router)
app.include_router(health_router)
