"""Health router for system status checks."""

import subprocess

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api/v1/health", tags=["health"])

APP_VERSION = "0.1.0"


@router.get("/", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    # Check database connectivity
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unavailable"

    # Check ADB availability
    adb_status = "ok"
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            adb_status = "unavailable"
    except Exception:
        adb_status = "unavailable"

    overall = "ok" if db_status == "ok" else "degraded"

    return HealthResponse(
        status=overall,
        database=db_status,
        adb=adb_status,
        version=APP_VERSION,
    )
