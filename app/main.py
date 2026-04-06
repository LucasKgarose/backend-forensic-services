from fastapi import FastAPI

from app.api.cases import router as cases_router
from app.api.devices import router as devices_router
from app.api.evidence import router as evidence_router
from app.api.reports import router as reports_router
from app.api.health import router as health_router
from app.api.exception_handlers import register_exception_handlers

app = FastAPI()

register_exception_handlers(app)
app.include_router(cases_router)
app.include_router(devices_router)
app.include_router(evidence_router)
app.include_router(reports_router)
app.include_router(health_router)
